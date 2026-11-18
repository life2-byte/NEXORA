import json
from typing import Callable

import random

from PyQt6.QtCore import QTimer
from PyQt6.QtWebEngineCore import QWebEngineScript

from backend.browser.actions import format_action
from backend.browser.snapshot import build_snapshot, format_found
from frontend.core import ai_privacy as privacy
from frontend.core.adblock import quiet_for as net_quiet_for
from frontend.core.settings_manager import settings

# Isolated world: website ki apni JS ko hamari script/variables nazar nahi aate
WORLD = QWebEngineScript.ScriptWorldId.ApplicationWorld.value

MAX_ELEMENTS = 600
SETTLE_MS = 700          # action ke baad page ko thehrne ka waqt
MAX_LOAD_WAIT_MS = 8000  # navigation ka intezar
WATCHDOG_MS = 15000      # callback kabhi na aaye to bhi jawab dena
NO_TOOLS = "page tools not available (page is loading, blank or an error page)"


def _eval(view, expression: str, callback) -> None:
    view.page().runJavaScript(expression, WORLD, callback)


def when_ready(view, max_ms: int, then: Callable[[], None]) -> None:
    """Page poori load hone ka intezar nahi. Aage barho jab DOM tayyar ho (interactive/complete) aur site ki
    data-requests (XHR/script) thori der shaant hon ("network idle"). Bhaari images/ads ka intezar nahi.
    DOM tayyar hone ke baad shaanti ka intezar max 1.5s, taake SPA pages (Facebook jese) adhure na padhe jayen."""
    state = {"done": False, "waited": 0, "interactive": False, "ok_at": None}

    def fire() -> None:
        if not state["done"]:
            state["done"] = True
            then()

    def poll() -> None:
        if state["done"]:
            return
        if state["waited"] >= max_ms:
            fire()
            return
        if view.loading and state["waited"] >= 750 and state["waited"] % 500 == 0:
            def got(info) -> None:
                # sirf is load ke baad bane document ka readyState maano (purani page ka 'complete' dhoka deta hai)
                if isinstance(info, list) and info[0] in ("interactive", "complete") \
                        and info[1] >= getattr(view, "load_started_ms", 0) - 100:
                    state["interactive"] = True
            _eval(view, "[document.readyState, performance.timeOrigin]", got)
        if (not view.loading) or state["interactive"]:
            if state["ok_at"] is None:
                state["ok_at"] = state["waited"]
            quiet = net_quiet_for(view.url().host())
            if quiet >= 0.4 or state["waited"] - state["ok_at"] >= 1500:
                fire()
                return
        state["waited"] += 250
        QTimer.singleShot(250, poll)

    poll()


def _blocked(view, callback: Callable[[str], None], tool: str) -> bool:
    """True = privacy ki wajah se roka gaya (callback ko wajah bata di)."""
    reason = privacy.tool_block_reason(view)
    if reason is None:
        return False
    privacy.audit(tool, view.url().toString(), 0, "blocked")
    callback(f"BLOCKED {tool}: {reason}")
    return True


def read_page(view, callback: Callable[[str], None], goal: str = "", scope: str = "viewport", budget: int = 6000) -> None:
    if _blocked(view, callback, "read_page"):
        return

    def on_result(raw) -> None:
        if not isinstance(raw, dict):
            callback(NO_TOOLS)
            return
        # JS chalte chalte page kisi private site pe ja sakta hai, dobara check
        reason = privacy.tool_block_reason(view, raw.get("url"))
        if reason:
            privacy.audit("read_page", raw.get("url", ""), 0, "blocked")
            callback(f"BLOCKED read_page: {reason}")
            return
        text = build_snapshot(raw, goal=goal, scope=scope, budget=budget)
        privacy.audit("read_page", raw.get("url", ""), len(text), "ok")
        callback(text)

    _eval(view, f"window.__agent ? window.__agent.snapshot({MAX_ELEMENTS}) : null", on_result)


def find(view, query: str, callback: Callable[[str], None], limit: int = 10) -> None:
    if _blocked(view, callback, "find"):
        return

    def on_result(items) -> None:
        if items is None:
            callback(NO_TOOLS)
            return
        if privacy.tool_block_reason(view):
            callback("BLOCKED find: the page moved to a private site")
            return
        text = format_found(items, query)
        privacy.audit("find", view.url().toString(), len(text), "ok")
        callback(text)

    _eval(view, f"window.__agent ? window.__agent.find({json.dumps(query)}, {limit}) : null", on_result)


