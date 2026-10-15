from PyQt6.QtCore import QSize, pyqtSignal
from PyQt6.QtWidgets import QHBoxLayout, QMenu, QToolButton, QWidget

from frontend.assets.icons import get_icon
from frontend.styles.theme import COLORS


class ToolbarActions(QWidget):
    """Omnibox ke right side ke buttons: bookmark star, downloads, account."""

    bookmark_toggled = pyqtSignal(bool)
    downloads_clicked = pyqtSignal()
    settings_clicked = pyqtSignal()

    def __init__(self, parent=None):
        super().__init__(parent)
        layout = QHBoxLayout(self)
        layout.setContentsMargins(0, 0, 0, 0)
        layout.setSpacing(2)

        self.star_btn = self._make_button("star", "Bookmark this page", checkable=True)
        self.star_btn.toggled.connect(self.bookmark_toggled.emit)

        self.downloads_btn = self._make_button("download", "Downloads")
        self.downloads_btn.clicked.connect(self.downloads_clicked.emit)

        self.account_btn = QToolButton()
        self.account_btn.setObjectName("AccountButton")
        self.account_btn.setIcon(get_icon("user", COLORS["text"]))
        self.account_btn.setIconSize(QSize(18, 18))
        self.account_btn.setToolTip("Account")
        self.account_btn.setPopupMode(QToolButton.ToolButtonPopupMode.InstantPopup)

        menu = QMenu(self.account_btn)
        sign_in = menu.addAction("Sign in (backend ke baad)")
        sign_in.setEnabled(False)
        menu.addSeparator()
        menu.addAction("Settings", self.settings_clicked.emit)
        self.account_btn.setMenu(menu)

        layout.addWidget(self.star_btn)
        layout.addWidget(self.downloads_btn)
        layout.addSpacing(6)
        layout.addWidget(self.account_btn)

    def _make_button(self, icon_name: str, tooltip: str, checkable: bool = False) -> QToolButton:
        btn = QToolButton()
        btn.setObjectName("NavButton")
        btn.setIcon(
            get_icon(
                icon_name,
                COLORS["muted"],
                active_color=COLORS["accent"],
                hover_color=COLORS["text"],
            )
        )
        btn.setIconSize(QSize(18, 18))
        btn.setAutoRaise(True)
        btn.setCheckable(checkable)
        btn.setToolTip(tooltip)
        return btn

    def set_bookmarked(self, value: bool) -> None:
        self.star_btn.blockSignals(True)
        self.star_btn.setChecked(value)
        self.star_btn.blockSignals(False)