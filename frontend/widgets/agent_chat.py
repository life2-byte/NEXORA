from PyQt6.QtCore import Qt, QTimer, pyqtSignal
from PyQt6.QtWidgets import (
    QFrame,
    QHBoxLayout,
    QLabel,
    QLineEdit,
    QPushButton,
    QScrollArea,
    QToolButton,
    QVBoxLayout,
    QWidget,
)

from frontend.styles.theme import COLORS

AUTO_HIDE_MS = 30_000


class AgentChat(QFrame):
    """Sidebar ke opposite (right) side ka chhota chat box. Sirf tab dikhta hai jab agent ko user se kuch kehna ho."""

    text_submitted = pyqtSignal(str)
    close_requested = pyqtSignal()

    def __init__(self, parent=None):
        super().__init__(parent)
        self.setObjectName("AgentChat")
        self.setFixedWidth(340)
        self.setStyleSheet(
            f"""
            QFrame#AgentChat {{ background:{COLORS['panel']}; border:1px solid {COLORS['border']}; border-radius:14px; }}
            QLabel {{ background:transparent; color:{COLORS['text']}; }}
            QLabel#Title {{ font-weight:600; }}
            QLabel#Muted {{ color:{COLORS['muted']}; }}
            QLabel#Agent, QLabel#User, QLabel#Plan, QLabel#Alert {{ padding:8px 10px; border-radius:10px; }}
            QLabel#Agent {{ background:{COLORS['bg']}; }}
            QLabel#Plan {{ background:{COLORS['bg']}; color:{COLORS['muted']}; }}
            QLabel#Alert {{ background:#3b2a12; color:#fcd34d; }}
            QLabel#User {{ background:#17406b; }}
            QLineEdit {{ background:{COLORS['bg']}; color:{COLORS['text']}; border:1px solid {COLORS['border']};
                         border-radius:8px; padding:7px 10px; }}
            QPushButton {{ background:#1a2740; color:{COLORS['text']}; border:1px solid {COLORS['border']};
                           border-radius:8px; padding:7px 12px; }}
            QPushButton:hover {{ border-color:{COLORS['accent']}; }}
            QToolButton {{ background:transparent; color:{COLORS['muted']}; border:none; font-size:14px; }}
            """
        )
        self.hide()

        outer = QVBoxLayout(self)
        outer.setContentsMargins(12, 10, 12, 12)
        outer.setSpacing(8)

        header = QHBoxLayout()
        self.title = QLabel("Agent")
        self.title.setObjectName("Title")
        self.status = QLabel("")
        self.status.setObjectName("Muted")
        close = QToolButton()
        close.setText("✕")
        close.setToolTip("Chhupao (agent kaam karta rahega)")
        close.clicked.connect(self.close_requested.emit)
        header.addWidget(self.title)
        header.addWidget(self.status, 1)
        header.addWidget(close)
        outer.addLayout(header)

        self.scroll = QScrollArea()
        self.scroll.setWidgetResizable(True)
        self.scroll.setFrameShape(QFrame.Shape.NoFrame)
        self.scroll.setHorizontalScrollBarPolicy(Qt.ScrollBarPolicy.ScrollBarAlwaysOff)
        self.scroll.setStyleSheet("background:transparent;")
        holder = QWidget()
        holder.setStyleSheet("background:transparent;")
        self.msgs = QVBoxLayout(holder)
        self.msgs.setContentsMargins(0, 0, 4, 0)
        self.msgs.setSpacing(6)
        self.msgs.addStretch(1)
        self.scroll.setWidget(holder)
        outer.addWidget(self.scroll, 1)

        self.actions = QHBoxLayout()
        self.actions.setSpacing(8)
        outer.addLayout(self.actions)

        self.input = QLineEdit()
        self.input.setPlaceholderText("Jawab likho ya naya kaam do...")
        self.input.returnPressed.connect(self._submit)
        self.input.textEdited.connect(lambda _: self._hide_timer.stop())
        outer.addWidget(self.input)

        self._hide_timer = QTimer(self)
        self._hide_timer.setSingleShot(True)
        self._hide_timer.timeout.connect(self.hide)

    # ---------- API ----------
    def set_status(self, text: str) -> None:
        self.status.setText(text[:50])

    def add(self, text: str, kind: str = "Agent") -> None:
        """kind: Agent | User | Plan | Alert"""
        label = QLabel(text)
        label.setObjectName(kind)
        label.setWordWrap(True)
        label.setTextInteractionFlags(Qt.TextInteractionFlag.TextSelectableByMouse | Qt.TextInteractionFlag.LinksAccessibleByMouse)
        label.setOpenExternalLinks(False)
        label.setMaximumWidth(300)
        self.msgs.insertWidget(self.msgs.count() - 1, label)
        QTimer.singleShot(30, lambda: self.scroll.verticalScrollBar().setValue(self.scroll.verticalScrollBar().maximum()))

    def set_actions(self, buttons: list) -> None:
        """buttons: [(label, callback)]. Khali list = buttons hata do."""
        while self.actions.count():
            item = self.actions.takeAt(0)
            if item.widget() is not None:
                w = item.widget()
                w.setParent(None)
                w.deleteLater()
        for label, cb in buttons:
            b = QPushButton(label)
            b.setCursor(Qt.CursorShape.PointingHandCursor)
            b.clicked.connect(lambda _=False, cb=cb: cb())
            self.actions.addWidget(b)

    def pop_up(self, focus: bool = False) -> None:
        self._hide_timer.stop()
        self.show()
        self.raise_()
        if focus:
            self.input.setFocus()

    def hide_later(self) -> None:
        self._hide_timer.start(AUTO_HIDE_MS)

    def clear(self) -> None:
        while self.msgs.count() > 1:
            item = self.msgs.takeAt(0)
            if item.widget() is not None:
                w = item.widget()
                w.setParent(None)
                w.deleteLater()

    def _submit(self) -> None:
        text = self.input.text().strip()
        if text:
            self.input.clear()
            self.add(text, "User")
            self.text_submitted.emit(text)