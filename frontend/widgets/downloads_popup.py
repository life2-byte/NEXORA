from PyQt6.QtCore import QPoint, Qt, QTimer, QUrl, pyqtSignal
from PyQt6.QtGui import QDesktopServices
from PyQt6.QtWidgets import (
    QFrame,
    QHBoxLayout,
    QLabel,
    QProgressBar,
    QPushButton,
    QVBoxLayout,
    QWidget,
)

from frontend.core.downloads import get_download_manager
from frontend.pages.downloads_page import _fmt
from frontend.pages.history_page import _elide

MAX_ROWS = 3


def _status_text(item: dict) -> str:
    state = item["state"]
    if state == "downloading":
        if item["total"] > 0:
            pct = item["received"] * 100 // item["total"]
            return f"{pct}%  -  {_fmt(item['received'])} of {_fmt(item['total'])}"
        return f"{_fmt(item['received'])} downloaded"
    if state == "done":
        return f"Done  -  {_fmt(item['total'] or item['received'])}"
    if state == "missing":
        return "File was moved or deleted"
    return "Cancelled" if state == "cancelled" else "Failed"


def _small_button(text: str, callback) -> QPushButton:
    btn = QPushButton(text)
    btn.setObjectName("SettingsButton")
    btn.setCursor(Qt.CursorShape.PointingHandCursor)
    btn.setFixedHeight(26)
    btn.clicked.connect(lambda _=False: callback())
    return btn


class DownloadsPopup(QFrame):
    """Toolbar ke download icon ke neeche chhota popup (Chrome jesa). Window ke andar float karta hai."""

    show_all_requested = pyqtSignal()

    def __init__(self, parent: QWidget):
        super().__init__(parent)
        self.setObjectName("DownloadsPopup")
        self.setFixedWidth(380)
        self.hide()
        self._mgr = get_download_manager()
        self._rows: dict = {}  # item id -> (bar, status label)

        self._hide_timer = QTimer(self)
        self._hide_timer.setSingleShot(True)
        self._hide_timer.setInterval(7000)
        self._hide_timer.timeout.connect(self.hide)

        outer = QVBoxLayout(self)
        outer.setContentsMargins(14, 12, 14, 12)
        outer.setSpacing(8)

        header = QHBoxLayout()
        title = QLabel("Downloads")
        title.setObjectName("PopupTitle")
        show_all = QPushButton("Show all")
        show_all.setObjectName("LinkButton")
        show_all.setCursor(Qt.CursorShape.PointingHandCursor)
        show_all.clicked.connect(self._on_show_all)
        header.addWidget(title)
        header.addStretch(1)
        header.addWidget(show_all)
        outer.addLayout(header)

        self.list_layout = QVBoxLayout()
        self.list_layout.setSpacing(8)
        outer.addLayout(self.list_layout)

        self._mgr.list_changed.connect(self._on_list_changed)
        self._mgr.progress.connect(self._on_progress)

    # ---------- show / hide ----------
    def show_under(self, anchor: QWidget, autohide: bool = True) -> None:
        self.refresh()
        parent = self.parentWidget()
        pos = anchor.mapTo(parent, QPoint(anchor.width(), anchor.height()))
        self.move(max(8, pos.x() - self.width()), pos.y() + 8)
        self.show()
        self.raise_()
        if autohide:
            self._hide_timer.start()
        else:
            self._hide_timer.stop()

    def toggle_under(self, anchor: QWidget) -> None:
        if self.isVisible():
            self.hide()
        else:
            self.show_under(anchor, autohide=False)

    def enterEvent(self, event) -> None:
        self._hide_timer.stop()
        super().enterEvent(event)

    def leaveEvent(self, event) -> None:
        if self.isVisible():
            self._hide_timer.start()
        super().leaveEvent(event)

    def _on_show_all(self) -> None:
        self.hide()
        self.show_all_requested.emit()

    # ---------- content ----------
    def _on_list_changed(self) -> None:
        if self.isVisible():
            self.refresh()

    def refresh(self) -> None:
        self._rows.clear()
        while self.list_layout.count():
            item = self.list_layout.takeAt(0)
            widget = item.widget()
            if widget is not None:
                widget.deleteLater()

        items = self._mgr.items()[:MAX_ROWS]
        if not items:
            empty = QLabel("No downloads yet.")
            empty.setObjectName("HintLabel")
            self.list_layout.addWidget(empty)
        for item in items:
            self.list_layout.addWidget(self._make_row(item))
        self.adjustSize()

    def _make_row(self, item: dict) -> QWidget:
        row = QWidget()
        layout = QHBoxLayout(row)
        layout.setContentsMargins(0, 0, 0, 0)
        layout.setSpacing(10)

        texts = QVBoxLayout()
        texts.setSpacing(3)
        title = QLabel()
        title.setObjectName("HistoryTitle")
        _elide(title, item["name"], 200)
        status = QLabel(_status_text(item))
        status.setObjectName("HistoryUrl")
        bar = QProgressBar()
        bar.setTextVisible(False)
        bar.setFixedHeight(5)
        bar.setVisible(item["state"] == "downloading")
        self._apply_bar(bar, item)
        texts.addWidget(title)
        texts.addWidget(status)
        texts.addWidget(bar)
        layout.addLayout(texts, 1)

        item_id = item["id"]
        if item["state"] == "downloading":
            layout.addWidget(_small_button("Cancel", lambda i=item_id: self._mgr.cancel(i)))
        elif item["state"] == "done":
            path, folder = item["path"], item["folder"]
            layout.addWidget(
                _small_button("Open", lambda p=path: QDesktopServices.openUrl(QUrl.fromLocalFile(p)))
            )
            layout.addWidget(
                _small_button("Folder", lambda f=folder: QDesktopServices.openUrl(QUrl.fromLocalFile(f)))
            )

        self._rows[item_id] = (bar, status)
        return row

    @staticmethod
    def _apply_bar(bar: QProgressBar, item: dict) -> None:
        if item["total"] > 0:
            bar.setRange(0, 100)
            bar.setValue(item["received"] * 100 // item["total"])
        else:
            bar.setRange(0, 0)  # size nahi pata: chalti hui patti

    def _on_progress(self, item_id: int) -> None:
        widgets = self._rows.get(item_id)
        item = self._mgr.get(item_id)
        if widgets is None or item is None:
            return
        bar, status = widgets
        self._apply_bar(bar, item)
        status.setText(_status_text(item))