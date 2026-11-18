from PyQt6.QtCore import QRectF, QSize, Qt, pyqtSignal
from PyQt6.QtGui import QColor, QFont, QIcon, QPainter, QPixmap
from PyQt6.QtWidgets import (
    QButtonGroup,
    QDialog,
    QDialogButtonBox,
    QHBoxLayout,
    QLabel,
    QLineEdit,
    QMenu,
    QMessageBox,
    QPushButton,
    QVBoxLayout,
    QWidget,
)

from frontend.core import profiles, single_instance


def avatar_icon(name: str, color: str, size: int = 64) -> QIcon:
    """Rang wala gol dabba jis mein naam ka pehla harf hota hai."""
    pixmap = QPixmap(size, size)
    pixmap.fill(Qt.GlobalColor.transparent)
    painter = QPainter(pixmap)
    painter.setRenderHint(QPainter.RenderHint.Antialiasing)
    painter.setBrush(QColor(color))
    painter.setPen(Qt.PenStyle.NoPen)
    painter.drawEllipse(QRectF(2, 2, size - 4, size - 4))
    painter.setPen(QColor("#0b1220"))
    font = QFont()
    font.setBold(True)
    font.setPixelSize(int(size * 0.5))
    painter.setFont(font)
    painter.drawText(QRectF(0, 0, size, size), Qt.AlignmentFlag.AlignCenter, (name.strip()[:1] or "?").upper())
    painter.end()
    return QIcon(pixmap)


class ProfileDialog(QDialog):
    """Naya profile banane ya maujooda ka naam/rang badalne ki window."""

    def __init__(self, title: str, name: str = "", color: str = "", parent=None):
        super().__init__(parent)
        self.setWindowTitle(title)
        self.setMinimumWidth(360)

        self.name = QLineEdit(name)
        self.name.setMaxLength(30)
        self.name.setPlaceholderText("Profile ka naam (jese Work, Personal)")

        self._color = color or profiles.COLORS[0]
        swatches = QHBoxLayout()
        swatches.setSpacing(6)
        self._group = QButtonGroup(self)
        for c in profiles.COLORS:
            btn = QPushButton()
            btn.setCheckable(True)
            btn.setFixedSize(28, 28)
            btn.setCursor(Qt.CursorShape.PointingHandCursor)
            btn.setStyleSheet(
                f"QPushButton {{ background:{c}; border-radius:14px; border:2px solid transparent; }}"
                f"QPushButton:checked {{ border:2px solid #ffffff; }}"
            )
            btn.setChecked(c == self._color)
            btn.clicked.connect(lambda _=False, col=c: self._pick(col))
            self._group.addButton(btn)
            swatches.addWidget(btn)
        swatches.addStretch(1)

        buttons = QDialogButtonBox(QDialogButtonBox.StandardButton.Save | QDialogButtonBox.StandardButton.Cancel)
        buttons.accepted.connect(self._accept)
        buttons.rejected.connect(self.reject)

        layout = QVBoxLayout(self)
        layout.addWidget(QLabel("Naam"))
        layout.addWidget(self.name)
        layout.addWidget(QLabel("Rang"))
        layout.addLayout(swatches)
        layout.addWidget(buttons)

    def _pick(self, color: str) -> None:
        self._color = color

    def _accept(self) -> None:
        if not self.name.text().strip():
            QMessageBox.warning(self, "Profile", "Naam likhna zaroori hai.")
            return
        self.accept()

    def values(self) -> tuple[str, str]:
        return self.name.text().strip(), self._color


class ProfileMenu(QMenu):
    """Top-right avatar ka menu: profiles ki list, switch, add, edit, delete."""

    edited = pyqtSignal()  # naam/rang badla, avatar aur window title refresh karo
    settings_requested = pyqtSignal()

    def __init__(self, parent: QWidget):
        super().__init__(parent)
        self._owner = parent
        self.aboutToShow.connect(self._rebuild)

    def _rebuild(self) -> None:
        self.clear()
        me = profiles.current_profile()
        others = [p for p in profiles.list_profiles() if p["id"] != me["id"]]

        header = self.addAction(avatar_icon(me["name"], me["color"]), f"{me['name']} (is window ka profile)")
        header.setEnabled(False)
        self.addAction("Edit this profile...", self._edit_current)
        self.addSeparator()

        for p in others:
            running = profiles.is_running(p["id"])
            label = f"{p['name']}  (khula hua)" if running else p["name"]
            self.addAction(avatar_icon(p["name"], p["color"]), label, lambda pid=p["id"]: self._open(pid))

        self.addAction("Add profile...", self._add)
        deletable = [p for p in others if p["id"] != profiles.DEFAULT_ID]
        if deletable:
            sub = self.addMenu("Delete profile")
            for p in deletable:
                sub.addAction(avatar_icon(p["name"], p["color"]), p["name"], lambda pid=p["id"], n=p["name"]: self._delete(pid, n))
        self.addSeparator()
        self.addAction("Settings", self.settings_requested.emit)

    # ---------- actions ----------
    def _open(self, profile_id: str) -> None:
        if profiles.is_running(profile_id):
            if not single_instance.forward([], profile_id):  # khuli window ko samne le aao
                QMessageBox.information(self._owner, "Profile", "Ye profile pehle se khula hua hai.")
            return
        if not profiles.launch(profile_id):
            QMessageBox.warning(self._owner, "Profile", "Profile start nahi ho saka.")

    def _add(self) -> None:
        dialog = ProfileDialog("Add profile", parent=self._owner)
        if dialog.exec() == QDialog.DialogCode.Accepted:
            name, color = dialog.values()
            self._open(profiles.add_profile(name, color))

    def _edit_current(self) -> None:
        me = profiles.current_profile()
        dialog = ProfileDialog("Edit profile", me["name"], me["color"], self._owner)
        if dialog.exec() == QDialog.DialogCode.Accepted:
            name, color = dialog.values()
            profiles.update_profile(me["id"], name, color)
            self.edited.emit()

    def _delete(self, profile_id: str, name: str) -> None:
        answer = QMessageBox.question(
            self._owner,
            "Delete profile",
            f"'{name}' ka sara data (cookies, history, bookmarks, settings) hamesha ke liye delete ho jayega. Pakka?",
        )
        if answer != QMessageBox.StandardButton.Yes:
            return
        error = profiles.delete_profile(profile_id)
        if error:
            QMessageBox.warning(self._owner, "Profile", error)