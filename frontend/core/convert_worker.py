from PyQt6.QtCore import QThread, pyqtSignal

from frontend.api.backend_client import backend_client


class ConvertWorker(QThread):
    progress = pyqtSignal(int)
    done = pyqtSignal(str)    # converted file ka path
    failed = pyqtSignal(str)  # error message

    def __init__(self, src: str, dest: str, parent=None):
        super().__init__(parent)
        self._src = src
        self._dest = dest
        self._cancel = False

    def cancel(self) -> None:
        self._cancel = True

    def run(self) -> None:
        try:
            out = backend_client.convert_video(
                self._src, self._dest, self.progress.emit, lambda: self._cancel
            )
            self.done.emit(str(out))
        except Exception as e:  # ConversionError ya koi aur masla
            self.failed.emit(str(e))