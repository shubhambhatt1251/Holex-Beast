"""Theme palette definitions and glassmorphism style helpers."""

from __future__ import annotations

from dataclasses import dataclass


@dataclass
class ColorPalette:
    """Complete color palette for a theme."""
    # Backgrounds
    bg_primary: str       # Main app background
    bg_secondary: str     # Sidebar / panels
    bg_tertiary: str      # Cards / elevated surfaces
    bg_input: str         # Input fields
    bg_hover: str         # Hover state
    bg_selected: str      # Selected / active item
    bg_overlay: str       # Modal overlays

    # Text
    text_primary: str     # Main text
    text_secondary: str   # Muted / secondary text
    text_tertiary: str    # Hints / placeholders
    text_inverse: str     # Text on accent backgrounds

    # Accents
    accent: str           # Primary accent (brand color)
    accent_hover: str     # Accent hover state
    accent_soft: str      # Accent at low opacity
    accent_gradient_start: str
    accent_gradient_end: str

    # Semantic
    success: str
    warning: str
    error: str
    info: str

    # Borders & Shadows
    border: str
    border_light: str
    shadow: str

    # Special
    user_bubble: str      # User message bubble
    ai_bubble: str        # AI message bubble
    code_bg: str          # Code block background
    scrollbar: str
    scrollbar_hover: str


# Dark Theme (Default)
DARK_PALETTE = ColorPalette(
    bg_primary="#0f0f14",
    bg_secondary="#16161e",
    bg_tertiary="#1e1e2a",
    bg_input="#1a1a26",
    bg_hover="#252536",
    bg_selected="#2a2a3d",
    bg_overlay="rgba(0, 0, 0, 0.6)",

    text_primary="#e4e4ed",
    text_secondary="#9394a5",
    text_tertiary="#5c5d72",
    text_inverse="#ffffff",

    accent="#6c5ce7",
    accent_hover="#7c6ef7",
    accent_soft="rgba(108, 92, 231, 0.15)",
    accent_gradient_start="#6c5ce7",
    accent_gradient_end="#a855f7",

    success="#10b981",
    warning="#f59e0b",
    error="#ef4444",
    info="#3b82f6",

    border="#2a2a3d",
    border_light="#1e1e2e",
    shadow="rgba(0, 0, 0, 0.4)",

    user_bubble="#6c5ce7",
    ai_bubble="#1e1e2a",
    code_bg="#12121a",
    scrollbar="#2a2a3d",
    scrollbar_hover="#3a3a50",
)

# Midnight Theme
MIDNIGHT_PALETTE = ColorPalette(
    bg_primary="#0a0a12",
    bg_secondary="#0f0f1a",
    bg_tertiary="#161625",
    bg_input="#111120",
    bg_hover="#1d1d30",
    bg_selected="#242440",
    bg_overlay="rgba(0, 0, 0, 0.7)",

    text_primary="#d8d8e8",
    text_secondary="#8888a8",
    text_tertiary="#555570",
    text_inverse="#ffffff",

    accent="#818cf8",
    accent_hover="#9198ff",
    accent_soft="rgba(129, 140, 248, 0.12)",
    accent_gradient_start="#818cf8",
    accent_gradient_end="#c084fc",

    success="#34d399",
    warning="#fbbf24",
    error="#f87171",
    info="#60a5fa",

    border="#1e1e35",
    border_light="#151528",
    shadow="rgba(0, 0, 0, 0.5)",

    user_bubble="#818cf8",
    ai_bubble="#161625",
    code_bg="#0d0d18",
    scrollbar="#1e1e35",
    scrollbar_hover="#2e2e48",
)

# Light Theme
LIGHT_PALETTE = ColorPalette(
    bg_primary="#f8f9fc",
    bg_secondary="#ffffff",
    bg_tertiary="#f0f1f5",
    bg_input="#ffffff",
    bg_hover="#e8e9f0",
    bg_selected="#dddef5",
    bg_overlay="rgba(0, 0, 0, 0.3)",

    text_primary="#1a1a2e",
    text_secondary="#64648c",
    text_tertiary="#9494b0",
    text_inverse="#ffffff",

    accent="#6c5ce7",
    accent_hover="#5a4bd6",
    accent_soft="rgba(108, 92, 231, 0.1)",
    accent_gradient_start="#6c5ce7",
    accent_gradient_end="#a855f7",

    success="#059669",
    warning="#d97706",
    error="#dc2626",
    info="#2563eb",

    border="#e2e3ec",
    border_light="#eeeef5",
    shadow="rgba(0, 0, 0, 0.08)",

    user_bubble="#6c5ce7",
    ai_bubble="#f0f1f5",
    code_bg="#f5f6fa",
    scrollbar="#d0d1dc",
    scrollbar_hover="#b0b1c0",
)


THEMES: dict[str, ColorPalette] = {
    "dark": DARK_PALETTE,
    "midnight": MIDNIGHT_PALETTE,
    "light": LIGHT_PALETTE,
}


def get_palette(theme: str = "dark") -> ColorPalette:
    """Get color palette for a theme."""
    return THEMES.get(theme, DARK_PALETTE)
