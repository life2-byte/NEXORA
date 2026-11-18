"""Agents: har agent = naam + hidayat + kaun se tools use kar sakta hai (+ optional alag model).
Built-in teen hain (badal nahi sakte, copy ban sakti hai); user apne bana sakta hai. Qt ka koi code nahi."""

import json
import os
import re
import uuid
from pathlib import Path

from backend.browser.tools import TOOL_NAMES

READ_ONLY = ("list_tabs", "read_page", "find", "scroll", "wait", "screenshot", "page_api")
ALL_TOOLS = ("list_tabs", "new_tab", "switch_tab", "close_tab", "read_page", "find", "click", "type_text", "press_keys",
             "scroll", "nav", "go", "wait", "screenshot", "click_at", "page_api")

BUILTIN = [
    {
        "id": "reader",
        "name": "Reader",
        "description": "Sirf padhta hai: page ka summary, sawalon ke jawab. Kuch click ya type nahi karta (sab se mehfooz).",
        "instructions": "You read pages and answer questions about them. You never click or type. If the user needs an action, tell them what to do.",
        "tools": list(READ_ONLY),
        "model": "",
        "builtin": True,
    },
    {
        "id": "researcher",
        "name": "Researcher",
        "description": "Kayi sites kholta hai (background tabs mein), padhta hai, compare karta hai aur links ke saath report deta hai. Forms nahi bharta.",
        "instructions": "You research a topic across several websites. Open pages in background tabs, read them, compare sources, and finish with a short report that lists the facts and the source links. Close tabs you opened when done. Do not fill forms.",
        "tools": ["list_tabs", "new_tab", "close_tab", "read_page", "find", "scroll", "nav", "go", "wait", "screenshot", "page_api"],
        "model": "",
        "builtin": True,
    },
    {
        "id": "browser",
        "name": "Browser Agent",
        "description": "Poora kaam kar sakta hai: pages kholna, click, type, scroll. Risky actions par tum se poochta hai.",
        "instructions": "You operate the browser to complete the user's task: open pages, read them, click, type and scroll. Work step by step and check each result before the next step.",
        "tools": list(ALL_TOOLS),
        "model": "",
        "builtin": True,
    },
]
DEFAULT_ID = "browser"
MAX_CUSTOM = 20


def _clean_tools(tools) -> list:
    return [t for t in ALL_TOOLS if t in set(tools or []) and t in TOOL_NAMES]


class AgentStore:
    def __init__(self, path):
        self._path = Path(path)

    def _custom(self) -> list:
        try:
            data = json.loads(self._path.read_text(encoding="utf-8"))
            return [a for a in data if isinstance(a, dict) and a.get("id") and a.get("name")]
        except (OSError, ValueError):
            return []

    def _write(self, agents: list) -> None:
        self._path.parent.mkdir(parents=True, exist_ok=True)
        tmp = self._path.with_suffix(".tmp")
        tmp.write_text(json.dumps(agents, ensure_ascii=False), encoding="utf-8")
        os.replace(tmp, self._path)

    def all(self) -> list:
        return [dict(a) for a in BUILTIN] + [
            {
                "id": a["id"],
                "name": a["name"][:40],
                "description": (a.get("description") or "")[:200],
                "instructions": (a.get("instructions") or "")[:2000],
                "tools": _clean_tools(a.get("tools")),
                "model": (a.get("model") or "")[:100],
                "builtin": False,
            }
            for a in self._custom()
        ]

    def get(self, agent_id: str) -> dict:
        for a in self.all():
            if a["id"] == agent_id:
                return a
        return next(a for a in self.all() if a["id"] == DEFAULT_ID)

    def save(self, agent: dict) -> tuple:
        """(agent id, error). Built-in ko save nahi kiya jata."""
        name = " ".join((agent.get("name") or "").split())[:40]
        if not name:
            return "", "Agent ka naam likho."
        tools = _clean_tools(agent.get("tools"))
        if not tools:
            return "", "Kam az kam ek tool chuno."
        custom = self._custom()
        aid = agent.get("id") or ""
        if aid and any(b["id"] == aid for b in BUILTIN):
            return "", "Built-in agent badla nahi ja sakta. Copy bana lo."
        existing = next((a for a in custom if a["id"] == aid), None)
        if existing is None:
            if len(custom) >= MAX_CUSTOM:
                return "", f"Zyada se zyada {MAX_CUSTOM} apne agents."
            aid = "c-" + uuid.uuid4().hex[:8]
            existing = {"id": aid}
            custom.append(existing)
        existing.update(
            name=name,
            description=(agent.get("description") or "").strip()[:200],
            instructions=(agent.get("instructions") or "").strip()[:2000],
            tools=tools,
            model=re.sub(r"\s+", "", agent.get("model") or "")[:100],
        )
        self._write(custom)
        return aid, ""

    def delete(self, agent_id: str) -> None:
        self._write([a for a in self._custom() if a["id"] != agent_id])