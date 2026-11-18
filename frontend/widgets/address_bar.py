from PyQt6.QtCore import Qt, pyqtSignal
from PyQt6.QtGui import QAction
from PyQt6.QtWidgets import QLabel, QLineEdit

from frontend.assets.icons import get_icon
from frontend.core.settings_manager import settings
from frontend.styles.theme import COLORS

AGENT_WORD_PREFIXES = ("ask ", "agent ", "ai ")
AGENT_CHAR_PREFIXES = ("/", ">")
TASK_VERBS = {
    "find", "open", "extract", "compare", "summarize", "summarise", "fill",
    "book", "buy", "download", "collect", "list", "scrape", "track", "write",
    "create", "order", "apply", "research", "gather",
}

SECURE_TIP = "Connection is encrypted (HTTPS). This does not mean the site is trustworthy."
INSECURE_TIP = "Not secure: this site uses plain HTTP, so others on the network can read what you send."


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
    if t.startswith("!"):
        return "search"  # dev tools command, AI task nahi
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
    agent_submitted = pyqtSignal(str)  # AI task (sirf jab AI chalu ho)

    def __init__(self, parent=None, ai_enabled: bool = True):
        super().__init__(parent)
        self._window_ai = ai_enabled  # No-AI window mein hamesha False
        self.setObjectName("AddressBar")

        muted, accent = COLORS["muted"], COLORS["accent"]
        self._icons = {
            "empty": get_icon("search", muted),
            "search": get_icon("search", muted),
            "url": get_icon("globe", muted),
            "agent": get_icon("agent", accent),
        }

        self.mode_action = QAction(self)
        self.mode_action.triggered.connect(self._force_agent)
        self.addAction(self.mode_action, QLineEdit.ActionPosition.TrailingPosition)

        # lock / warning: QAction ki jagah seedha chhota label (Qt ke action icons kabhi gayab ho jate the)
        self._sec_pixmaps = {
            "secure": get_icon("lock", muted).pixmap(16, 16),
            "insecure": get_icon("alert", "#f59e0b").pixmap(16, 16),
        }
        self.sec_label = QLabel(self)
        self.sec_label.setFixedSize(18, 18)
        self.sec_label.hide()

        self.textEdited.connect(self._update_mode)
        self.returnPressed.connect(self._on_return)
        settings.changed.connect(self._on_setting)
        self._refresh()

    @property
    def ai_active(self) -> bool:
        return self._window_ai and bool(settings.get("ai_enabled"))

    def _tip(self, mode: str) -> str:
        if self.ai_active:
            return {
                "empty": "Click = ask AI  |  Alt+Enter = ask AI",
                "search": "Web search  (click = ask AI instead)",
                "url": "Open website  (click = ask AI instead)",
                "agent": "AI task  (Enter to run)",
            }[mode]
        return {
            "empty": "Search or open a website (AI is off)",
            "search": "Web search",
            "url": "Open website",
            "agent": "Web search",
        }[mode]

    def _on_setting(self, key: str, _value) -> None:
        if key == "ai_enabled":
            self._refresh()

    def _refresh(self) -> None:
        self.setPlaceholderText(
            "Search, enter a URL, or tell the AI what to do" if self.ai_active else "Search or enter a URL"
        )
        self._update_mode(self.text())

    def _mode(self, text: str) -> str:
        mode = detect_intent(text)
        if mode == "agent" and not self.ai_active:
            return "search"
        return mode

    def _update_mode(self, text: str) -> None:
        mode = self._mode(text)
        self.mode_action.setIcon(self._icons[mode])
        self.mode_action.setToolTip(self._tip(mode))

    def _on_return(self) -> None:
        text = self.text().strip()
        if not text:
            return
        if text.startswith("!"):
            self.url_submitted.emit(text)
            return
        if self._mode(text) == "agent":
            self.agent_submitted.emit(strip_agent_prefix(text))
        else:
            self.url_submitted.emit(text)

    def _force_agent(self) -> None:
        if not self.ai_active:
            return
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

    # ---------- lock / warning icon ----------
    def set_security(self, url: str) -> None:
        low = url.lower()
        if low.startswith("https://"):
            state, tip = "secure", SECURE_TIP
        elif low.startswith("http://"):
            state, tip = "insecure", INSECURE_TIP
        else:
            self.sec_label.hide()
            self.setTextMargins(0, 0, 0, 0)
            return

        self.sec_label.setPixmap(self._sec_pixmaps[state])
        self.sec_label.setToolTip(tip)
        self.setTextMargins(20, 0, 0, 0)  # text icon ke baad shuru ho
        self._place_security_icon()
        self.sec_label.show()
        self.sec_label.raise_()

    def _place_security_icon(self) -> None:
        self.sec_label.move(12, (self.height() - self.sec_label.height()) // 2)

    def resizeEvent(self, event) -> None:
        super().resizeEvent(event)
        self._place_security_icon()