import json
import shutil
import time
from pathlib import Path

from PyQt6.QtCore import QObject, QStandardPaths, pyqtSignal

DEFAULTS = {
    # appearance
    "bg_mode": "default",  # default | image | video | none
    "bg_path": "",
    "bg_dim": 55,
    "bg_animated": True,
    # pages
    "zoom": 100,
    "font_size": 16,
    "smooth_scroll": True,
    "force_dark_web": False,
    # search
    "search_engine": "DuckDuckGo",
    # privacy
    "block_popups": False,
    "block_third_party_cookies": False,
    "clear_cookies_on_exit": False,
    # general
    "startup_mode": "home",  # home | blank | custom
    "startup_url": "",
    "newtab_mode": "home",  # home | blank
    "ai_strip": True,
    "restore_geometry": True,
    "window_geometry": "",
    # downloads
    "download_dir": str(Path.home() / "Downloads"),
    "ask_download": False,
}

SEARCH_ENGINES = {
    "DuckDuckGo": "https://duckduckgo.com/?q={query}",
    "Google": "https://www.google.com/search?q={query}",
    "Brave": "https://search.brave.com/search?q={query}",
    "Bing": "https://www.bing.com/search?q={query}",
}


class SettingsManager(QObject):
    changed = pyqtSignal(str, object)

    def __init__(self):
        super().__init__()
        base = QStandardPaths.writableLocation(
            QStandardPaths.StandardLocation.GenericConfigLocation
        )
        self.config_dir = Path(base) / "agentic-browser"
        self.backgrounds_dir = self.config_dir / "backgrounds"
        self._file = self.config_dir / "settings.json"
        self._data = dict(DEFAULTS)
        self._load()

    def _load(self) -> None:
        try:
            stored = json.loads(self._file.read_text(encoding="utf-8"))
        except (OSError, ValueError):
            return
        for key in DEFAULTS:
            if key in stored:
                self._data[key] = stored[key]

    def _save(self) -> None:
        try:
            self.config_dir.mkdir(parents=True, exist_ok=True)
            self._file.write_text(json.dumps(self._data, indent=2), encoding="utf-8")
        except OSError:
            pass

    def get(self, key: str):
        return self._data.get(key, DEFAULTS.get(key))

    def set(self, key: str, value) -> None:
        self.set_many({key: value})

    def set_many(self, values: dict) -> None:
        changed = []
        for key, value in values.items():
            if self._data.get(key) != value:
                self._data[key] = value
                changed.append(key)
        if not changed:
            return
        self._save()
        for key in changed:
            self.changed.emit(key, self._data[key])

    def reset(self) -> None:
        self._data = dict(DEFAULTS)
        self._save()
        for key, value in self._data.items():
            self.changed.emit(key, value)

    def set_background(self, mode: str, source: str) -> None:
        """User ki image/video ko app ke folder mein copy karke use set karta hai."""
        src = Path(source)
        self.backgrounds_dir.mkdir(parents=True, exist_ok=True)
        for old in self.backgrounds_dir.glob("custom_*"):
            try:
                old.unlink()
            except OSError:
                pass
        dest = self.backgrounds_dir / f"custom_{int(time.time())}{src.suffix.lower()}"
        shutil.copy2(src, dest)
        self.set_many({"bg_mode": mode, "bg_path": str(dest)})


settings = SettingsManager()