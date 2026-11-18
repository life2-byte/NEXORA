import time
import json
from pathlib import Path
from urllib.parse import parse_qs, urlencode

from PyQt6 import sip
from PyQt6.QtCore import QTimer, QUrl, pyqtSignal
from PyQt6.QtGui import QIcon
from PyQt6.QtNetwork import QAuthenticator
from PyQt6.QtWebEngineCore import QWebEngineContextMenuRequest, QWebEnginePage, QWebEngineSettings
from PyQt6.QtWebEngineWidgets import QWebEngineView
from PyQt6.QtWidgets import QMenu
from frontend.core import favicons, internal_pages, passwords
from frontend.widgets.page_dialogs import ask_credentials
from frontend.core.web_profile import make_page_tools_script
from frontend.core.settings_manager import SEARCH_ENGINES, settings
from frontend.core.history import history
from frontend.core.profile import get_profile

HOME_FILE = Path(__file__).resolve().parents[1] / "assets" / "home" / "home.html"

WA = QWebEnginePage.WebAction
MEDIA = QWebEngineContextMenuRequest.MediaType

_CERT_ALLOWED: set = set()  # hosts jin ko user ne "Proceed anyway" kaha (sirf is session ke liye)
_HTTP_ALLOWED: set = set()  # http hosts jin ko user ne "Continue" kaha (sirf is session ke liye)


def _is_local_host(host: str) -> bool:
    """Ghar/office ke network ke addresses pe warning nahi aati."""
    host = host.lower()
    if not host or "." not in host or ":" in host:  # single label (router), IPv6 (::1)
        return True
    if host == "localhost" or host.endswith((".local", ".localhost", ".lan", ".home", ".internal")):
        return True
    parts = host.split(".")
    if len(parts) == 4 and all(p.isdigit() for p in parts):
        a, b = int(parts[0]), int(parts[1])
        return a in (10, 127) or (a == 192 and b == 168) or (a == 172 and 16 <= b <= 31) or (a == 169 and b == 254)
    return False


ZOOM_MIN, ZOOM_MAX = 50, 200


def search_template() -> str:
    return SEARCH_ENGINES.get(settings.get("search_engine"), SEARCH_ENGINES["DuckDuckGo"])


def home_url() -> QUrl:
    """Home page + settings URL query ke zariye (background, search engine, most visited)."""
    url = QUrl.fromLocalFile(str(HOME_FILE))
    mode = settings.get("bg_mode")
    bg_path = settings.get("bg_path")
    if mode in ("image", "video") and not (bg_path and Path(bg_path).is_file()):
        mode = "default"  # file gum ho gayi: default moon wallpaper
    params = {
        "theme": "dark",
        "mode": mode,
        "dim": str(settings.get("bg_dim")),
        "anim": "1" if settings.get("bg_animated") else "0",
        "engine": search_template(),
    }
    if mode in ("image", "video"):
        params["src"] = QUrl.fromLocalFile(bg_path).toString()
    if settings.get("show_most_visited") and settings.get("save_history"):
        try:
            tops = history.top_sites(8)
        except Exception:
            tops = []
        if tops:
            params["top"] = json.dumps([{"h": t["host"], "u": t["url"], "i": favicons.url_for(t["host"])} for t in tops])
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
    if text.startswith(("http://", "https://", "file://", "view-source:", "about:")):
        return QUrl(text)
    if " " in text or "." not in text:
        return QUrl(search_template().replace("{query}", text.replace(" ", "+")))
    return QUrl("https://" + text)

