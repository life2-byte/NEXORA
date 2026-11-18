"""Sites ke asli icons (favicons): jab koi site khulti hai to uska icon profile folder mein save hota hai,
home page ke most-visited tiles wahi dikhate hain. Koi third-party service use nahi hoti."""

import re
import time
from pathlib import Path
from typing import Optional

from PyQt6.QtCore import QSize, Qt
from PyQt6.QtGui import QIcon

from frontend.core.settings_manager import settings

SIZE = 64
_REFRESH_SECONDS = 24 * 3600


def _dir() -> Path:
    return settings.config_dir / "favicons"


def key_for(host: str) -> str:
    host = host.lower().removeprefix("www.")
    return re.sub(r"[^a-z0-9.\-]", "_", host)[:100]


def file_for(host: str) -> Path:
    return _dir() / f"{key_for(host)}.png"


def save(host: str, icon: QIcon) -> None:
    if not host or icon.isNull():
        return
    path = file_for(host)
    try:
        if path.exists() and time.time() - path.stat().st_mtime < _REFRESH_SECONDS:
            return
        pixmap = icon.pixmap(QSize(SIZE, SIZE))
        if pixmap.isNull() or pixmap.width() < 8:
            return
        if pixmap.width() != SIZE:
            pixmap = pixmap.scaled(SIZE, SIZE, Qt.AspectRatioMode.KeepAspectRatio, Qt.TransformationMode.SmoothTransformation)
        _dir().mkdir(parents=True, exist_ok=True)
        pixmap.save(str(path), "PNG")
    except OSError:
        pass


def url_for(host: str) -> Optional[str]:
    """file:// URL agar icon save hai, warna None."""
    path = file_for(host)
    return path.as_uri() if path.is_file() else None


def clear() -> None:
    d = _dir()
    if d.exists():
        for f in d.glob("*.png"):
            try:
                f.unlink()
            except OSError:
                pass