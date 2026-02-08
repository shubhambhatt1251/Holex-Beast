"""Firebase integration + SQLite local fallback for persistence."""

from __future__ import annotations

import logging
from datetime import datetime, timezone
from pathlib import Path
from typing import Optional

from core.config import get_settings
from core.events import EventType, get_event_bus

logger = logging.getLogger(__name__)


class FirebaseService:
    """
    Firebase integration for Holex Beast.
    Provides: Auth, Firestore (database), Storage.
    Falls back to local SQLite if Firebase is not configured.
    """

    def __init__(self):
        self.settings = get_settings()
        self.bus = get_event_bus()
        self._db = None  # Firestore client
        self._auth = None
        self._storage = None
        self._initialized = False
        self._current_user: Optional[dict] = None

    async def initialize(self) -> bool:
        """Initialize Firebase connection."""
        if not self.settings.is_firebase_configured:
            logger.info("Firebase not configured - using local storage")
            return False

        try:
            import firebase_admin
            from firebase_admin import auth, credentials, firestore, storage

            # Initialize with service account or default
            if self.settings.firebase.service_account_path:
                cred = credentials.Certificate(
                    self.settings.firebase.service_account_path
                )
            else:
                cred = credentials.ApplicationDefault()

            try:
                firebase_admin.get_app()
            except ValueError:
                firebase_admin.initialize_app(cred, {
                    "storageBucket": self.settings.firebase.storage_bucket,
                })

            self._db = firestore.client()
            self._auth = auth
            self._storage = storage.bucket()
            self._initialized = True

            logger.info("Firebase initialized")
            return True

        except ImportError:
            logger.warning(
                "firebase-admin not installed. Run: pip install firebase-admin"
            )
            return False
        except Exception as e:
            logger.error(f"Firebase init failed: {e}")
            return False

    # Authentication

    async def create_user(self, email: str, password: str, display_name: str = "") -> Optional[dict]:
        """Create a new user account."""
        if not self._initialized:
            return None
        try:
            user = self._auth.create_user(
                email=email,
                password=password,
                display_name=display_name or email.split("@")[0],
            )
            user_data = {
                "uid": user.uid,
                "email": user.email,
                "display_name": user.display_name,
                "created_at": datetime.now(timezone.utc).isoformat(),
            }
            # Store user profile in Firestore
            self._db.collection("users").document(user.uid).set(user_data)
            self._current_user = user_data

            self.bus.emit(EventType.FIREBASE_AUTH_LOGIN, user_data)
            return user_data
        except Exception as e:
            logger.error(f"User creation failed: {e}")
            return None

    async def sign_in(self, email: str, password: str) -> Optional[dict]:
        """Sign in (verify user exists). Note: Admin SDK doesn't do client-side sign-in."""
        if not self._initialized:
            return None
        try:
            user = self._auth.get_user_by_email(email)
            user_data = {
                "uid": user.uid,
                "email": user.email,
                "display_name": user.display_name,
            }
            self._current_user = user_data
            self.bus.emit(EventType.FIREBASE_AUTH_LOGIN, user_data)
            return user_data
        except Exception as e:
            logger.error(f"Sign in failed: {e}")
            return None

    async def sign_out(self) -> None:
        """Sign out current user."""
        self._current_user = None
        self.bus.emit(EventType.FIREBASE_AUTH_LOGOUT, {})

    # Conversations

    async def save_conversation(
        self, conversation_id: str, title: str, messages: list[dict]
    ) -> bool:
        """Save a conversation to Firestore."""
        if not self._initialized:
            return False
        try:
            uid = self._current_user["uid"] if self._current_user else "anonymous"
            doc_ref = self._db.collection("conversations").document(conversation_id)
            doc_ref.set({
                "user_id": uid,
                "title": title,
                "messages": messages,
                "message_count": len(messages),
                "updated_at": datetime.now(timezone.utc).isoformat(),
                "created_at": (
                    datetime.now(timezone.utc).isoformat()
                    if not doc_ref.get().exists
                    else doc_ref.get().to_dict().get("created_at")
                ),
            }, merge=True)
            return True
        except Exception as e:
            logger.error(f"Save conversation failed: {e}")
            return False

    async def load_conversation(self, conversation_id: str) -> Optional[dict]:
        """Load a conversation from Firestore."""
        if not self._initialized:
            return None
        try:
            doc = self._db.collection("conversations").document(conversation_id).get()
            if doc.exists:
                return doc.to_dict()
            return None
        except Exception as e:
            logger.error(f"Load conversation failed: {e}")
            return None

    async def list_conversations(self, limit: int = 50) -> list[dict]:
        """List all conversations for current user."""
        if not self._initialized:
            return []
        try:
            uid = self._current_user["uid"] if self._current_user else "anonymous"
            query = (
                self._db.collection("conversations")
                .where("user_id", "==", uid)
                .order_by("updated_at", direction="DESCENDING")
                .limit(limit)
            )
            docs = query.stream()
            return [
                {"id": doc.id, **doc.to_dict()}
                for doc in docs
            ]
        except Exception as e:
            logger.error(f"List conversations failed: {e}")
            return []

    async def delete_conversation(self, conversation_id: str) -> bool:
        """Delete a conversation."""
        if not self._initialized:
            return False
        try:
            self._db.collection("conversations").document(conversation_id).delete()
            return True
        except Exception as e:
            logger.error(f"Delete conversation failed: {e}")
            return False

    # Settings Sync

    async def save_settings(self, settings: dict) -> bool:
        """Sync user settings to Firebase."""
        if not self._initialized or not self._current_user:
            return False
        try:
            self._db.collection("settings").document(
                self._current_user["uid"]
            ).set(settings, merge=True)
            return True
        except Exception as e:
            logger.error(f"Save settings failed: {e}")
            return False

    async def load_settings(self) -> Optional[dict]:
        """Load user settings from Firebase."""
        if not self._initialized or not self._current_user:
            return None
        try:
            doc = self._db.collection("settings").document(
                self._current_user["uid"]
            ).get()
            return doc.to_dict() if doc.exists else None
        except Exception as e:
            logger.error(f"Load settings failed: {e}")
            return None

    # File Storage

    async def upload_file(self, local_path: str, remote_path: str) -> Optional[str]:
        """Upload a file to Firebase Storage."""
        if not self._initialized or not self._storage:
            return None
        try:
            blob = self._storage.blob(remote_path)
            blob.upload_from_filename(local_path)
            blob.make_public()
            return blob.public_url
        except Exception as e:
            logger.error(f"Upload failed: {e}")
            return None

    async def download_file(self, remote_path: str, local_path: str) -> bool:
        """Download a file from Firebase Storage."""
        if not self._initialized or not self._storage:
            return False
        try:
            blob = self._storage.blob(remote_path)
            Path(local_path).parent.mkdir(parents=True, exist_ok=True)
            blob.download_to_filename(local_path)
            return True
        except Exception as e:
            logger.error(f"Download failed: {e}")
            return False

    # Properties

    @property
    def is_connected(self) -> bool:
        return self._initialized

    @property
    def current_user(self) -> Optional[dict]:
        return self._current_user


