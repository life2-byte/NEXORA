from PyQt6.QtCore import QSize, Qt, pyqtSignal
from PyQt6.QtGui import QIcon
from PyQt6.QtWidgets import QHBoxLayout, QTabBar, QToolButton, QWidget

from frontend.assets.icons import get_icon
from frontend.styles.theme import COLORS


class TabStrip(QWidget):
    new_tab_requested = pyqtSignal()
    tab_changed = pyqtSignal(int)
    tab_close_requested = pyqtSignal(int)
    tab_clicked = pyqtSignal(int)

    def __init__(self, parent=None):
        super().__init__(parent)
        self.setObjectName("TabStrip")
        self._close_icon = get_icon("x", COLORS["muted"], hover_color=COLORS["text"])

        layout = QHBoxLayout(self)
        layout.setContentsMargins(10, 8, 10, 0)
        layout.setSpacing(4)

        self.bar = QTabBar()
        self.bar.setObjectName("BrowserTabBar")
        self.bar.setTabsClosable(False)
        self.bar.setMovable(False)
        self.bar.setExpanding(False)
        self.bar.setDrawBase(False)
        self.bar.setUsesScrollButtons(True)
        self.bar.setElideMode(Qt.TextElideMode.ElideRight)
        self.bar.setIconSize(QSize(16, 16))
        self.bar.currentChanged.connect(self.tab_changed.emit)
        self.bar.tabBarClicked.connect(self.tab_clicked.emit)

        self.add_btn = QToolButton()
        self.add_btn.setObjectName("NewTabButton")
        self.add_btn.setIcon(
            get_icon("plus", COLORS["muted"], hover_color=COLORS["text"])
        )
        self.add_btn.setIconSize(QSize(16, 16))
        self.add_btn.setAutoRaise(True)
        self.add_btn.setToolTip("New tab (Ctrl+T)")
        self.add_btn.clicked.connect(self.new_tab_requested.emit)

        layout.addWidget(self.bar)
        layout.addWidget(self.add_btn)
        layout.addStretch(1)

    def add_tab(self, title: str = "New Tab") -> int:
        index = self.bar.addTab(title)

        close_btn = QToolButton()
        close_btn.setObjectName("TabClose")
        close_btn.setIcon(self._close_icon)
        close_btn.setIconSize(QSize(12, 12))
        close_btn.setAutoRaise(True)
        close_btn.setToolTip("Close tab (Ctrl+W)")
        close_btn.clicked.connect(lambda _, b=close_btn: self._on_close_clicked(b))
        self.bar.setTabButton(index, QTabBar.ButtonPosition.RightSide, close_btn)
        return index

    def _on_close_clicked(self, button: QToolButton) -> None:
        for i in range(self.bar.count()):
            if self.bar.tabButton(i, QTabBar.ButtonPosition.RightSide) is button:
                self.tab_close_requested.emit(i)
                return

    def remove_tab(self, index: int) -> None:
        self.bar.removeTab(index)

    def set_title(self, index: int, title: str) -> None:
        if 0 <= index < self.bar.count():
            self.bar.setTabText(index, title)
            self.bar.setTabToolTip(index, title)

    def set_icon(self, index: int, icon: QIcon) -> None:
        if 0 <= index < self.bar.count():
            self.bar.setTabIcon(index, icon)

    def set_current(self, index: int) -> None:
        self.bar.setCurrentIndex(index)

    def current_index(self) -> int:
        return self.bar.currentIndex()

    def count(self) -> int:
        return self.bar.count()