def _do_action(view, js_call: str, label: tuple, callback: Callable[[str], None]) -> None:
    """JS action chalao, page ke thehrne ka intezar karo, phir before/after compare karke verified result do."""
    if _blocked(view, callback, label[0]):
        return

    state = {"done": False}
    before_url = view.url().toString()

    def deliver(text: str, ok: bool = True) -> None:
        if not state["done"]:
            state["done"] = True
            privacy.audit(label[0], before_url, len(text), "ok" if ok else "failed")
            callback(text)

    def fail(error: str) -> None:
        deliver(format_action(label[0], label[1], {"ok": False, "error": error}), ok=False)

    QTimer.singleShot(WATCHDOG_MS, lambda: fail("timed out waiting for the page"))

    def start(fp_before) -> None:
        if not isinstance(fp_before, dict):
            fail(NO_TOOLS)
            return
        _eval(view, f"window.__agent.{js_call}", lambda result: after_action(fp_before, result))

    def after_action(fp_before, result) -> None:
        if not isinstance(result, dict):
            result = {"ok": False, "error": "action returned nothing (page may have navigated)"}
        def settle() -> None:
            _eval(
                view,
                "window.__agent ? window.__agent.fingerprint() : null",
                lambda fp_after: finish(fp_before, fp_after, result),
            )

        QTimer.singleShot(SETTLE_MS, lambda: when_ready(view, MAX_LOAD_WAIT_MS, settle))

    def finish(fp_before, fp_after, result: dict) -> None:
        after_url = view.url().toString()
        hidden = privacy.url_block_reason(after_url) is not None
        result["url"] = "(private site)" if hidden else after_url
        result["url_changed"] = after_url != before_url
        if hidden:
            result["note"] = "now on a private site the AI cannot read; ask the user to continue there"
        result["load_failed"] = not getattr(view, "last_load_ok", True)
        if isinstance(fp_after, dict):
            keys = ("textLen", "nodes", "title", "dialogs")
            result["page_changed"] = any(fp_after.get(k) != fp_before.get(k) for k in keys)
        else:
            result["page_changed"] = result["url_changed"]
        deliver(format_action(label[0], label[1], result), ok=bool(result.get("ok")))

    _eval(view, "window.__agent ? window.__agent.fingerprint() : null", start)


def click(view, element_id: str, callback: Callable[[str], None]) -> None:
    _do_action(view, f"click({json.dumps(element_id)})", ("click", element_id), callback)


HUMAN_MAX_CHARS = 500
HUMAN_BUDGET_MS = 7000   # lambi text bhi itne mein poori (chunks bade ho jate hain)


