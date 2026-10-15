from PyQt6.QtCore import Qt, pyqtSignal
from PyQt6.QtGui import QAction
from PyQt6.QtWidgets import QLineEdit

from frontend.assets.icons import get_icon
from frontend.styles.theme import COLORS

AGENT_WORD_PREFIXES = ("ask ", "agent ", "ai ")
AGENT_CHAR_PREFIXES = ("/", ">")
TASK_VERBS = {
    "find", "open", "extract", "compare", "summarize", "summarise", "fill",
    "book", "buy", "download", "collect", "list", "scrape", "track", "write",
    "create", "order", "apply", "research", "gather",
}


def looks_like_url(text: str) -> bool:
    low = text.lower()
    if low.startswith(("http://", "https://", "file://", "localhost")):
        return True
    return " " not in text and "." in text


def detect_intent(text: str) -> str:
    """Return 'url', 'search', 'agent' ya 'empty'."""
    t = text.strip()
    if not t:
        return "empty"
    low = t.lower()
    if low.startswith(AGENT_WORD_PREFIXES) or t[0] in AGENT_CHAR_PREFIXES:
        return "agent"
    if looks_like_url(t):
        return "url"
    words = low.split()
    if words[0] in TASK_VERBS and len(words) >= 3:
        return "agent"
    if len(words) >= 8:
        return "agent"
    return "search"


def strip_agent_prefix(text: str) -> str:
    t = text.strip()
    low = t.lower()
    for p in AGENT_WORD_PREFIXES:
        if low.startswith(p):
            return t[len(p):].strip()
    if t and t[0] in AGENT_CHAR_PREFIXES:
        return t[1:].strip()
    return t


class AddressBar(QLineEdit):
    url_submitted = pyqtSignal(str)    # website ya normal search
    agent_submitted = pyqtSignal(str)  # AI task

    def __init__(self, parent=None):
        super().__init__(parent)
        self.setObjectName("AddressBar")
        self.setPlaceholderText("Search, enter a URL, or tell the AI what to do")

        muted, accent = COLORS["muted"], COLORS["accent"]
        self._icons = {
            "empty": get_icon("search", muted),
            "search": get_icon("search", muted),
            "url": get_icon("globe", muted),
            "agent": get_icon("agent", accent),
        }
        self._tips = {
            "empty": "Click = ask AI  |  Alt+Enter = ask AI",
            "search": "Web search  (click = ask AI instead)",
            "url": "Open website  (click = ask AI instead)",
            "agent": "AI task  (Enter to run)",
        }

        self.mode_action = QAction(self)
        self.mode_action.triggered.connect(self._force_agent)
        self.addAction(self.mode_action, QLineEdit.ActionPosition.TrailingPosition)

        self.textEdited.connect(self._update_mode)
        self.returnPressed.connect(self._on_return)
        self._update_mode("")

    def _update_mode(self, text: str) -> None:
        mode = detect_intent(text)
        self.mode_action.setIcon(self._icons[mode])
        self.mode_action.setToolTip(self._tips[mode])

    def _on_return(self) -> None:
        text = self.text().strip()
        if not text:
            return
        if detect_intent(text) == "agent":
            self.agent_submitted.emit(strip_agent_prefix(text))
        else:
            self.url_submitted.emit(text)

    def _force_agent(self) -> None:
        task = strip_agent_prefix(self.text())
        if task:
            self.agent_submitted.emit(task)
        else:
            self.setFocus()

    def keyPressEvent(self, event) -> None:
        is_enter = event.key() in (Qt.Key.Key_Return, Qt.Key.Key_Enter)
        if is_enter and event.modifiers() & Qt.KeyboardModifier.AltModifier:
            self._force_agent()
            return
        super().keyPressEvent(event)

    def set_url(self, url: str) -> None:
        if self.hasFocus():
            return
        self.setText(url)
        self.setCursorPosition(0)
        self._update_mode(url)