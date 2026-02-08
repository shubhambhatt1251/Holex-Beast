"""Windows desktop control — full Siri/Alexa/Google-level tool.

Handles: apps, browser, YouTube, file CRUD, system settings,
volume, brightness, WiFi, screenshots, clipboard, system info,
wallpaper, process management, recycle bin, media keys, and more.
Every operation a desktop voice assistant could ever need.
"""

from __future__ import annotations

import logging
import os
import platform
import shutil
import subprocess
import webbrowser
from datetime import datetime
from pathlib import Path

from core.agent.tools.base import BaseTool, ToolResult
from core.config import TEMP_DIR

logger = logging.getLogger(__name__)

# ── App name → executable mapping (case-insensitive) ──

APP_MAP = {
    # Windows built-in
    "notepad": "notepad.exe",
    "calculator": "calc.exe",
    "paint": "mspaint.exe",
    "explorer": "explorer.exe",
    "file explorer": "explorer.exe",
    "this pc": "explorer.exe",
    "task manager": "taskmgr.exe",
    "cmd": "cmd.exe",
    "command prompt": "cmd.exe",
    "terminal": "wt.exe",
    "powershell": "powershell.exe",
    "settings": "ms-settings:",
    "control panel": "control.exe",
    "device manager": "devmgmt.msc",
    "disk management": "diskmgmt.msc",
    "snipping tool": "snippingtool.exe",
    "snip and sketch": "ms-screenclip:",
    "screen sketch": "ms-screenclip:",
    "magnifier": "magnify.exe",
    "sticky notes": "ms-stickynotes:",
    "clock": "ms-clock:",
    "alarms": "ms-clock:",
    "camera": "ms-camera:",
    "sound recorder": "ms-soundrecorder:",
    "maps": "bingmaps:",
    "store": "ms-windows-store:",
    "microsoft store": "ms-windows-store:",
    "photos": "ms-photos:",
    "weather": "bingweather:",
    "news": "bingnews:",
    "feedback hub": "feedback-hub:",
    "xbox": "xbox:",
    "xbox game bar": "ms-gamebar:",
    "movies and tv": "mswindowsvideo:",
    "groove music": "mswindowsmusic:",
    "mail": "outlookmail:",
    "calendar app": "outlookcal:",
    # Browsers
    "chrome": "chrome.exe",
    "google chrome": "chrome.exe",
    "firefox": "firefox.exe",
    "edge": "msedge.exe",
    "microsoft edge": "msedge.exe",
    "brave": "brave.exe",
    "opera": "opera.exe",
    "vivaldi": "vivaldi.exe",
    # Dev tools
    "vscode": "code",
    "visual studio code": "code",
    "visual studio": "devenv.exe",
    "git bash": "git-bash.exe",
    "postman": "Postman.exe",
    "sublime text": "sublime_text.exe",
    "notepad++": "notepad++.exe",
    "intellij": "idea64.exe",
    "pycharm": "pycharm64.exe",
    "android studio": "studio64.exe",
    "docker desktop": "Docker Desktop.exe",
    "wsl": "wsl.exe",
    # Communication
    "discord": "discord.exe",
    "telegram": "Telegram.exe",
    "whatsapp": "WhatsApp.exe",
    "zoom": "Zoom.exe",
    "teams": "ms-teams.exe",
    "microsoft teams": "ms-teams.exe",
    "slack": "slack.exe",
    "skype": "skype.exe",
    "signal": "Signal.exe",
    "google meet": "https://meet.google.com",
    # Media
    "spotify": "spotify.exe",
    "vlc": "vlc.exe",
    "itunes": "iTunes.exe",
    "audacity": "audacity.exe",
    # Office
    "word": "winword.exe",
    "microsoft word": "winword.exe",
    "excel": "excel.exe",
    "microsoft excel": "excel.exe",
    "powerpoint": "powerpnt.exe",
    "microsoft powerpoint": "powerpnt.exe",
    "outlook": "outlook.exe",
    "onenote": "onenote.exe",
    "access": "msaccess.exe",
    "libreoffice": "soffice.exe",
    # Creative
    "photoshop": "Photoshop.exe",
    "illustrator": "Illustrator.exe",
    "premiere": "Adobe Premiere Pro.exe",
    "after effects": "AfterFX.exe",
    "blender": "blender.exe",
    "figma": "Figma.exe",
    "obs": "obs64.exe",
    "obs studio": "obs64.exe",
    "gimp": "gimp-2.10.exe",
    "davinci resolve": "Resolve.exe",
    # Gaming
    "steam": "steam.exe",
    "epic games": "EpicGamesLauncher.exe",
    # Utilities
    "winrar": "WinRAR.exe",
    "7zip": "7zFM.exe",
    "everything": "Everything.exe",
    "ccleaner": "CCleaner64.exe",
    "teamviewer": "TeamViewer.exe",
    "anydesk": "AnyDesk.exe",
    "bitwarden": "Bitwarden.exe",
    "handbrake": "HandBrake.exe",
    "unity": "Unity.exe",
}

# ── Windows Settings URIs ──

