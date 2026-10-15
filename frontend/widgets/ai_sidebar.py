from PyQt6.QtCore import Qt, QTimer, pyqtSignal
from PyQt6.QtWidgets import (
    QFrame,
    QHBoxLayout,
    QLabel,
    QLineEdit,
    QScrollArea,
    QToolButton,
    QVBoxLayout,
    QWidget,
)


class AiSidebar(QWidget):
    prompt_submitted = pyqtSignal(str)
    close_requested = pyqtSignal()

    def __init__(self, parent=None):
        super().__init__(parent)
        self.setObjectName("AiSidebar")
        self.setFixedWidth(320)

        layout = QVBoxLayout(self)
        layout.setContentsMargins(12, 12, 12, 12)
        layout.setSpacing(12)

        # ---------- header ----------
        header = QHBoxLayout()
        title = QLabel("Agent")
        title.setObjectName("AgentTitle")
        close_btn = QToolButton()
        close_btn.setObjectName("PanelClose")
        close_btn.setText("✕")
        close_btn.setToolTip("Hide panel (Ctrl+J)")
        close_btn.clicked.connect(self.close_requested.emit)
        header.addWidget(title)
        header.addStretch(1)
        header.addWidget(close_btn)
        layout.addLayout(header)

        # ---------- status card ----------
        card = QFrame()
        card.setObjectName("StatusCard")
        card_layout = QHBoxLayout(card)
        card_layout.setContentsMargins(12, 10, 12, 10)
        card_layout.setSpacing(10)

        avatar = QLabel("A")
        avatar.setObjectName("AgentAvatar")
        avatar.setFixedSize(36, 36)
        avatar.setAlignment(Qt.AlignmentFlag.AlignCenter)

        info = QVBoxLayout()
        info.setSpacing(2)
        self.agent_name = QLabel("Browser Agent")
        self.agent_name.setObjectName("AgentName")
        self.status_label = QLabel()
        self.status_label.setObjectName("StatusText")
        self.status_label.setTextFormat(Qt.TextFormat.RichText)
        info.addWidget(self.agent_name)
        info.addWidget(self.status_label)

        card_layout.addWidget(avatar)
        card_layout.addLayout(info, 1)
        layout.addWidget(card)
        self.set_status("Idle", "#7f8ba3")

        # ---------- messages ----------
        self.scroll = QScrollArea()
        self.scroll.setObjectName("Messages")
        self.scroll.setWidgetResizable(True)
        self.scroll.setFrameShape(QFrame.Shape.NoFrame)
        self.scroll.setHorizontalScrollBarPolicy(Qt.ScrollBarPolicy.ScrollBarAlwaysOff)

        self.messages_container = QWidget()
        self.messages_container.setObjectName("MessagesContainer")
        self.messages_layout = QVBoxLayout(self.messages_container)
        self.messages_layout.setContentsMargins(0, 0, 4, 0)
        self.messages_layout.setSpacing(8)
        self.messages_layout.addStretch(1)
        self.scroll.setWidget(self.messages_container)
        layout.addWidget(self.scroll, 1)

        # ---------- input ----------
        input_row = QHBoxLayout()
        input_row.setSpacing(8)

        self.input = QLineEdit()
        self.input.setObjectName("PromptInput")
        self.input.setPlaceholderText("Enter agent prompt...")
        self.input.returnPressed.connect(self._submit)

        send_btn = QToolButton()
        send_btn.setObjectName("SendButton")
        send_btn.setText("➤")
        send_btn.setToolTip("Send")
        send_btn.clicked.connect(self._submit)

        input_row.addWidget(self.input, 1)
        input_row.addWidget(send_btn)
        layout.addLayout(input_row)

        self.add_agent_message(
            "Hi! Main tera browser agent hoon. Abhi demo mode mein hoon, backend baad mein judega."
        )

    # ---------- public API ----------
    def set_status(self, text: str, color: str = "#22c55e") -> None:
        self.status_label.setText(f"<span style='color:{color}'>●</span>&nbsp;{text}")

    def add_user_message(self, text: str) -> None:
        self._add_bubble(text, "user")

    def add_agent_message(self, text: str) -> None:
        self._add_bubble(text, "agent")

    def focus_input(self) -> None:
        self.input.setFocus()

    # ---------- internals ----------
    def _submit(self) -> None:
        text = self.input.text().strip()
        if not text:
            return
        self.input.clear()
        self.add_user_message(text)
        self.prompt_submitted.emit(text)

    def _add_bubble(self, text: str, role: str) -> None:
        bubble = QLabel(text)
        bubble.setObjectName("UserBubble" if role == "user" else "AgentBubble")
        bubble.setWordWrap(True)
        bubble.setMaximumWidth(240)
        bubble.setTextInteractionFlags(Qt.TextInteractionFlag.TextSelectableByMouse)

        row = QHBoxLayout()
        row.setContentsMargins(0, 0, 0, 0)
        if role == "user":
            row.addStretch(1)
            row.addWidget(bubble)
        else:
            row.addWidget(bubble)
            row.addStretch(1)

        wrapper = QWidget()
        wrapper.setLayout(row)
        self.messages_layout.insertWidget(self.messages_layout.count() - 1, wrapper)
        QTimer.singleShot(30, self._scroll_to_bottom)

    def _scroll_to_bottom(self) -> None:
        bar = self.scroll.verticalScrollBar()
        bar.setValue(bar.maximum())