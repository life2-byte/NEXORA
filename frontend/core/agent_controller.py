"""Agent ko GUI se jodta hai: worker thread, chat box, strip, usage ginti, user se sawal/madad/ijazat."""

import dataclasses
import threading

from PyQt6.QtCore import QEvent, QObject, pyqtSignal
from PyQt6.QtWidgets import QApplication

from backend.ai import agent_loop
from backend.ai.agents import AgentStore
from backend.ai.base import ProviderError
from backend.ai.memory_store import NotesStore, memory_block
from backend.ai.providers import make_provider
from backend.ai.reasoning import effort_for
from backend.ai.vision import supports_vision
from backend.browser.tools import format_tabs
from frontend.core import ai_privacy
from frontend.core.ai_provider import current_config
from frontend.core.ai_usage import ai_usage
from frontend.core.settings_manager import settings
from frontend.widgets.agent_chat import AgentChat


class AgentController(QObject):
    # worker thread -> GUI
    _plan = pyqtSignal(str)
    _step = pyqtSignal(str)
    _say = pyqtSignal(str)
    _ask = pyqtSignal(str)
    _help = pyqtSignal(str)
    _confirm = pyqtSignal(str)
    _usage = pyqtSignal(object, object)
    _done = pyqtSignal(bool, str)

    def __init__(self, window, root):
        super().__init__(window)
        self.w = window
        self.root = root
        self.chat = AgentChat(root)
        self.chat.close_requested.connect(self.chat.hide)
        self.chat.text_submitted.connect(self._on_text)
        root.installEventFilter(self)

        self._thread = None
        self._hooks = None
        self._wait = None        # (Event, dict) jab worker user ka intezar kar raha ho
        self._over_budget = False
        self._task = ""
        self._agent_id = ""
        self._model = ""

        self._plan.connect(lambda t: self.chat.add("Plan:\n" + t, "Plan"))
        self._step.connect(self._on_step)
        self._say.connect(lambda t: self.chat.set_status(t.replace("\n", " ")))   # beech ka sochna sirf status mein
        self._ask.connect(self._on_ask)
        self._help.connect(self._on_help)
        self._confirm.connect(self._on_confirm)
        self._usage.connect(self._on_usage)
        self._done.connect(self._on_done)

    # ---------- chat box ki jagah ----------
    def eventFilter(self, obj, event):
        if obj is self.root and event.type() == QEvent.Type.Resize:
            self._place()
        return False

    def _place(self) -> None:
        h = max(260, min(520, self.root.height() - 140))
        self.chat.setFixedHeight(h)
        self.chat.move(self.root.width() - self.chat.width() - 16, 110)

    # ---------- public ----------
    @property
    def running(self) -> bool:
        return self._thread is not None and self._thread.is_alive()

    def start(self, task: str) -> None:
        if not task.strip():
            return
        if self.running:
            self.chat.pop_up(True)
            self.chat.add("Agent abhi kaam kar raha hai. Pehle Stop dabao.", "Alert")
            return
        problem = ai_privacy.readiness()
        if problem:
            self.w.statusBar().showMessage(problem, 6000)
            return
        try:
            cfg = current_config()
        except ProviderError as e:
            self.w.statusBar().showMessage(e.message, 6000)
            return
        store = AgentStore(settings.config_dir / "agents.json")
        agent = store.get(settings.get("default_agent") or "browser")
        if agent.get("model"):
            cfg = dataclasses.replace(cfg, model=agent["model"])
        cfg = dataclasses.replace(cfg, reasoning=effort_for(cfg.base_url, cfg.model, settings.get("ai_thinking") or "low"))
        provider = make_provider(cfg)

        notes = NotesStore(settings.config_dir / "agent_notes.json").list()
        prefs = {
            "language": settings.get("agent_language"), "detail": settings.get("agent_detail"),
            "confirm": settings.get("agent_confirm"), "instructions": settings.get("agent_instructions"),
        }
        infos = [dict(i, title="(private)", url="(private)") if ai_privacy.url_block_reason(i["raw_url"]) else i
                 for i in self.w.tab_infos()]
        st = agent_loop.Settings(
            max_steps=int(settings.get("agent_max_steps") or 25),
            confirm_mode=settings.get("agent_confirm") or "risky",
            allowed_tools=tuple(
                t for t in agent["tools"]
                if t not in ("screenshot", "click_at") or supports_vision(cfg.model, settings.get("ai_vision"))
            ),
            system_prompt=agent_loop.build_system_prompt(agent, memory_block(prefs, notes), format_tabs(infos)),
        )
        view = self.w.current_view
        self.w.tools.default_tab = getattr(view, "tab_id", "") if view is not None else ""   # task isi tab par rahe
        self._task, self._agent_id, self._model = task, agent["id"], cfg.model
        self._over_budget = ai_usage.over_budget()
        hooks = agent_loop.Hooks(
            plan=self._plan.emit, step=self._step.emit, say=self._say.emit,
            ask=self._block_ask, help=self._block_help, confirm=self._block_confirm,
            usage=lambda u, l: self._usage.emit(u, l), over_budget=lambda: self._over_budget,
        )
        self._hooks = hooks
        self.chat.clear()
        self.chat.set_actions([("Stop", self.stop)])
        self.chat.title.setText(agent["name"])
        self.chat.add(task, "User")
        self.chat.set_status("shuru...")
        if settings.get("ai_strip"):
            self.w.agent_strip.start(task)
        self._thread = threading.Thread(target=self._work, args=(provider, st, task, agent["id"] != "reader"), daemon=True)
        self._thread.start()

    def stop(self) -> None:
        if self._hooks:
            self._hooks.stopped.set()
        self._release(None)

    # ---------- worker ----------
    def _work(self, provider, st, task, plan_first) -> None:
        try:
            res = agent_loop.run(provider, self.w.tools, task, st, self._hooks, plan_first)
        except Exception as e:  # worker kabhi bina batae na mare
            res = agent_loop.Result(False, f"Agent crash hua: {e}")
        self._done.emit(res.ok, res.text)

    def _block(self, signal, payload):
        event, box = threading.Event(), {}
        self._wait = (event, box)
        signal.emit(payload)
        while not event.wait(0.3):
            if self._hooks.stopped.is_set():
                break
        self._wait = None
        return box.get("value")

    def _block_ask(self, q): return self._block(self._ask, q) or ""
    def _block_help(self, r): return bool(self._block(self._help, r))
    def _block_confirm(self, t): return bool(self._block(self._confirm, t))

    def _release(self, value) -> None:
        if self._wait:
            event, box = self._wait
            box["value"] = value
            event.set()

    # ---------- GUI slots ----------
    def _on_step(self, text: str) -> None:
        self.chat.set_status(text)
        self.w.agent_strip.set_step(text)

    def _on_usage(self, usage, limits) -> None:
        ai_usage.record(usage, limits, self._model, self._agent_id, self._task[:80])
        self._over_budget = ai_usage.over_budget()

    def _alert(self) -> None:
        self.chat.pop_up(True)
        QApplication.alert(self.w, 4000)

    def _on_ask(self, question: str) -> None:
        self.chat.add(question, "Alert")
        self.chat.set_actions([("Stop", self.stop)])
        self._alert()

    def _on_text(self, text: str) -> None:
        if self._wait and self._hooks and not self._hooks.stopped.is_set():
            self._release(text)
            self.chat.set_actions([("Stop", self.stop)])
        elif not self.running:
            self.start(text)

    def _on_help(self, reason: str) -> None:
        self.chat.add(reason, "Alert")
        self.w.statusBar().showMessage("Agent ko tumhari madad chahiye", 8000)
        self.chat.set_actions([("Ho gaya, aage barho", lambda: self._answer_help(True)), ("Chhod do", lambda: self._answer_help(False))])
        self._alert()

    def _answer_help(self, ok: bool) -> None:
        self.chat.set_actions([("Stop", self.stop)])
        self._release(ok)
        self.chat.hide()

    def _on_confirm(self, what: str) -> None:
        self.chat.add("Ijazat chahiye:\n" + what[:300], "Alert")
        self.chat.set_actions([("Haan, karo", lambda: self._answer_confirm(True)), ("Nahi", lambda: self._answer_confirm(False))])
        self._alert()

    def _answer_confirm(self, ok: bool) -> None:
        self.chat.set_actions([("Stop", self.stop)])
        self._release(ok)

    def _on_done(self, ok: bool, text: str) -> None:
        self.w.tools.default_tab = ""
        self.chat.set_actions([])
        self.chat.add(text, "Agent" if ok else "Alert")
        self.chat.set_status("khatam" if ok else "ruk gaya")
        self.w.agent_strip.finish("Done" if ok else "Stopped")
        self.chat.pop_up()
        self.chat.hide_later()   # jawab dene ke baad khud chhup jata hai