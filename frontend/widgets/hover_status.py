from PyQt6.QtCore import QEvent, Qt
from PyQt6.QtWidgets import QLabel

from frontend.styles.theme import COLORS


class HoverStatus(QLabel):
    """Link ke upar mouse aaye to neeche-left kone mein URL dikhata hai (Chrome jesa)."""

    def __init__(self, parent):
        super().__init__(parent)
        self.setAttribute(Qt.WidgetAttribute.WA_TransparentForMouseEvents)
        self.setStyleSheet(
            f"background-color: {COLORS['panel']}; color: {COLORS['text']};"
            f"border: 1px solid {COLORS['border']}; border-left: none; border-bottom: none;"
            "border-top-right-radius: 8px; padding: 3px 10px;"
        )
        self.hide()
        parent.installEventFilter(self)  # parent resize ho to apni jagah theek karo

    def show_url(self, url: str) -> None:
        if not url:
            self.hide()
            return
        limit = max(200, int(self.parentWidget().width() * 0.6))
        self.setText(self.fontMetrics().elidedText(url, Qt.TextElideMode.ElideMiddle, limit))
        self.adjustSize()
        self._place()
        self.show()
        self.raise_()

    def _place(self) -> None:
        parent = self.parentWidget()
        self.move(0, parent.height() - self.height())

    def eventFilter(self, obj, event) -> bool:
        if event.type() == QEvent.Type.Resize and self.isVisible():
            self._place()
        return False