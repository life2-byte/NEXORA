import html

from PyQt6.QtCore import QByteArray, QTimer
from PyQt6.QtGui import QIcon, QKeySequence, QShortcut
from PyQt6.QtWidgets import (
    QHBoxLayout,
    QMainWindow,
    QStackedWidget,
    QVBoxLayout,
    QWidget,
)

from frontend.core.downloads import DownloadManager
from frontend.core.settings_manager import settings
from frontend.core.web_profile import apply_web_settings
from frontend.pages.agents_page import AgentsPage
from frontend.pages.bookmarks_page import BookmarksPage
from frontend.pages.downloads_page import DownloadsPage
from frontend.pages.memory_page import MemoryPage
from frontend.pages.settings_page import SettingsPage
from frontend.pages.tasks_page import TasksPage
from frontend.widgets.address_bar import AddressBar
from frontend.widgets.agent_strip import AgentStrip
from frontend.widgets.nav_bar import NavBar
from frontend.widgets.sidebar import COLLAPSED_W, Sidebar
from frontend.widgets.tab_bar import TabStrip
from frontend.widgets.toolbar_actions import ToolbarActions
from frontend.widgets.web_view import WebView, display_url, is_home_url

HOME_KEYS = {"bg_mode", "bg_path", "bg_dim", "bg_animated", "search_engine"}
WEB_KEYS = {
    "font_size",
    "smooth_scroll",
    "force_dark_web",
    "block_popups",
    "block_third_party_cookies",
    "clear_cookies_on_exit",
}
ZOOM_MIN, ZOOM_MAX, ZOOM_STEP = 50, 200, 10

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
    def __init__(self):
        super().__init__()
        self.setWindowTitle("Agentic Browser")
        self.resize(1280, 800)
        self._restore_geometry()

        self.nav_bar = NavBar()
        self.address_bar = AddressBar()
        self.toolbar_actions = ToolbarActions()
        self.agent_strip = AgentStrip()
        self.tab_strip = TabStrip()
        self.stack = QStackedWidget()  # sirf web views (tabs)

        self._agent_timer = QTimer(self)
        self._agent_timer.timeout.connect(self._agent_tick)
        self._agent_task = ""
        self._agent_step = 0

        # settings change pe home tabs ko ek hi baar reload karne ke liye (slider drag ke waqt)
        self._home_timer = QTimer(self)
        self._home_timer.setSingleShot(True)
        self._home_timer.setInterval(300)
        self._home_timer.timeout.connect(self._reload_home_tabs)

        # downloads
        self.downloads = DownloadManager(self)
        self.downloads.message.connect(lambda msg: self.statusBar().showMessage(msg, 6000))

        # ---------- pages ----------
        # stack = browser (Home/Browse dono yahi dikhate hain), baqi alag screens
        self.pages = QStackedWidget()
        self.pages.addWidget(self.stack)
        self.page_map = {
            "agents": AgentsPage(),
            "tasks": TasksPage(),
            "memory": MemoryPage(),
            "downloads": DownloadsPage(),
            "bookmarks": BookmarksPage(),
            "settings": SettingsPage(),
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
        top_layout.addWidget(self.toolbar_actions)

        content_layout.addWidget(self.tab_strip)
        content_layout.addWidget(top_bar)
        content_layout.addWidget(self.agent_strip)
        content_layout.addWidget(self.pages, 1)

        root_layout.addWidget(spacer)
        root_layout.addWidget(content, 1)

        self.sidebar = Sidebar(root)
        root.overlay = self.sidebar
        self.sidebar.raise_()

        self.setCentralWidget(root)

        self._connect_widgets()
        self._setup_shortcuts()
        self._open_startup()

    # ---------- helpers ----------
    @property
    def current_view(self):
        return self.stack.currentWidget()

    def _views(self) -> list:
        return [self.stack.widget(i) for i in range(self.stack.count())]

    # ---------- window ----------
    def _restore_geometry(self) -> None:
        data = settings.get("window_geometry")
        if settings.get("restore_geometry") and data:
            self.restoreGeometry(QByteArray.fromBase64(data.encode("ascii")))

    def closeEvent(self, event) -> None:
        if settings.get("restore_geometry"):
            encoded = bytes(self.saveGeometry().toBase64()).decode("ascii")
            settings.set("window_geometry", encoded)
        super().closeEvent(event)

    def _open_startup(self) -> None:
        mode = settings.get("startup_mode")
        url = (settings.get("startup_url") or "").strip()
        if mode == "custom" and url:
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
        self.toolbar_actions.downloads_clicked.connect(lambda: self._open_page("downloads"))
        self.toolbar_actions.settings_clicked.connect(lambda: self._open_page("settings"))
        self.toolbar_actions.bookmark_toggled.connect(self._on_bookmark_toggled)

        self.tab_strip.new_tab_requested.connect(lambda: self.add_tab())
        self.tab_strip.tab_changed.connect(self._on_tab_changed)
        self.tab_strip.tab_close_requested.connect(self.close_tab)
        self.tab_strip.tab_clicked.connect(lambda _: self._show_browser())

        settings.changed.connect(self._on_setting_changed)

    def _setup_shortcuts(self) -> None:
        QShortcut(QKeySequence("Ctrl+T"), self, activated=lambda: self.add_tab())
        QShortcut(
            QKeySequence("Ctrl+W"),
            self,
            activated=lambda: self.close_tab(self.stack.currentIndex()),
        )
        QShortcut(QKeySequence("Ctrl+L"), self, activated=self._focus_address_bar)
        QShortcut(QKeySequence("Ctrl+="), self, activated=lambda: self._change_zoom(ZOOM_STEP))
        QShortcut(QKeySequence("Ctrl++"), self, activated=lambda: self._change_zoom(ZOOM_STEP))
        QShortcut(QKeySequence("Ctrl+-"), self, activated=lambda: self._change_zoom(-ZOOM_STEP))
        QShortcut(QKeySequence("Ctrl+0"), self, activated=lambda: settings.set("zoom", 100))

    def _focus_address_bar(self) -> None:
        self._show_browser()
        self.address_bar.setFocus()
        self.address_bar.selectAll()

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

    def _reload_home_tabs(self) -> None:
        for view in self._views():
            if is_home_url(view.url().toString()):
                view.load_home()

    def _change_zoom(self, delta: int) -> None:
        new_zoom = max(ZOOM_MIN, min(ZOOM_MAX, int(settings.get("zoom")) + delta))
        settings.set("zoom", new_zoom)

    # ---------- page switching ----------
    def _show_browser(self) -> None:
        self.pages.setCurrentWidget(self.stack)
        self._sync_rail()

    def _open_page(self, name: str) -> None:
        page = self.page_map.get(name)
        if page is None:
            return
        self.pages.setCurrentWidget(page)
        self.sidebar.select(name)

    def _sync_rail(self) -> None:
        """Browser dikh raha ho to sidebar mein Home ya Browse highlight karo."""
        if self.pages.currentWidget() is not self.stack or self.current_view is None:
            return
        url = self.current_view.url().toString()
        self.sidebar.select("home" if is_home_url(url) else "browse")

    def _on_url_submitted(self, text: str) -> None:
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

    def _on_bookmark_toggled(self, checked: bool) -> None:
        self.statusBar().showMessage("Bookmark button ka UI ready hai, saving agle step mein judegi.", 3500)

    # ---------- AI agent (demo, backend baad mein) ----------
    def _on_agent_task(self, task: str) -> None:
        self._restore_address()
        self._agent_timer.stop()
        self._agent_task = task
        self._agent_step = 0
        if settings.get("ai_strip"):
            self.agent_strip.start(task)
        self.agent_strip.set_step(DEMO_STEPS[0])
        self._agent_timer.start(900)

    def _agent_tick(self) -> None:
        self._agent_step += 1
        if self._agent_step < len(DEMO_STEPS):
            self.agent_strip.set_step(DEMO_STEPS[self._agent_step])
            return
        self._agent_timer.stop()
        self.agent_strip.finish("Done, result opened in a new tab")
        self._open_agent_result(self._agent_task)

    def _on_agent_stop(self) -> None:
        self._agent_timer.stop()
        self.agent_strip.finish("Stopped")

    def _open_agent_result(self, task: str) -> None:
        view = self.add_tab(blank=True)
        view.setHtml(RESULT_HTML.format(task=html.escape(task)))

    def _restore_address(self) -> None:
        self.address_bar.setText(display_url(self.current_view.url().toString()))
        self.address_bar.clearFocus()

    # ---------- tabs ----------
    def add_tab(self, url: str | None = None, blank: bool = False, mode: str | None = None) -> WebView:
        """blank=True: kuch load nahi hota (popup / agent result ke liye).
        mode: 'home' ya 'blank'; None to settings ka 'New tab opens' use hota hai."""
        view = WebView()
        view.tab_factory = lambda: self.add_tab(blank=True)

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

        self.tab_strip.set_current(index)
        self._show_browser()
        return view

    def close_tab(self, index: int) -> None:
        if index < 0 or index >= self.stack.count():
            return

        # last tab band ho to naya tab khol do (window khali nahi rehti)
        if self.stack.count() == 1:
            self.add_tab()

        view = self.stack.widget(index)
        self.stack.removeWidget(view)
        self.tab_strip.remove_tab(index)
        view.deleteLater()

    def _on_tab_changed(self, index: int) -> None:
        if index < 0 or index >= self.stack.count():
            return
        self.stack.setCurrentIndex(index)
        view = self.current_view

        self.address_bar.setText(display_url(view.url().toString()))
        self.address_bar.setCursorPosition(0)
        self.nav_bar.set_loading(view.loading)
        self.toolbar_actions.set_bookmarked(False)
        self.setWindowTitle(f"{view.title() or 'New Tab'} - Agentic Browser")
        self._sync_rail()

    # ---------- per-view signals ----------
    def _on_view_url(self, view: WebView, url: str) -> None:
        if view is self.current_view:
            self.address_bar.set_url(display_url(url))
            self.toolbar_actions.set_bookmarked(False)
            self._sync_rail()

    def _on_view_title(self, view: WebView, title: str) -> None:
        index = self.stack.indexOf(view)
        self.tab_strip.set_title(index, title or "New Tab")
        if view is self.current_view:
            self.setWindowTitle(f"{title or 'New Tab'} - Agentic Browser")

    def _on_view_icon(self, view: WebView, icon: QIcon) -> None:
        self.tab_strip.set_icon(self.stack.indexOf(view), icon)

    def _on_view_loading(self, view: WebView, loading: bool) -> None:
        if view is self.current_view:
            self.nav_bar.set_loading(loading)