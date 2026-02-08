"""Timer, alarm, and stopwatch tool.

Handles: set timer, set alarm, start/stop stopwatch.
Uses threading for background countdown and system notifications.
"""

from __future__ import annotations

import logging
import re
import threading
import time
from datetime import datetime, timedelta
from typing import Optional

from core.agent.tools.base import BaseTool, ToolResult

logger = logging.getLogger(__name__)

# Active timers/alarms stored in memory
_active_timers: dict[str, dict] = {}
_stopwatch_start: Optional[float] = None
_stopwatch_elapsed: float = 0.0
_timer_lock = threading.Lock()


def _parse_duration(text: str) -> Optional[int]:
    """Parse a human duration string into seconds.

    Supports: '5 minutes', '1 hour 30 minutes', '90 seconds',
    '2h 15m', '1h30m', '45s', '10 min', etc.
    """
    text = text.lower().strip()

    # Try direct seconds
    if text.isdigit():
        return int(text)

    total = 0
    # hours
    m = re.search(r'(\d+)\s*(?:hours?|hrs?|h)', text)
    if m:
        total += int(m.group(1)) * 3600
    # minutes
    m = re.search(r'(\d+)\s*(?:minutes?|mins?|m(?!s))', text)
    if m:
        total += int(m.group(1)) * 60
    # seconds
    m = re.search(r'(\d+)\s*(?:seconds?|secs?|s)', text)
    if m:
        total += int(m.group(1))

    return total if total > 0 else None


def _format_duration(seconds: int) -> str:
    """Format seconds into a readable string."""
    if seconds < 60:
        return f"{seconds} second{'s' if seconds != 1 else ''}"
    if seconds < 3600:
        m, s = divmod(seconds, 60)
        parts = [f"{m} minute{'s' if m != 1 else ''}"]
        if s:
            parts.append(f"{s} second{'s' if s != 1 else ''}")
        return " ".join(parts)
    h, remainder = divmod(seconds, 3600)
    m, s = divmod(remainder, 60)
    parts = [f"{h} hour{'s' if h != 1 else ''}"]
    if m:
        parts.append(f"{m} minute{'s' if m != 1 else ''}")
    return " ".join(parts)


def _notify(title: str, message: str) -> None:
    """Show a Windows toast notification."""
    try:
        from plyer import notification
        notification.notify(
            title=title,
            message=message,
            app_name="Holex Beast",
            timeout=10,
        )
        return
    except Exception:
        pass

    # Fallback: PowerShell toast
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
        subprocess.Popen(
            ["powershell", "-c", ps],
            stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL,
        )
    except Exception:
        logger.warning(f"Could not show notification: {title} — {message}")


def _timer_thread(timer_id: str, seconds: int, label: str) -> None:
    """Background thread that counts down and fires notification."""
    time.sleep(seconds)
    with _timer_lock:
        if timer_id in _active_timers:
            del _active_timers[timer_id]
    _notify("⏰ Timer Done!", f"{label} — {_format_duration(seconds)} elapsed")
    logger.info(f"Timer '{label}' completed after {seconds}s")


