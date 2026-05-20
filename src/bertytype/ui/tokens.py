"""Shared color and typography tokens for the BertyType UI."""
from __future__ import annotations

# --- Dark palette constants (module-level for backward compat) ---
BG           = "#121212"
BG_ELEVATED  = "#181818"
BG_MID       = "#1f1f1f"
BORDER       = "#4d4d4d"
BORDER_LIGHT = "#7c7c7c"
TEXT           = "#ffffff"
TEXT_SECONDARY = "#b3b3b3"
TEXT_DIM       = "#909090"   # lightened from #888 for better AA margin
ACCENT       = "#1ed760"
ACCENT_HVR   = "#22e865"
DESTRUCTIVE  = "#f3727f"
WARNING      = "#ffa42b"
ANNOUNCEMENT = "#539df5"
SWITCH_TRACK = "#4d4d4d"

STATUS_COLORS: dict[str, str] = {
    "idle":       ACCENT,
    "recording":  DESTRUCTIVE,
    "processing": WARNING,
    "error":      TEXT_DIM,
}

FONT_FAMILY = "Segoe UI"
FONT = ("Segoe UI", 11)


def _dark_palette() -> dict:
    return dict(
        bg=BG, bg_elevated=BG_ELEVATED, bg_mid=BG_MID,
        border=BORDER, border_light=BORDER_LIGHT,
        text=TEXT, text_secondary=TEXT_SECONDARY, text_dim=TEXT_DIM,
        accent=ACCENT, accent_hvr=ACCENT_HVR, accent_pressed="#18a348",
        destructive=DESTRUCTIVE, switch_track=SWITCH_TRACK,
        font_family=FONT_FAMILY,
    )


def _light_palette() -> dict:
    return dict(
        bg="#f5f5f5", bg_elevated="#ffffff", bg_mid="#ebebeb",
        border="#d4d4d4", border_light="#999999",
        text="#121212", text_secondary="#555555", text_dim="#6b6b6b",
        accent=ACCENT, accent_hvr=ACCENT_HVR, accent_pressed="#18a348",
        destructive=DESTRUCTIVE, switch_track="#c7c7c7",
        font_family=FONT_FAMILY,
    )


def build_qss(theme: str = "dark") -> str:
    if theme not in ("dark", "light"):
        raise ValueError(f"Unknown theme: {theme!r}")
    p = _light_palette() if theme == "light" else _dark_palette()
    return f"""
    * {{
        font-family: "{p['font_family']}";
    }}
    QDialog, QWizard {{
        background: {p['bg']};
        color: {p['text']};
        font-size: 13px;
    }}
    QLabel {{
        color: {p['text']};
        background: transparent;
    }}
    QToolTip {{
        background: {p['bg_elevated']};
        color: {p['text']};
        border: 1px solid {p['border']};
        padding: 4px 8px;
        border-radius: 4px;
        font-size: 12px;
    }}
    QLineEdit, QKeySequenceEdit {{
        background: {p['bg_mid']};
        border: 1px solid {p['border']};
        border-radius: 500px;
        padding: 6px 14px;
        color: {p['text']};
        font-size: 13px;
    }}
    QLineEdit:focus, QKeySequenceEdit:focus {{
        border-color: {p['border_light']};
    }}
    QComboBox {{
        background: {p['bg_mid']};
        border: 1px solid {p['border']};
        border-radius: 500px;
        padding: 6px 14px;
        color: {p['text']};
        font-size: 13px;
    }}
    QComboBox:hover {{
        border-color: {p['border_light']};
    }}
    QComboBox:focus {{
        border-color: {p['accent']};
    }}
    QComboBox::drop-down {{
        border: none;
        width: 24px;
    }}
    QComboBox QAbstractItemView {{
        background: {p['bg_elevated']};
        border: 1px solid {p['border']};
        color: {p['text']};
        selection-background-color: {p['bg_mid']};
    }}
    QComboBox QAbstractItemView::item:hover {{
        background: {p['bg_mid']};
    }}
    QSlider::groove:horizontal {{
        background: {p['bg_mid']};
        height: 4px;
        border-radius: 2px;
    }}
    QSlider::handle:horizontal {{
        background: {p['accent']};
        width: 11px;
        height: 11px;
        margin: -4px 0;
        border-radius: 5px;
    }}
    QSlider::handle:horizontal:pressed {{
        background: {p['accent_hvr']};
        width: 14px;
        height: 14px;
        margin: -5px 0;
    }}
    QSlider::sub-page:horizontal {{
        background: {p['accent']};
        border-radius: 2px;
    }}
    QPushButton {{
        background: {p['bg_mid']};
        border: 1px solid {p['border']};
        border-radius: 9999px;
        padding: 8px 20px;
        color: {p['text']};
        font-size: 13px;
        font-weight: 700;
    }}
    QPushButton:hover {{
        border-color: {p['text']};
    }}
    QPushButton:focus {{
        border-color: {p['accent']};
        outline: none;
    }}
    QPushButton:pressed {{
        background: {p['bg']};
    }}
    QPushButton[accent="true"] {{
        background: {p['accent']};
        border: none;
        color: {p['bg']};
        font-weight: 700;
    }}
    QPushButton[accent="true"]:hover {{
        background: {p['accent_hvr']};
    }}
    QPushButton[accent="true"]:pressed {{
        background: {p['accent_pressed']};
    }}
    QCheckBox {{
        color: {p['text']};
        spacing: 8px;
    }}
    QCheckBox::indicator {{
        width: 38px;
        height: 20px;
        border-radius: 10px;
    }}
    QCheckBox::indicator:unchecked {{
        background: {p['switch_track']};
    }}
    QCheckBox::indicator:checked {{
        background: {p['accent']};
    }}
    QCheckBox:focus {{
        outline: 1px dotted {p['accent']};
    }}
    QScrollArea, QScrollArea > QWidget > QWidget {{
        background: {p['bg']};
        border: none;
    }}
    QScrollBar:vertical {{
        background: {p['bg']};
        width: 8px;
    }}
    QScrollBar::handle:vertical {{
        background: {p['border']};
        border-radius: 4px;
        min-height: 20px;
    }}
    QScrollBar::add-line:vertical, QScrollBar::sub-line:vertical {{
        height: 0;
    }}
    QScrollBar:horizontal {{
        background: {p['bg']};
        height: 8px;
    }}
    QScrollBar::handle:horizontal {{
        background: {p['border']};
        border-radius: 4px;
        min-width: 20px;
    }}
    QScrollBar::add-line:horizontal, QScrollBar::sub-line:horizontal {{
        width: 0;
    }}
    QPlainTextEdit {{
        background: {p['bg_elevated']};
        border: 1px solid {p['border']};
        border-radius: 6px;
        color: {p['text_secondary']};
        font-size: 12px;
    }}
    QProgressBar {{
        background: {p['bg_elevated']};
        border: none;
        border-radius: 4px;
        height: 8px;
        color: transparent;
    }}
    QProgressBar::chunk {{
        background: {p['accent']};
        border-radius: 4px;
    }}
    QWizard QPushButton {{
        min-width: 80px;
    }}
    """
