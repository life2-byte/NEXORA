from PyQt6.QtCore import Qt, QUrl
from PyQt6.QtGui import QDesktopServices
from PyQt6.QtWidgets import (
    QHBoxLayout,
    QLabel,
    QProgressBar,
    QPushButton,
    QVBoxLayout,
    QWidget,
)

from frontend.core.downloads import get_download_manager
from frontend.core.settings_manager import settings
from frontend.pages.base_page import BasePage
from frontend.pages.history_page import _elide, _Row


def _fmt(size: int) -> str:
    value = float(size)
    for unit in ("B", "KB", "MB", "GB"):
        if value < 1024 or unit == "GB":
            return f"{value:.0f} {unit}" if unit == "B" else f"{value:.1f} {unit}"
        value /= 1024
    return f"{size} B"


def _button(text: str, callback) -> QPushButton:
    btn = QPushButton(text)
    btn.setObjectName("SettingsButton")
    btn.setCursor(Qt.CursorShape.PointingHandCursor)
    btn.setFixedHeight(28)
    btn.clicked.connect(lambda _=False: callback())
    return btn


class DownloadsPage(BasePage):
    def __init__(self, parent=None):
        super().__init__("Downloads", "Is session ki downloads.", parent)
        self._mgr = get_download_manager()
        self._rows: dict = {}  # item id -> (progress bar, status label)

        top = QWidget()
        top_layout = QHBoxLayout(top)
        top_layout.setContentsMargins(0, 0, 0, 0)
        top_layout.setSpacing(10)
        self.folder_label = QLabel()
        self.folder_label.setObjectName("HintLabel")
        self._update_folder_label()
        top_layout.addWidget(self.folder_label, 1)
        top_layout.addWidget(_button("Open folder", self._open_folder))
        top_layout.addWidget(_button("Clear finished", self._mgr.clear_finished))
        self.body.addWidget(top)

        self.list_box = QWidget()
        self.list_layout = QVBoxLayout(self.list_box)
        self.list_layout.setContentsMargins(0, 0, 0, 0)
        self.list_layout.setSpacing(4)
        self.body.addWidget(self.list_box)
        self.body.addStretch(1)

        self._mgr.list_changed.connect(self.refresh)
        self._mgr.progress.connect(self._on_progress)
        settings.changed.connect(self._on_setting)
        self.refresh()

    # ---------- folder ----------
    def _update_folder_label(self) -> None:
        self.folder_label.setText(f"Save folder: {settings.get('download_dir')}")

    def _on_setting(self, key: str, _value) -> None:
        if key == "download_dir":
            self._update_folder_label()

    def _open_folder(self) -> None:
        QDesktopServices.openUrl(QUrl.fromLocalFile(str(settings.get("download_dir"))))

    # ---------- list ----------
    def refresh(self) -> None:
        self._rows.clear()
        while self.list_layout.count():
            item = self.list_layout.takeAt(0)
            widget = item.widget()
            if widget is not None:
                widget.deleteLater()

        items = self._mgr.items()
        if not items:
            empty = QLabel("Abhi koi download nahi.")
            empty.setObjectName("HintLabel")
            self.list_layout.addWidget(empty)
            return
        for item in items:
            self.list_layout.addWidget(self._make_row(item))

    def _status_text(self, item: dict) -> str:
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

    def _make_row(self, item: dict) -> QWidget:
        row = _Row()
        row.setObjectName("HistoryRow")
        layout = QHBoxLayout(row)
        layout.setContentsMargins(10, 8, 10, 8)
        layout.setSpacing(12)

        texts = QVBoxLayout()
        texts.setSpacing(3)
        title = QLabel()
        title.setObjectName("HistoryTitle")
        _elide(title, item["name"], 480)
        status = QLabel(self._status_text(item))
        status.setObjectName("HistoryUrl")
        bar = QProgressBar()
        bar.setTextVisible(False)
        bar.setFixedHeight(6)
        bar.setVisible(item["state"] == "downloading")
        self._apply_bar(bar, item)
        texts.addWidget(title)
        texts.addWidget(status)
        texts.addWidget(bar)
        layout.addLayout(texts, 1)

        item_id = item["id"]
        if item["state"] == "downloading":
            layout.addWidget(_button("Cancel", lambda i=item_id: self._mgr.cancel(i)))
        else:
            if item["state"] == "done":
                path, folder = item["path"], item["folder"]
                layout.addWidget(
                    _button("Open", lambda p=path: QDesktopServices.openUrl(QUrl.fromLocalFile(p)))
                )
                layout.addWidget(
                    _button("Folder", lambda f=folder: QDesktopServices.openUrl(QUrl.fromLocalFile(f)))
                )
            layout.addWidget(_button("Remove", lambda i=item_id: self._mgr.remove(i)))

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
        status.setText(self._status_text(item))