class BrowserPage(QWebEnginePage):
    """Websites ke console messages terminal mein na aayein (DevTools mein dikhte rehte hain).
    Permission requests (camera, location...) signal ke zariye UI tak jati hain."""

    permission_asked = pyqtSignal(object)
    fullscreen_requested = pyqtSignal(bool)
    print_requested = pyqtSignal()
    find_result = pyqtSignal(int, int)  # active match, total matches

    def __init__(self, profile, parent=None):
        super().__init__(profile, parent)
        if hasattr(self, "permissionRequested"):  # Qt 6.8+
            self.permissionRequested.connect(self.permission_asked.emit)

        self.settings().setAttribute(QWebEngineSettings.WebAttribute.FullScreenSupportEnabled, True)
        self.passwords = passwords.PageBridge(self)
        self._upgrades: dict = {}  # https url -> asli http url (HTTPS-first)
        self.loadFinished.connect(self._on_load_finished)
        self.fullScreenRequested.connect(self._on_fullscreen)
        self.certificateError.connect(self._on_certificate_error)
        self.authenticationRequired.connect(self._on_authentication)
        self.printRequested.connect(self.print_requested.emit)  # website ka window.print()
        self.findTextFinished.connect(
            lambda r: self.find_result.emit(r.activeMatch(), r.numberOfMatches())
        )

    def javaScriptConsoleMessage(self, level, message, line_number, source_id) -> None:
        self.passwords.handle(message)  # password manager ke apne messages; baqi sab chhupa diye jate hain

    def _dialog_parent(self):
        view = QWebEngineView.forPage(self)
        return view.window() if view is not None else None

    # ---------- fullscreen (video ka fullscreen button) ----------
    def _on_fullscreen(self, request) -> None:
        request.accept()
        self.fullscreen_requested.emit(request.toggleOn())

    # ---------- warning pages (http / certificate) ----------
    def acceptNavigationRequest(self, url, nav_type, is_main_frame) -> bool:
        if is_main_frame:
            if url.scheme() == internal_pages.SCHEME:
                return self._handle_internal(url)
            if url.scheme() == "http" and self._should_upgrade(url):
                https = QUrl(url)  # pehle HTTPS try karo; na chale to warning page
                https.setScheme("https")
                if https.port() == 80:
                    https.setPort(-1)
                self._upgrades[https.toString()] = url.toString()
                QTimer.singleShot(0, lambda u=https: self.load(u))
                return False
        return super().acceptNavigationRequest(url, nav_type, is_main_frame)

    def _should_upgrade(self, url) -> bool:
        return (
            bool(settings.get("https_first"))
            and url.port() in (-1, 80)
            and url.host() not in _HTTP_ALLOWED
            and not _is_local_host(url.host())
        )

    def _handle_internal(self, url) -> bool:
        host = url.host()
        if host == "warning":
            return True  # scheme handler page dikhata hai
        # back / proceed sirf tab chalte hain jab user ab warning page par ho (website in links se bypass nahi kara sakti)
        if self.url().scheme() == internal_pages.SCHEME:
            q = parse_qs(url.query(url.ComponentFormattingOption.FullyEncoded))
            kind = (q.get("kind") or [""])[0]
            target = (q.get("url") or [""])[0]
            if host == "back":
                QTimer.singleShot(0, self._go_back_or_home)
            elif host == "proceed" and target.startswith(("http://", "https://")):
                if kind == "http":
                    _HTTP_ALLOWED.add(QUrl(target).host())
                elif kind == "cert":
                    _CERT_ALLOWED.add(QUrl(target).host())
                QTimer.singleShot(0, lambda: self.load(QUrl(target)))
        return False

    def _go_back_or_home(self) -> None:
        if self.history().canGoBack():
            self.triggerAction(WA.Back)
        else:
            self.load(home_url())

    def _show_warning(self, kind: str, url: str, detail: str = "") -> None:
        QTimer.singleShot(0, lambda: self.load(QUrl(internal_pages.warning_url(kind, url, detail))))

    def _on_load_finished(self, ok: bool) -> None:
        http_url = self._upgrades.pop(self.requestedUrl().toString(), None)
        if http_url and not ok:  # HTTPS chali hi nahi: site shayad sirf http pe hai
            self._show_warning("http", http_url)

    # ---------- https certificate galat ho ----------
    def _on_certificate_error(self, error) -> None:
        if not error.isMainFrame():
            error.rejectCertificate()
            return
        host = error.url().host()
        if error.isOverridable() and host in _CERT_ALLOWED:
            error.acceptCertificate()
            return
        self._upgrades.pop(error.url().toString(), None)  # HTTP warning nahi, certificate warning dikhao
        error.rejectCertificate()
        kind = "cert" if error.isOverridable() else "cert-fatal"
        self._show_warning(kind, error.url().toString(), error.description())

    # ---------- http login popup ----------
    def _on_authentication(self, url, authenticator) -> None:
        creds = ask_credentials(self._dialog_parent(), url.host(), authenticator.realm())
        if creds is None:
            sip.assign(authenticator, QAuthenticator())  # khali authenticator = cancel
        else:
            authenticator.setUser(creds[0])
            authenticator.setPassword(creds[1])


