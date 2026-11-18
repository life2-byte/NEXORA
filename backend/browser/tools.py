from abc import ABC, abstractmethod
from typing import Any, Optional


def _spec(name: str, description: str, params: Optional[dict] = None, required=()) -> dict:
    return {
        "name": name,
        "description": description,
        "parameters": {"type": "object", "properties": params or {}, "required": list(required)},
    }


_TAB = {"type": "string", "description": "Tab id like t2. Omit to use the tab the user is looking at."}

# LLM ko ye list dikhayenge (baad mein provider ke format mein badal jayegi)
TOOL_SPECS = [
    _spec("list_tabs", "List all open tabs with their ids, titles and urls."),
    _spec(
        "new_tab",
        "Open a new tab and load a url. Opens in the background by default.",
        {
            "url": {"type": "string", "description": "Address or search text to open."},
            "activate": {"type": "boolean", "description": "Show the tab to the user. Default false."},
        },
        ["url"],
    ),
    _spec("switch_tab", "Show a tab to the user.", {"tab_id": _TAB}, ["tab_id"]),
    _spec("close_tab", "Close a tab.", {"tab_id": _TAB}, ["tab_id"]),
    _spec(
        "read_page",
        "Snapshot of a page: headings, text, links, buttons and inputs with ids like e12. "
        "Pass a goal so the most relevant elements come first.",
        {
            "goal": {"type": "string", "description": "What you are trying to do on this page."},
            "scope": {"type": "string", "enum": ["viewport", "page"], "description": "Default viewport."},
            "tab_id": _TAB,
        },
    ),
    _spec(
        "find",
        "Find elements on the page whose text, link or placeholder contains the given words.",
        {"query": {"type": "string"}, "tab_id": _TAB},
        ["query"],
    ),
    _spec(
        "click",
        "Click an element by id (from read_page or find).",
        {"element_id": {"type": "string"}, "tab_id": _TAB},
        ["element_id"],
    ),
    _spec(
        "type_text",
        "Type text into an input, textarea or dropdown by id. submit=true also presses Enter. "
        "Never works on password fields (the user fills those).",
        {
            "element_id": {"type": "string"},
            "text": {"type": "string"},
            "submit": {"type": "boolean"},
            "tab_id": _TAB,
        },
        ["element_id", "text"],
    ),
    _spec(
        "scroll",
        "Scroll the page.",
        {
            "direction": {"type": "string", "enum": ["down", "up", "top", "bottom"]},
            "tab_id": _TAB,
        },
    ),
    _spec(
        "nav",
        "Browser history: go back, go forward or reload the page.",
        {"action": {"type": "string", "enum": ["back", "forward", "reload"]}, "tab_id": _TAB},
        ["action"],
    ),
    _spec(
        "wait",
        "Wait a few seconds (page loading, animation, something that needs time).",
        {"seconds": {"type": "number", "description": "1 to 10. Default 2."}},
    ),
    _spec(
        "press_keys",
        "Real keyboard input to the focused element of the page (works in editors like Google Docs, games, canvas apps). "
        "Use text to type characters like a person, or key for one key or shortcut such as Enter, Tab, Escape, "
        "Backspace, ArrowDown, Ctrl+A, Ctrl+Enter. Click the target first (click or click_at).",
        {
            "text": {"type": "string", "description": "Characters to type."},
            "key": {"type": "string", "description": "One key or combo, e.g. Enter or Ctrl+B."},
            "tab_id": _TAB,
        },
    ),
    _spec(
        "screenshot",
        "Take a picture of the tab (for canvas, games, editors, odd layouts where read_page is not enough). "
        "The picture has yellow pixel numbers on its top and left edges; click_at uses those numbers. "
        "To see a small part in more detail, pass region_x/y/width/height (in the pixel numbers of the last picture). "
        "If nothing changed since the last picture you are told so instead of getting it again.",
        {
            "tab_id": _TAB,
            "region_x": {"type": "integer"}, "region_y": {"type": "integer"},
            "region_width": {"type": "integer"}, "region_height": {"type": "integer"},
        },
    ),
    _spec(
        "click_at",
        "Real mouse click at pixel coordinates of the LAST screenshot (x from left, y from top). "
        "Use only when no element id works, e.g. on canvas.",
        {"x": {"type": "integer"}, "y": {"type": "integer"}, "double": {"type": "boolean"}, "tab_id": _TAB},
        ["x", "y"],
    ),
    _spec(
        "page_api",
        "Read the data the site itself loads. Without url: lists recent fetch/XHR calls of the page. With url "
        "(same site only, GET): returns the shortened JSON. Often cheaper and more exact than reading the page.",
        {"url": {"type": "string"}, "tab_id": _TAB},
    ),
    _spec(
        "go",
        "Load a url or search text in a tab.",
        {"target": {"type": "string"}, "tab_id": _TAB},
        ["target"],
    ),
]

