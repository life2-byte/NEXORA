import re
import threading

from PyQt6.QtCore import QObject, Qt, pyqtSignal
from PyQt6.QtWidgets import QPlainTextEdit

from backend.browser.tools import dispatch, format_tabs
from frontend.core import browser_bridge as bridge

HELP = """Dev tools (omnibox mein ! se shuru karo, Enter dabao)

Page tools (current tab pe):
  !read [goal]         screen ka snapshot (goal likho to ranking us hisaab se)
  !page [goal]         poore page ka snapshot
  !find words          elements dhoondo
  !click e12           element pe click
  !type e14 text       text likho
  !typego e14 text     text likho + Enter
  !scroll down         down | up | top | bottom
  !go url-or-search    page kholo

Tab tools:
  !tabs                saare tabs (ids ke saath)
  !newtab [url]        naya tab (user ko dikhta hai)
  !switch t2           tab dikhao
  !closetab t2         tab band karo
  !@t2 read            koi bhi page tool kisi bhi tab pe (e.g. !@t2 click e5)

Test:
  !selftest            worker thread se poora raasta (tabs + read + scroll), bina AI ke
  !help                ye list

Ids (e12...) !read ke output se lo. Page badle to dobara !read karo."""


class DevConsole(QObject):
    """Agent ke tools ko AI ke bagair haath se chalane ka tareeqa (har tool alag test)."""

    _log = pyqtSignal(str, str)  # worker thread se bhi safely output dikhane ke liye

    def __init__(self, window):
        super().__init__(window)
        self._window = window
        self._out = QPlainTextEdit(window)
        self._out.setWindowFlags(Qt.WindowType.Tool)
        self._out.setWindowTitle("Agent tools output")
        self._out.setReadOnly(True)
        self._out.setAttribute(Qt.WidgetAttribute.WA_ShowWithoutActivating)
        self._out.resize(640, 700)
        self._out.setStyleSheet(
            "QPlainTextEdit { background: #0b1220; color: #c9d1e0; border: none; padding: 8px;"
            " font-family: 'JetBrains Mono', 'Ubuntu Mono', monospace; font-size: 12px; }"
        )
        self._log.connect(self._show)

    def run(self, line: str) -> None:
        line = line.strip()
        tab_id = None
        if line.startswith("@"):
            tab_id, _, line = line[1:].partition(" ")
            line = line.strip()

        cmd, _, rest = line.partition(" ")
        cmd, rest = cmd.lower(), rest.strip()
        title = f"!{'@' + tab_id + ' ' if tab_id else ''}{cmd} {rest}".strip()

        def show(text: str) -> None:
            self._show(title, text)

        w = self._window

        # ---- tab tools ----
        if cmd == "tabs":
            show(format_tabs(w.tab_infos()))
            return
        if cmd == "newtab":
            view = w.open_tab(rest, activate=True)
            if rest:
                bridge.navigate(view, rest, lambda text: show(f"[{view.tab_id}] {text}"))
            else:
                show(f"OK newtab [{view.tab_id}] blank page")
            return
        if cmd == "switch":
            show(f"OK switch {rest}" if w.activate_tab(rest) else f"FAILED: no tab '{rest}'")
            return
        if cmd == "closetab":
            show(f"OK closetab {rest}" if w.close_tab_by_id(rest) else f"FAILED: no tab '{rest}'")
            return
        if cmd == "selftest":
            self._selftest()
            return

        # ---- page tools ----
        view = w.view_by_id(tab_id)
        if view is None:
            show(f"FAILED: no tab '{tab_id}'")
        elif cmd in ("read", "page"):
            scope = "page" if cmd == "page" else "viewport"
            bridge.read_page(view, show, goal=rest, scope=scope, budget=12000 if cmd == "page" else 6000)
        elif cmd == "find":
            bridge.find(view, rest, show) if rest else show("usage: !find some words")
        elif cmd == "click":
            bridge.click(view, rest, show) if rest else show("usage: !click e12")
        elif cmd in ("type", "typego"):
            element_id, _, text = rest.partition(" ")
            if not element_id or not text:
                show(f"usage: !{cmd} e14 some text")
            else:
                bridge.type_text(view, element_id, text.strip(), show, submit=(cmd == "typego"))
        elif cmd == "scroll":
            bridge.scroll(view, rest or "down", show)
        elif cmd == "go":
            bridge.navigate(view, rest, show) if rest else show("usage: !go example.com")
        else:
            show(HELP)

    # ---------- selftest: agent jis raaste se chalega, usi se ----------
    def _selftest(self) -> None:
        tools = self._window.tools

        def worker() -> None:
            transcript = []

            def emit() -> None:
                self._log.emit("!selftest", "\n".join(transcript))

            def step(name: str, **args) -> str:
                out = dispatch(tools, name, args)
                transcript.append(f"--- {name} {args}\n{out}\n")
                emit()
                return out

            step("list_tabs")
            out = step("new_tab", url="https://example.com", activate=False)
            match = re.search(r"\[(t\d+)\]", out)
            if not match or "FAILED" in out:
                transcript.append("selftest roka gaya: naya tab load nahi hua (internet?)")
                emit()
                return
            tab = match.group(1)
            step("read_page", tab_id=tab, goal="main heading")
            step("scroll", direction="down", tab_id=tab)
            step("list_tabs")
            step("close_tab", tab_id=tab)
            step("list_tabs")
            transcript.append("selftest poora hua")
            emit()

        self._show("!selftest", "worker thread mein chal raha hai...")
        threading.Thread(target=worker, daemon=True).start()

    def _show(self, title: str, text: str) -> None:
        print(f"> {title}\n{text}\n")
        self._out.setPlainText(f"> {title}\n\n{text}")
        self._out.show()
        self._out.raise_()