SETTINGS_MAP = {
    "display": "ms-settings:display",
    "sound": "ms-settings:sound",
    "notifications": "ms-settings:notifications",
    "focus": "ms-settings:quiethours",
    "power": "ms-settings:powersleep",
    "battery": "ms-settings:batterysaver",
    "storage": "ms-settings:storagesense",
    "multitasking": "ms-settings:multitasking",
    "about": "ms-settings:about",
    "bluetooth": "ms-settings:bluetooth",
    "wifi": "ms-settings:network-wifi",
    "vpn": "ms-settings:network-vpn",
    "proxy": "ms-settings:network-proxy",
    "network": "ms-settings:network-status",
    "ethernet": "ms-settings:network-ethernet",
    "background": "ms-settings:personalization-background",
    "colors": "ms-settings:personalization-colors",
    "themes": "ms-settings:themes",
    "lock screen": "ms-settings:lockscreen",
    "taskbar": "ms-settings:taskbar",
    "start menu": "ms-settings:personalization-start",
    "apps": "ms-settings:appsfeatures",
    "default apps": "ms-settings:defaultapps",
    "startup": "ms-settings:startupapps",
    "date and time": "ms-settings:dateandtime",
    "language": "ms-settings:regionlanguage",
    "keyboard": "ms-settings:keyboard",
    "mouse": "ms-settings:mousetouchpad",
    "privacy": "ms-settings:privacy",
    "update": "ms-settings:windowsupdate",
    "recovery": "ms-settings:recovery",
    "developers": "ms-settings:developers",
    "accessibility": "ms-settings:easeofaccess",
    "night light": "ms-settings:nightlight",
    "gaming": "ms-settings:gaming-gamebar",
    "accounts": "ms-settings:yourinfo",
}


