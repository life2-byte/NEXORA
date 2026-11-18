import html
from urllib.parse import parse_qs, urlparse

from PyQt6.QtCore import QByteArray, QTimer, QUrl
from PyQt6.QtGui import QDesktopServices, QIcon, QKeySequence, QShortcut
from PyQt6.QtWebEngineCore import QWebEnginePage
from PyQt6.QtWidgets import (
    QHBoxLayout,
    QLabel,
    QMainWindow,
    QMessageBox,
    QStackedWidget,
    QVBoxLayout,
    QWidget,
)
from frontend.core.agent_controller import AgentController
from frontend.core import ai_privacy
from frontend.core.bookmarks import bookmarks
from frontend.core.browser_tools import QtBrowserTools
from frontend.core.dev_console import DevConsole
from frontend.core.downloads import get_download_manager
from frontend.core.history import history
from frontend.core.settings_manager import settings
from frontend.core.web_profile import apply_web_settings
from frontend.pages.agents_page import AgentsPage
from frontend.pages.bookmarks_page import BookmarksPage
from frontend.pages.downloads_page import DownloadsPage
from frontend.pages.history_page import HistoryPage
from frontend.pages.memory_page import MemoryPage
from frontend.pages.settings_page import SettingsPage
from frontend.pages.tasks_page import TasksPage
from frontend.widgets.address_bar import AddressBar
from frontend.widgets.agent_strip import AgentStrip
from frontend.widgets.devtools_window import DevToolsWindow
from frontend.widgets.downloads_popup import DownloadsPopup
from frontend.widgets.nav_bar import NavBar
from frontend.widgets.permission_bar import describe
from frontend.widgets.sidebar import COLLAPSED_W, Sidebar
from frontend.widgets.tab_bar import TabStrip
from frontend.widgets.tab_stack import TabStack
from frontend.widgets.toolbar_actions import ToolbarActions
from frontend.widgets.web_view import WebView, display_url, is_home_url
from frontend.pages.cookies_page import CookiesPage
from frontend.core.browser_features import BrowserFeatures
from frontend.widgets.find_bar import FindBar
from frontend.pages.passwords_page import PasswordsPage
from frontend.pages.scripts_page import ScriptsPage

APP_NAME = "Nexora"

HOME_KEYS = {"bg_mode", "bg_path", "bg_dim", "bg_animated", "search_engine", "show_most_visited"}
WEB_KEYS = {
    "font_size",
    "smooth_scroll",
    "force_dark_web",
    "block_popups",
    "block_third_party_cookies",
    "clear_cookies_on_exit",
    "cache_limit_mb",
    "cookie_policy",
    "cookie_block_sites",
    "cookie_allow_sites",
    "clear_site_data_on_exit",
}
ZOOM_MIN, ZOOM_MAX, ZOOM_STEP = 50, 200, 10
MAX_CLOSED_TABS = 20

DEMO_STEPS = [
    "Reading current page",
    "Planning steps",
    "Searching the web",
    "Extracting data",
    "Building result",
]

RESULT_HTML = """<!DOCTYPE html>
<html><head><meta charset="UTF-8"><title>AI Result</title>
<style>
  body {{ margin:0; background:#0b1220; color:#e6eaf2;
         font-family:"Segoe UI","Inter","Ubuntu",sans-serif; }}
  .wrap {{ max-width:760px; margin:60px auto; padding:0 24px; }}
  .tag {{ color:#38bdf8; font-size:13px; letter-spacing:1px; text-transform:uppercase; }}
  h1 {{ font-size:28px; margin:8px 0 24px; }}
  .card {{ background:#111a2b; border:1px solid #1f2d45; border-radius:12px;
          padding:18px 20px; color:#9fb0cc; line-height:1.6; }}
</style></head>
<body><div class="wrap">
  <div class="tag">AI Result</div>
  <h1>{task}</h1>
  <div class="card">Demo mode: backend abhi judna baaki hai. Asli agent aane pe
  yahan structured result (tables, links, JSON) aayega, ek normal webpage ki tarah.</div>
</div></body></html>"""