def type_text(view, element_id: str, text: str, callback: Callable[[str], None], submit: bool = False) -> None:
    shown = text if len(text) <= 30 else text[:27] + "..."
    label = ("type" + ("+enter" if submit else ""), f'{element_id} "{shown}"')

    def instant() -> None:
        js = f"type({json.dumps(element_id)}, {json.dumps(text)}, {json.dumps(submit)})"
        _do_action(view, js, label, callback)

    if settings.get("agent_typing") != "human" or not text or len(text) > HUMAN_MAX_CHARS:
        instant()
        return
    if _blocked(view, callback, label[0]):
        return

    def on_prepared(res) -> None:
        if not isinstance(res, dict):
            callback(format_action(label[0], label[1], {"ok": False, "error": NO_TOOLS}))
            return
        if not res.get("ok"):
            callback(format_action(label[0], label[1], res))
            return
        if res.get("mode") != "human":
            instant()
            return
        chunk = max(2, -(-len(text) * 70 // HUMAN_BUDGET_MS))   # ~70ms/char se lambi ho to chunk bade
        pos = [0]

        def tick() -> None:
            if privacy.tool_block_reason(view):
                callback("BLOCKED type: the page moved to a private site")
                return
            if pos[0] >= len(text):
                QTimer.singleShot(random.randint(120, 300), finish)
                return
            part = text[pos[0] : pos[0] + chunk]
            pos[0] += chunk
            _eval(view, f"window.__agent.insertChars({json.dumps(element_id)}, {json.dumps(part)})", lambda ok: None)
            delay = random.randint(35, 110) * len(part)
            if part[-1:] in " ,.":
                delay += random.randint(40, 160)
            QTimer.singleShot(delay, tick)

        def finish() -> None:
            _do_action(view, f"finishType({json.dumps(element_id)}, {json.dumps(submit)})", label, callback)

        tick()

    _eval(view, f"window.__agent ? window.__agent.prepareType({json.dumps(element_id)}) : null", on_prepared)


def scroll(view, direction: str, callback: Callable[[str], None], amount: float = 0.8) -> None:
    js = f"scroll({json.dumps(direction)}, {amount})"
    _do_action(view, js, ("scroll", direction), callback)


def navigate(view, target: str, callback: Callable[[str], None]) -> None:
    reason = privacy.tool_block_reason(view, target)
    if reason:
        privacy.audit("go", target, 0, "blocked")
        callback(f"BLOCKED go: {reason}")
        return

    view.navigate(target)

    def done() -> None:
        url = view.url().toString()
        if privacy.url_block_reason(url):
            privacy.audit("go", url, 0, "landed on a private site")
            callback(
                "OK go | the page is a private site (blocklist). The AI cannot read it; "
                "ask the user to continue there."
            )
            return
        if not getattr(view, "last_load_ok", True) and not view.loading:
            callback(f"FAILED go {target}: page failed to load (network or site error) | url {url}")
            return
        text = f'OK go {target} | url {url} | title "{view.title()}"'
        privacy.audit("go", url, len(text), "ok")
        callback(text)

    QTimer.singleShot(400, lambda: when_ready(view, 15000, done))  # loadStarted aane ka waqt


def history_nav(view, action: str, callback: Callable[[str], None]) -> None:
    if action not in ("back", "forward", "reload"):
        callback("FAILED nav: action must be back, forward or reload")
        return
    if _blocked(view, callback, "nav"):
        return
    before = view.url().toString()
    page_history = view.history()
    if action == "back" and not page_history.canGoBack():
        callback("FAILED nav back: there is no previous page")
        return
    if action == "forward" and not page_history.canGoForward():
        callback("FAILED nav forward: there is no next page")
        return
    if action == "reload":
        view.reload()
    else:
        # goToItem: Chromium ke 'history skip' (bina click wali entries chhodna) se bachne ke liye
        item = page_history.backItem() if action == "back" else page_history.forwardItem()
        page_history.goToItem(item)
    waited = [0]

    def poll() -> None:
        if (view.loading or view.url().toString() == before and action != "reload") and waited[0] < 8000:
            waited[0] += 250
            QTimer.singleShot(250, poll)
            return
        url = view.url().toString()
        if privacy.url_block_reason(url):
            callback(f"OK nav {action} | now on a private site the AI cannot read; ask the user to continue there")
            return
        callback(f'OK nav {action} | url {url} | title "{view.title()}"')

    QTimer.singleShot(300, poll)


def page_api(view, url: str, callback: Callable[[str], None]) -> None:
    """url khali = is page ne kaunsi API mangwayi (list). url diya = wahi (same-site) GET karke chhota JSON do."""
    if _blocked(view, callback, "page_api"):
        return
    if not url.strip():
        def on_list(items) -> None:
            if not isinstance(items, list):
                callback(NO_TOOLS)
                return
            if not items:
                callback("PAGE_API: no fetch/XHR calls seen on this page yet (scroll or interact, then try again)")
                return
            lines = [f"{it.get('url', '')}  ({it.get('kb', 0)} KB)" for it in items]
            callback("PAGE_API: recent data calls made by this page (read one with page_api url=...):\n" + "\n".join(lines))

        _eval(view, "window.__agent ? window.__agent.apiList(25) : null", on_list)
        return

    def on_json(res) -> None:
        if not isinstance(res, dict):
            callback(NO_TOOLS)
            return
        if not res.get("ok"):
            callback(f"FAILED page_api {url[:80]}: {res.get('error', 'unknown error')}")
            return
        privacy.audit("page_api", view.url().toString(), len(res.get("body", "")), "ok")
        callback(f"OK page_api {url[:80]} (HTTP {res.get('status')}), shortened JSON:\n{res.get('body', '')}")

    _eval(view, f"window.__agent ? window.__agent.fetchJson({json.dumps(url)}) : null", on_json)


_when_ready = when_ready   # purana naam