class SystemControlTool(BaseTool):
    """Full desktop assistant — controls Windows like Siri/Alexa/Google.

    46 actions covering apps, browser, YouTube, files, system settings,
    volume, brightness, WiFi, bluetooth, screenshots, clipboard,
    system info, wallpaper, process management, and more.
    """

    @property
    def name(self) -> str:
        return "system_control"

    @property
    def description(self) -> str:
        return (
            "Control the user's Windows PC like a desktop assistant. "
            "Can open/close any application, search Google or YouTube, "
            "play videos, control volume and brightness, toggle WiFi "
            "and Bluetooth, take screenshots, manage clipboard, open "
            "files/folders, create/delete/rename/move files, set wallpaper, "
            "get system info and battery status, manage processes, empty "
            "recycle bin, open any Windows settings page, zip/unzip files, "
            "lock screen, put to sleep, shutdown/restart with confirmation, "
            "media playback control, and any system operation a user asks."
        )

    @property
    def parameters(self) -> dict:
        return {
            "type": "object",
            "properties": {
                "action": {
                    "type": "string",
                    "enum": [
                        # App management
                        "open_app", "close_app",
                        # Browser / search / media
                        "search_google", "search_youtube", "play_youtube",
                        "open_url", "open_website",
                        # Volume
                        "volume_up", "volume_down", "volume_mute", "set_volume",
                        # Brightness
                        "brightness_up", "brightness_down", "set_brightness",
                        # System
                        "screenshot", "lock_screen", "sleep",
                        "shutdown", "restart",
                        # Network
                        "wifi_on", "wifi_off", "bluetooth_on", "bluetooth_off",
                        # File / folder ops
                        "open_folder", "open_file",
                        "create_file", "create_folder",
                        "delete_file", "rename_file", "move_file", "copy_file",
                        # Clipboard & typing
                        "type_text", "copy_to_clipboard",
                        # Window management
                        "minimize_all", "show_desktop",
                        "switch_window", "close_window",
                        # Advanced
                        "system_info", "battery_status",
                        "list_processes", "kill_process",
                        "set_wallpaper", "empty_recycle_bin",
                        "open_settings",
                        "zip_files", "unzip_file",
                        "print_file",
                        "media_play_pause", "media_next", "media_previous",
                    ],
                    "description": "The system action to perform.",
                },
                "target": {
                    "type": "string",
                    "description": (
                        "Target for the action — app name, URL, search query, "
                        "file path, folder path, volume level (0-100), "
                        "text to type, process name/PID, settings page, etc."
                    ),
                },
                "destination": {
                    "type": "string",
                    "description": (
                        "Secondary target — used for move_file (destination path), "
                        "rename_file (new name), copy_file (destination), "
                        "unzip_file (extract-to folder), etc."
                    ),
                },
            },
            "required": ["action"],
        }

    async def execute(
        self, action: str, target: str = "", destination: str = "", **kw
    ) -> ToolResult:
        try:
            handler = {
                "open_app": self._open_app,
                "close_app": self._close_app,
                "search_google": self._search_google,
                "search_youtube": self._search_youtube,
                "play_youtube": self._play_youtube,
                "open_url": self._open_url,
                "open_website": self._open_url,
                "volume_up": lambda t, d: self._volume("up"),
                "volume_down": lambda t, d: self._volume("down"),
                "volume_mute": lambda t, d: self._volume("mute"),
                "set_volume": lambda t, d: self._set_volume(t),
                "brightness_up": lambda t, d: self._brightness("up"),
                "brightness_down": lambda t, d: self._brightness("down"),
                "set_brightness": lambda t, d: self._set_brightness(t),
                "screenshot": lambda t, d: self._screenshot(),
                "lock_screen": lambda t, d: self._lock_screen(),
                "sleep": lambda t, d: self._sleep(),
                "shutdown": lambda t, d: self._shutdown(),
                "restart": lambda t, d: self._restart(),
                "wifi_on": lambda t, d: self._wifi(True),
                "wifi_off": lambda t, d: self._wifi(False),
                "bluetooth_on": lambda t, d: self._bluetooth(True),
                "bluetooth_off": lambda t, d: self._bluetooth(False),
                "open_folder": lambda t, d: self._open_folder(t),
                "open_file": lambda t, d: self._open_file(t),
                "create_file": lambda t, d: self._create_file(t),
                "create_folder": lambda t, d: self._create_folder(t),
                "delete_file": lambda t, d: self._delete_file(t),
                "rename_file": self._rename_dispatch,
                "move_file": self._move_dispatch,
                "copy_file": self._copy_dispatch,
                "type_text": lambda t, d: self._type_text(t),
                "copy_to_clipboard": lambda t, d: self._copy_to_clipboard(t),
                "minimize_all": lambda t, d: self._show_desktop(),
                "show_desktop": lambda t, d: self._show_desktop(),
                "switch_window": lambda t, d: self._switch_window(t),
                "close_window": lambda t, d: self._close_window(t),
                "system_info": lambda t, d: self._system_info(),
                "battery_status": lambda t, d: self._battery_status(),
                "list_processes": lambda t, d: self._list_processes(),
                "kill_process": lambda t, d: self._kill_process(t),
                "set_wallpaper": lambda t, d: self._set_wallpaper(t),
                "empty_recycle_bin": lambda t, d: self._empty_recycle_bin(),
                "open_settings": lambda t, d: self._open_settings(t),
                "zip_files": self._zip_dispatch,
                "unzip_file": lambda t, d: self._unzip_file(t, d),
                "print_file": lambda t, d: self._print_file(t),
                "media_play_pause": lambda t, d: self._media_key("play_pause"),
                "media_next": lambda t, d: self._media_key("next"),
                "media_previous": lambda t, d: self._media_key("previous"),
            }.get(action)

            if not handler:
                return ToolResult(success=False, output="", error=f"Unknown action: {action}")

            return await handler(target, destination)

        except Exception as e:
            logger.error(f"System control error [{action}]: {e}")
            return ToolResult(success=False, output="", error=str(e))

    # ── Helper dispatchers for two-arg calls ──

    async def _rename_dispatch(self, t: str, d: str) -> ToolResult:
        return await self._rename_file(t, d)

    async def _move_dispatch(self, t: str, d: str) -> ToolResult:
        return await self._move_file(t, d)

    async def _copy_dispatch(self, t: str, d: str) -> ToolResult:
        return await self._copy_file(t, d)

    async def _zip_dispatch(self, t: str, d: str) -> ToolResult:
        return await self._zip_files(t, d)

    # ══════════════════════════════════════════════════════════════════════════
    #   APP MANAGEMENT
    # ══════════════════════════════════════════════════════════════════════════

    async def _open_app(self, app_name: str, _d: str = "") -> ToolResult:
        if not app_name:
            return ToolResult(success=False, output="", error="No app name provided.")

        key = app_name.lower().strip()
        executable = APP_MAP.get(key)

        if not executable:
            try:
                os.startfile(app_name)
                return ToolResult(success=True, output=f"Opened **{app_name}**")
            except Exception:
                return ToolResult(
                    success=False, output="",
                    error=f"App not found: '{app_name}'. Try the exact name.",
                )

        try:
            if executable.endswith(":") or executable.startswith("ms-"):
                os.startfile(executable)
            elif executable.endswith(".msc"):
                subprocess.Popen(
                    ["mmc", executable],
                    stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL,
                )
            else:
                subprocess.Popen(
                    [executable],
                    stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL, shell=False,
                )
            return ToolResult(success=True, output=f"Opened **{app_name}**")
        except FileNotFoundError:
            try:
                subprocess.Popen(
                    f'start "" "{executable}"', shell=True,
                    stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL,
                )
                return ToolResult(success=True, output=f"Opened **{app_name}**")
            except Exception as e:
                return ToolResult(success=False, output="", error=f"Cannot open {app_name}: {e}")

    async def _close_app(self, app_name: str, _d: str = "") -> ToolResult:
        if not app_name:
            return ToolResult(success=False, output="", error="No app name provided.")

        key = app_name.lower().strip()
        exe = APP_MAP.get(key)
        if exe and not exe.endswith(":") and not exe.startswith("ms-") and not exe.endswith(".msc"):
            proc_name = exe
        else:
            proc_name = f"{app_name}.exe"

        try:
            r = subprocess.run(
                ["taskkill", "/f", "/im", proc_name],
                capture_output=True, text=True, timeout=5,
            )
            if r.returncode == 0:
                return ToolResult(success=True, output=f"Closed **{app_name}**")
            r2 = subprocess.run(
                ["taskkill", "/f", "/fi", f"WINDOWTITLE eq {app_name}*"],
                capture_output=True, text=True, timeout=5,
            )
            if r2.returncode == 0:
                return ToolResult(success=True, output=f"Closed **{app_name}**")
            return ToolResult(
                success=False, output="",
                error=f"Could not find running process for '{app_name}'",
            )
        except Exception as e:
            return ToolResult(success=False, output="", error=str(e))

    # ══════════════════════════════════════════════════════════════════════════
    #   BROWSER / SEARCH / YOUTUBE
    # ══════════════════════════════════════════════════════════════════════════

    async def _search_google(self, query: str, _d: str = "") -> ToolResult:
        if not query:
            return ToolResult(success=False, output="", error="No search query.")
        import urllib.parse
        url = f"https://www.google.com/search?q={urllib.parse.quote_plus(query)}"
        webbrowser.open(url)
        return ToolResult(success=True, output=f"Searching Google for **{query}**")

    async def _search_youtube(self, query: str, _d: str = "") -> ToolResult:
        if not query:
            return ToolResult(success=False, output="", error="No search query.")
        import urllib.parse
        url = f"https://www.youtube.com/results?search_query={urllib.parse.quote_plus(query)}"
        webbrowser.open(url)
        return ToolResult(success=True, output=f"Searching YouTube for **{query}**")

    async def _play_youtube(self, query: str, _d: str = "") -> ToolResult:
        """Open YouTube and auto-play the first matching video."""
        if not query:
            return ToolResult(success=False, output="", error="No video query.")
        try:
            import re
            import urllib.parse
            import urllib.request
            search_url = (
                f"https://www.youtube.com/results?search_query="
                f"{urllib.parse.quote_plus(query)}"
            )
            req = urllib.request.Request(search_url, headers={
                "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64)"
            })
            html = urllib.request.urlopen(req, timeout=8).read().decode("utf-8", errors="ignore")
            match = re.search(r'/watch\?v=([\w-]{11})', html)
            if match:
                webbrowser.open(f"https://www.youtube.com/watch?v={match.group(1)}")
                return ToolResult(success=True, output=f"Playing **{query}** on YouTube")
        except Exception:
            pass
        import urllib.parse
        webbrowser.open(
            f"https://www.youtube.com/results?search_query={urllib.parse.quote_plus(query)}"
        )
        return ToolResult(success=True, output=f"Playing **{query}** on YouTube")

    async def _open_url(self, url: str, _d: str = "") -> ToolResult:
        if not url:
            return ToolResult(success=False, output="", error="No URL provided.")
        if not url.startswith(("http://", "https://")):
            url = f"https://{url}"
        webbrowser.open(url)
        return ToolResult(success=True, output=f"Opened **{url}**")

    # ══════════════════════════════════════════════════════════════════════════
    #   VOLUME
    # ══════════════════════════════════════════════════════════════════════════

    async def _volume(self, direction: str) -> ToolResult:
        try:
            from ctypes import POINTER, cast

            from comtypes import CLSCTX_ALL
            from pycaw.pycaw import AudioUtilities, IAudioEndpointVolume

            devices = AudioUtilities.GetSpeakers()
            iface = devices.Activate(IAudioEndpointVolume._iid_, CLSCTX_ALL, None)
            vol = cast(iface, POINTER(IAudioEndpointVolume))
            if direction == "mute":
                muted = vol.GetMute()
                vol.SetMute(not muted, None)
                return ToolResult(success=True, output=f"Volume {'unmuted 🔊' if muted else 'muted 🔇'}")
            current = vol.GetMasterVolumeLevelScalar()
            delta = 0.1 if direction == "up" else -0.1
            new_vol = max(0.0, min(1.0, current + delta))
            vol.SetMasterVolumeLevelScalar(new_vol, None)
            return ToolResult(success=True, output=f"Volume: **{int(new_vol * 100)}%**")
        except ImportError:
            return await self._volume_fallback(direction)

    async def _volume_fallback(self, direction: str) -> ToolResult:
        vk_map = {"up": "0xAF", "down": "0xAE", "mute": "0xAD"}
        vk = vk_map.get(direction, "0xAF")
        try:
            ps = (
                "Add-Type -TypeDefinition '"
                "using System; using System.Runtime.InteropServices;"
                "public class VK { "
                "[DllImport(\"user32.dll\")] public static extern void keybd_event(byte k, byte s, uint f, UIntPtr e); "
                "}';"
                f"[VK]::keybd_event({vk},0,0,[UIntPtr]::Zero);"
                f"[VK]::keybd_event({vk},0,2,[UIntPtr]::Zero)"
            )
            subprocess.run(["powershell", "-c", ps], capture_output=True, timeout=5)
            return ToolResult(success=True, output=f"Volume {direction}")
        except Exception as e:
            return ToolResult(success=False, output="", error=str(e))

    async def _set_volume(self, level_str: str) -> ToolResult:
        try:
            level = int(str(level_str).strip().rstrip("%")) / 100.0
            level = max(0.0, min(1.0, level))
            from ctypes import POINTER, cast

            from comtypes import CLSCTX_ALL
            from pycaw.pycaw import AudioUtilities, IAudioEndpointVolume
            devices = AudioUtilities.GetSpeakers()
            iface = devices.Activate(IAudioEndpointVolume._iid_, CLSCTX_ALL, None)
            vol = cast(iface, POINTER(IAudioEndpointVolume))
            vol.SetMasterVolumeLevelScalar(level, None)
            return ToolResult(success=True, output=f"Volume set to **{int(level * 100)}%**")
        except Exception as e:
            return ToolResult(success=False, output="", error=str(e))

    # ══════════════════════════════════════════════════════════════════════════
    #   BRIGHTNESS
    # ══════════════════════════════════════════════════════════════════════════

    async def _brightness(self, direction: str) -> ToolResult:
        # Prefer screen_brightness_control (works on desktop + laptop)
        try:
            import screen_brightness_control as sbc
            current = sbc.get_brightness(display=0)[0]
            delta = 10 if direction == "up" else -10
            new_val = max(0, min(100, current + delta))
            sbc.set_brightness(new_val, display=0)
            return ToolResult(success=True, output=f"Brightness: **{new_val}%**")
        except Exception:
            pass
        # WMI fallback (laptops)
        try:
            r = subprocess.run(
                ["powershell", "-c",
                 "(Get-WmiObject -Namespace root/WMI -Class WmiMonitorBrightness)"
                 ".CurrentBrightness"],
                capture_output=True, text=True, timeout=5,
            )
            current = int(r.stdout.strip()) if r.stdout.strip() else 50
            delta = 10 if direction == "up" else -10
            new_val = max(0, min(100, current + delta))
            subprocess.run(
                ["powershell", "-c",
                 f"(Get-WmiObject -Namespace root/WMI -Class WmiMonitorBrightnessMethods)"
                 f".WmiSetBrightness(1,{new_val})"],
                capture_output=True, timeout=5,
            )
            return ToolResult(success=True, output=f"Brightness: **{new_val}%**")
        except Exception as e:
            return ToolResult(success=False, output="", error=f"Brightness not available: {e}")

    async def _set_brightness(self, level_str: str) -> ToolResult:
        level = max(0, min(100, int(str(level_str).strip().rstrip("%"))))
        try:
            import screen_brightness_control as sbc
            sbc.set_brightness(level, display=0)
            return ToolResult(success=True, output=f"Brightness set to **{level}%**")
        except Exception:
            pass
        try:
            subprocess.run(
                ["powershell", "-c",
                 f"(Get-WmiObject -Namespace root/WMI -Class WmiMonitorBrightnessMethods)"
                 f".WmiSetBrightness(1,{level})"],
                capture_output=True, timeout=5,
            )
            return ToolResult(success=True, output=f"Brightness set to **{level}%**")
        except Exception as e:
            return ToolResult(success=False, output="", error=str(e))

    # ══════════════════════════════════════════════════════════════════════════
    #   SCREENSHOT
    # ══════════════════════════════════════════════════════════════════════════

    async def _screenshot(self) -> ToolResult:
        try:
            import pyautogui
            path = TEMP_DIR / f"screenshot_{datetime.now():%Y%m%d_%H%M%S}.png"
            path.parent.mkdir(exist_ok=True)
            pyautogui.screenshot(str(path))
            return ToolResult(
                success=True,
                output=f"Screenshot saved: **{path.name}**",
                data={"path": str(path)},
            )
        except ImportError:
            try:
                subprocess.Popen(["snippingtool.exe", "/clip"])
                return ToolResult(success=True, output="Snipping Tool opened for screenshot")
            except Exception:
                return ToolResult(success=False, output="", error="Install pyautogui for screenshots")

    # ══════════════════════════════════════════════════════════════════════════
    #   SYSTEM POWER
    # ══════════════════════════════════════════════════════════════════════════

    async def _lock_screen(self) -> ToolResult:
        subprocess.run(["rundll32.exe", "user32.dll,LockWorkStation"])
        return ToolResult(success=True, output="Screen locked 🔒")

    async def _sleep(self) -> ToolResult:
        subprocess.run(
            ["powershell", "-c",
             "Add-Type -Assembly System.Windows.Forms; "
             "[System.Windows.Forms.Application]::SetSuspendState('Suspend', $false, $false)"],
            capture_output=True, timeout=5,
        )
        return ToolResult(success=True, output="PC going to sleep 💤")

    async def _shutdown(self) -> ToolResult:
        subprocess.run(
            ["shutdown", "/s", "/t", "30", "/c",
             "Holex Beast: Shutting down in 30 seconds. Run 'shutdown /a' to cancel."],
            capture_output=True, timeout=5,
        )
        return ToolResult(
            success=True,
            output="Shutting down in **30 seconds**. Say 'cancel shutdown' or run `shutdown /a` to abort.",
        )

    async def _restart(self) -> ToolResult:
        subprocess.run(
            ["shutdown", "/r", "/t", "30", "/c",
             "Holex Beast: Restarting in 30 seconds. Run 'shutdown /a' to cancel."],
            capture_output=True, timeout=5,
        )
        return ToolResult(
            success=True,
            output="Restarting in **30 seconds**. Say 'cancel restart' or run `shutdown /a` to abort.",
        )

    async def _show_desktop(self) -> ToolResult:
        subprocess.run(
            ["powershell", "-c", "(New-Object -ComObject Shell.Application).MinimizeAll()"],
            capture_output=True, timeout=5,
        )
        return ToolResult(success=True, output="All windows minimized")

    # ══════════════════════════════════════════════════════════════════════════
    #   WIFI / BLUETOOTH
    # ══════════════════════════════════════════════════════════════════════════

    async def _wifi(self, enable: bool) -> ToolResult:
        state = "enable" if enable else "disable"
        try:
            detect = subprocess.run(
                ["netsh", "interface", "show", "interface"],
                capture_output=True, text=True, timeout=5,
            )
            iface = "Wi-Fi"
            for line in detect.stdout.splitlines():
                lower = line.lower()
                if "wireless" in lower or "wi-fi" in lower or "wlan" in lower:
                    parts = line.split()
                    if len(parts) >= 4:
                        iface = " ".join(parts[3:])
                        break
            subprocess.run(
                ["netsh", "interface", "set", "interface", iface, state],
                capture_output=True, timeout=10,
            )
            return ToolResult(success=True, output=f"WiFi {'enabled ✅' if enable else 'disabled ❌'}")
        except Exception as e:
            return ToolResult(success=False, output="", error=str(e))

    async def _bluetooth(self, enable: bool) -> ToolResult:
        try:
            os.startfile("ms-settings:bluetooth")
            word = "enable" if enable else "disable"
            return ToolResult(success=True, output=f"Opened Bluetooth settings — please {word} it there")
        except Exception as e:
            return ToolResult(success=False, output="", error=str(e))

    # ══════════════════════════════════════════════════════════════════════════
    #   FILE / FOLDER OPERATIONS
    # ══════════════════════════════════════════════════════════════════════════

    async def _open_folder(self, path: str) -> ToolResult:
        if not path:
            path = os.path.expanduser("~")
        target = Path(path).expanduser()
        if not target.exists():
            return ToolResult(success=False, output="", error=f"Path not found: {path}")
        os.startfile(str(target))
        return ToolResult(success=True, output=f"Opened **{target}**")

    async def _open_file(self, path: str) -> ToolResult:
        if not path:
            return ToolResult(success=False, output="", error="No file path provided.")
        target = Path(path).expanduser()
        if not target.exists():
            return ToolResult(success=False, output="", error=f"File not found: {path}")
        os.startfile(str(target))
        return ToolResult(success=True, output=f"Opened **{target.name}**")

    async def _create_file(self, path: str) -> ToolResult:
        if not path:
            return ToolResult(success=False, output="", error="No file path provided.")
        target = Path(path).expanduser()
        target.parent.mkdir(parents=True, exist_ok=True)
        target.touch()
        return ToolResult(success=True, output=f"Created file: **{target.name}**")

    async def _create_folder(self, path: str) -> ToolResult:
        if not path:
            return ToolResult(success=False, output="", error="No folder path provided.")
        target = Path(path).expanduser()
        target.mkdir(parents=True, exist_ok=True)
        return ToolResult(success=True, output=f"Created folder: **{target.name}**")

    async def _delete_file(self, path: str) -> ToolResult:
        if not path:
            return ToolResult(success=False, output="", error="No file path provided.")
        target = Path(path).expanduser()
        if not target.exists():
            return ToolResult(success=False, output="", error=f"Not found: {path}")
        try:
            from send2trash import send2trash
            send2trash(str(target))
            return ToolResult(success=True, output=f"Moved **{target.name}** to Recycle Bin 🗑️")
        except ImportError:
            if target.is_dir():
                shutil.rmtree(str(target))
            else:
                target.unlink()
            return ToolResult(success=True, output=f"Deleted **{target.name}** permanently")

    async def _rename_file(self, path: str, new_name: str) -> ToolResult:
        if not path or not new_name:
            return ToolResult(success=False, output="", error="Need both path and new name.")
        target = Path(path).expanduser()
        if not target.exists():
            return ToolResult(success=False, output="", error=f"Not found: {path}")
        target.rename(target.parent / new_name)
        return ToolResult(success=True, output=f"Renamed to **{new_name}**")

    async def _move_file(self, source: str, dest: str) -> ToolResult:
        if not source or not dest:
            return ToolResult(success=False, output="", error="Need both source and destination.")
        src = Path(source).expanduser()
        if not src.exists():
            return ToolResult(success=False, output="", error=f"Not found: {source}")
        dst = Path(dest).expanduser()
        dst.parent.mkdir(parents=True, exist_ok=True)
        shutil.move(str(src), str(dst))
        return ToolResult(success=True, output=f"Moved **{src.name}** → **{dst}**")

    async def _copy_file(self, source: str, dest: str) -> ToolResult:
        if not source or not dest:
            return ToolResult(success=False, output="", error="Need both source and destination.")
        src = Path(source).expanduser()
        if not src.exists():
            return ToolResult(success=False, output="", error=f"Not found: {source}")
        dst = Path(dest).expanduser()
        dst.parent.mkdir(parents=True, exist_ok=True)
        if src.is_dir():
            shutil.copytree(str(src), str(dst))
        else:
            shutil.copy2(str(src), str(dst))
        return ToolResult(success=True, output=f"Copied **{src.name}** → **{dst}**")

    # ══════════════════════════════════════════════════════════════════════════
    #   CLIPBOARD / TYPING
    # ══════════════════════════════════════════════════════════════════════════

    async def _type_text(self, text: str) -> ToolResult:
        if not text:
            return ToolResult(success=False, output="", error="No text to type.")
        try:
            import time

            import pyautogui
            time.sleep(0.5)
            if text.isascii():
                pyautogui.typewrite(text, interval=0.02)
            else:
                self._clipboard_set(text)
                pyautogui.hotkey("ctrl", "v")
            return ToolResult(success=True, output=f"Typed text ({len(text)} chars)")
        except ImportError:
            return ToolResult(success=False, output="", error="pyautogui needed: pip install pyautogui")

    async def _copy_to_clipboard(self, text: str) -> ToolResult:
        if not text:
            return ToolResult(success=False, output="", error="No text to copy.")
        try:
            self._clipboard_set(text)
            return ToolResult(success=True, output="Text copied to clipboard ✅")
        except Exception as e:
            return ToolResult(success=False, output="", error=str(e))

    @staticmethod
    def _clipboard_set(text: str) -> None:
        """Set clipboard safely — no command injection."""
        proc = subprocess.Popen(
            ["powershell", "-c", "Set-Clipboard -Value $input"],
            stdin=subprocess.PIPE, stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL,
        )
        proc.communicate(input=text.encode("utf-8"), timeout=5)

    # ══════════════════════════════════════════════════════════════════════════
    #   WINDOW MANAGEMENT
    # ══════════════════════════════════════════════════════════════════════════

    async def _switch_window(self, title: str) -> ToolResult:
        try:
            subprocess.run(
                ["powershell", "-c",
                 f'(New-Object -ComObject WScript.Shell).AppActivate("{title}")'],
                capture_output=True, timeout=5,
            )
            return ToolResult(success=True, output=f"Switched to **{title}**")
        except Exception as e:
            return ToolResult(success=False, output="", error=str(e))

    async def _close_window(self, title: str) -> ToolResult:
        if not title:
            try:
                import pyautogui
                pyautogui.hotkey("alt", "F4")
                return ToolResult(success=True, output="Closed active window")
            except ImportError:
                pass
        return await self._close_app(title)

    # ══════════════════════════════════════════════════════════════════════════
    #   SYSTEM INFO / BATTERY
    # ══════════════════════════════════════════════════════════════════════════

    async def _system_info(self) -> ToolResult:
        try:
            import psutil
        except ImportError:
            psutil = None

        uname = platform.uname()
        lines = [
            f"**Computer**: {uname.node}",
            f"**OS**: {uname.system} {uname.release} ({uname.version})",
            f"**Processor**: {uname.processor or platform.processor()}",
            f"**Architecture**: {uname.machine}",
        ]
        if psutil:
            mem = psutil.virtual_memory()
            disk = psutil.disk_usage("/")
            cpu = psutil.cpu_percent(interval=0.5)
            lines += [
                f"**CPU Usage**: {cpu}%",
                f"**RAM**: {mem.used // (1024**3):.1f} GB / {mem.total // (1024**3):.1f} GB ({mem.percent}%)",
                f"**Disk**: {disk.used // (1024**3):.1f} GB / {disk.total // (1024**3):.1f} GB ({disk.percent}%)",
                f"**Cores**: {psutil.cpu_count(logical=False)} physical / {psutil.cpu_count()} logical",
            ]
            boot = datetime.fromtimestamp(psutil.boot_time())
            lines.append(f"**Boot Time**: {boot:%Y-%m-%d %H:%M}")
        else:
            lines.append("*(Install psutil for CPU/RAM/disk details)*")
        return ToolResult(success=True, output="\n".join(lines))

    async def _battery_status(self) -> ToolResult:
        try:
            import psutil
            batt = psutil.sensors_battery()
            if batt is None:
                return ToolResult(success=True, output="No battery detected — this is a desktop PC 🖥️")
            plug = "🔌 Plugged in" if batt.power_plugged else "🔋 On battery"
            time_left = ""
            if batt.secsleft > 0 and not batt.power_plugged:
                h, m = divmod(batt.secsleft, 3600)
                m = m // 60
                time_left = f" — ~{h}h {m}m left"
            return ToolResult(success=True, output=f"Battery: **{batt.percent}%** {plug}{time_left}")
        except ImportError:
            return ToolResult(success=False, output="", error="Install psutil: pip install psutil")

    # ══════════════════════════════════════════════════════════════════════════
    #   PROCESS MANAGEMENT
    # ══════════════════════════════════════════════════════════════════════════

    async def _list_processes(self) -> ToolResult:
        try:
            import psutil
            procs = []
            for p in sorted(
                psutil.process_iter(["pid", "name", "memory_percent"]),
                key=lambda x: x.info.get("memory_percent", 0) or 0,
                reverse=True,
            )[:20]:
                i = p.info
                procs.append(f"**{i['name']}** (PID {i['pid']}) — {i.get('memory_percent', 0):.1f}% RAM")
            return ToolResult(success=True, output="Top 20 processes by memory:\n" + "\n".join(procs))
        except ImportError:
            r = subprocess.run(["tasklist", "/fo", "csv", "/nh"], capture_output=True, text=True, timeout=10)
            return ToolResult(success=True, output="Processes:\n" + "\n".join(r.stdout.strip().splitlines()[:20]))

    async def _kill_process(self, target: str) -> ToolResult:
        if not target:
            return ToolResult(success=False, output="", error="No process name or PID given.")
        try:
            pid = int(target)
            subprocess.run(["taskkill", "/f", "/pid", str(pid)], capture_output=True, timeout=5)
            return ToolResult(success=True, output=f"Killed process PID {pid}")
        except ValueError:
            name = target if target.endswith(".exe") else f"{target}.exe"
            r = subprocess.run(["taskkill", "/f", "/im", name], capture_output=True, text=True, timeout=5)
            if r.returncode == 0:
                return ToolResult(success=True, output=f"Killed **{target}**")
            return ToolResult(success=False, output="", error=f"Process not found: {target}")

    # ══════════════════════════════════════════════════════════════════════════
    #   WALLPAPER / SETTINGS / RECYCLE BIN
    # ══════════════════════════════════════════════════════════════════════════

    async def _set_wallpaper(self, path: str) -> ToolResult:
        if not path:
            return ToolResult(success=False, output="", error="No image path provided.")
        target = Path(path).expanduser().resolve()
        if not target.exists():
            return ToolResult(success=False, output="", error=f"Image not found: {path}")
        try:
            import ctypes
            ctypes.windll.user32.SystemParametersInfoW(0x0014, 0, str(target), 0x01 | 0x02)
            return ToolResult(success=True, output=f"Wallpaper set to **{target.name}** 🖼️")
        except Exception as e:
            return ToolResult(success=False, output="", error=str(e))

    async def _empty_recycle_bin(self) -> ToolResult:
        try:
            subprocess.run(
                ["powershell", "-c", "Clear-RecycleBin -Force -ErrorAction SilentlyContinue"],
                capture_output=True, timeout=15,
            )
            return ToolResult(success=True, output="Recycle Bin emptied 🗑️")
        except Exception as e:
            return ToolResult(success=False, output="", error=str(e))

    async def _open_settings(self, page: str) -> ToolResult:
        if not page:
            os.startfile("ms-settings:")
            return ToolResult(success=True, output="Opened Windows Settings")
        key = page.lower().strip()
        uri = SETTINGS_MAP.get(key)
        if uri:
            os.startfile(uri)
            return ToolResult(success=True, output=f"Opened **{page}** settings")
        if page.startswith("ms-settings:"):
            os.startfile(page)
            return ToolResult(success=True, output=f"Opened settings: {page}")
        os.startfile("ms-settings:")
        return ToolResult(success=True, output=f"Opened Windows Settings ('{page}' page not recognized)")

    # ══════════════════════════════════════════════════════════════════════════
    #   ZIP / UNZIP / PRINT / MEDIA KEYS
    # ══════════════════════════════════════════════════════════════════════════

    async def _zip_files(self, source: str, dest: str) -> ToolResult:
        if not source:
            return ToolResult(success=False, output="", error="No source path for zip.")
        src = Path(source).expanduser()
        if not src.exists():
            return ToolResult(success=False, output="", error=f"Not found: {source}")
        out = dest or str(src.parent / src.stem)
        import zipfile
        archive = f"{out}.zip" if not out.endswith(".zip") else out
        with zipfile.ZipFile(archive, "w", zipfile.ZIP_DEFLATED) as zf:
            if src.is_dir():
                for f in src.rglob("*"):
                    zf.write(f, f.relative_to(src.parent))
            else:
                zf.write(src, src.name)
        return ToolResult(success=True, output=f"Created **{Path(archive).name}** 📦")

    async def _unzip_file(self, source: str, dest: str) -> ToolResult:
        if not source:
            return ToolResult(success=False, output="", error="No zip file path.")
        src = Path(source).expanduser()
        if not src.exists():
            return ToolResult(success=False, output="", error=f"Not found: {source}")
        out = dest or str(src.parent / src.stem)
        import zipfile
        with zipfile.ZipFile(str(src), "r") as zf:
            zf.extractall(out)
        return ToolResult(success=True, output=f"Extracted to **{out}** 📂")

    async def _print_file(self, path: str) -> ToolResult:
        if not path:
            return ToolResult(success=False, output="", error="No file path to print.")
        target = Path(path).expanduser()
        if not target.exists():
            return ToolResult(success=False, output="", error=f"File not found: {path}")
        os.startfile(str(target), "print")
        return ToolResult(success=True, output=f"Printing **{target.name}** 🖨️")

    async def _media_key(self, action: str) -> ToolResult:
        vk_map = {"play_pause": "0xB3", "next": "0xB0", "previous": "0xB1"}
        vk = vk_map.get(action, "0xB3")
        ps = (
            "Add-Type -TypeDefinition '"
            "using System; using System.Runtime.InteropServices;"
            "public class MK { "
            "[DllImport(\"user32.dll\")] public static extern void keybd_event(byte k, byte s, uint f, UIntPtr e); "
            "}';"
            f"[MK]::keybd_event({vk},0,0,[UIntPtr]::Zero);"
            f"[MK]::keybd_event({vk},0,2,[UIntPtr]::Zero)"
        )
        subprocess.run(["powershell", "-c", ps], capture_output=True, timeout=5)
        labels = {"play_pause": "Play/Pause ⏯️", "next": "Next Track ⏭️", "previous": "Previous Track ⏮️"}
        return ToolResult(success=True, output=labels.get(action, action))
