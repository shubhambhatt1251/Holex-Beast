"""Reminders tool — schedule reminders that fire as desktop notifications.

Supports: create reminder at specific time, list active, cancel,
and recurring daily reminders.
"""

from __future__ import annotations

import json
import logging
import threading
import time
from datetime import datetime, timedelta
from typing import Optional

from core.agent.tools.base import BaseTool, ToolResult
from core.config import DATA_DIR

logger = logging.getLogger(__name__)

_REMINDERS_FILE = DATA_DIR / "reminders.json"
_active_reminders: dict[str, dict] = {}
_reminder_lock = threading.Lock()


def _notify(title: str, message: str) -> None:
    """Show a Windows notification."""
    try:
        from plyer import notification
        notification.notify(
            title=title, message=message,
            app_name="Holex Beast", timeout=10,
        )
        return
    except Exception:
        pass
    try:
        import subprocess
        ps = (
            "Add-Type -AssemblyName System.Windows.Forms;"
            "$n = New-Object System.Windows.Forms.NotifyIcon;"
            "$n.Icon = [System.Drawing.SystemIcons]::Information;"
            "$n.Visible = $true;"
            f"$n.ShowBalloonTip(5000, '{title}', '{message}', 'Info');"
            "Start-Sleep -Seconds 6; $n.Dispose()"
        )
        subprocess.Popen(["powershell", "-c", ps], stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL)
    except Exception:
        logger.warning(f"Notification failed: {title}")


def _reminder_thread(rid: str, seconds: float, text: str) -> None:
    """Sleep then fire notification."""
    time.sleep(max(0, seconds))
    with _reminder_lock:
        _active_reminders.pop(rid, None)
    _notify("📌 Reminder", text)
    logger.info(f"Reminder fired: {text}")
    _save_reminders()


def _save_reminders() -> None:
    """Persist active reminders to disk."""
    try:
        _REMINDERS_FILE.parent.mkdir(parents=True, exist_ok=True)
        data = {}
        with _reminder_lock:
            for rid, info in _active_reminders.items():
                data[rid] = {
                    "text": info["text"],
                    "fire_at": info["fire_at"],
                }
        _REMINDERS_FILE.write_text(json.dumps(data, indent=2), encoding="utf-8")
    except Exception as e:
        logger.error(f"Failed to save reminders: {e}")


def _load_reminders() -> None:
    """Load persisted reminders and reschedule unexpired ones."""
    if not _REMINDERS_FILE.exists():
        return
    try:
        data = json.loads(_REMINDERS_FILE.read_text(encoding="utf-8"))
        now = time.time()
        for rid, info in data.items():
            fire_at = info["fire_at"]
            if fire_at > now:
                remaining = fire_at - now
                with _reminder_lock:
                    _active_reminders[rid] = info
                threading.Thread(
                    target=_reminder_thread,
                    args=(rid, remaining, info["text"]),
                    daemon=True,
                ).start()
    except Exception as e:
        logger.error(f"Failed to load reminders: {e}")


# Auto-load on import
_load_reminders()


def _parse_reminder_time(text: str) -> Optional[float]:
    """Parse time expression into a Unix timestamp.

    Supports:
    - 'in 5 minutes', 'in 2 hours', 'in 30 seconds'
    - 'at 3:00 PM', 'at 14:30', 'at 7 AM'
    - 'tomorrow at 9 AM'
    """
    import re
    text_lower = text.lower().strip()
    now = datetime.now()

    # Relative: "in X minutes/hours/seconds"
    m = re.search(r'in\s+(\d+)\s*(seconds?|secs?|s|minutes?|mins?|m|hours?|hrs?|h)', text_lower)
    if m:
        val = int(m.group(1))
        unit = m.group(2)[0]
        if unit == 's':
            delta = timedelta(seconds=val)
        elif unit == 'm':
            delta = timedelta(minutes=val)
        else:
            delta = timedelta(hours=val)
        return (now + delta).timestamp()

    # Check for "tomorrow"
    add_day = "tomorrow" in text_lower

    # Absolute: "at 3:00 PM" or "3 PM"
    time_pattern = re.search(r'(?:at\s+)?(\d{1,2})(?::(\d{2}))?\s*(am|pm)?', text_lower)
    if time_pattern:
        hour = int(time_pattern.group(1))
        minute = int(time_pattern.group(2) or 0)
        ampm = time_pattern.group(3)
        if ampm == "pm" and hour < 12:
            hour += 12
        elif ampm == "am" and hour == 12:
            hour = 0
        target = now.replace(hour=hour, minute=minute, second=0, microsecond=0)
        if add_day:
            target += timedelta(days=1)
        elif target <= now:
            target += timedelta(days=1)
        return target.timestamp()

    return None


