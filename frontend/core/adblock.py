"""Ad / tracker blocker: Chromium ki har sub-request (scripts, images, XHR...) ko interceptor se guzarta hai.
Page ki apni navigation kabhi block nahi hoti, sirf us ke andar ke ads aur trackers."""

import threading
import time
import urllib.request
from pathlib import Path

from PyQt6.QtCore import QObject, pyqtSignal
from PyQt6.QtWebEngineCore import QWebEngineUrlRequestInfo, QWebEngineUrlRequestInterceptor

from backend.privacy.adblock import FilterEngine
from frontend.core.profile import get_profile
from frontend.core.settings_manager import settings

BUILTIN_LIST = Path(__file__).resolve().parents[2] / "backend" / "privacy" / "default_filters.txt"
FILTERS_DIR = settings.root_dir / "filters"  # saare profiles ke liye ek hi jagah
LIST_URLS = {
    "easylist.txt": "https://easylist.to/easylist/easylist.txt",
    "easyprivacy.txt": "https://easylist.to/easylist/easyprivacy.txt",
}

RT = QWebEngineUrlRequestInfo.ResourceType
_TYPE_NAMES = {
    RT.ResourceTypeScript: "script",
    RT.ResourceTypeImage: "image",
    RT.ResourceTypeStylesheet: "stylesheet",
    RT.ResourceTypeXhr: "xmlhttprequest",
    RT.ResourceTypeSubFrame: "subdocument",
    RT.ResourceTypeMedia: "media",
    RT.ResourceTypeFontResource: "font",
    RT.ResourceTypePing: "ping",
    RT.ResourceTypeObject: "object",
}


# host -> aakhri baar kab data-request (XHR/script/frame) gayi. Agent "network idle" ke liye padhta hai.
_last_activity: dict = {}
_ACTIVITY_TYPES = {RT.ResourceTypeXhr, RT.ResourceTypeScript, RT.ResourceTypeSubFrame, RT.ResourceTypeMainFrame}


def quiet_for(host: str) -> float:
    """Is site se aakhri data-request ko kitne second ho gaye (0 se bara = shaant)."""
    last = _last_activity.get((host or "").lower())
    return 999.0 if last is None else time.monotonic() - last


def _build_engine() -> FilterEngine:
    engine = FilterEngine()
    engine.load_file(BUILTIN_LIST)
    if FILTERS_DIR.is_dir():
        for path in sorted(FILTERS_DIR.glob("*.txt")):
            engine.load_file(path)
    return engine


class AdBlocker(QWebEngineUrlRequestInterceptor):
    """interceptRequest Chromium ke IO thread se chalta hai (GUI thread se nahi), isliye is mein sirf tez, thread-safe kaam."""

    def __init__(self) -> None:
        super().__init__()
        self.engine = _build_engine()
        self.enabled = bool(settings.get("adblock_enabled"))
        self.blocked = 0
        self.allow = frozenset(settings.get("adblock_allow") or [])  # in sites par blocker band
        settings.changed.connect(self._on_setting)

    def _on_setting(self, key: str, value) -> None:
        if key == "adblock_allow":
            self.allow = frozenset(value or [])  # ek assignment: IO thread safe

    def interceptRequest(self, info) -> None:
        rtype = info.resourceType()
        if rtype in _ACTIVITY_TYPES:
            _last_activity[info.firstPartyUrl().host().lower()] = time.monotonic()  # IO thread: sirf ek dict assignment
        if not self.enabled:
            return
        if rtype == RT.ResourceTypeMainFrame:  # kabhi page ki apni navigation block nahi
            return
        url = info.requestUrl()
        if url.scheme() not in ("http", "https", "ws", "wss"):
            return
        if self.allow and info.firstPartyUrl().host().lower() in self.allow:
            return
        query = url.query()
        path_query = url.path() + (f"?{query}" if query else "")
        if self.engine.should_block(
            url.host(), path_query, info.firstPartyUrl().host(), _TYPE_NAMES.get(rtype, "other")
        ):
            info.block(True)
            self.blocked += 1


class AdBlockManager(QObject):
    update_finished = pyqtSignal(str)  # GUI thread pe aata hai

    def __init__(self) -> None:
        super().__init__()
        self.blocker = AdBlocker()
        settings.changed.connect(self._on_setting)

    def _on_setting(self, key: str, value) -> None:
        if key == "adblock_enabled":
            self.blocker.enabled = bool(value)

    def install(self) -> None:
        get_profile().setUrlRequestInterceptor(self.blocker)

    def stats_text(self) -> str:
        return f"Is session mein {self.blocker.blocked} ads/trackers block hue  |  {self.blocker.engine.count} filter rules"

    def update_lists(self) -> None:
        """EasyList wagera download karta hai (background thread mein), phir engine badal deta hai."""
        threading.Thread(target=self._download, daemon=True).start()

    def _download(self) -> None:
        FILTERS_DIR.mkdir(parents=True, exist_ok=True)
        done, failed = 0, []
        for name, url in LIST_URLS.items():
            try:
                req = urllib.request.Request(url, headers={"User-Agent": "Nexora"})
                with urllib.request.urlopen(req, timeout=30) as resp:
                    data = resp.read()
                if len(data) < 1000:
                    raise ValueError("list bohat chhoti")
                (FILTERS_DIR / name).write_bytes(data)
                done += 1
            except Exception as e:  # network ya file ka koi bhi masla
                failed.append(f"{name}: {e}")
        if done:
            engine = _build_engine()
            self.blocker.engine = engine  # ek assignment: IO thread purani ya nayi poori engine dekhta hai
        message = f"{done} list update hui" + (f", {len(failed)} fail ({'; '.join(failed)})" if failed else "")
        self.update_finished.emit(message)  # background thread se emit: receiver GUI thread mein hai to queued chalta hai


_manager = None


def get_adblock() -> AdBlockManager:
    global _manager
    if _manager is None:
        _manager = AdBlockManager()
    return _manager


def install() -> None:
    """QApplication aur profile banne ke baad ek dafa call karo."""
    get_adblock().install()