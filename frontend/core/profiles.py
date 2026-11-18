"""Browser profiles (Chrome jese). Har profile apni alag process mein chalta hai aur uska apna data folder hota hai:
cookies, history, bookmarks, downloads, settings sab alag. 'default' profile purane folder mein hi rehta hai."""

import json
import os
import re
import shutil
import subprocess
import sys
from pathlib import Path
from typing import Optional

from PyQt6.QtCore import QLockFile

from frontend.core.settings_manager import settings

DEFAULT_ID = "default"
COLORS = ["#38bdf8", "#a78bfa", "#f472b6", "#fb923c", "#4ade80", "#facc15", "#f87171", "#2dd4bf"]

_FILE = settings.root_dir / "profiles.json"
_ID_OK = re.compile(r"[a-z0-9-]{1,40}")
_MAIN_SCRIPT = Path(sys.argv[0]).resolve()
_held_lock: Optional[QLockFile] = None


def profile_dir(profile_id: str) -> Path:
    return settings.root_dir if profile_id == DEFAULT_ID else settings.root_dir / "profiles" / profile_id


# ---------- registry (profiles.json) ----------
def _read() -> list[dict]:
    try:
        data = json.loads(_FILE.read_text(encoding="utf-8"))
    except (OSError, ValueError):
        data = []
    items = []
    for p in data if isinstance(data, list) else []:
        if isinstance(p, dict) and _ID_OK.fullmatch(str(p.get("id", ""))) and p.get("name"):
            items.append({"id": p["id"], "name": str(p["name"])[:30], "color": p.get("color") or COLORS[0]})
    if not any(p["id"] == DEFAULT_ID for p in items):
        items.insert(0, {"id": DEFAULT_ID, "name": "Default", "color": COLORS[0]})
    return items


def _write(items: list[dict]) -> None:
    try:
        settings.root_dir.mkdir(parents=True, exist_ok=True)
        _FILE.write_text(json.dumps(items, indent=2), encoding="utf-8")
    except OSError:
        pass


def list_profiles() -> list[dict]:
    return _read()


def get_profile_info(profile_id: str) -> Optional[dict]:
    return next((p for p in _read() if p["id"] == profile_id), None)


def current_profile() -> dict:
    return get_profile_info(settings.profile_id) or {"id": settings.profile_id, "name": settings.profile_id, "color": COLORS[0]}


def add_profile(name: str, color: str) -> str:
    items = _read()
    base = re.sub(r"[^a-z0-9]+", "-", name.lower()).strip("-")[:30] or "profile"
    taken = {p["id"] for p in items}
    pid, n = base, 2
    while pid in taken or pid == DEFAULT_ID:
        pid = f"{base}-{n}"
        n += 1
    items.append({"id": pid, "name": name.strip()[:30] or "Profile", "color": color})
    _write(items)
    return pid


def update_profile(profile_id: str, name: str, color: str) -> None:
    items = _read()
    for p in items:
        if p["id"] == profile_id:
            p["name"] = name.strip()[:30] or p["name"]
            p["color"] = color
    _write(items)


def delete_profile(profile_id: str) -> Optional[str]:
    """None = delete ho gaya, warna error text."""
    if profile_id == DEFAULT_ID:
        return "Default profile delete nahi hota."
    if is_running(profile_id):
        return "Ye profile abhi khula hua hai. Pehle is ki window band karo."
    shutil.rmtree(profile_dir(profile_id), ignore_errors=True)
    _write([p for p in _read() if p["id"] != profile_id])
    return None


# ---------- ek profile = ek process ----------
def _lock_path(profile_id: str) -> Path:
    return profile_dir(profile_id) / "profile.lock"


def acquire_lock() -> bool:
    """App ke shuru mein call karo. False = ye profile pehle se kisi aur process mein khula hai."""
    global _held_lock
    settings.config_dir.mkdir(parents=True, exist_ok=True)
    lock = QLockFile(str(_lock_path(settings.profile_id)))
    if not lock.tryLock(200):
        return False
    _held_lock = lock  # reference zinda rakho, process khatam hone tak lock rahega
    return True


def is_running(profile_id: str) -> bool:
    if profile_id == settings.profile_id:
        return True
    path = _lock_path(profile_id)
    if not path.parent.exists():
        return False
    probe = QLockFile(str(path))
    if probe.tryLock(0):
        probe.unlock()
        return False
    return True


def launch(profile_id: str) -> bool:
    """Profile ko nayi alag window (process) mein kholta hai."""
    if getattr(sys, "frozen", False):
        cmd = [sys.executable, "--profile", profile_id]
    else:
        cmd = [sys.executable, str(_MAIN_SCRIPT), "--profile", profile_id]
    env = dict(os.environ)
    env.pop("NEXORA_PROFILE", None)
    kwargs: dict = {"env": env, "stdin": subprocess.DEVNULL, "stdout": subprocess.DEVNULL, "stderr": subprocess.DEVNULL}
    if sys.platform.startswith("win"):
        kwargs["creationflags"] = 0x00000008 | 0x00000200  # DETACHED_PROCESS | CREATE_NEW_PROCESS_GROUP
    else:
        kwargs["start_new_session"] = True
    try:
        subprocess.Popen(cmd, cwd=str(_MAIN_SCRIPT.parent), **kwargs)
        return True
    except OSError:
        return False