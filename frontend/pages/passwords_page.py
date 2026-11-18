from datetime import datetime

from PyQt6.QtCore import Qt, QTimer
from PyQt6.QtGui import QGuiApplication
from PyQt6.QtWidgets import (
    QHBoxLayout,
    QLabel,
    QLineEdit,
    QMessageBox,
    QPushButton,
    QVBoxLayout,
    QWidget,
)

from frontend.core.passwords import get_vault, host_label
from frontend.pages.base_page import BasePage
from frontend.styles.theme import COLORS


class _Row(QWidget):
    def __init__(self, entry: dict, vault, on_delete, parent=None):
        super().__init__(parent)
        self._entry, self._vault = entry, vault
        self._shown = False

        layout = QHBoxLayout(self)
        layout.setContentsMargins(12, 8, 12, 8)
        layout.setSpacing(10)

        info = QVBoxLayout()
        info.setSpacing(2)
        site = QLabel(host_label(entry["origin"]))
        site.setStyleSheet(f"color:{COLORS['text']}; font-weight:600; background:transparent;")
        who = entry["username"] or "(bina username)"
        stamp = datetime.fromtimestamp(entry["updated"]).strftime("%d %b %Y")
        self.line = QLabel(f"{who}   •   {stamp}")
        self.line.setStyleSheet(f"color:{COLORS['muted']}; background:transparent;")
        info.addWidget(site)
        info.addWidget(self.line)
        layout.addLayout(info, 1)

        self.value = QLabel("")
        self.value.setStyleSheet(f"color:{COLORS['text']}; background:transparent;")
        layout.addWidget(self.value)

        for text, fn in (("Show", self._toggle), ("Copy", self._copy), ("Delete", on_delete)):
            btn = QPushButton(text)
            btn.setObjectName("SettingsButton")
            btn.setCursor(Qt.CursorShape.PointingHandCursor)
            btn.clicked.connect(lambda _=False, f=fn: f())
            layout.addWidget(btn)
            if text == "Show":
                self.show_btn = btn

        self.setStyleSheet(f"_Row {{ background:{COLORS['panel']}; border-radius:8px; }}")
        self.setAttribute(Qt.WidgetAttribute.WA_StyledBackground, True)

    def _toggle(self) -> None:
        if self._shown:
            self._hide()
            return
        password = self._vault.get_password(self._entry["id"])
        if password is None:
            self.value.setText("(decrypt nahi hua)")
            return
        self._shown = True
        self.value.setText(password)
        self.show_btn.setText("Hide")
        QTimer.singleShot(15000, self._hide)  # 15 sec baad khud chhup jata hai

    def _hide(self) -> None:
        self._shown = False
        self.value.setText("")
        self.show_btn.setText("Show")

    def _copy(self) -> None:
        password = self._vault.get_password(self._entry["id"])
        if password is None:
            return
        clipboard = QGuiApplication.clipboard()
        clipboard.setText(password)
        QTimer.singleShot(30000, lambda: clipboard.text() == password and clipboard.clear())  # 30 sec baad clipboard saaf
        self.show_btn.setToolTip("Copy ho gaya (30 sec baad clipboard saaf ho jayega)")


class PasswordsPage(BasePage):
    def __init__(self, parent=None):
        super().__init__("Passwords", "Saved logins. Passwords encrypt hote hain, key system keyring mein rehti hai.", parent)
        self._handle = get_vault()

        self.search = QLineEdit()
        self.search.setObjectName("SettingsInput")
        self.search.setPlaceholderText("Search site ya username")
        self.search.setClearButtonEnabled(True)
        self.body.addWidget(self.search)

        self.list_box = QWidget()
        self.list_layout = QVBoxLayout(self.list_box)
        self.list_layout.setContentsMargins(0, 0, 0, 0)
        self.list_layout.setSpacing(6)
        self.body.addWidget(self.list_box)

        self.never_btn = QPushButton("")
        self.never_btn.setObjectName("SettingsButton")
        self.never_btn.clicked.connect(self._clear_never)
        self.body.addWidget(self.never_btn, 0, Qt.AlignmentFlag.AlignLeft)
        self.body.addStretch(1)

        self._debounce = QTimer(self)
        self._debounce.setSingleShot(True)
        self._debounce.setInterval(200)
        self._debounce.timeout.connect(self.refresh)
        self.search.textChanged.connect(lambda _: self._debounce.start())
        self._handle.changed.connect(self.refresh)
        self.refresh()

    def showEvent(self, event) -> None:
        super().showEvent(event)
        self.refresh()

    def refresh(self) -> None:
        while self.list_layout.count():
            item = self.list_layout.takeAt(0)
            if item.widget() is not None:
                item.widget().deleteLater()

        vault = self._handle.vault
        if not vault.available:
            note = QLabel(f"Password vault chal nahi raha: {vault.error}")
            note.setObjectName("HintLabel")
            note.setWordWrap(True)
            self.list_layout.addWidget(note)
            self.never_btn.hide()
            return

        entries = vault.entries(self.search.text())
        if not entries:
            empty = QLabel("Abhi koi saved password nahi. Kisi site pe login karoge to save karne ka poochega.")
            empty.setObjectName("HintLabel")
            empty.setWordWrap(True)
            self.list_layout.addWidget(empty)
        for entry in entries:
            self.list_layout.addWidget(_Row(entry, vault, lambda e=entry: self._delete(e)))

        count = vault.never_count()
        self.never_btn.setVisible(count > 0)
        self.never_btn.setText(f"'Never save' list saaf karo ({count} sites)")

    def _delete(self, entry: dict) -> None:
        answer = QMessageBox.question(
            self, "Delete password", f"{host_label(entry['origin'])} ka {entry['username'] or 'saved'} password delete karun?"
        )
        if answer == QMessageBox.StandardButton.Yes:
            self._handle.vault.delete(entry["id"])
            self.refresh()

    def _clear_never(self) -> None:
        self._handle.vault.clear_never()
        self.refresh()