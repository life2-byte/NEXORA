from pathlib import Path

from PyQt6.QtWidgets import QApplication

BASE_QSS = Path(__file__).parent / "base.qss"

PALETTES = {
    "dark": {
        "bg": "#0b1220",
        "surface": "#0e1626",
        "panel": "#111a2b",
        "border": "#1f2d45",
        "border_hover": "#2a4468",
        "text": "#e6eaf2",
        "text2": "#c9d1e0",
        "muted": "#8b98b0",
        "accent": "#38bdf8",
        "accent_rgb": "56, 189, 248",
        "accent_soft": "#12384d",
        "checked": "#132033",
        "hover_soft": "#162238",
        "hover": "#1a2740",
        "pressed": "#24344f",
        "disabled": "#4a5063",
        "strip": "#0d1a2b",
    },
}

# icons ke liye
COLORS = {
    "bg": "#0b1220",
    "panel": "#111a2b",
    "border": "#1f2d45",
    "accent": "#38bdf8",
    "text": "#e6eaf2",
    "muted": "#7f8ba3",
}


def build_stylesheet(mode: str | None = None) -> str:
    palette = PALETTES.get(mode or "dark", PALETTES["dark"])
    qss = BASE_QSS.read_text(encoding="utf-8")
    for key, value in palette.items():
        qss = qss.replace(f"@{key}@", value)
    return qss


def apply_theme(app: QApplication, mode: str | None = None) -> None:
    app.setStyleSheet(build_stylesheet(mode))