from PyQt6.QtCore import QPoint, QSize, Qt, pyqtSignal
from PyQt6.QtGui import QIcon
from PyQt6.QtWidgets import QHBoxLayout, QTabBar, QToolButton, QWidget

from frontend.assets.icons import get_icon
from frontend.styles.theme import COLORS


PINNED_WIDTH = 44


class _Bar(QTabBar):
    """Pinned tab (tabData == True) sirf icon jitna chhota hota hai. Right-click pe context_requested."""

    context_requested = pyqtSignal(int, QPoint)

    def tabSizeHint(self, index: int) -> QSize:
        size = super().tabSizeHint(index)
        if self.tabData(index) is True:
            size.setWidth(PINNED_WIDTH)
        return size

    def contextMenuEvent(self, event) -> None:
        index = self.tabAt(event.pos())
        if index >= 0:
            self.context_requested.emit(index, event.globalPos())


class TabStrip(QWidget):
    new_tab_requested = pyqtSignal()
    context_requested = pyqtSignal(int, QPoint)
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

        self.bar = _Bar()
        self.bar.context_requested.connect(self.context_requested.emit)
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
            self.bar.setTabText(index, "" if self.is_pinned(index) else title)
            self.bar.setTabToolTip(index, title)

    # ---------- pinned tabs ----------
    def is_pinned(self, index: int) -> bool:
        return 0 <= index < self.bar.count() and self.bar.tabData(index) is True

    def set_pinned(self, index: int, pinned: bool) -> None:
        if not 0 <= index < self.bar.count():
            return
        tooltip = self.bar.tabToolTip(index)
        text = self.bar.tabText(index)
        self.bar.setTabData(index, True if pinned else None)
        if pinned:
            self.bar.setTabText(index, "")
            self.bar.setTabToolTip(index, tooltip or text)
        else:
            self.bar.setTabText(index, tooltip or text or "New Tab")
        button = self.bar.tabButton(index, QTabBar.ButtonPosition.RightSide)
        if button is not None:
            button.setVisible(not pinned)
        self.bar.updateGeometry()

    def move_tab(self, source: int, target: int) -> None:
        self.bar.moveTab(source, target)

    def set_icon(self, index: int, icon: QIcon) -> None:
        if 0 <= index < self.bar.count():
            self.bar.setTabIcon(index, icon)

    def set_current(self, index: int) -> None:
        self.bar.setCurrentIndex(index)

    def current_index(self) -> int:
        return self.bar.currentIndex()

    def count(self) -> int:
        return self.bar.count()