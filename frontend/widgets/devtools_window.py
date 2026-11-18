from PyQt6.QtCore import Qt
from PyQt6.QtWebEngineCore import QWebEnginePage
from PyQt6.QtWebEngineWidgets import QWebEngineView
from PyQt6.QtWidgets import QVBoxLayout, QWidget

from frontend.core.profile import get_profile


class DevToolsWindow(QWidget):
    """Ek tab ke liye Chromium DevTools (Elements, Console, Network...) alag window mein."""

    def __init__(self, parent_window, inspected_view):
        # parent dene se main window band hote hi ye bhi band ho jati hai
        super().__init__(parent_window, Qt.WindowType.Window)
        self._inspected = inspected_view
        self.resize(1050, 680)
        self._update_title(inspected_view.title())

        self._view = QWebEngineView(self)
        self._view.setPage(QWebEnginePage(get_profile(), self._view))
        layout = QVBoxLayout(self)
        layout.setContentsMargins(0, 0, 0, 0)
        layout.addWidget(self._view)

        inspected_view.page().setDevToolsPage(self._view.page())
        inspected_view.title_changed.connect(self._update_title)

    def _update_title(self, title: str) -> None:
        self.setWindowTitle(f"DevTools - {title or 'page'}")

    def shutdown(self) -> None:
        self.close()
        self.deleteLater()