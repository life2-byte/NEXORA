from PyQt6.QtCore import QObject, pyqtSignal

from backend.storage.bookmarks_store import BookmarkStore
from frontend.core.settings_manager import settings


class BookmarkManager(QObject):
    """Poori app ke liye ek manager. changed signal se star aur page sab windows mein sync rehte hain."""

    changed = pyqtSignal()

    def __init__(self):
        super().__init__()
        self._store = BookmarkStore(settings.config_dir / "bookmarks.db")

    def is_bookmarked(self, url: str) -> bool:
        return self._store.is_bookmarked(url)

    def add(self, url: str, title: str = "", folder: str = "") -> None:
        self._store.add(url, title, folder)
        self.changed.emit()

    def remove(self, url: str) -> None:
        self._store.remove_by_url(url)
        self.changed.emit()

    def search(self, query: str = "", limit: int = 500, folder=None) -> list:
        return self._store.search(query, limit, folder)

    def delete(self, bookmark_id: int) -> None:
        self._store.delete(bookmark_id)
        self.changed.emit()

    def folders(self) -> list:
        return self._store.folders()

    def move(self, bookmark_id: int, folder: str) -> None:
        self._store.set_folder(bookmark_id, folder)
        self.changed.emit()

    def rename_folder(self, old: str, new: str) -> None:
        self._store.rename_folder(old, new)
        self.changed.emit()

    def delete_folder(self, name: str, with_bookmarks: bool = False) -> None:
        self._store.delete_folder(name, with_bookmarks)
        self.changed.emit()

    def import_file(self, path: str) -> tuple:
        result = self._store.import_html(path)
        self.changed.emit()
        return result

    def export_file(self, path: str) -> int:
        return self._store.export_html(path)


bookmarks = BookmarkManager()