# Local Fallback (SQLite)

class LocalStorageService:
    """
    Local SQLite fallback when Firebase is not configured.
    Provides the same interface as FirebaseService.
    """

    def __init__(self):
        import sqlite3

        from core.config import DATA_DIR

        self.db_path = DATA_DIR / "holex_beast.db"
        self.db_path.parent.mkdir(parents=True, exist_ok=True)
        self._conn = sqlite3.connect(str(self.db_path))
        self._conn.row_factory = sqlite3.Row
        self._init_tables()

    def _init_tables(self) -> None:
        """Create tables if they don't exist."""
        self._conn.executescript("""
            CREATE TABLE IF NOT EXISTS conversations (
                id TEXT PRIMARY KEY,
                title TEXT NOT NULL,
                messages TEXT NOT NULL DEFAULT '[]',
                message_count INTEGER DEFAULT 0,
                created_at TEXT NOT NULL,
                updated_at TEXT NOT NULL
            );

            CREATE TABLE IF NOT EXISTS settings (
                key TEXT PRIMARY KEY,
                value TEXT NOT NULL
            );

            CREATE TABLE IF NOT EXISTS documents (
                id TEXT PRIMARY KEY,
                filename TEXT NOT NULL,
                path TEXT NOT NULL,
                doc_type TEXT,
                chunk_count INTEGER DEFAULT 0,
                created_at TEXT NOT NULL
            );

            CREATE INDEX IF NOT EXISTS idx_conv_updated ON conversations(updated_at DESC);
        """)
        self._conn.commit()

    def save_conversation(self, conversation_id: str, title: str, messages: list[dict]) -> bool:
        """Save conversation to SQLite."""
        import json
        now = datetime.now(timezone.utc).isoformat()
        try:
            self._conn.execute(
                """INSERT OR REPLACE INTO conversations
                   (id, title, messages, message_count, created_at, updated_at)
                   VALUES (?, ?, ?, ?, COALESCE(
                       (SELECT created_at FROM conversations WHERE id = ?), ?
                   ), ?)""",
                (conversation_id, title, json.dumps(messages), len(messages),
                 conversation_id, now, now),
            )
            self._conn.commit()
            return True
        except Exception as e:
            logger.error(f"Local save failed: {e}")
            return False

    def load_conversation(self, conversation_id: str) -> Optional[dict]:
        """Load conversation from SQLite."""
        import json
        try:
            row = self._conn.execute(
                "SELECT * FROM conversations WHERE id = ?",
                (conversation_id,),
            ).fetchone()
            if row:
                d = dict(row)
                d["messages"] = json.loads(d["messages"])
                return d
            return None
        except Exception as e:
            logger.error(f"Local load failed: {e}")
            return None

    def list_conversations(self, limit: int = 50) -> list[dict]:
        """List conversations from SQLite."""
        try:
            rows = self._conn.execute(
                "SELECT id, title, message_count, updated_at FROM conversations "
                "ORDER BY updated_at DESC LIMIT ?",
                (limit,),
            ).fetchall()
            return [dict(row) for row in rows]
        except Exception as e:
            logger.error(f"Local list failed: {e}")
            return []

    def delete_conversation(self, conversation_id: str) -> bool:
        """Delete conversation from SQLite."""
        try:
            self._conn.execute(
                "DELETE FROM conversations WHERE id = ?",
                (conversation_id,),
            )
            self._conn.commit()
            return True
        except Exception as e:
            logger.error(f"Local delete failed: {e}")
            return False

    def close(self) -> None:
        """Close SQLite connection."""
        self._conn.close()
