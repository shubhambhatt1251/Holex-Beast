"""QSS stylesheet generator — builds a complete Qt style sheet from a theme palette."""

from __future__ import annotations

from typing import Union

from gui.styles import ColorPalette, get_palette


def generate_stylesheet(theme: Union[str, ColorPalette] = "dark") -> str:
    """Generate the complete QSS stylesheet for the entire application."""
    if isinstance(theme, ColorPalette):
        p = theme
        theme_name = "custom"
    else:
        p = get_palette(theme)
        theme_name = theme
    return f"""
/* Holex Beast styles - {theme_name.upper()} */

/* Global Reset */
* {{
    margin: 0;
    padding: 0;
    font-family: 'Segoe UI', 'SF Pro Display', 'Inter', sans-serif;
}}

QMainWindow {{
    background-color: {p.bg_primary};
}}

QWidget {{
    background-color: transparent;
    color: {p.text_primary};
    font-size: 13px;
}}

/* Scrollbars (Thin & Modern) */
QScrollBar:vertical {{
    background: transparent;
    width: 5px;
    margin: 0;
    border-radius: 2px;
}}
QScrollBar::handle:vertical {{
    background: {p.scrollbar};
    border-radius: 2px;
    min-height: 40px;
}}
QScrollBar::handle:vertical:hover {{
    background: {p.scrollbar_hover};
}}
QScrollBar::add-line:vertical, QScrollBar::sub-line:vertical {{
    height: 0;
}}
QScrollBar::add-page:vertical, QScrollBar::sub-page:vertical {{
    background: transparent;
}}

QScrollBar:horizontal {{
    background: transparent;
    height: 5px;
    border-radius: 2px;
}}
QScrollBar::handle:horizontal {{
    background: {p.scrollbar};
    border-radius: 2px;
    min-width: 40px;
}}
QScrollBar::handle:horizontal:hover {{
    background: {p.scrollbar_hover};
}}
QScrollBar::add-line:horizontal, QScrollBar::sub-line:horizontal {{
    width: 0;
}}

/* TOP HEADER BAR */
#TopHeader {{
    background-color: {p.bg_secondary};
    border-bottom: 1px solid {p.border};
}}

#HeaderBtn {{
    background-color: transparent;
    color: {p.text_secondary};
    border: none;
    border-radius: 6px;
    font-size: 14px;
    padding: 4px;
}}
#HeaderBtn:hover {{
    background-color: {p.bg_hover};
    color: {p.text_primary};
}}

#HeaderAvatar {{
    background-color: {p.accent};
    color: {p.text_inverse};
    border: none;
    border-radius: 15px;
    font-size: 12px;
    font-weight: bold;
}}
#HeaderAvatar:hover {{
    background-color: {p.accent_hover};
}}

#PlanBadge {{
    background-color: {p.bg_tertiary};
    color: {p.text_secondary};
    border: 1px solid {p.border};
    border-radius: 12px;
    padding: 3px 12px;
    font-size: 11px;
    font-weight: 500;
}}

#UpgradeBtn {{
    background: qlineargradient(x1:0, y1:0, x2:1, y2:0,
        stop:0 {p.accent_gradient_start}, stop:1 {p.accent_gradient_end});
    color: {p.text_inverse};
    border: none;
    border-radius: 12px;
    padding: 3px 14px;
    font-size: 11px;
    font-weight: 600;
}}
#UpgradeBtn:hover {{
    background: qlineargradient(x1:0, y1:0, x2:1, y2:0,
        stop:0 {p.accent_hover}, stop:1 {p.accent_gradient_end});
}}

/* SIDEBAR */
#Sidebar {{
    background-color: {p.bg_secondary};
    border-right: 1px solid {p.border};
}}

#SidebarSearch {{
    background: rgba(255,255,255,0.03);
    border: 1px solid rgba(255,255,255,0.06);
    border-radius: 8px;
    padding: 8px 12px;
    font-size: 12px;
    color: {p.text_secondary};
}}
#SidebarSearch:focus {{
    border-color: rgba(108,92,231,0.4);
}}

#HistoryLabel {{
    color: {p.text_secondary};
    font-size: 12px;
    font-weight: 600;
}}

/* Conversation Items */
#ConvItem {{
    background-color: transparent;
    border-radius: 8px;
    padding: 6px 8px;
    margin: 1px 4px;
}}
#ConvItem:hover {{
    background-color: {p.bg_hover};
}}
#ConvItemActive {{
    background-color: {p.bg_selected};
    border-left: 3px solid {p.accent};
    border-radius: 8px;
    padding: 6px 8px;
    margin: 1px 4px;
}}
#ConvTitle {{
    color: {p.text_primary};
    font-size: 12px;
    font-weight: 500;
}}

/* New Chat Button */
#NewChatBtn {{
    background: qlineargradient(x1:0, y1:0, x2:1, y2:0,
        stop:0 {p.accent_gradient_start}, stop:1 {p.accent_gradient_end});
    color: {p.text_inverse};
    border: none;
    border-radius: 10px;
    padding: 9px 16px;
    font-size: 13px;
    font-weight: 600;
    margin: 6px 12px;
}}
#NewChatBtn:hover {{
    background: qlineargradient(x1:0, y1:0, x2:1, y2:0,
        stop:0 {p.accent_hover}, stop:1 {p.accent_gradient_end});
}}
#NewChatBtn:pressed {{
    padding: 10px 15px 8px 17px;
}}

/* Theme Toggle Buttons */
#ThemeBtn {{
    background-color: transparent;
    border: 1px solid {p.border};
    border-radius: 6px;
    color: {p.text_secondary};
    font-size: 12px;
    padding: 2px;
}}
#ThemeBtn:hover {{
    background-color: {p.bg_hover};
    color: {p.text_primary};
}}
#ThemeBtn:checked {{
    background-color: {p.accent_soft};
    border-color: {p.accent};
    color: {p.accent};
}}

/* Sidebar Bottom */
#SidebarBottom {{
    border-top: 1px solid {p.border};
}}

/* CHAT AREA */
#ChatArea {{
    background-color: {p.bg_primary};
    border: none;
}}

#ChatScroll {{
    background-color: {p.bg_primary};
    border: none;
}}

/* Welcome Screen */
#WelcomeScreen {{
    background-color: {p.bg_primary};
}}

#WelcomeTitle {{
    color: {p.text_tertiary};
    font-size: 30px;
    font-weight: 600;
    letter-spacing: -0.3px;
}}

/* MESSAGE BUBBLES */
#UserBubble {{
    background: qlineargradient(x1:0, y1:0, x2:1, y2:1,
        stop:0 {p.accent_gradient_start}, stop:1 {p.accent_gradient_end});
    color: {p.text_inverse};
    border-radius: 18px 18px 4px 18px;
    padding: 12px 16px;
    font-size: 14px;
    line-height: 1.5;
    max-width: 65%;
}}

#AIBubble {{
    background-color: transparent;
    color: {p.text_primary};
    border: none;
    border-radius: 4px;
    padding: 10px 14px;
    font-size: 14px;
    line-height: 1.6;
    max-width: 85%;
}}

#AIName {{
    color: {p.text_primary};
    font-size: 13px;
    font-weight: 700;
}}

#AIBubble code {{
    background-color: {p.code_bg};
    border-radius: 4px;
    padding: 1px 6px;
    font-family: 'JetBrains Mono', 'Fira Code', 'Cascadia Code', monospace;
    font-size: 12px;
}}

/* Action Buttons (Regenerate / Copy) */
#BubbleActionBtn {{
    background-color: transparent;
    border: 1px solid {p.border};
    border-radius: 6px;
    color: {p.text_secondary};
    font-size: 12px;
    padding: 3px;
}}
#BubbleActionBtn:hover {{
    background-color: {p.bg_hover};
    color: {p.text_primary};
    border-color: {p.accent};
}}

/* Thinking/Tool Indicator */
#ThinkingLabel {{
    color: {p.accent};
    font-size: 13px;
    font-weight: 500;
    padding: 4px 12px;
}}

#ToolBadge {{
    background-color: {p.accent_soft};
    color: {p.accent};
    border: 1px solid {p.accent};
    border-radius: 12px;
    padding: 3px 10px;
    font-size: 11px;
    font-weight: 600;
}}

/* FLOATING INPUT BAR */
#InputContainer {{
    background-color: {p.bg_primary};
    border: none;
    padding: 0;
}}

#InputCard {{
    background-color: {p.bg_secondary};
    border: 1px solid {p.border};
    border-radius: 16px;
    padding: 10px 14px;
}}

#InputField {{
    background-color: transparent;
    color: {p.text_primary};
    border: none;
    border-radius: 0;
    padding: 6px 8px;
    font-size: 14px;
    selection-background-color: {p.accent_soft};
}}
#InputField:focus {{
    border: none;
}}

/* Mode Toggle Buttons */
#ModeToggle {{
    background-color: transparent;
    border: 1px solid {p.border};
    border-radius: 8px;
    color: {p.text_tertiary};
    font-size: 14px;
    padding: 2px;
}}
#ModeToggle:hover {{
    background-color: {p.bg_hover};
    color: {p.text_primary};
}}
#ModeToggle:checked {{
    background-color: {p.accent_soft};
    border-color: {p.accent};
    color: {p.accent};
}}

/* Input Model Selector */
#InputModelSelector {{
    background-color: {p.bg_tertiary};
    color: {p.text_secondary};
    border: 1px solid {p.border};
    border-radius: 8px;
    padding: 4px 20px 4px 8px;
    font-size: 11px;
    font-weight: 500;
}}
#InputModelSelector:hover {{
    border-color: {p.accent};
    color: {p.text_primary};
}}
#InputModelSelector::drop-down {{
    border: none;
    width: 16px;
}}
#InputModelSelector QAbstractItemView {{
    background-color: {p.bg_tertiary};
    color: {p.text_primary};
    border: 1px solid {p.border};
    border-radius: 8px;
    padding: 4px;
    selection-background-color: {p.accent_soft};
    selection-color: {p.accent};
}}

/* Voice Button (purple mic) */
#VoiceBtn {{
    background: qlineargradient(x1:0, y1:0, x2:1, y2:1,
        stop:0 {p.accent_gradient_start}, stop:1 {p.accent_gradient_end});
    border: none;
    border-radius: 18px;
    color: {p.text_inverse};
    font-size: 16px;
    padding: 6px;
}}
#VoiceBtn:hover {{
    background: qlineargradient(x1:0, y1:0, x2:1, y2:1,
        stop:0 {p.accent_hover}, stop:1 {p.accent_gradient_end});
}}
#VoiceBtn:checked {{
    background: qlineargradient(x1:0, y1:0, x2:1, y2:1,
        stop:0 #ef4444, stop:1 #f87171);
}}

/* Stop Button (red square) */
#StopBtn {{
    background-color: #ef4444;
    border: none;
    border-radius: 18px;
    color: white;
    font-size: 14px;
    padding: 6px;
}}
#StopBtn:hover {{
    background-color: #dc2626;
}}

/* Attach Button */
#AttachBtn {{
    background-color: transparent;
    border: none;
    border-radius: 8px;
    padding: 4px;
    color: {p.text_secondary};
    font-size: 14px;
}}
#AttachBtn:hover {{
    background-color: {p.bg_hover};
    color: {p.accent};
}}

/* LEGACY TOOLBAR (kept for compat) */
#Toolbar {{
    background-color: {p.bg_secondary};
    border-bottom: 1px solid {p.border};
    padding: 8px 16px;
}}
#ModelSelector {{
    background-color: {p.bg_tertiary};
    color: {p.text_primary};
    border: 1px solid {p.border};
    border-radius: 8px;
    padding: 6px 28px 6px 10px;
    font-size: 12px;
    font-weight: 500;
    min-width: 180px;
}}
#ModelSelector:hover {{
    border-color: {p.accent};
}}
#ModelSelector::drop-down {{
    border: none;
    width: 20px;
}}
#ModelSelector QAbstractItemView {{
    background-color: {p.bg_tertiary};
    color: {p.text_primary};
    border: 1px solid {p.border};
    border-radius: 8px;
    padding: 4px;
    selection-background-color: {p.accent_soft};
    selection-color: {p.accent};
}}
#ProviderBadge {{
    background-color: {p.accent_soft};
    color: {p.accent};
    border-radius: 6px;
    padding: 4px 10px;
    font-size: 11px;
    font-weight: 600;
}}
#ToolbarBtn {{
    background-color: transparent;
    color: {p.text_secondary};
    border: none;
    border-radius: 8px;
    padding: 6px 8px;
    font-size: 14px;
}}
#ToolbarBtn:hover {{
    background-color: {p.bg_hover};
    color: {p.text_primary};
}}

/* VOICE VISUALIZER */
#VoiceVisualizer {{
    background-color: {p.bg_tertiary};
    border: 1px solid {p.border};
    border-radius: 16px;
    padding: 16px;
}}
#VoiceWaveform {{
    background-color: transparent;
    min-height: 60px;
    }}
#VoiceStatus {{
    color: {p.accent};
    font-size: 13px;
    font-weight: 600;
}}

/* SETTINGS PANEL */
#SettingsPanel {{
    background-color: {p.bg_secondary};
    border-left: 1px solid {p.border};
}}
#SettingsTitle {{
    color: {p.text_primary};
    font-size: 15px;
    font-weight: 700;
    padding: 16px;
    border-bottom: 1px solid {p.border};
}}
#SettingsGroup {{
    background-color: {p.bg_tertiary};
    border-radius: 10px;
    padding: 12px;
    margin: 6px 10px;
}}
#SettingsGroupTitle {{
    color: {p.text_secondary};
    font-size: 10px;
    font-weight: 700;
    letter-spacing: 1px;
    text-transform: uppercase;
    margin-bottom: 8px;
}}

QSlider::groove:horizontal {{
    background: {p.border};
    height: 4px;
    border-radius: 2px;
}}
QSlider::handle:horizontal {{
    background: {p.accent};
    width: 16px;
    height: 16px;
    margin: -6px 0;
    border-radius: 8px;
}}
QSlider::sub-page:horizontal {{
    background: {p.accent};
    border-radius: 2px;
}}

QSpinBox, QDoubleSpinBox {{
    background-color: {p.bg_input};
    color: {p.text_primary};
    border: 1px solid {p.border};
    border-radius: 6px;
    padding: 4px 8px;
}}

/* RAG Document Panel */
#DocPanel {{
    background-color: {p.bg_tertiary};
    border-radius: 10px;
    padding: 10px;
    margin: 6px 10px;
}}
#DocItem {{
    background-color: {p.bg_input};
    border: 1px solid {p.border};
    border-radius: 8px;
    padding: 8px 12px;
    margin: 3px 0;
}}
#DocItem:hover {{
    border-color: {p.accent};
}}

/* TOOLS PANEL (Left) */
#ToolsPanel {{
    background-color: {p.bg_secondary};
    border-right: 1px solid {p.border};
}}

#ToolsPanelBottom {{
    background: transparent;
    border-top: 1px solid {p.border_light};
}}

/* Tool Card */
#ToolCard {{
    background: transparent;
    border: 1px solid transparent;
    border-radius: 8px;
}}
#ToolCard:hover {{
    background: rgba(108,92,231,0.06);
    border: 1px solid rgba(108,92,231,0.15);
}}

/* CONTROL CENTER (Center) */
#ControlCenter {{
    background: qlineargradient(
        x1:0, y1:0, x2:0, y2:1,
        stop:0 {p.bg_primary},
        stop:0.3 rgba(12, 14, 28, 1),
        stop:0.5 rgba(10, 12, 25, 1),
        stop:0.7 rgba(12, 14, 28, 1),
        stop:1 {p.bg_primary}
    );
}}

#QuickAction {{
    background: rgba(255,255,255,0.02);
    border: 1px solid rgba(255,255,255,0.04);
    border-radius: 12px;
}}
#QuickAction:hover {{
    background: {p.accent_soft};
    border-color: {p.accent};
}}

#BigMicBtn {{
    border-radius: 28px;
}}

/* CHAT PANEL (Right) */
#ChatPanel {{
    background-color: {p.bg_primary};
}}

#ChatPanelHeader {{
    background-color: {p.bg_secondary};
    border-bottom: 1px solid {p.border_light};
}}

/* MISC */
QToolTip {{
    background-color: {p.bg_tertiary};
    color: {p.text_primary};
    border: 1px solid {p.border};
    border-radius: 6px;
    padding: 6px 10px;
    font-size: 12px;
}}

QDialog {{
    background-color: {p.bg_secondary};
    border: 1px solid {p.border};
    border-radius: 12px;
}}

QTabWidget::pane {{
    background-color: {p.bg_secondary};
    border: 1px solid {p.border};
    border-radius: 0 0 8px 8px;
}}
QTabBar::tab {{
    background-color: {p.bg_tertiary};
    color: {p.text_secondary};
    border: none;
    padding: 8px 16px;
    font-size: 12px;
    font-weight: 500;
}}
QTabBar::tab:selected {{
    background-color: {p.bg_secondary};
    color: {p.accent};
    border-bottom: 2px solid {p.accent};
}}
QTabBar::tab:hover {{
    color: {p.text_primary};
}}
"""
