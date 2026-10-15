from pathlib import Path

from PyQt6.QtCore import QObject, pyqtSignal
from PyQt6.QtWebEngineCore import QWebEngineDownloadRequest, QWebEngineProfile
from PyQt6.QtWidgets import QFileDialog

from frontend.core.settings_manager import settings


def _unique_name(folder: Path, name: str) -> str:
    stem, suffix = Path(name).stem, Path(name).suffix
    final, n = name, 1
    while (folder / final).exists():
        final = f"{stem} ({n}){suffix}"
        n += 1
    return final


class DownloadManager(QObject):
    message = pyqtSignal(str)

    def __init__(self, parent=None):
        super().__init__(parent)
        QWebEngineProfile.defaultProfile().downloadRequested.connect(self._on_download)

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
        download.isFinishedChanged.connect(
            lambda d=download, n=name, f=folder: self._on_finished(d, n, f)
        )
        download.accept()
        self.message.emit(f"Downloading {name}...")

    def _on_finished(self, download: QWebEngineDownloadRequest, name: str, folder: Path) -> None:
        done = download.state() == QWebEngineDownloadRequest.DownloadState.DownloadCompleted
        self.message.emit(f"Saved: {folder / name}" if done else f"Download failed: {name}")