from PyQt6.QtCore import pyqtSignal
from PyQt6.QtWidgets import QStackedLayout, QWidget


class TabStack(QWidget):
    """Tabs ka stack. QStackedWidget ki tarah kaam karta hai, lekin background tabs hide nahi hote
    (sab stack hote hain, current upar), taake un ka asli viewport rahe aur agent unhe padh sake."""

    widgetRemoved = pyqtSignal(int)

    def __init__(self, parent=None):
        super().__init__(parent)
        self._layout = QStackedLayout(self)
        self._layout.widgetRemoved.connect(self.widgetRemoved.emit)
        self._layout.setContentsMargins(0, 0, 0, 0)
        self._layout.setStackingMode(QStackedLayout.StackingMode.StackAll)

    def addWidget(self, widget) -> int:
        return self._layout.addWidget(widget)

    def insertWidget(self, index: int, widget) -> int:
        return self._layout.insertWidget(index, widget)

    def setCurrentWidget(self, widget) -> None:
        self._layout.setCurrentWidget(widget)

    def removeWidget(self, widget) -> None:
        self._layout.removeWidget(widget)

    def currentWidget(self):
        return self._layout.currentWidget()

    def currentIndex(self) -> int:
        return self._layout.currentIndex()

    def setCurrentIndex(self, index: int) -> None:
        self._layout.setCurrentIndex(index)

    def indexOf(self, widget) -> int:
        return self._layout.indexOf(widget)

    def count(self) -> int:
        return self._layout.count()

    def widget(self, index: int):
        return self._layout.widget(index)