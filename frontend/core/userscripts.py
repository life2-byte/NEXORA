"""User scripts ko browser mein lagata hai (profile ki scripts collection mein; har page par sirf match wali chalti hain)."""

from PyQt6.QtCore import QObject, pyqtSignal
from PyQt6.QtWebEngineCore import QWebEngineScript

from backend.extensions.userscripts import ScriptStore
from frontend.core.profile import get_profile
from frontend.core.settings_manager import settings

PREFIX = "nexora-us:"
_POINTS = {
    "document-start": QWebEngineScript.InjectionPoint.DocumentCreation,
    "document-end": QWebEngineScript.InjectionPoint.DocumentReady,
    "document-idle": QWebEngineScript.InjectionPoint.Deferred,
}


class UserScriptManager(QObject):
    changed = pyqtSignal()

    def __init__(self) -> None:
        super().__init__()
        self.store = ScriptStore(settings.config_dir / "userscripts")
        self._installed: list = []  # jo scripts humne lagayi (Qt header se naam badal deta hai, isliye naam par bharosa nahi)

    def scripts(self) -> list:
        return self.store.list()

    def is_enabled(self, filename: str) -> bool:
        return filename not in (settings.get("userscripts_off") or [])

    def set_enabled(self, filename: str, on: bool) -> None:
        off = [f for f in (settings.get("userscripts_off") or []) if f != filename]
        if not on:
            off.append(filename)
        settings.set("userscripts_off", off)
        self.rebuild()

    def save(self, filename: str, text: str) -> str:
        name = self.store.save(filename, text)
        self.rebuild()
        return name

    def delete(self, filename: str) -> None:
        self.store.delete(filename)
        off = [f for f in (settings.get("userscripts_off") or []) if f != filename]
        settings.set("userscripts_off", off)
        self.rebuild()

    def rebuild(self) -> None:
        """Purani scripts hatao, ab ki enabled scripts dobara lagao. Khuli tabs ko reload karna padta hai."""
        collection = get_profile().scripts()
        for script in self._installed:
            collection.remove(script)
        self._installed = []
        for item in self.scripts():
            if not item.valid or not self.is_enabled(item.filename):
                continue
            script = QWebEngineScript()
            script.setSourceCode(item.wrapped_source())
            script.setName(PREFIX + item.filename)  # source ke baad: Qt @name header se naam badal deta hai
            script.setInjectionPoint(_POINTS[item.meta["run-at"]])
            world = QWebEngineScript.ScriptWorldId.MainWorld if item.meta["world"] == "main" else QWebEngineScript.ScriptWorldId.UserWorld
            script.setWorldId(world.value)
            script.setRunsOnSubFrames(False)
            collection.insert(script)
            self._installed.append(script)
        self.changed.emit()


_manager = None


def get_userscripts() -> UserScriptManager:
    global _manager
    if _manager is None:
        _manager = UserScriptManager()
    return _manager


def install() -> None:
    get_userscripts().rebuild()