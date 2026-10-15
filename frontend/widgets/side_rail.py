from PyQt6.QtCore import QSize, pyqtSignal
from PyQt6.QtWidgets import QButtonGroup, QToolButton, QVBoxLayout, QWidget

from frontend.assets.icons import get_icon
from frontend.styles.theme import COLORS


class SideRail(QWidget):
    item_selected = pyqtSignal(str)

    TOP_ITEMS = [
        ("home", "Home"),
        ("workspace", "Workspace"),
        ("team", "Team"),
        ("files", "Files"),
        ("apps", "Apps"),
    ]
    BOTTOM_ITEMS = [
        ("settings", "Settings"),
    ]

    def __init__(self, parent=None):
        super().__init__(parent)
        self.setObjectName("SideRail")
        self.setFixedWidth(56)

        layout = QVBoxLayout(self)
        layout.setContentsMargins(0, 10, 0, 10)
        layout.setSpacing(6)

        self.group = QButtonGroup(self)
        self.group.setExclusive(True)
        self.buttons = {}

        for name, tooltip in self.TOP_ITEMS:
            layout.addWidget(self._add_item(name, tooltip))

        layout.addStretch(1)

        for name, tooltip in self.BOTTOM_ITEMS:
            layout.addWidget(self._add_item(name, tooltip))

        self.buttons["home"].setChecked(True)

    def _add_item(self, name: str, tooltip: str) -> QToolButton:
        btn = QToolButton()
        btn.setObjectName("RailButton")
        btn.setIcon(get_icon(name, COLORS["muted"], COLORS["accent"]))
        btn.setIconSize(QSize(22, 22))
        btn.setToolTip(tooltip)
        btn.setCheckable(True)
        btn.setFixedSize(56, 44)
        btn.clicked.connect(lambda _, n=name: self.item_selected.emit(n))
        self.group.addButton(btn)
        self.buttons[name] = btn
        return btn

    def select(self, name: str) -> None:
        if name in self.buttons:
            self.buttons[name].setChecked(True)