class TimerAlarmTool(BaseTool):
    """Timer, alarm, and stopwatch for the desktop assistant."""

    @property
    def name(self) -> str:
        return "timer_alarm"

    @property
    def description(self) -> str:
        return (
            "Set timers, alarms, and use a stopwatch. "
            "Timer: counts down and notifies (e.g., '5 minutes'). "
            "Alarm: fires at a specific time (e.g., '7:30 AM'). "
            "Stopwatch: start, stop, lap, reset."
        )

    @property
    def parameters(self) -> dict:
        return {
            "type": "object",
            "properties": {
                "action": {
                    "type": "string",
                    "enum": [
                        "set_timer", "cancel_timer", "list_timers",
                        "set_alarm",
                        "stopwatch_start", "stopwatch_stop",
                        "stopwatch_lap", "stopwatch_reset",
                    ],
                    "description": "The timer/alarm action to perform.",
                },
                "duration": {
                    "type": "string",
                    "description": (
                        "For set_timer: duration like '5 minutes', '1 hour 30 min', '90s'. "
                        "For set_alarm: time like '7:30 AM', '14:00', '6:00 PM'."
                    ),
                },
                "label": {
                    "type": "string",
                    "description": "Optional label for the timer/alarm (e.g., 'cooking', 'meeting').",
                },
            },
            "required": ["action"],
        }

    async def execute(self, action: str, duration: str = "", label: str = "", **kw) -> ToolResult:
        global _stopwatch_start, _stopwatch_elapsed

        if action == "set_timer":
            return self._set_timer(duration, label)
        elif action == "cancel_timer":
            return self._cancel_timer(label)
        elif action == "list_timers":
            return self._list_timers()
        elif action == "set_alarm":
            return self._set_alarm(duration, label)
        elif action == "stopwatch_start":
            _stopwatch_start = time.time()
            _stopwatch_elapsed = 0.0
            return ToolResult(success=True, output="Stopwatch started ⏱️")
        elif action == "stopwatch_stop":
            if _stopwatch_start is None:
                return ToolResult(success=False, output="", error="Stopwatch not running.")
            _stopwatch_elapsed += time.time() - _stopwatch_start
            _stopwatch_start = None
            return ToolResult(
                success=True,
                output=f"Stopwatch stopped: **{_stopwatch_elapsed:.2f}** seconds",
            )
        elif action == "stopwatch_lap":
            if _stopwatch_start is None:
                return ToolResult(success=False, output="", error="Stopwatch not running.")
            lap = _stopwatch_elapsed + (time.time() - _stopwatch_start)
            return ToolResult(success=True, output=f"Lap: **{lap:.2f}** seconds")
        elif action == "stopwatch_reset":
            _stopwatch_start = None
            _stopwatch_elapsed = 0.0
            return ToolResult(success=True, output="Stopwatch reset ⏱️")
        else:
            return ToolResult(success=False, output="", error=f"Unknown action: {action}")

    def _set_timer(self, duration: str, label: str) -> ToolResult:
        if not duration:
            return ToolResult(success=False, output="", error="No duration specified.")
        seconds = _parse_duration(duration)
        if not seconds:
            return ToolResult(success=False, output="", error=f"Could not parse duration: '{duration}'")

        timer_id = f"timer_{int(time.time())}_{label or 'default'}"
        display_label = label or "Timer"
        with _timer_lock:
            _active_timers[timer_id] = {
                "label": display_label,
                "seconds": seconds,
                "started": time.time(),
            }
        t = threading.Thread(
            target=_timer_thread, args=(timer_id, seconds, display_label), daemon=True,
        )
        t.start()
        return ToolResult(
            success=True,
            output=f"⏰ Timer set: **{display_label}** for {_format_duration(seconds)}",
        )

    def _cancel_timer(self, label: str) -> ToolResult:
        with _timer_lock:
            if not _active_timers:
                return ToolResult(success=True, output="No active timers to cancel.")
            if label:
                to_remove = [k for k, v in _active_timers.items() if label.lower() in v["label"].lower()]
            else:
                to_remove = list(_active_timers.keys())
            for k in to_remove:
                del _active_timers[k]
        count = len(to_remove)
        return ToolResult(success=True, output=f"Cancelled {count} timer(s)")

    def _list_timers(self) -> ToolResult:
        with _timer_lock:
            if not _active_timers:
                return ToolResult(success=True, output="No active timers.")
            lines = []
            now = time.time()
            for info in _active_timers.values():
                elapsed = now - info["started"]
                remaining = max(0, info["seconds"] - elapsed)
                lines.append(
                    f"**{info['label']}** — {_format_duration(int(remaining))} remaining"
                )
        return ToolResult(success=True, output="Active timers:\n" + "\n".join(lines))

    def _set_alarm(self, time_str: str, label: str) -> ToolResult:
        if not time_str:
            return ToolResult(success=False, output="", error="No alarm time specified.")

        now = datetime.now()
        alarm_time = None

        # Try parsing various formats
        for fmt in ("%I:%M %p", "%I:%M%p", "%H:%M", "%I %p", "%I%p"):
            try:
                parsed = datetime.strptime(time_str.strip().upper(), fmt)
                alarm_time = now.replace(
                    hour=parsed.hour, minute=parsed.minute, second=0, microsecond=0,
                )
                break
            except ValueError:
                continue

        if alarm_time is None:
            return ToolResult(success=False, output="", error=f"Could not parse time: '{time_str}'")

        # If the time is in the past today, set it for tomorrow
        if alarm_time <= now:
            alarm_time += timedelta(days=1)

        seconds_until = (alarm_time - now).total_seconds()
        display_label = label or "Alarm"
        timer_id = f"alarm_{int(time.time())}_{display_label}"

        with _timer_lock:
            _active_timers[timer_id] = {
                "label": display_label,
                "seconds": int(seconds_until),
                "started": time.time(),
            }

        t = threading.Thread(
            target=_timer_thread,
            args=(timer_id, int(seconds_until), f"🔔 {display_label}"),
            daemon=True,
        )
        t.start()

        return ToolResult(
            success=True,
            output=(
                f"🔔 Alarm set: **{display_label}** at {alarm_time:%I:%M %p}"
                f" ({_format_duration(int(seconds_until))} from now)"
            ),
        )
