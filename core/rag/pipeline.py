"""Retrieval-augmented generation pipeline backed by ChromaDB and Ollama embeddings."""

from __future__ import annotations

import logging
from pathlib import Path

from core.config import get_settings
from core.events import EventType, get_event_bus

logger = logging.getLogger(__name__)


class RAGPipeline:
    """
    Complete RAG pipeline: ingest documents → chunk → embed → store → query.
    Uses ChromaDB for vector storage and Ollama for embeddings.
    Everything runs locally.
    """

    def __init__(self):
        self.settings = get_settings()
        self.bus = get_event_bus()
        self._collection = None
        self._client = None

    def initialize(self) -> bool:
        """Initialize ChromaDB and create/load collection."""
        try:
            import chromadb
            from chromadb.config import Settings

            db_path = self.settings.rag.chroma_db_path
            Path(db_path).mkdir(parents=True, exist_ok=True)

            self._client = chromadb.PersistentClient(
                path=db_path,
                settings=Settings(anonymized_telemetry=False),
            )

            self._collection = self._client.get_or_create_collection(
                name="holex_documents",
                metadata={"hnsw:space": "cosine"},
            )

            doc_count = self._collection.count()
            logger.info(f"RAG initialized - {doc_count} documents in store")
            return True

        except ImportError:
            logger.error("chromadb not installed. Run: pip install chromadb")
            return False
        except Exception as e:
            logger.error(f"RAG init failed: {e}")
            return False

    async def ingest_file(self, file_path: str) -> dict:
        """
        Ingest a document: parse → chunk → embed → store.
        Returns stats about the ingestion.
        """
        path = Path(file_path)
        if not path.exists():
            raise FileNotFoundError(f"File not found: {file_path}")

        # Parse document
        text = self._parse_file(path)
        if not text.strip():
            return {"error": "No text content found in file"}

        # Chunk text
        chunks = self._chunk_text(
            text,
            chunk_size=self.settings.rag.chunk_size,
            overlap=self.settings.rag.chunk_overlap,
        )

        # Generate embeddings and store
        ids = []
        documents = []
        metadatas = []

        for i, chunk in enumerate(chunks):
            chunk_id = f"{path.stem}_{i}"
            ids.append(chunk_id)
            documents.append(chunk)
            metadatas.append({
                "source": path.name,
                "chunk_index": i,
                "total_chunks": len(chunks),
                "file_type": path.suffix.lower(),
            })

        # Upsert to ChromaDB (it handles embeddings internally if configured)
        self._collection.upsert(
            ids=ids,
            documents=documents,
            metadatas=metadatas,
        )

        stats = {
            "file": path.name,
            "chunks": len(chunks),
            "total_chars": len(text),
            "avg_chunk_size": len(text) // max(len(chunks), 1),
        }

        self.bus.emit(EventType.RAG_DOCUMENT_ADDED, stats)
        logger.info(f"Ingested: {path.name} ({len(chunks)} chunks)")
        return stats

    async def query(self, question: str, top_k: int = 0) -> str:
        """
        Query the document store and return relevant context.
        Returns formatted context string for the LLM.
        """
        if not self._collection or self._collection.count() == 0:
            return ""

        top_k = top_k or self.settings.rag.top_k

        try:
            results = self._collection.query(
                query_texts=[question],
                n_results=min(top_k, self._collection.count()),
            )

            if not results["documents"] or not results["documents"][0]:
                return ""

            # Format context
            context_parts = []
            for i, (doc, meta, dist) in enumerate(zip(
                results["documents"][0],
                results["metadatas"][0],
                results["distances"][0],
            )):
                similarity = 1 - dist  # ChromaDB returns distances
                if similarity < self.settings.rag.similarity_threshold:
                    continue

                source = meta.get("source", "unknown")
                context_parts.append(
                    f"[Source: {source} | Relevance: {similarity:.0%}]\n{doc}"
                )

            context = "\n\n---\n\n".join(context_parts)

            self.bus.emit(EventType.RAG_QUERY_RESULT, {
                "question": question,
                "results_count": len(context_parts),
            })

            return context

        except Exception as e:
            logger.error(f"RAG query failed: {e}")
            return ""

    async def remove_document(self, filename: str) -> bool:
        """Remove all chunks from a specific document."""
        try:
            # Get all chunk IDs for this document
            results = self._collection.get(
                where={"source": filename},
            )
            if results["ids"]:
                self._collection.delete(ids=results["ids"])
                self.bus.emit(EventType.RAG_DOCUMENT_REMOVED, {"file": filename})
                logger.info(f"Removed: {filename} ({len(results['ids'])} chunks)")
                return True
            return False
        except Exception as e:
            logger.error(f"Remove document failed: {e}")
            return False

    def list_documents(self) -> list[dict]:
        """List all ingested documents."""
        if not self._collection:
            return []
        try:
            results = self._collection.get()
            # Group by source
            sources = {}
            for meta in results.get("metadatas", []):
                source = meta.get("source", "unknown")
                if source not in sources:
                    sources[source] = {
                        "filename": source,
                        "chunks": 0,
                        "file_type": meta.get("file_type", ""),
                    }
                sources[source]["chunks"] += 1
            return list(sources.values())
        except Exception:
            return []

    @property
    def document_count(self) -> int:
        """Total number of chunks in the store."""
        if not self._collection:
            return 0
        return self._collection.count()

    # Private Helpers

    def _parse_file(self, path: Path) -> str:
        """Parse a file into plain text."""
        suffix = path.suffix.lower()

        if suffix in (".txt", ".md", ".py", ".js", ".json", ".csv", ".log"):
            return path.read_text(encoding="utf-8", errors="ignore")

        elif suffix == ".pdf":
            try:
                import PyPDF2
                text = ""
                with open(path, "rb") as f:
                    reader = PyPDF2.PdfReader(f)
                    for page in reader.pages:
                        text += page.extract_text() or ""
                return text
            except ImportError:
                logger.warning("PyPDF2 not installed for PDF support")
                return ""

        elif suffix in (".docx",):
            try:
                from docx import Document
                doc = Document(str(path))
                return "\n".join(p.text for p in doc.paragraphs)
            except ImportError:
                logger.warning("python-docx not installed for DOCX support")
                return ""

        elif suffix == ".html":
            try:
                from bs4 import BeautifulSoup
                html = path.read_text(encoding="utf-8", errors="ignore")
                soup = BeautifulSoup(html, "html.parser")
                return soup.get_text()
            except ImportError:
                # Strip tags manually
                import re
                html = path.read_text(encoding="utf-8", errors="ignore")
                return re.sub(r"<[^>]+>", "", html)

        else:
            # Try reading as text
            try:
                return path.read_text(encoding="utf-8", errors="ignore")
            except Exception:
                return ""

    @staticmethod
    def _chunk_text(text: str, chunk_size: int = 512, overlap: int = 50) -> list[str]:
        """Split text into overlapping chunks."""
        if len(text) <= chunk_size:
            return [text] if text.strip() else []

        chunks = []
        # Try to split on paragraph boundaries
        paragraphs = text.split("\n\n")
        current_chunk = ""

        for para in paragraphs:
            if len(current_chunk) + len(para) + 2 <= chunk_size:
                current_chunk += para + "\n\n"
            else:
                if current_chunk.strip():
                    chunks.append(current_chunk.strip())
                # Start new chunk with overlap
                if overlap > 0 and current_chunk:
                    current_chunk = current_chunk[-overlap:] + para + "\n\n"
                else:
                    current_chunk = para + "\n\n"

                # Handle paragraphs larger than chunk_size
                while len(current_chunk) > chunk_size:
                    chunks.append(current_chunk[:chunk_size].strip())
                    current_chunk = current_chunk[chunk_size - overlap:]

        if current_chunk.strip():
            chunks.append(current_chunk.strip())

        return chunks
