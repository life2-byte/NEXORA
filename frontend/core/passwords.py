"""Password manager ka Qt hissa: page se submit/focus messages leta hai, save prompt aur autofill menu dikhata hai.
Dono Qt widgets hain (page ke andar nahi), isliye website ya agent unhe click/padh nahi sakte."""

import json
import secrets
from pathlib import Path
from urllib.parse import urlsplit

from PyQt6.QtCore import QObject, QPoint, QTimer, pyqtSignal
from PyQt6.QtWebEngineCore import QWebEngineScript
from PyQt6.QtWebEngineWidgets import QWebEngineView
from PyQt6.QtWidgets import QMenu, QMessageBox

from backend.security.vault import PasswordVault
from frontend.core.settings_manager import settings

_JS = (Path(__file__).parent / "bridge_scripts" / "password_helper.js").read_text(encoding="utf-8")
_WORLD = QWebEngineScript.ScriptWorldId.UserWorld.value


class VaultHandle(QObject):
    """Poore app ke liye ek vault; changed signal se Passwords page refresh hota hai."""

    changed = pyqtSignal()

    def __init__(self) -> None:
        super().__init__()
        self.vault = PasswordVault(settings.config_dir / "passwords.json", f"vault-key-{settings.profile_id}")


_handle = None


def get_vault() -> VaultHandle:
    global _handle
    if _handle is None:
        _handle = VaultHandle()
    return _handle


def origin_of(url) -> str:
    """Page ka origin (scheme://host[:port]); sirf http/https."""
    parts = urlsplit(url if isinstance(url, str) else url.toString())
    if parts.scheme not in ("http", "https") or not parts.hostname:
        return ""
    port = f":{parts.port}" if parts.port else ""
    return f"{parts.scheme}://{parts.hostname}{port}"


def host_label(origin: str) -> str:
    return urlsplit(origin).netloc or origin


class PageBridge(QObject):
    """Har BrowserPage ke saath ek: apna random token, apni script."""

    def __init__(self, page) -> None:
        super().__init__(page)
        self._page = page
        self._token = secrets.token_hex(16)
        self._busy = False
        script = QWebEngineScript()
        script.setName("nexora-passwords")
        script.setSourceCode(_JS.replace("__NX_TOKEN__", self._token))
        script.setInjectionPoint(QWebEngineScript.InjectionPoint.DocumentReady)
        script.setWorldId(_WORLD)
        script.setRunsOnSubFrames(False)
        page.scripts().insert(script)

    def handle(self, message: str) -> bool:
        """True = ye hamara message tha (console mein mat dikhao)."""
        if not message.startswith("NXPW:"):
            return False
        token, _, body = message[5:].partition(":")
        if not secrets.compare_digest(token, self._token):
            return True  # website ne nakli message bheja: ignore
        try:
            data = json.loads(body)
        except ValueError:
            return True
        kind = data.get("t")
        if kind == "submit":
            QTimer.singleShot(0, lambda: self._on_submit(data))
        elif kind == "query":
            QTimer.singleShot(0, lambda: self._on_query(data))
        return True

    def _valid_origin(self, data: dict) -> str:
        origin = origin_of(self._page.url())
        if not origin or data.get("origin") != origin:
            return ""
        if not settings.get("passwords_enabled"):
            return ""
        return origin if get_vault().vault.available else ""

    def _window(self):
        view = QWebEngineView.forPage(self._page)
        return view.window() if view is not None else None

    # ---------- save / update prompt ----------
    def _on_submit(self, data: dict) -> None:
        origin = self._valid_origin(data)
        user, password = str(data.get("user", "")), str(data.get("pass", ""))
        handle = get_vault()
        vault = handle.vault
        if not origin or not password or self._busy or vault.is_never(origin):
            return
        status = vault.check(origin, user, password)
        if status == "same":
            return
        self._busy = True
        try:
            box = QMessageBox(self._window())
            box.setIcon(QMessageBox.Icon.Question)
            box.setWindowTitle("Save password?" if status == "new" else "Update password?")
            who = user or "(bina username)"
            box.setText(f"<b>{host_label(origin)}</b> ke liye {who} ka password " + ("save karun?" if status == "new" else "update karun?"))
            save = box.addButton("Save" if status == "new" else "Update", QMessageBox.ButtonRole.AcceptRole)
            box.addButton("Not now", QMessageBox.ButtonRole.RejectRole)
            never = box.addButton("Never for this site", QMessageBox.ButtonRole.DestructiveRole)
            box.setDefaultButton(save)
            box.exec()
            clicked = box.clickedButton()
            if clicked is save:
                vault.save(origin, user, password)
                handle.changed.emit()
            elif clicked is never:
                vault.add_never(origin)
        finally:
            self._busy = False

    # ---------- autofill menu ----------
    def _on_query(self, data: dict) -> None:
        origin = self._valid_origin(data)
        if not origin:
            return
        vault = get_vault().vault
        rows = vault.for_origin(origin)
        view = QWebEngineView.forPage(self._page)
        if not rows or view is None or self._busy:
            return
        if len(rows) == 1:  # ek hi login saved ho to seedha fill (user ne field pe click kiya hai)
            self._fill(rows[0])
            return
        menu = QMenu(self._window())
        for row in rows:
            label = row["username"] or "(bina username)"
            menu.addAction(f"Fill: {label}", lambda r=row: self._fill(r))
        zoom = view.zoomFactor()
        pos = view.mapToGlobal(QPoint(int(float(data.get("x", 0)) * zoom), int(float(data.get("y", 0)) * zoom)))
        self._busy = True
        try:
            menu.exec(pos)
        finally:
            self._busy = False

    def _fill(self, row: dict) -> None:
        if origin_of(self._page.url()) != row["origin"]:
            return  # menu khula tha aur page badal gaya
        password = get_vault().vault.get_password(row["id"])
        if password is None:
            return
        self._page.runJavaScript(f"window.__nxFill({json.dumps(row['username'])},{json.dumps(password)})", _WORLD)