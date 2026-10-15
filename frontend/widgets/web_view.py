from pathlib import Path
from urllib.parse import urlencode

from PyQt6.QtCore import QUrl, pyqtSignal
from PyQt6.QtGui import QIcon
from PyQt6.QtWebEngineWidgets import QWebEngineView

from frontend.core.settings_manager import SEARCH_ENGINES, settings

HOME_FILE = Path(__file__).resolve().parents[1] / "assets" / "home" / "home.html"


def search_template() -> str:
    return SEARCH_ENGINES.get(settings.get("search_engine"), SEARCH_ENGINES["DuckDuckGo"])


def home_url() -> QUrl:
    """Home page + settings URL query ke zariye (background, search engine)."""
    url = QUrl.fromLocalFile(str(HOME_FILE))
    mode = settings.get("bg_mode")
    params = {
        "theme": "dark",
        "mode": mode,
        "dim": str(settings.get("bg_dim")),
        "anim": "1" if settings.get("bg_animated") else "0",
        "engine": search_template(),
    }
    bg_path = settings.get("bg_path")
    if mode in ("image", "video") and bg_path:
        params["src"] = QUrl.fromLocalFile(bg_path).toString()
    url.setQuery(urlencode(params))
    return url


def is_home_url(url: str) -> bool:
    u = QUrl(url)
    return u.isLocalFile() and u.toLocalFile() == str(HOME_FILE)


def display_url(url: str) -> str:
    """Address bar mein kya dikhana hai (home aur blank page pe khali)."""
    return "" if (url == "about:blank" or is_home_url(url)) else url


def resolve_input(text: str) -> QUrl:
    text = text.strip()
    if text.startswith(("http://", "https://", "file://")):
        return QUrl(text)
    if " " in text or "." not in text:
        return QUrl(search_template().replace("{query}", text.replace(" ", "+")))
    return QUrl("https://" + text)


class WebView(QWebEngineView):
    url_changed = pyqtSignal(str)
    title_changed = pyqtSignal(str)
    icon_changed = pyqtSignal(QIcon)
    loading_changed = pyqtSignal(bool)

    def __init__(self, parent=None):
        super().__init__(parent)
        self.loading = False
        self.tab_factory = None  # MainWindow set karta hai (target=_blank / popups ke liye)

        self.urlChanged.connect(self._on_url_changed)
        self.titleChanged.connect(self.title_changed.emit)
        self.iconChanged.connect(self.icon_changed.emit)
        self.loadStarted.connect(self._on_load_started)
        self.loadFinished.connect(self._on_load_finished)

    def _on_url_changed(self, url: QUrl) -> None:
        self.apply_zoom()
        self.url_changed.emit(url.toString())

    def _on_load_started(self) -> None:
        self.loading = True
        self.loading_changed.emit(True)

    def _on_load_finished(self, ok: bool) -> None:
        self.loading = False
        self.apply_zoom()
        self.loading_changed.emit(False)

    def apply_zoom(self) -> None:
        if is_home_url(self.url().toString()):
            self.setZoomFactor(1.0)  # home page ka design zoom nahi hota
        else:
            self.setZoomFactor(settings.get("zoom") / 100)

    def navigate(self, text: str) -> None:
        if text.strip():
            self.load(resolve_input(text))

    def load_home(self) -> None:
        self.load(home_url())

    def load_blank(self) -> None:
        self.setHtml("<html><body style='margin:0;background:#0b1220'></body></html>")

    def createWindow(self, window_type):
        if self.tab_factory:
            return self.tab_factory()
        return None