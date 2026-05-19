"""Shared color and typography tokens for the BertyType UI."""
from __future__ import annotations

# Surfaces
BG           = "#121212"   # Near Black - deepest background
BG_ELEVATED  = "#181818"   # Dark Surface - cards, containers
BG_MID       = "#1f1f1f"   # Mid Dark - interactive surfaces, button backgrounds
BORDER       = "#4d4d4d"   # Border Gray
BORDER_LIGHT = "#7c7c7c"   # Light Border - outlined elements, focus rings

# Text
TEXT           = "#ffffff"   # White - primary text
TEXT_SECONDARY = "#b3b3b3"   # Silver - secondary text, muted labels
TEXT_DIM       = "#888888"   # Dimmed - tray error state, fine print

# Semantic
ACCENT       = "#1ed760"   # Spotify Green - play, active states, CTAs
ACCENT_HVR   = "#22e865"   # Green hover
DESTRUCTIVE  = "#f3727f"   # Negative Red - error states
WARNING      = "#ffa42b"   # Warning Orange - warning states
ANNOUNCEMENT = "#539df5"   # Announcement Blue - info states

# Control-specific surfaces
SWITCH_TRACK = "#4d4d4d"   # Toggle switch off-state track

# Tray status icon colors
STATUS_COLORS: dict[str, str] = {
    "idle":       ACCENT,
    "recording":  DESTRUCTIVE,
    "processing": WARNING,
    "error":      TEXT_DIM,
}

# Typography
FONT_FAMILY = "Segoe UI"   # Windows system UI font, nearest to Spotify's SpotifyMixUI/CircularSp
FONT = ("Segoe UI", 11)    # Kept for any legacy callers


def build_qss() -> str:
    return f"""
    * {{
        font-family: "{FONT_FAMILY}";
    }}
    QDialog, QWizard {{
        background: {BG};
        color: {TEXT};
        font-size: 13px;
    }}
    QLabel {{
        color: {TEXT};
        background: transparent;
    }}
    QLineEdit, QKeySequenceEdit {{
        background: {BG_MID};
        border: 1px solid {BORDER};
        border-radius: 500px;
        padding: 6px 14px;
        color: {TEXT};
        font-size: 13px;
    }}
    QLineEdit:focus, QKeySequenceEdit:focus {{
        border-color: {BORDER_LIGHT};
    }}
    QComboBox {{
        background: {BG_MID};
        border: 1px solid {BORDER};
        border-radius: 500px;
        padding: 6px 14px;
        color: {TEXT};
        font-size: 13px;
    }}
    QComboBox:focus {{
        border-color: {BORDER_LIGHT};
    }}
    QComboBox QAbstractItemView {{
        background: {BG_ELEVATED};
        border: 1px solid {BORDER};
        color: {TEXT};
        selection-background-color: {BG_MID};
    }}
    QSlider::groove:horizontal {{
        background: {BG_MID};
        height: 4px;
        border-radius: 2px;
    }}
    QSlider::handle:horizontal {{
        background: {ACCENT};
        width: 11px;
        height: 11px;
        margin: -4px 0;
        border-radius: 5px;
    }}
    QSlider::sub-page:horizontal {{
        background: {ACCENT};
        border-radius: 2px;
    }}
    QPushButton {{
        background: {BG_MID};
        border: 1px solid {BORDER};
        border-radius: 9999px;
        padding: 8px 20px;
        color: {TEXT};
        font-size: 13px;
        font-weight: 700;
    }}
    QPushButton:hover {{
        border-color: {TEXT};
    }}
    QPushButton:focus {{
        border-color: {ACCENT};
        outline: none;
    }}
    QPushButton[accent="true"] {{
        background: {ACCENT};
        border: none;
        color: {BG};
        font-weight: 700;
    }}
    QPushButton[accent="true"]:hover {{
        background: {ACCENT_HVR};
    }}
    QCheckBox {{
        color: {TEXT};
        spacing: 8px;
    }}
    QCheckBox::indicator {{
        width: 38px;
        height: 20px;
        border-radius: 10px;
    }}
    QCheckBox::indicator:unchecked {{
        background: {SWITCH_TRACK};
    }}
    QCheckBox::indicator:checked {{
        background: {ACCENT};
    }}
    QScrollArea, QScrollArea > QWidget > QWidget {{
        background: {BG};
        border: none;
    }}
    QScrollBar:vertical {{
        background: {BG};
        width: 8px;
    }}
    QScrollBar::handle:vertical {{
        background: {BORDER};
        border-radius: 4px;
        min-height: 20px;
    }}
    QScrollBar::add-line:vertical, QScrollBar::sub-line:vertical {{
        height: 0;
    }}
    QPlainTextEdit {{
        background: {BG_ELEVATED};
        border: 1px solid {BORDER};
        border-radius: 6px;
        color: {TEXT_SECONDARY};
        font-size: 12px;
    }}
    QProgressBar {{
        background: {BG_ELEVATED};
        border: none;
        border-radius: 4px;
        height: 8px;
        color: transparent;
    }}
    QProgressBar::chunk {{
        background: {ACCENT};
        border-radius: 4px;
    }}
    QWizard QPushButton {{
        min-width: 80px;
    }}
    """
