from PyQt6.QtCore import Qt
from PyQt6.QtWidgets import QDialog, QLabel, QLineEdit, QListWidget, QListWidgetItem, QVBoxLayout

from frontend.styles.theme import COLORS


class TabSearch(QDialog):
    """Ctrl+Shift+A: khuli hui tabs mein dhundo, Enter se wahan jao."""

    def __init__(self, entries: list, parent=None):
        """entries = [(tab index, title, url)]"""
        super().__init__(parent)
        self.setWindowFlags(Qt.WindowType.Popup | Qt.WindowType.FramelessWindowHint)
        self.setMinimumWidth(520)
        self.setStyleSheet(
            f"""
            QDialog {{ background:{COLORS['panel']}; border:1px solid {COLORS['border']}; border-radius:10px; }}
            QLineEdit {{ background:{COLORS['bg']}; color:{COLORS['text']}; border:1px solid {COLORS['border']};
                        border-radius:8px; padding:8px 10px; }}
            QLineEdit:focus {{ border:1px solid {COLORS['accent']}; }}
            QListWidget {{ background:transparent; color:{COLORS['text']}; border:none; outline:none; }}
            QListWidget::item {{ padding:7px 8px; border-radius:6px; }}
            QListWidget::item:selected {{ background:{COLORS['border']}; color:{COLORS['text']}; }}
            QLabel {{ color:{COLORS['muted']}; }}
            """
        )
        self._entries = entries
        self.chosen = -1

        self.input = QLineEdit()
        self.input.setPlaceholderText("Search open tabs")
        self.list = QListWidget()
        self.list.setMinimumHeight(260)
        self.empty = QLabel("Koi tab nahi mili.")
        self.empty.hide()

        layout = QVBoxLayout(self)
        layout.setContentsMargins(10, 10, 10, 10)
        layout.addWidget(self.input)
        layout.addWidget(self.list)
        layout.addWidget(self.empty)

        self.input.textChanged.connect(self._fill)
        self.input.returnPressed.connect(self._accept_current)
        self.list.itemActivated.connect(lambda _item: self._accept_current())
        self.list.itemClicked.connect(lambda _item: self._accept_current())
        self.input.installEventFilter(self)
        self._fill("")

    def eventFilter(self, obj, event) -> bool:
        if obj is self.input and event.type() == event.Type.KeyPress:
            key = event.key()
            if key in (Qt.Key.Key_Down, Qt.Key.Key_Up):
                step = 1 if key == Qt.Key.Key_Down else -1
                row = max(0, min(self.list.count() - 1, self.list.currentRow() + step))
                self.list.setCurrentRow(row)
                return True
        return super().eventFilter(obj, event)

    def _fill(self, text: str) -> None:
        q = text.strip().lower()
        self.list.clear()
        for index, title, url in self._entries:
            if q and q not in title.lower() and q not in url.lower():
                continue
            item = QListWidgetItem(f"{title or 'New Tab'}\n{url}")
            item.setData(Qt.ItemDataRole.UserRole, index)
            self.list.addItem(item)
        if self.list.count():
            self.list.setCurrentRow(0)
        self.empty.setVisible(self.list.count() == 0)

    def _accept_current(self) -> None:
        item = self.list.currentItem()
        if item is not None:
            self.chosen = int(item.data(Qt.ItemDataRole.UserRole))
            self.accept()

    def show_centered(self, window) -> int:
        """Window ke upar-beech mein kholo; chuni hui tab ka index (ya -1) wapas deta hai."""
        geo = window.geometry()
        self.adjustSize()
        self.move(geo.center().x() - self.width() // 2, geo.top() + 90)
        self.input.setFocus()
        self.exec()
        return self.chosen