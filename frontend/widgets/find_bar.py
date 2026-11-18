from PyQt6.QtCore import Qt, pyqtSignal
from PyQt6.QtWidgets import QHBoxLayout, QLabel, QLineEdit, QToolButton, QWidget

from frontend.styles.theme import COLORS


class _FindInput(QLineEdit):
    next_requested = pyqtSignal()
    prev_requested = pyqtSignal()
    close_requested = pyqtSignal()

    def keyPressEvent(self, event) -> None:
        key = event.key()
        if key in (Qt.Key.Key_Return, Qt.Key.Key_Enter):
            (self.prev_requested if event.modifiers() & Qt.KeyboardModifier.ShiftModifier else self.next_requested).emit()
            return
        if key == Qt.Key.Key_Escape:
            self.close_requested.emit()
            return
        super().keyPressEvent(event)


class FindBar(QWidget):
    """Ctrl+F wali bar (page ke andar nahi, Qt widget hai)."""

    find_requested = pyqtSignal(str, bool, bool)  # text, forward, case sensitive
    closed = pyqtSignal()

    def __init__(self, parent=None):
        super().__init__(parent)
        self.setObjectName("FindBar")
        self.hide()
        self.setStyleSheet(
            f"""
            QWidget#FindBar {{ background-color: {COLORS['panel']}; border-bottom: 1px solid {COLORS['border']}; }}
            QWidget#FindBar QLineEdit {{
                background-color: {COLORS['bg']}; color: {COLORS['text']};
                border: 1px solid {COLORS['border']}; border-radius: 8px; padding: 5px 10px;
            }}
            QWidget#FindBar QLineEdit:focus {{ border: 1px solid {COLORS['accent']}; }}
            QWidget#FindBar QLabel {{ color: {COLORS['muted']}; background: transparent; }}
            QWidget#FindBar QToolButton {{
                color: {COLORS['text']}; background: transparent; border: none;
                border-radius: 6px; padding: 4px 8px;
            }}
            QWidget#FindBar QToolButton:hover {{ background-color: {COLORS['border']}; }}
            QWidget#FindBar QToolButton:checked {{ color: {COLORS['accent']}; }}
            """
        )

        layout = QHBoxLayout(self)
        layout.setContentsMargins(14, 6, 10, 6)
        layout.setSpacing(6)

        self.input = _FindInput()
        self.input.setPlaceholderText("Find in page")
        self.input.setFixedWidth(280)
        self.count = QLabel("")
        self.count.setMinimumWidth(80)

        self.prev_btn = QToolButton()
        self.prev_btn.setText("▲")
        self.prev_btn.setToolTip("Previous (Shift+Enter)")
        self.next_btn = QToolButton()
        self.next_btn.setText("▼")
        self.next_btn.setToolTip("Next (Enter)")
        self.case_btn = QToolButton()
        self.case_btn.setText("Aa")
        self.case_btn.setToolTip("Match case")
        self.case_btn.setCheckable(True)
        close_btn = QToolButton()
        close_btn.setText("✕")
        close_btn.setToolTip("Close (Esc)")

        layout.addWidget(self.input)
        layout.addWidget(self.count)
        layout.addWidget(self.prev_btn)
        layout.addWidget(self.next_btn)
        layout.addWidget(self.case_btn)
        layout.addStretch(1)
        layout.addWidget(close_btn)

        self.input.textChanged.connect(lambda _: self._emit(True))
        self.input.next_requested.connect(lambda: self._emit(True))
        self.input.prev_requested.connect(lambda: self._emit(False))
        self.input.close_requested.connect(self.close_bar)
        self.next_btn.clicked.connect(lambda: self._emit(True))
        self.prev_btn.clicked.connect(lambda: self._emit(False))
        self.case_btn.toggled.connect(lambda _: self._emit(True))
        close_btn.clicked.connect(self.close_bar)

    def _emit(self, forward: bool) -> None:
        text = self.input.text()
        if not text:
            self.count.setText("")
        self.find_requested.emit(text, forward, self.case_btn.isChecked())

    def open_bar(self, preset: str = "") -> None:
        self.show()
        if preset:
            self.input.setText(preset)
        self.input.setFocus()
        self.input.selectAll()
        if self.input.text():
            self._emit(True)

    def close_bar(self) -> None:
        self.hide()
        self.closed.emit()

    def set_result(self, active: int, total: int) -> None:
        if not self.input.text():
            self.count.setText("")
        elif total == 0:
            self.count.setText("No results")
        else:
            self.count.setText(f"{active} / {total}")