TOOL_NAMES = {spec["name"] for spec in TOOL_SPECS}


def format_tabs(infos: list) -> str:
    if not infos:
        return "TABS: none"
    lines = []
    for t in infos:
        mark = "*" if t["active"] else " "
        loading = " (loading)" if t.get("loading") else ""
        lines.append(f'{mark} {t["id"]} "{t["title"]}" {t["url"]}{loading}')
    return "TABS (* = visible to the user):\n" + "\n".join(lines)


class BrowserTools(ABC):
    """Har method ek text observation wapas deta hai ('OK ...' ya 'FAILED ...').
    Methods blocking hain: agent ke worker thread se chalao, GUI thread se nahi."""

    @abstractmethod
    def list_tabs(self) -> str: ...

    @abstractmethod
    def new_tab(self, url: str = "", activate: bool = False) -> str: ...

    @abstractmethod
    def switch_tab(self, tab_id: str) -> str: ...

    @abstractmethod
    def close_tab(self, tab_id: str) -> str: ...

    @abstractmethod
    def read_page(self, tab_id: Optional[str] = None, goal: str = "", scope: str = "viewport") -> str: ...

    @abstractmethod
    def find(self, query: str, tab_id: Optional[str] = None) -> str: ...

    @abstractmethod
    def click(self, element_id: str, tab_id: Optional[str] = None) -> str: ...

    @abstractmethod
    def type_text(
        self, element_id: str, text: str, submit: bool = False, tab_id: Optional[str] = None
    ) -> str: ...

    @abstractmethod
    def scroll(self, direction: str = "down", tab_id: Optional[str] = None) -> str: ...

    def wait(self, seconds: float = 2) -> str:
        import time

        try:
            secs = min(max(float(seconds), 0.5), 10.0)
        except (TypeError, ValueError):
            secs = 2.0
        time.sleep(secs)
        return f"OK waited {secs:g}s"

    @abstractmethod
    def press_keys(self, text: str = "", key: str = "", tab_id: Optional[str] = None) -> str: ...

    @abstractmethod
    def screenshot(self, tab_id: Optional[str] = None, region_x: Optional[int] = None, region_y: Optional[int] = None,
                   region_width: Optional[int] = None, region_height: Optional[int] = None) -> str: ...

    @abstractmethod
    def page_api(self, url: str = "", tab_id: Optional[str] = None) -> str: ...

    @abstractmethod
    def click_at(self, x: int, y: int, double: bool = False, tab_id: Optional[str] = None) -> str: ...

    def pop_images(self) -> list:
        """Naye screenshots (base64 jpeg), ek baar. Sirf RAM mein - disk par kuch nahi likha jata."""
        return []

    @abstractmethod
    def nav(self, action: str, tab_id: Optional[str] = None) -> str: ...

    @abstractmethod
    def go(self, target: str, tab_id: Optional[str] = None) -> str: ...


def dispatch(tools: BrowserTools, name: str, args: dict[str, Any]) -> str:
    """LLM ke tool call (naam + arguments) ko sahi method se jodta hai. Kabhi crash nahi karta."""
    if name not in TOOL_NAMES:
        return f"FAILED: unknown tool '{name}'. Available: {', '.join(sorted(TOOL_NAMES))}"
    try:
        return getattr(tools, name)(**(args or {}))
    except TypeError as e:
        return f"FAILED {name}: bad arguments ({e})"
    except Exception as e:  # tool ki ghalti agent ko saaf text mein milni chahiye
        return f"FAILED {name}: {e}"