class _Root(QWidget):
    """Central widget. Sidebar iske upar float karti hai, isliye height yahan sync hoti hai."""

    def __init__(self):
        super().__init__()
        self.setObjectName("Root")
        self.overlay = None

    def resizeEvent(self, event) -> None:
        super().resizeEvent(event)
        if self.overlay is not None:
            self.overlay.move(0, 0)
            self.overlay.setFixedHeight(self.height())


class MainWindow(QMainWindow):
    _instances: list = []  # khuli windows (references zinda rakhne ke liye)

    def __init__(self, ai_enabled: bool = True):
        super().__init__()
        self.ai_enabled = ai_enabled
        self._is_first = not MainWindow._instances
        MainWindow._instances.append(self)
        self._tab_counter = 0
        self._closed_tabs: list = []

        self._set_page_title("")
        self.resize(1280, 800)
        if self._is_first:
            self._restore_geometry()

        self.nav_bar = NavBar()
        self.address_bar = AddressBar(ai_enabled=ai_enabled)
        self.toolbar_actions = ToolbarActions()
        self.agent_strip = AgentStrip()
        self.tab_strip = TabStrip()
        self.stack = TabStack()  # sirf web views (tabs)

        self.no_ai_badge = QLabel("No AI")
        self.no_ai_badge.setObjectName("NoAiBadge")

        self._agent_timer = QTimer(self)
        self._agent_timer.timeout.connect(self._agent_tick)
        self._agent_task = ""
        self._agent_step = 0

        # settings change pe home tabs ko ek hi baar reload karne ke liye (slider drag ke waqt)
        self._home_timer = QTimer(self)
        self._home_timer.setSingleShot(True)
        self._home_timer.setInterval(300)
        self._home_timer.timeout.connect(self._reload_home_tabs)

        # downloads (poori app mein ek shared manager)
        self.downloads = get_download_manager()
        self.downloads.message.connect(self._on_download_message)
        self.downloads.started.connect(self._on_download_started)
        self.downloads.activity.connect(self._on_download_activity)

        self.dev_console = DevConsole(self)
        self.tools = QtBrowserTools(self) if ai_enabled else None

        # ---------- pages ----------
        # stack = browser (Home/Browse dono yahi dikhate hain), baqi alag screens
        self.pages = QStackedWidget()
        self.pages.addWidget(self.stack)
        self.page_map = {
            "history": HistoryPage(),
            "agents": AgentsPage(),
            "tasks": TasksPage(),
            "memory": MemoryPage(),
            "downloads": DownloadsPage(),
            "bookmarks": BookmarksPage(),
            "cookies": CookiesPage(),
            "settings": SettingsPage(),
            "passwords": PasswordsPage(),
            "scripts": ScriptsPage(),
        }
        for page in self.page_map.values():
            self.pages.addWidget(page)

        # ---------- layout ----------
        root = _Root()
        root_layout = QHBoxLayout(root)
        root_layout.setContentsMargins(0, 0, 0, 0)
        root_layout.setSpacing(0)

        # sidebar ki jagah reserve (sidebar khud upar float karti hai)
        spacer = QWidget()
        spacer.setFixedWidth(COLLAPSED_W)

        content = QWidget()
        content_layout = QVBoxLayout(content)
        content_layout.setContentsMargins(0, 0, 0, 0)
        content_layout.setSpacing(0)

        top_bar = QWidget()
        top_bar.setObjectName("TopBar")
        top_layout = QHBoxLayout(top_bar)
        top_layout.setContentsMargins(10, 6, 12, 6)
        top_layout.setSpacing(8)
        top_layout.addWidget(self.nav_bar)
        top_layout.addWidget(self.address_bar, 1)
        top_layout.addWidget(self.no_ai_badge)
        top_layout.addWidget(self.toolbar_actions)

        content_layout.addWidget(self.tab_strip)
        content_layout.addWidget(top_bar)
        content_layout.addWidget(self.agent_strip)
        self.find_bar = FindBar()
        content_layout.addWidget(self.find_bar)
        content_layout.addWidget(self.pages, 1)

        root_layout.addWidget(spacer)
        root_layout.addWidget(content, 1)

        self.sidebar = Sidebar(root)
        root.overlay = self.sidebar
        self.sidebar.raise_()
        self.features = BrowserFeatures(
            self, self.find_bar, [self.tab_strip, top_bar, self.agent_strip, spacer, self.sidebar]
        )

        # downloads ka popup (toolbar ke download icon ke neeche float karta hai)
        self.downloads_popup = DownloadsPopup(root)
        self.downloads_popup.show_all_requested.connect(lambda: self._open_page("downloads"))

        self.setCentralWidget(root)
        self.agent = AgentController(self, root)
        self._update_ai_badge()

        self._connect_widgets()
        self._setup_shortcuts()
        self.features.install_shortcuts()
        if self._is_first:
            self._open_startup()
        else:
            self.add_tab()

    # ---------- helpers ----------
    @property
    def current_view(self):
        return self.stack.currentWidget()

    def _views(self) -> list:
        return [self.stack.widget(i) for i in range(self.stack.count())]

    @property
    def ai_active(self) -> bool:
        """Is window mein AI chal sakta hai? (window ka flag aur Settings ka master switch dono)"""
        return self.ai_enabled and bool(settings.get("ai_enabled"))

    def _update_ai_badge(self) -> None:
        if not self.ai_enabled:
            self.no_ai_badge.setText("No AI")
            self.no_ai_badge.setToolTip("AI is turned off in this window")
            self.no_ai_badge.setVisible(True)
        elif not settings.get("ai_enabled"):
            self.no_ai_badge.setText("AI off")
            self.no_ai_badge.setToolTip("AI is turned off in Settings")
            self.no_ai_badge.setVisible(True)
        else:
            self.no_ai_badge.setVisible(False)

    def _set_page_title(self, page_title: str) -> None:
        suffix = APP_NAME if self.ai_enabled else f"{APP_NAME} (No AI)"
        self.setWindowTitle(f"{page_title} - {suffix}" if page_title else suffix)

    # ---------- window ----------
    def _restore_geometry(self) -> None:
        data = settings.get("window_geometry")
        if settings.get("restore_geometry") and data:
            self.restoreGeometry(QByteArray.fromBase64(data.encode("ascii")))

    def closeEvent(self, event) -> None:
        if self._is_first and settings.get("restore_geometry"):
            encoded = bytes(self.saveGeometry().toBase64()).decode("ascii")
            settings.set("window_geometry", encoded)
        if len(MainWindow._instances) <= 1:  # aakhri window: session yaad rakho
            urls, active = self._session_snapshot()
            settings.set_many({"session_tabs": urls, "session_active": active})
        if self in MainWindow._instances:
            MainWindow._instances.remove(self)
        super().closeEvent(event)

    def _session_snapshot(self):
        urls, active = [], 0
        current = self.current_view
        for view in self._views():
            url = view.url().toString()
            if url.startswith(("http://", "https://")):
                if view is current:
                    active = len(urls)
                urls.append(url)
        return urls, active

    def open_new_window(self, ai_enabled: bool = True) -> "MainWindow":
        window = MainWindow(ai_enabled=ai_enabled)
        window.resize(self.size())
        window.move(self.x() + 36, self.y() + 36)
        window.show()
        return window

    def _open_startup(self) -> None:
        mode = settings.get("startup_mode")
        url = (settings.get("startup_url") or "").strip()

        if mode == "restore":
            urls = list(settings.get("session_tabs") or [])
            if urls:
                for saved in urls:
                    self.add_tab(url=saved, activate=False)
                active = int(settings.get("session_active") or 0)
                self.tab_strip.set_current(max(0, min(active, len(urls) - 1)))
                self._show_browser()
                return
            self.add_tab(mode="home")
        elif mode == "custom" and url:
            self.add_tab(url=url)
        elif mode == "blank":
            self.add_tab(mode="blank")
        else:
            self.add_tab(mode="home")

    # ---------- wiring ----------
    def _connect_widgets(self) -> None:
        self.nav_bar.back_clicked.connect(lambda: self.current_view.back())
        self.nav_bar.forward_clicked.connect(lambda: self.current_view.forward())
        self.nav_bar.reload_clicked.connect(lambda: self.current_view.reload())
        self.nav_bar.stop_clicked.connect(lambda: self.current_view.stop())

        self.address_bar.url_submitted.connect(self._on_url_submitted)
        self.address_bar.agent_submitted.connect(self._on_agent_task)
        self.agent_strip.stop_requested.connect(self._on_agent_stop)

        self.sidebar.item_selected.connect(self._on_rail_selected)
        self.sidebar.action_triggered.connect(self._on_sidebar_action)
        self.page_map["history"].open_url.connect(self._on_history_open)
        self.page_map["bookmarks"].open_url.connect(self._on_history_open)
        self.page_map["settings"].open_page.connect(self._open_page)
        bookmarks.changed.connect(self._refresh_star)

        self.toolbar_actions.downloads_clicked.connect(self._toggle_downloads_popup)
        self.toolbar_actions.settings_clicked.connect(lambda: self._open_page("settings"))
        self.toolbar_actions.bookmark_toggled.connect(self._on_bookmark_toggled)

        self.tab_strip.new_tab_requested.connect(lambda: self.add_tab())
        self.tab_strip.tab_changed.connect(self._on_tab_changed)
        self.tab_strip.tab_close_requested.connect(self.close_tab)
        self.tab_strip.tab_clicked.connect(lambda _: self._show_browser())

        settings.changed.connect(self._on_setting_changed)

    def _setup_shortcuts(self) -> None:
        def key(seq: str, fn) -> None:
            QShortcut(QKeySequence(seq), self, activated=fn)

        key("Ctrl+T", lambda: self.add_tab())
        key("Ctrl+W", lambda: self.close_tab(self.stack.currentIndex()))
        key("Ctrl+Shift+T", self.reopen_closed_tab)
        key("Ctrl+N", lambda: self.open_new_window(True))
        key("Ctrl+Shift+N", lambda: self.open_new_window(False))
        key("Ctrl+H", lambda: self._open_page("history"))
        key("Ctrl+J", lambda: self._open_page("downloads"))
        key("Ctrl+D", self.toolbar_actions.star_btn.toggle)
        key("Ctrl+L", self._focus_address_bar)
        key("Ctrl+=", lambda: self._change_zoom(ZOOM_STEP))
        key("Ctrl++", lambda: self._change_zoom(ZOOM_STEP))
        key("Ctrl+-", lambda: self._change_zoom(-ZOOM_STEP))
        key("Ctrl+0", lambda: self._reset_zoom())
        key("Ctrl+Shift+D", lambda: self._dev("read"))
        key("F12", self._toggle_devtools)
        key("Ctrl+Shift+I", self._toggle_devtools)
        key("Ctrl+U", self._view_source)
        key("Ctrl+Shift+O", lambda: self._open_external(self.current_view.url().toString()))

    def _focus_address_bar(self) -> None:
        self._show_browser()
        self.address_bar.setFocus()
        self.address_bar.selectAll()

    # ---------- developer tools ----------
    def _toggle_devtools(self) -> None:
        view = self.current_view
        if view is None:
            return
        win = getattr(view, "devtools_window", None)
        if win is None:
            win = DevToolsWindow(self, view)
            view.devtools_window = win
            win.show()
        elif win.isVisible():
            win.hide()
        else:
            win.show()
            win.raise_()

    def _view_source(self, view=None) -> None:
        view = view or self.current_view
        if view is None:
            return
        url = view.url().toString()
        if url.startswith(("http://", "https://")):
            self.add_tab(url=f"view-source:{url}")

    def _inspect(self, view) -> None:
        win = getattr(view, "devtools_window", None)
        if win is None:
            win = DevToolsWindow(self, view)
            view.devtools_window = win
        win.show()
        win.raise_()
        view.triggerPageAction(QWebEnginePage.WebAction.InspectElement)

    def _dev(self, command: str) -> None:
        if not self.ai_active:
            self.statusBar().showMessage("Agent tools are off (No-AI window ya Settings mein AI band)", 4000)
            return
        self.dev_console.run(command)

    # ---------- default browser / Google sign-in ----------
    def _open_external(self, url: str) -> None:
        if url.startswith(("http://", "https://")):
            QDesktopServices.openUrl(QUrl(url))

    def _offer_system_browser(self, rejected_url: str) -> None:
        """Google embedded browser mein sign-in rok de to default browser mein kholne ka option."""
        if getattr(self, "_google_prompted", "") == rejected_url:
            return
        self._google_prompted = rejected_url
        query = parse_qs(urlparse(rejected_url).query)
        target = query.get("continue", ["https://accounts.google.com"])[0]
        answer = QMessageBox.question(
            self,
            "Google sign-in",
            "Google embedded browsers mein sign-in nahi karne deta (unki security policy).\n\n"
            "Ye page apne default browser mein kholun?",
        )
        if answer == QMessageBox.StandardButton.Yes:
            self._open_external(target)

    # ---------- site permissions (camera, mic, location...) ----------
    def _on_permission(self, permission) -> None:
        """Jawab isi slot ke ANDAR dena zaroori hai (isolated test mein yahi chala), kyunke
        permission object slot ke baad invalid ho sakta hai."""
        text = describe(permission)
        print(f"[permission] asked: {text}")

        box = QMessageBox(self)
        box.setWindowTitle("Site permission")
        box.setText(f"{text}?")
        allow = box.addButton("Allow", QMessageBox.ButtonRole.AcceptRole)
        block = box.addButton("Block", QMessageBox.ButtonRole.DestructiveRole)
        box.addButton("Not now", QMessageBox.ButtonRole.RejectRole)
        box.exec()

        clicked = box.clickedButton()
        if clicked is allow:
            print("[permission] allowed")
            permission.grant()
        elif clicked is block:
            print("[permission] blocked")
            permission.deny()
        else:
            print("[permission] not answered")

    # ---------- settings ----------
    def _on_setting_changed(self, key: str, value) -> None:
        if key in HOME_KEYS:
            self._home_timer.start()
        if key == "zoom":
            for view in self._views():
                view.apply_zoom()
        if key in WEB_KEYS:
            apply_web_settings()
        if key == "ai_strip" and not value:
            self.agent_strip.hide()
        if key == "ai_enabled":
            self._update_ai_badge()

    def _reload_home_tabs(self) -> None:
        for view in self._views():
            if is_home_url(view.url().toString()):
                view.load_home()

    def _change_zoom(self, delta: int) -> None:
        view = self.current_view
        if view is None:
            return
        percent = view.change_site_zoom(delta)
        host = view.site_key()
        self.statusBar().showMessage(f"Zoom {percent}%" + (f" ({host})" if host else ""), 2000)

    def _reset_zoom(self) -> None:
        view = self.current_view
        if view is not None:
            percent = view.reset_site_zoom()
            self.statusBar().showMessage(f"Zoom {percent}%", 2000)

    # ---------- downloads ----------
    def _on_download_message(self, message: str) -> None:
        self.statusBar().showMessage(message, 6000)

    def _on_download_activity(self) -> None:
        """Naya download ya khatam: toolbar ke neeche popup dikhao (sirf active window mein)."""
        if self.isActiveWindow() and self.isVisible():
            self.downloads_popup.show_under(self.toolbar_actions.downloads_btn)

    def _toggle_downloads_popup(self) -> None:
        self.downloads_popup.toggle_under(self.toolbar_actions.downloads_btn)

    def _on_download_started(self, page) -> None:
        """Download kisi naye (khali) tab se shuru hua to wo tab band kar do (Chrome jesa)."""
        if page is None:
            return
        for view in self._views():
            if view.page() is page:
                if self.stack.count() > 1 and self._is_blank_view(view):
                    QTimer.singleShot(400, lambda v=view: self._close_if_still_blank(v))
                return

    @staticmethod
    def _is_blank_view(view) -> bool:
        try:
            return view.url().toString() in ("", "about:blank") and view.title() in ("", "about:blank")
        except RuntimeError:  # tab pehle hi delete ho chuka
            return False

    def _close_if_still_blank(self, view) -> None:
        try:
            index = self.stack.indexOf(view)
            if index >= 0 and self.stack.count() > 1 and self._is_blank_view(view):
                self.close_tab(index)
        except RuntimeError:
            pass

    # ---------- page switching ----------
    def _show_browser(self) -> None:
        self.pages.setCurrentWidget(self.stack)
        self._sync_rail()

    def _open_page(self, name: str) -> None:
        page = self.page_map.get(name)
        if page is None:
            return
        self.downloads_popup.hide()
        if name in ("history", "bookmarks"):
            page.refresh()
        self.pages.setCurrentWidget(page)
        self.sidebar.select(name)

    def _sync_rail(self) -> None:
        """Browser dikh raha ho to sidebar mein Home ya Browse highlight karo."""
        if self.pages.currentWidget() is not self.stack or self.current_view is None:
            return
        url = self.current_view.url().toString()
        self.sidebar.select("home" if is_home_url(url) else "browse")

    def _on_url_submitted(self, text: str) -> None:
        if text.strip().startswith("!"):
            self._restore_address()
            self._dev(text.strip()[1:])
            return
        self._show_browser()
        self.current_view.navigate(text)

    def _on_rail_selected(self, name: str) -> None:
        if name == "browse":
            self._show_browser()
            return

        if name != "home":
            self._open_page(name)
            return

        # Home: koi tab pehle se home pe ho to usi pe jao, warna naya home tab.
        self.pages.setCurrentWidget(self.stack)
        if not is_home_url(self.current_view.url().toString()):
            for i, view in enumerate(self._views()):
                if is_home_url(view.url().toString()):
                    self.tab_strip.set_current(i)
                    break
            else:
                self.add_tab(mode="home")
        self._sync_rail()

    def _on_sidebar_action(self, key: str) -> None:
        if key == "new_tab":
            self.add_tab()
        elif key == "new_window":
            self.open_new_window(True)
        elif key == "new_window_noai":
            self.open_new_window(False)

    def _on_history_open(self, url: str) -> None:
        self._show_browser()
        self.current_view.navigate(url)

    # ---------- bookmarks ----------
    def _on_bookmark_toggled(self, checked: bool) -> None:
        view = self.current_view
        url = view.url().toString() if view is not None else ""
        if not url.startswith(("http://", "https://")):
            self.statusBar().showMessage("Sirf websites ko bookmark kiya ja sakta hai", 3000)
            self.toolbar_actions.set_bookmarked(False)
            return
        if checked:
            bookmarks.add(url, view.title() or url)
            self.statusBar().showMessage("Bookmark saved", 2500)
        else:
            bookmarks.remove(url)
            self.statusBar().showMessage("Bookmark removed", 2500)

    def _refresh_star(self) -> None:
        """Current page bookmarked ho to star bhara dikhao."""
        view = self.current_view
        if view is None:
            return
        url = view.url().toString()
        marked = url.startswith(("http://", "https://")) and bookmarks.is_bookmarked(url)
        self.toolbar_actions.set_bookmarked(marked)

    # ---------- AI agent (demo, backend baad mein) ----------
    def _on_agent_task(self, task: str) -> None:
        if not self.ai_active:
            return
        self._restore_address()
        self.agent.start(task)

    def _on_agent_stop(self) -> None:
        self.agent.stop()

    def _agent_tick(self) -> None:
        self._agent_step += 1
        if self._agent_step < len(DEMO_STEPS):
            self.agent_strip.set_step(DEMO_STEPS[self._agent_step])
            return
        self._agent_timer.stop()
        self.agent_strip.finish("Done, result opened in a new tab")
        self._open_agent_result(self._agent_task)

    def _open_agent_result(self, task: str) -> None:
        view = self.add_tab(blank=True)
        view.setHtml(RESULT_HTML.format(task=html.escape(task)))

    def _restore_address(self) -> None:
        self.address_bar.setText(display_url(self.current_view.url().toString()))
        self.address_bar.clearFocus()

    # ---------- tabs ----------
    def add_tab(
        self,
        url: str | None = None,
        blank: bool = False,
        mode: str | None = None,
        activate: bool = True,
    ) -> WebView:
        """blank=True: kuch load nahi hota (popup / agent ke liye).
        mode: 'home' ya 'blank'; None to settings ka 'New tab opens' use hota hai.
        activate=False: tab background mein banta hai, user ka screen nahi badalta."""
        view = WebView(ai_enabled=self.ai_enabled)
        self._tab_counter += 1
        view.tab_id = f"t{self._tab_counter}"
        view.tab_factory = lambda: self.add_tab(blank=True)
        if not activate:
            view.page().setAudioMuted(True)  # background tab ki awaaz band

        # site permission requests (camera, mic, location...)
        if hasattr(view.page(), "permissionRequested"):  # Qt 6.8+
            view.page().permissionRequested.connect(self._on_permission)

        # right-click menu ki requests
        view.open_link_requested.connect(lambda url, act: self.add_tab(url=url, activate=act))
        view.search_selection_requested.connect(lambda text: self.add_tab(url=text))
        view.view_source_requested.connect(lambda v=view: self._view_source(v))
        view.inspect_requested.connect(lambda v=view: self._inspect(v))
        self.features.attach_view(view)
        if hasattr(view, "open_external_requested"):
            view.open_external_requested.connect(self._open_external)

        view.url_changed.connect(lambda u, v=view: self._on_view_url(v, u))
        view.title_changed.connect(lambda t, v=view: self._on_view_title(v, t))
        view.icon_changed.connect(lambda i, v=view: self._on_view_icon(v, i))
        view.loading_changed.connect(lambda l, v=view: self._on_view_loading(v, l))

        self.stack.addWidget(view)
        index = self.tab_strip.add_tab("New Tab")

        if not blank:
            if url:
                view.navigate(url)
            else:
                kind = mode or settings.get("newtab_mode")
                if kind == "blank":
                    view.load_blank()
                else:
                    view.load_home()

        if activate:
            self.tab_strip.set_current(index)
            self._show_browser()
        return view

    def close_tab(self, index: int) -> None:
        if index < 0 or index >= self.stack.count():
            return

        if self.stack.count() == 1:
            # extra window ka aakhri tab band ho to window band; pehli window mein naya tab
            if not self._is_first and len(MainWindow._instances) > 1:
                self.close()
                return
            self.add_tab()

        view = self.stack.widget(index)

        url = view.url().toString()
        if url.startswith(("http://", "https://")):  # Ctrl+Shift+T ke liye yaad rakho
            self._closed_tabs.append(url)
            del self._closed_tabs[:-MAX_CLOSED_TABS]

        win = getattr(view, "devtools_window", None)
        if win is not None:
            win.shutdown()

        self.stack.removeWidget(view)
        self.tab_strip.remove_tab(index)
        view.deleteLater()

    def reopen_closed_tab(self) -> None:
        if not self._closed_tabs:
            self.statusBar().showMessage("Koi band kiya hua tab nahi", 2500)
            return
        self.add_tab(url=self._closed_tabs.pop())

    # ---------- tab ids (agent tools ke liye) ----------
    def view_by_id(self, tab_id):
        """tab_id None/khali ho to user wala (current) tab."""
        if not tab_id:
            return self.current_view
        for view in self._views():
            if getattr(view, "tab_id", None) == tab_id:
                return view
        return None

    def tab_infos(self) -> list:
        active = self.current_view
        infos = []
        for view in self._views():
            url = view.url().toString()
            if is_home_url(url):
                shown = "(home page)"
            else:
                shown = display_url(url) or "(blank)"
            infos.append(
                {
                    "id": view.tab_id,
                    "title": view.title() or "New Tab",
                    "url": shown,
                    "raw_url": url,
                    "active": view is active,
                    "loading": view.loading,
                }
            )
        return infos

    def open_tab(self, url: str = "", activate: bool = False) -> WebView:
        """Khali tab banata hai; load karna caller ka kaam (taake wo load ka intezar kar sake)."""
        view = self.add_tab(blank=True, activate=activate)
        if not url:
            view.load_blank()
        return view

    def activate_tab(self, tab_id: str) -> bool:
        view = self.view_by_id(tab_id)
        if view is None:
            return False
        self.tab_strip.set_current(self.stack.indexOf(view))
        self._show_browser()
        return True

    def close_tab_by_id(self, tab_id: str) -> bool:
        if not tab_id:
            return False
        view = self.view_by_id(tab_id)
        if view is None:
            return False
        self.close_tab(self.stack.indexOf(view))
        return True

    # ---------- tab / view events ----------
    def _on_tab_changed(self, index: int) -> None:
        if index < 0 or index >= self.stack.count():
            return
        self.stack.setCurrentIndex(index)
        view = self.current_view
        view.page().setAudioMuted(False)  # jab user dekhe to awaaz chalne do

        url = view.url().toString()
        self.address_bar.setText(display_url(url))
        self.address_bar.setCursorPosition(0)
        self.address_bar.set_security(url)
        self.nav_bar.set_loading(view.loading)
        self._refresh_star()
        self._set_page_title(view.title() or "New Tab")
        self._sync_rail()
        self.features.on_tab_changed()

    def _on_view_url(self, view: WebView, url: str) -> None:
        if view is self.current_view:
            self.address_bar.set_url(display_url(url))
            self.address_bar.set_security(url)
            self._refresh_star()
            self._sync_rail()
        if "accounts.google.com" in url and "signin/rejected" in url:
            QTimer.singleShot(0, lambda u=url: self._offer_system_browser(u))

    def _on_view_title(self, view: WebView, title: str) -> None:
        index = self.stack.indexOf(view)
        self.tab_strip.set_title(index, title or "New Tab")
        if view is self.current_view:
            self._set_page_title(title or "New Tab")
        if settings.get("save_history"):
            url = view.url().toString()
            if url.startswith(("http://", "https://")):
                history.update_title(url, title)

    def _on_view_icon(self, view: WebView, icon: QIcon) -> None:
        self.tab_strip.set_icon(self.stack.indexOf(view), icon)

    def _on_view_loading(self, view: WebView, loading: bool) -> None:
        if view is self.current_view:
            self.nav_bar.set_loading(loading)
            if not loading:
                self.address_bar.set_security(view.url().toString())
        if not loading and view.last_load_ok:
            self._record_visit(view)

    def _record_visit(self, view: WebView) -> None:
        if not settings.get("save_history"):
            return
        url = view.url().toString()
        if url.startswith(("http://", "https://")):
            history.add_visit(url, view.title())