from pathlib import Path

from PyQt6.QtCore import QObject, pyqtSignal
from PyQt6.QtWebEngineCore import QWebEngineDownloadRequest
from PyQt6.QtWidgets import QFileDialog

from backend.storage.downloads_store import DownloadStore
from frontend.core.profile import get_profile
from frontend.core.settings_manager import settings

DS = QWebEngineDownloadRequest.DownloadState


def _unique_name(folder: Path, name: str) -> str:
    stem, suffix = Path(name).stem, Path(name).suffix
    final, n = name, 1
    while (folder / final).exists():
        final = f"{stem} ({n}){suffix}"
        n += 1
    return final


class DownloadManager(QObject):
    """Poori app ka ek manager: downloads ko save karta hai, list/progress track karta hai,
    aur history SQLite mein rakhta hai (restart ke baad bhi list rehti hai)."""

    message = pyqtSignal(str)       # status bar ke liye
    list_changed = pyqtSignal()     # naya item / khatam / remove
    progress = pyqtSignal(int)      # item id (bytes badhe)
    started = pyqtSignal(object)    # jis page se download shuru hua (QWebEnginePage ya None)
    activity = pyqtSignal()         # naya download ya khatam: popup dikhane ke liye

    def __init__(self, parent=None):
        super().__init__(parent)
        self._store = DownloadStore(settings.config_dir / "downloads.db")
        self._store.mark_interrupted()
        self._items: list = self._load_saved()
        get_profile().downloadRequested.connect(self._on_download)

    def _load_saved(self) -> list:
        items = []
        for row in self._store.load():
            row["request"] = None
            if row["state"] == "done" and not Path(row["path"]).exists():
                row["state"] = "missing"  # file hata di gayi ya move ho gayi
            items.append(row)
        return items

    # ---------- public ----------
    def items(self) -> list:
        return list(self._items)

    def get(self, item_id: int):
        for item in self._items:
            if item["id"] == item_id:
                return item
        return None

    def cancel(self, item_id: int) -> None:
        item = self.get(item_id)
        if item and item["request"] is not None:
            item["request"].cancel()

    def remove(self, item_id: int) -> None:
        item = self.get(item_id)
        if item is None:
            return
        self.cancel(item_id)
        if item in self._items:
            self._items.remove(item)
        self._store.delete(item_id)
        self.list_changed.emit()

    def clear_finished(self) -> None:
        self._items = [i for i in self._items if i["state"] == "downloading"]
        self._store.delete_finished()
        self.list_changed.emit()

    # ---------- internals ----------
    def _on_download(self, download: QWebEngineDownloadRequest) -> None:
        folder = Path(settings.get("download_dir"))
        name = download.downloadFileName() or "download"
        try:
            folder.mkdir(parents=True, exist_ok=True)
        except OSError:
            folder = Path.home()

        if settings.get("ask_download"):
            path, _ = QFileDialog.getSaveFileName(None, "Save file as", str(folder / name))
            if not path:
                download.cancel()
                return
            target = Path(path)
            folder, name = target.parent, target.name
        else:
            name = _unique_name(folder, name)

        download.setDownloadDirectory(str(folder))
        download.setDownloadFileName(name)

        try:
            origin = download.page()  # kis page se shuru hua (khali popup tab band karne ke liye)
        except AttributeError:
            origin = None

        full_path = str(folder / name)
        item_id = self._store.add(name, str(folder), full_path, download.url().toString())
        item = {
            "id": item_id,
            "name": name,
            "folder": str(folder),
            "path": full_path,
            "url": download.url().toString(),
            "state": "downloading",
            "received": 0,
            "total": 0,
            "request": download,
        }
        self._items.insert(0, item)

        download.receivedBytesChanged.connect(lambda i=item, d=download: self._on_progress(i, d))
        download.isFinishedChanged.connect(lambda i=item, d=download: self._on_finished(i, d))
        download.accept()

        self.message.emit(f"Downloading {name}...")
        self.list_changed.emit()
        self.started.emit(origin)
        self.activity.emit()

    def _on_progress(self, item: dict, download: QWebEngineDownloadRequest) -> None:
        item["received"] = download.receivedBytes()
        item["total"] = download.totalBytes()
        self.progress.emit(item["id"])

    def _on_finished(self, item: dict, download: QWebEngineDownloadRequest) -> None:
        state = download.state()
        if state == DS.DownloadCompleted:
            item["state"] = "done"
            item["received"] = download.receivedBytes()
            item["total"] = download.totalBytes() or item["received"]
        elif state == DS.DownloadCancelled:
            item["state"] = "cancelled"
        else:
            item["state"] = "failed"
        item["request"] = None
        self._store.update(item["id"], item["state"], item["received"], item["total"])

        if item["state"] == "done":
            self.message.emit(f"Saved: {item['path']}")
        elif item["state"] == "failed":
            self.message.emit(f"Download failed: {item['name']}")
        self.list_changed.emit()
        self.activity.emit()


_manager = None


def get_download_manager() -> DownloadManager:
    global _manager
    if _manager is None:
        _manager = DownloadManager()
    return _manager