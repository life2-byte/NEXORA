import json
import os
import re
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
    "show_most_visited": True,
    "site_zoom": {},  # host -> zoom percent
    "adblock_allow": [],  # in sites par ad blocker band
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
    "save_history": True,
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

    "cache_limit_mb": 0,  # 0 = automatic

        # AI and privacy
    "ai_enabled": True,  # release se pehle False karna (privacy-first)
    "ai_provider": "local",  # local | remote
    "ai_local_kind": "ollama",  # ollama | openai (LM Studio, llama.cpp...)
    "ai_local_endpoint": "http://127.0.0.1:11434",
    "ai_local_model": "",
    "ai_remote_provider": "anthropic",
    "ai_remote_model": "",
    "ai_remote_base_url": "",
    "ai_remote_consent": False,
    "ai_blocklist_custom": [],
    "ai_budget_period": "none",  # none | day | month (tumhari apni token limit)
    "ai_budget_tokens": 100000,
    "agent_language": "auto",  # auto | english | roman_urdu | urdu
    "agent_detail": "normal",  # short | normal | detailed
    "agent_confirm": "risky",  # risky | always
    "ai_vision": "auto",       # auto | on | off (screenshot dekhne wale model)
    "ai_thinking": "low",      # low (tez) | auto (model ka apna default)
    "agent_typing": "human",   # human | instant
    "agent_max_steps": 25,
    "agent_instructions": "",
    "default_agent": "browser",
    "ai_log_enabled": True,

    "adblock_enabled": True,
    "https_first": True,
    "passwords_enabled": True,
    "userscripts_off": [],  # band ki hui user scripts ke filenames
    "pinned_tabs": [],
    "spellcheck": True,

    "session_tabs": [],
    "session_active": 0,
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
        # Default profile purane folder mein hi rehta hai (koi migration nahi),
        # baqi profiles root/profiles/<id> mein. Profile id main.py se env var mein aati hai.
        self.root_dir = Path(base) / "agentic-browser"
        pid = os.environ.get("NEXORA_PROFILE", "") or "default"
        if not re.fullmatch(r"[a-z0-9-]{1,40}", pid):
            pid = "default"
        self.profile_id = pid
        self.config_dir = self.root_dir if pid == "default" else self.root_dir / "profiles" / pid
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

    # ---------- home background library (sab user ke apne profile folder mein) ----------
    IMAGE_EXT = (".png", ".jpg", ".jpeg", ".webp", ".gif", ".bmp")
    VIDEO_EXT = (".webm", ".mp4", ".mkv", ".mov", ".avi", ".ogv", ".ogg")

    def list_backgrounds(self) -> list:
        """[{'path', 'name', 'kind'}] purani se nayi tak"""
        if not self.backgrounds_dir.exists():
            return []
        items = []
        for f in sorted(self.backgrounds_dir.iterdir(), key=lambda x: x.stat().st_mtime, reverse=True):
            ext = f.suffix.lower()
            if f.name.startswith("custom_") or ext not in self.IMAGE_EXT + self.VIDEO_EXT:
                continue
            items.append({"path": str(f), "name": f.stem.rsplit("_", 1)[0] or f.stem,
                          "kind": "image" if ext in self.IMAGE_EXT else "video"})
        return items

    def set_background(self, mode: str, source: str, label: str = "") -> None:
        """User ki image/video ko profile folder mein copy karke use set karta hai (purani files rehti hain)."""
        src = Path(source)
        self.backgrounds_dir.mkdir(parents=True, exist_ok=True)
        if src.parent == self.backgrounds_dir:
            dest = src
        else:
            stem = re.sub(r"[^\w\- ]+", "", label or src.stem).strip()[:40] or "background"
            dest = self.backgrounds_dir / f"{stem}_{int(time.time() * 1000)}{src.suffix.lower()}"
            shutil.copy2(src, dest)
        self.set_many({"bg_mode": mode, "bg_path": str(dest)})

    def use_background(self, path: str) -> None:
        kind = "image" if Path(path).suffix.lower() in self.IMAGE_EXT else "video"
        self.set_many({"bg_mode": kind, "bg_path": path})

    def remove_background(self, path: str) -> None:
        f = Path(path)
        if f.parent != self.backgrounds_dir:
            return  # sirf apne folder ki files delete hoti hain
        try:
            f.unlink()
        except OSError:
            pass
        if self._data.get("bg_path") == path:
            self.set_many({"bg_mode": "default", "bg_path": ""})
        else:
            self.changed.emit("bg_library", None)


settings = SettingsManager()