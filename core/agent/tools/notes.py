"""Notes and todo list tool — persistent local note-taking.

Handles: add note, list notes, search, delete, and simple todos.
Data persisted to JSON in the data/ directory.
"""

from __future__ import annotations

import json
import logging
from datetime import datetime

from core.agent.tools.base import BaseTool, ToolResult
from core.config import DATA_DIR

logger = logging.getLogger(__name__)

_NOTES_FILE = DATA_DIR / "notes.json"


def _load_notes() -> dict:
    """Load notes from disk."""
    if _NOTES_FILE.exists():
        try:
            return json.loads(_NOTES_FILE.read_text(encoding="utf-8"))
        except Exception:
            pass
    return {"notes": [], "todos": []}


def _save_notes(data: dict) -> None:
    """Save notes to disk."""
    _NOTES_FILE.parent.mkdir(parents=True, exist_ok=True)
    _NOTES_FILE.write_text(json.dumps(data, indent=2, ensure_ascii=False), encoding="utf-8")


class NotesTool(BaseTool):
    """Personal notes and todo list manager."""

    @property
    def name(self) -> str:
        return "notes"

    @property
    def description(self) -> str:
        return (
            "Manage the user's personal notes and todo list. "
            "Can add notes, list all notes, search notes, delete notes, "
            "add todos, mark todos as done, and list todos. "
            "Examples: 'Add a note: buy groceries tomorrow', "
            "'Show my notes', 'Add to my todo list: finish homework', "
            "'Mark todo 1 as done'."
        )

    @property
    def parameters(self) -> dict:
        return {
            "type": "object",
            "properties": {
                "action": {
                    "type": "string",
                    "enum": [
                        "add_note", "list_notes", "search_notes", "delete_note",
                        "add_todo", "list_todos", "complete_todo", "delete_todo",
                    ],
                    "description": "The notes/todo action.",
                },
                "text": {
                    "type": "string",
                    "description": "Note text, search query, or todo item text.",
                },
                "index": {
                    "type": "integer",
                    "description": "Index number for delete_note, complete_todo, delete_todo (1-based).",
                },
            },
            "required": ["action"],
        }

    async def execute(
        self, action: str, text: str = "", index: int = 0, target: str = "", **kw
    ) -> ToolResult:
        # LLM sometimes sends 'target' instead of 'text'
        text = text or target
        data = _load_notes()

        if action == "add_note":
            return self._add_note(data, text)
        elif action == "list_notes":
            return self._list_notes(data)
        elif action == "search_notes":
            return self._search_notes(data, text)
        elif action == "delete_note":
            return self._delete_note(data, index)
        elif action == "add_todo":
            return self._add_todo(data, text)
        elif action == "list_todos":
            return self._list_todos(data)
        elif action == "complete_todo":
            return self._complete_todo(data, index)
        elif action == "delete_todo":
            return self._delete_todo(data, index)
        return ToolResult(success=False, output="", error=f"Unknown action: {action}")

    def _add_note(self, data: dict, text: str) -> ToolResult:
        if not text:
            return ToolResult(success=False, output="", error="No note text provided.")
        note = {
            "text": text,
            "created": datetime.now().isoformat(),
        }
        data.setdefault("notes", []).append(note)
        _save_notes(data)
        count = len(data["notes"])
        return ToolResult(success=True, output=f"📝 Note added (#{count}): **{text}**")

    def _list_notes(self, data: dict) -> ToolResult:
        notes = data.get("notes", [])
        if not notes:
            return ToolResult(success=True, output="No notes yet. Say 'add a note' to create one.")
        lines = []
        for i, n in enumerate(notes, 1):
            dt = n.get("created", "")[:10]
            lines.append(f"**{i}.** {n['text']}  *({dt})*")
        return ToolResult(success=True, output="📝 Your notes:\n" + "\n".join(lines))

    def _search_notes(self, data: dict, query: str) -> ToolResult:
        if not query:
            return ToolResult(success=False, output="", error="No search query.")
        notes = data.get("notes", [])
        matches = [
            (i, n) for i, n in enumerate(notes, 1)
            if query.lower() in n["text"].lower()
        ]
        if not matches:
            return ToolResult(success=True, output=f"No notes matching '{query}'.")
        lines = [f"**{i}.** {n['text']}" for i, n in matches]
        return ToolResult(success=True, output=f"Found {len(matches)} note(s):\n" + "\n".join(lines))

    def _delete_note(self, data: dict, index: int) -> ToolResult:
        notes = data.get("notes", [])
        if not notes:
            return ToolResult(success=True, output="No notes to delete.")
        idx = index - 1
        if idx < 0 or idx >= len(notes):
            return ToolResult(
                success=False, output="",
                error=f"Invalid note number. You have {len(notes)} notes (1-{len(notes)}).",
            )
        removed = notes.pop(idx)
        _save_notes(data)
        return ToolResult(success=True, output=f"Deleted note: **{removed['text']}**")

    def _add_todo(self, data: dict, text: str) -> ToolResult:
        if not text:
            return ToolResult(success=False, output="", error="No todo text provided.")
        todo = {
            "text": text,
            "done": False,
            "created": datetime.now().isoformat(),
        }
        data.setdefault("todos", []).append(todo)
        _save_notes(data)
        count = len(data["todos"])
        return ToolResult(success=True, output=f"✅ Todo added (#{count}): **{text}**")

    def _list_todos(self, data: dict) -> ToolResult:
        todos = data.get("todos", [])
        if not todos:
            return ToolResult(success=True, output="No todos. Say 'add a todo' to start your list.")
        lines = []
        for i, t in enumerate(todos, 1):
            check = "✅" if t.get("done") else "⬜"
            lines.append(f"{check} **{i}.** {t['text']}")
        return ToolResult(success=True, output="Your todo list:\n" + "\n".join(lines))

    def _complete_todo(self, data: dict, index: int) -> ToolResult:
        todos = data.get("todos", [])
        idx = index - 1
        if idx < 0 or idx >= len(todos):
            return ToolResult(
                success=False, output="",
                error=f"Invalid todo number. You have {len(todos)} todos.",
            )
        todos[idx]["done"] = True
        _save_notes(data)
        return ToolResult(success=True, output=f"✅ Completed: **{todos[idx]['text']}**")

    def _delete_todo(self, data: dict, index: int) -> ToolResult:
        todos = data.get("todos", [])
        idx = index - 1
        if idx < 0 or idx >= len(todos):
            return ToolResult(
                success=False, output="",
                error=f"Invalid todo number. You have {len(todos)} todos.",
            )
        removed = todos.pop(idx)
        _save_notes(data)
        return ToolResult(success=True, output=f"Deleted todo: **{removed['text']}**")
