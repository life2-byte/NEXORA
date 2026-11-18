"""Saved passwords ka vault. Passwords Fernet se encrypt hote hain; encryption key OS keyring mein rehti hai
(file ke saath nahi). Qt ka koi code nahi."""

import json
import os
import time
import uuid
from pathlib import Path
from typing import Optional

from backend.security import secrets as keyring_store

try:
    from cryptography.fernet import Fernet, InvalidToken
except ImportError:  # pip install cryptography
    Fernet = None
    InvalidToken = Exception


class PasswordVault:
    def __init__(self, path: Path, key_name: str):
        self._path = Path(path)
        self._key_name = key_name
        self._fernet = None
        self._error = ""
        self._data = {"entries": [], "never": []}
        self._init_crypto()
        self._load()

    # ---------- setup ----------
    def _init_crypto(self) -> None:
        if Fernet is None:
            self._error = "pip install cryptography zaroori hai."
            return
        key = keyring_store.get_secret(self._key_name)
        if not key:
            key = Fernet.generate_key().decode()
            problem = keyring_store.set_secret(self._key_name, key)
            if problem:
                self._error = problem
                return
        try:
            self._fernet = Fernet(key.encode())
        except Exception:
            self._error = "Vault ki key kharab hai."

    @property
    def available(self) -> bool:
        return self._fernet is not None

    @property
    def error(self) -> str:
        return self._error

    def _load(self) -> None:
        try:
            data = json.loads(self._path.read_text(encoding="utf-8"))
            if isinstance(data, dict):
                self._data["entries"] = list(data.get("entries", []))
                self._data["never"] = list(data.get("never", []))
        except (OSError, ValueError):
            pass

    def _save(self) -> None:
        self._path.parent.mkdir(parents=True, exist_ok=True)
        tmp = self._path.with_suffix(".tmp")
        fd = os.open(tmp, os.O_WRONLY | os.O_CREAT | os.O_TRUNC, 0o600)
        with os.fdopen(fd, "w", encoding="utf-8") as f:
            json.dump(self._data, f)
        os.replace(tmp, self._path)

    # ---------- queries ----------
    def _find(self, origin: str, username: str) -> Optional[dict]:
        return next((e for e in self._data["entries"] if e["origin"] == origin and e["username"] == username), None)

    def entries(self, query: str = "") -> list[dict]:
        q = query.strip().lower()
        rows = [
            {"id": e["id"], "origin": e["origin"], "username": e["username"], "updated": e["updated"]}
            for e in self._data["entries"]
            if not q or q in e["origin"].lower() or q in e["username"].lower()
        ]
        return sorted(rows, key=lambda r: (r["origin"], r["username"]))

    def for_origin(self, origin: str) -> list[dict]:
        return [r for r in self.entries() if r["origin"] == origin]

    def get_password(self, entry_id: str) -> Optional[str]:
        if not self.available:
            return None
        for e in self._data["entries"]:
            if e["id"] == entry_id:
                try:
                    return self._fernet.decrypt(e["pw"].encode()).decode()
                except (InvalidToken, ValueError):
                    return None
        return None

    def check(self, origin: str, username: str, password: str) -> str:
        """'new' | 'update' | 'same'"""
        entry = self._find(origin, username)
        if entry is None:
            return "new"
        return "same" if self.get_password(entry["id"]) == password else "update"

    # ---------- changes ----------
    def save(self, origin: str, username: str, password: str) -> bool:
        if not self.available:
            return False
        token = self._fernet.encrypt(password.encode()).decode()
        now = int(time.time())
        entry = self._find(origin, username)
        if entry:
            entry["pw"], entry["updated"] = token, now
        else:
            self._data["entries"].append(
                {"id": uuid.uuid4().hex, "origin": origin, "username": username, "pw": token, "updated": now}
            )
        self._save()
        return True

    def delete(self, entry_id: str) -> None:
        self._data["entries"] = [e for e in self._data["entries"] if e["id"] != entry_id]
        self._save()

    def is_never(self, origin: str) -> bool:
        return origin in self._data["never"]

    def add_never(self, origin: str) -> None:
        if origin not in self._data["never"]:
            self._data["never"].append(origin)
            self._save()

    def clear_never(self) -> None:
        self._data["never"] = []
        self._save()

    def never_count(self) -> int:
        return len(self._data["never"])