class RemindersTool(BaseTool):
    """Schedule, list, and cancel reminders with desktop notifications."""

    @property
    def name(self) -> str:
        return "reminders"

    @property
    def description(self) -> str:
        return (
            "Set reminders that pop up as desktop notifications. "
            "Supports: 'Remind me to call Mom in 30 minutes', "
            "'Remind me at 3 PM to take medicine', 'List my reminders', "
            "'Cancel reminder about X'."
        )

    @property
    def parameters(self) -> dict:
        return {
            "type": "object",
            "properties": {
                "action": {
                    "type": "string",
                    "enum": ["set_reminder", "list_reminders", "cancel_reminder"],
                    "description": "The reminder action.",
                },
                "text": {
                    "type": "string",
                    "description": "The reminder message (e.g., 'Call Mom', 'Take medicine').",
                },
                "when": {
                    "type": "string",
                    "description": (
                        "When to remind — 'in 30 minutes', 'at 3 PM', "
                        "'tomorrow at 9 AM', etc."
                    ),
                },
            },
            "required": ["action"],
        }

    async def execute(self, action: str, text: str = "", when: str = "", **kw) -> ToolResult:
        if action == "set_reminder":
            return self._set(text, when)
        elif action == "list_reminders":
            return self._list()
        elif action == "cancel_reminder":
            return self._cancel(text)
        return ToolResult(success=False, output="", error=f"Unknown action: {action}")

    def _set(self, text: str, when: str) -> ToolResult:
        if not text:
            return ToolResult(success=False, output="", error="No reminder text.")
        if not when:
            return ToolResult(success=False, output="", error="No time specified for the reminder.")

        fire_at = _parse_reminder_time(when)
        if fire_at is None:
            return ToolResult(
                success=False, output="",
                error=f"Could not parse time: '{when}'. Try 'in 5 minutes' or 'at 3 PM'.",
            )

        rid = f"rem_{int(time.time())}_{hash(text) % 10000}"
        remaining = fire_at - time.time()
        if remaining <= 0:
            return ToolResult(success=False, output="", error="That time is in the past.")

        info = {"text": text, "fire_at": fire_at}
        with _reminder_lock:
            _active_reminders[rid] = info

        threading.Thread(
            target=_reminder_thread, args=(rid, remaining, text), daemon=True,
        ).start()
        _save_reminders()

        fire_dt = datetime.fromtimestamp(fire_at)
        return ToolResult(
            success=True,
            output=f"📌 Reminder set: **{text}** at {fire_dt:%I:%M %p}",
        )

    def _list(self) -> ToolResult:
        with _reminder_lock:
            if not _active_reminders:
                return ToolResult(success=True, output="No active reminders.")
            lines = []
            for info in _active_reminders.values():
                fire_dt = datetime.fromtimestamp(info["fire_at"])
                remaining = max(0, info["fire_at"] - time.time())
                mins = int(remaining // 60)
                lines.append(
                    f"📌 **{info['text']}** — {fire_dt:%I:%M %p} (~{mins} min from now)"
                )
        return ToolResult(success=True, output="Active reminders:\n" + "\n".join(lines))

    def _cancel(self, text: str) -> ToolResult:
        with _reminder_lock:
            if not _active_reminders:
                return ToolResult(success=True, output="No reminders to cancel.")
            if text:
                to_remove = [
                    k for k, v in _active_reminders.items()
                    if text.lower() in v["text"].lower()
                ]
            else:
                to_remove = list(_active_reminders.keys())
            for k in to_remove:
                del _active_reminders[k]
        count = len(to_remove)
        _save_reminders()
        return ToolResult(success=True, output=f"Cancelled {count} reminder(s)")