class WebView(QWebEngineView):
    url_changed = pyqtSignal(str)
    title_changed = pyqtSignal(str)
    icon_changed = pyqtSignal(QIcon)
    loading_changed = pyqtSignal(bool)

    # right-click menu se MainWindow ko request
    open_link_requested = pyqtSignal(str, bool)   # url, activate
    permission_requested = pyqtSignal(object)  # QWebEnginePermission
    search_selection_requested = pyqtSignal(str)
    view_source_requested = pyqtSignal()
    inspect_requested = pyqtSignal()
    fullscreen_changed = pyqtSignal(bool)
    print_requested = pyqtSignal()
    link_hovered = pyqtSignal(str)

    def __init__(self, parent=None, ai_enabled: bool = True):
        super().__init__(parent)
        self.setPage(BrowserPage(get_profile(), self))  # permanent profile wala page
        self.page().permission_asked.connect(self.permission_requested.emit)
        self.page().fullscreen_requested.connect(self.fullscreen_changed.emit)
        self.page().print_requested.connect(self.print_requested.emit)
        self.page().linkHovered.connect(self.link_hovered.emit)
        self.ai_enabled = ai_enabled
        self.loading = False
        self.last_load_ok = True
        self.load_started_ms = 0.0
        self.tab_id = ""
        self.devtools_window = None
        self.tab_factory = None  # MainWindow set karta hai (target=_blank / popups ke liye)

        if ai_enabled:
            # per-page: AI wale tabs ko hi agent ki script milti hai
            self.page().scripts().insert(make_page_tools_script())

        settings.changed.connect(self._on_zoom_setting)
        self.iconChanged.connect(self._cache_favicon)
        self.urlChanged.connect(self._on_url_changed)
        self.titleChanged.connect(self.title_changed.emit)
        self.iconChanged.connect(self.icon_changed.emit)
        self.loadStarted.connect(self._on_load_started)
        self.loadFinished.connect(self._on_load_finished)

    def _on_url_changed(self, url: QUrl) -> None:
        self.apply_zoom()
        self.url_changed.emit(url.toString())

    def _on_load_started(self) -> None:
        self.load_started_ms = time.time() * 1000   # agent: kaunsa document is load ke baad bana, ye pehchanne ke liye
        self.loading = True
        self.loading_changed.emit(True)

    def _on_load_finished(self, ok: bool) -> None:
        self.loading = False
        self.last_load_ok = ok
        self.apply_zoom()
        self.loading_changed.emit(False)

    def _cache_favicon(self, icon) -> None:
        host = self.site_key()
        if host and settings.get("show_most_visited") and settings.get("save_history"):
            favicons.save(host, icon)

    # ---------- zoom (har site ka apna, warna default) ----------
    def _on_zoom_setting(self, key: str, _value) -> None:
        if key in ("zoom", "site_zoom"):
            self.apply_zoom()

    def site_key(self) -> str:
        url = self.url()
        return url.host().lower() if url.scheme() in ("http", "https") else ""

    def zoom_percent(self) -> int:
        site = self.site_key()
        saved = (settings.get("site_zoom") or {}).get(site) if site else None
        return int(saved or settings.get("zoom"))

    def apply_zoom(self) -> None:
        if is_home_url(self.url().toString()):
            self.setZoomFactor(1.0)  # home page ka design zoom nahi hota
        else:
            self.setZoomFactor(self.zoom_percent() / 100)

    def change_site_zoom(self, delta: int) -> int:
        """Is site ka zoom badlo aur yaad rakho. Naya percent wapas deta hai."""
        percent = max(ZOOM_MIN, min(ZOOM_MAX, self.zoom_percent() + delta))
        site = self.site_key()
        if not site:
            settings.set("zoom", percent)
            return percent
        saved = dict(settings.get("site_zoom") or {})
        if percent == int(settings.get("zoom")):
            saved.pop(site, None)  # default ke barabar: entry ki zarurat nahi
        else:
            saved[site] = percent
        settings.set("site_zoom", saved)
        return percent

    def reset_site_zoom(self) -> int:
        site = self.site_key()
        if site:
            saved = dict(settings.get("site_zoom") or {})
            saved.pop(site, None)
            settings.set("site_zoom", saved)
        else:
            settings.set("zoom", 100)
        return self.zoom_percent()

    def navigate(self, text: str) -> None:
        if text.strip():
            self.load(resolve_input(text))

    def load_home(self) -> None:
        self.load(home_url())

    def load_blank(self) -> None:
        self.setHtml("<html><body style='margin:0;background:#0b1220'></body></html>")

    # ---------- find in page ----------
    def find(self, text: str, forward: bool = True, case: bool = False) -> None:
        flags = QWebEnginePage.FindFlag(0)
        if not forward:
            flags |= QWebEnginePage.FindFlag.FindBackward
        if case:
            flags |= QWebEnginePage.FindFlag.FindCaseSensitively
        self.page().findText(text, flags)

    def clear_find(self) -> None:
        self.page().findText("")

    def createWindow(self, window_type):
        if self.tab_factory:
            return self.tab_factory()
        return None

    # ---------- right-click menu ----------
    def contextMenuEvent(self, event) -> None:
        req = self.lastContextMenuRequest()
        if req is None:
            return

        page = self.page()
        menu = QMenu(self)

        def add(text: str, slot, enabled: bool = True) -> None:
            action = menu.addAction(text)
            action.setEnabled(enabled)
            action.triggered.connect(lambda _checked=False: slot())

        def web(text: str, web_action, enabled: bool = True) -> None:
            add(text, lambda: page.triggerAction(web_action), enabled)

        link = req.linkUrl()
        has_link = link.isValid() and not link.isEmpty()
        selected = (req.selectedText() or "").strip()
        is_image = req.mediaType() == MEDIA.MediaTypeImage and req.mediaUrl().isValid()
        editable = req.isContentEditable()

        if has_link:
            add("Open link in new tab", lambda: self.open_link_requested.emit(link.toString(), False))
            web("Copy link address", WA.CopyLinkToClipboard)
            web("Save link as...", WA.DownloadLinkToDisk)
            menu.addSeparator()

        if is_image:
            add("Open image in new tab", lambda: self.open_link_requested.emit(req.mediaUrl().toString(), False))
            web("Copy image", WA.CopyImageToClipboard)
            web("Copy image address", WA.CopyImageUrlToClipboard)
            web("Save image as...", WA.DownloadImageToDisk)
            menu.addSeparator()

        word = req.misspelledWord() if editable else ""
        if word:
            for suggestion in list(req.spellCheckerSuggestions())[:5]:
                add(suggestion, lambda sug=suggestion: page.replaceMisspelledWord(sug))
            menu.addSeparator()

        if editable:
            web("Undo", WA.Undo)
            web("Redo", WA.Redo)
            menu.addSeparator()
            web("Cut", WA.Cut, bool(selected))
            web("Copy", WA.Copy, bool(selected))
            web("Paste", WA.Paste)
            web("Select all", WA.SelectAll)
        elif selected:
            web("Copy", WA.Copy)
            short = selected if len(selected) <= 28 else selected[:25] + "..."
            add(f'Search for "{short}"', lambda: self.search_selection_requested.emit(selected))
            web("Select all", WA.SelectAll)
        elif not has_link and not is_image:
            history = page.history()
            web("Back", WA.Back, history.canGoBack())
            web("Forward", WA.Forward, history.canGoForward())
            web("Reload", WA.Reload)
            menu.addSeparator()
            web("Save page as...", WA.SavePage)
            add("Print...", self.print_requested.emit)
            add("View page source", self.view_source_requested.emit)
            web("Select all", WA.SelectAll)

        menu.addSeparator()
        add("Inspect", self.inspect_requested.emit)
        menu.exec(event.globalPos())