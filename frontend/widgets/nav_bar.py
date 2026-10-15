from PyQt6.QtCore import QSize, pyqtSignal
from PyQt6.QtWidgets import QHBoxLayout, QToolButton, QWidget

from frontend.assets.icons import get_icon
from frontend.styles.theme import COLORS


def _icon(name: str):
    return get_icon(name, COLORS["muted"], hover_color=COLORS["text"])


class NavBar(QWidget):
    back_clicked = pyqtSignal()
    forward_clicked = pyqtSignal()
    reload_clicked = pyqtSignal()
    stop_clicked = pyqtSignal()

    def __init__(self, parent=None):
        super().__init__(parent)
        self._loading = False
        self._icon_reload = _icon("refresh")
        self._icon_stop = _icon("x")

        layout = QHBoxLayout(self)
        layout.setContentsMargins(0, 0, 0, 0)
        layout.setSpacing(2)

        self.back_btn = self._make_button("arrow-left", "Back")
        self.forward_btn = self._make_button("arrow-right", "Forward")
        self.reload_btn = self._make_button("refresh", "Reload")

        self.back_btn.clicked.connect(self.back_clicked.emit)
        self.forward_btn.clicked.connect(self.forward_clicked.emit)
        self.reload_btn.clicked.connect(self._on_reload_clicked)

        layout.addWidget(self.back_btn)
        layout.addWidget(self.forward_btn)
        layout.addWidget(self.reload_btn)

    def _make_button(self, icon_name: str, tooltip: str) -> QToolButton:
        btn = QToolButton()
        btn.setObjectName("NavButton")
        btn.setIcon(_icon(icon_name))
        btn.setIconSize(QSize(18, 18))
        btn.setAutoRaise(True)
        btn.setToolTip(tooltip)
        return btn

    def _on_reload_clicked(self) -> None:
        if self._loading:
            self.stop_clicked.emit()
        else:
            self.reload_clicked.emit()

    def set_loading(self, loading: bool) -> None:
        self._loading = loading
        self.reload_btn.setIcon(self._icon_stop if loading else self._icon_reload)
        self.reload_btn.setToolTip("Stop" if loading else "Reload")