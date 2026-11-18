import threading
import time
from concurrent.futures import Future
from typing import Callable, Optional

from PyQt6.QtCore import QObject, Qt, QTimer, pyqtSignal
from frontend.core import ai_privacy as privacy
from backend.browser.tools import BrowserTools, format_tabs
from frontend.core import browser_bridge as bridge
from frontend.core import browser_input as binput
from frontend.core.settings_manager import settings


MAX_AGENT_TABS = 8
PAGE_WAIT_MS = 6000   # tools chalne se pehle page ke load hone ka max intezar


class _Executor(QObject):
    """GUI thread mein jeeta hai. Kisi bhi thread se emit karo, function GUI thread pe chalta hai."""

    run = pyqtSignal(object)

    def __init__(self):
        super().__init__()
        self.run.connect(self._on_run, Qt.ConnectionType.QueuedConnection)

    def _on_run(self, fn: Callable[[], None]) -> None:
        fn()


class QtBrowserTools(BrowserTools):
    """BrowserTools ka Qt version. Agent ke worker thread se call hota hai, kaam GUI thread pe hota hai."""

    def __init__(self, window):
        self._w = window
        self._lock = threading.Lock()
        self.default_tab = ""            # agent ka apna tab: tab_id na diya ho to yahi (user kisi bhi tab par ho)
        self._agent_tabs: set = set()    # agent ke khole hue tab ids (RAM bachane ke liye hadd)
        self._images: list = []          # naye screenshots (sirf RAM)
        self._shots: dict = {}           # tab_id -> aakhri screenshot ka mapping (scale, ox, oy, hash)
        self._exec = _Executor()  # GUI thread mein banana zaroori hai (MainWindow ke __init__ mein)

    # ---------- thread marshalling ----------
    def _call(self, starter: Callable[[Callable[[str], None]], None], timeout: float = 45.0) -> str:
        if threading.current_thread() is threading.main_thread():
            raise RuntimeError("QtBrowserTools blocking hai: worker thread se chalao, GUI thread se nahi")

        future: Future = Future()

        def deliver(text: str) -> None:
            if not future.done():
                future.set_result(text)

        def run_in_gui() -> None:
            try:
                starter(deliver)
            except Exception as e:
                deliver(f"FAILED: {e}")

        self._exec.run.emit(run_in_gui)
        try:
            return future.result(timeout=timeout)
        except Exception:
            return "FAILED: tool timed out"

    def _on_view(self, tab_id: Optional[str], action: Callable, mode: str = "read") -> str:
        """mode: read = padhne wale tools, act = click/type (page load na hua to nahi karte), none = intezar nahi."""
        def start(cb: Callable[[str], None]) -> None:
            wanted = tab_id or self.default_tab or None
            view = self._w.view_by_id(wanted)
            if view is None and not tab_id and self.default_tab:
                view = self._w.view_by_id(None)     # agent ka tab band ho gaya: user wala tab
            if view is None:
                cb(f"FAILED: no tab '{tab_id}'. Call list_tabs to see the ids.")
                return
            if mode == "none" or not view.loading:
                action(view, cb)
                return
            t0 = time.monotonic()

            def ready() -> None:
                waited = time.monotonic() - t0
                timed_out = waited * 1000 >= PAGE_WAIT_MS - 300 and view.loading
                if timed_out and mode == "act":
                    cb(f"PAGE STILL LOADING after {waited:.0f}s, nothing was done. Call wait(3) and read_page again, "
                       "then retry. Do not take screenshots to check.")
                    return
                note = (f"WARNING: page still loading after {waited:.0f}s, content may be partial.\n" if timed_out
                        else f"NOTE: page was still loading; waited {waited:.1f}s, now ready.\n")
                action(view, lambda text: cb(note + text))

            bridge.when_ready(view, PAGE_WAIT_MS, ready)

        return self._call(start)

    # ---------- tabs ----------
    def list_tabs(self) -> str:
        def start(cb: Callable[[str], None]) -> None:
            if not privacy.ai_globally_enabled():
                cb("BLOCKED list_tabs: AI is turned off in Settings")
                return
            infos = []
            for info in self._w.tab_infos():
                if privacy.url_block_reason(info["raw_url"]):
                    info = {**info, "title": "(private site)", "url": "(private site)"}
                infos.append(info)
            cb(format_tabs(infos))

        return self._call(start)

    def new_tab(self, url: str = "", activate: bool = False) -> str:
        def start(cb: Callable[[str], None]) -> None:
            reason = None
            if not privacy.ai_globally_enabled():
                reason = "AI is turned off in Settings"
            elif url:
                reason = privacy.url_block_reason(url)
            if reason:
                privacy.audit("new_tab", url, 0, "blocked")
                cb(f"BLOCKED new_tab: {reason}")
                return

            open_ids = {i["id"] for i in self._w.tab_infos()}
            self._agent_tabs &= open_ids
            if len(self._agent_tabs) >= MAX_AGENT_TABS:
                cb(f"BLOCKED new_tab: {MAX_AGENT_TABS} tabs opened by the agent are already open (RAM is limited). "
                   "Close the ones you no longer need with close_tab, or reuse a tab with go.")
                return
            view = self._w.open_tab(url, activate)
            self._agent_tabs.add(view.tab_id)
            if not url:
                cb(f"OK new_tab [{view.tab_id}] blank page")
                return
            bridge.navigate(view, url, lambda text: cb(f"[{view.tab_id}] {text}"))

        return self._call(start)

    def switch_tab(self, tab_id: str) -> str:
        def start(cb: Callable[[str], None]) -> None:
            if self._w.activate_tab(tab_id):
                if self.default_tab:
                    self.default_tab = tab_id     # agent ne ye tab user ko dikhaya, ab yahan kaam karega
                cb(f"OK switch_tab {tab_id}")
            else:
                cb(f"FAILED: no tab '{tab_id}'. Call list_tabs to see the ids.")

        return self._call(start)

    def close_tab(self, tab_id: str) -> str:
        def start(cb: Callable[[str], None]) -> None:
            if self._w.close_tab_by_id(tab_id):
                cb(f"OK close_tab {tab_id}")
            else:
                cb(f"FAILED: no tab '{tab_id}'. Call list_tabs to see the ids.")

        return self._call(start)

    # ---------- page tools ----------
    def read_page(self, tab_id: Optional[str] = None, goal: str = "", scope: str = "viewport") -> str:
        return self._on_view(tab_id, lambda v, cb: bridge.read_page(v, cb, goal=goal, scope=scope))

    def find(self, query: str, tab_id: Optional[str] = None) -> str:
        return self._on_view(tab_id, lambda v, cb: bridge.find(v, query, cb))

    def click(self, element_id: str, tab_id: Optional[str] = None) -> str:
        return self._on_view(tab_id, lambda v, cb: bridge.click(v, element_id, cb), "act")

    def type_text(
        self, element_id: str, text: str, submit: bool = False, tab_id: Optional[str] = None
    ) -> str:
        return self._on_view(
            tab_id, lambda v, cb: bridge.type_text(v, element_id, text, cb, submit=submit), "act"
        )

    def scroll(self, direction: str = "down", tab_id: Optional[str] = None) -> str:
        return self._on_view(tab_id, lambda v, cb: bridge.scroll(v, direction, cb))

    def go(self, target: str, tab_id: Optional[str] = None) -> str:
        return self._on_view(tab_id, lambda v, cb: bridge.navigate(v, target, cb), "none")

    def nav(self, action: str, tab_id: Optional[str] = None) -> str:
        return self._on_view(tab_id, lambda v, cb: bridge.history_nav(v, action, cb), "none")

    # ---------- asli keyboard / mouse / screenshot ----------
    def pop_images(self) -> list:
        with self._lock:
            imgs, self._images = self._images, []
        return imgs

    def screenshot(self, tab_id=None, region_x=None, region_y=None, region_width=None, region_height=None) -> str:
        def action(view, cb) -> None:
            shot = self._shots.get(view.tab_id)
            crop = None
            if None not in (region_x, region_y, region_width, region_height):
                if shot is None:
                    cb("FAILED screenshot: take a normal screenshot first, then ask for a region of it.")
                    return
                crop = (shot["ox"] + region_x * shot["scale"], shot["oy"] + region_y * shot["scale"],
                        region_width * shot["scale"], region_height * shot["scale"])
                crop = tuple(int(v) for v in crop)
            res = binput.take_screenshot(view, crop, (shot or {}).get("hash", "") if crop is None else "")
            if "error" in res:
                cb(res["error"])
                return
            self._shots[view.tab_id] = {k: res[k] for k in ("scale", "ox", "oy", "w", "h", "hash")}
            if res["same"] and crop is None:
                cb(f"OK screenshot of {view.tab_id}: UNCHANGED since the last picture (still {res['w']}x{res['h']}). "
                   "Nothing visibly changed, so try something different instead of repeating.")
                return
            with self._lock:
                self._images.append(res["b64"])
            cb(f"OK screenshot of {view.tab_id} {res['w']}x{res['h']}px"
               + (" (zoomed region)" if crop else "")
               + ". The picture is in the next message; click_at uses its pixel numbers.")

        return self._on_view(tab_id, action)

    def click_at(self, x: int, y: int, double: bool = False, tab_id: Optional[str] = None) -> str:
        def action(view, cb) -> None:
            shot = self._shots.get(view.tab_id)
            if shot is None:
                cb("FAILED click_at: take a screenshot of this tab first, then use its pixel numbers.")
                return
            text = binput.click_at(view, int(x), int(y), shot, bool(double))
            QTimer.singleShot(bridge.SETTLE_MS, lambda: cb(text))

        return self._on_view(tab_id, action, "act")

    def page_api(self, url: str = "", tab_id: Optional[str] = None) -> str:
        return self._on_view(tab_id, lambda v, cb: bridge.page_api(v, str(url or ""), cb))

    def press_keys(self, text: str = "", key: str = "", tab_id: Optional[str] = None) -> str:
        human = settings.get("agent_typing") == "human"
        return self._on_view(tab_id, lambda v, cb: binput.press_keys(v, str(text or ""), str(key or ""), human, cb), "act")