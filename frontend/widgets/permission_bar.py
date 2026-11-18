import re

from PyQt6.QtCore import Qt
from PyQt6.QtWidgets import QHBoxLayout, QLabel, QPushButton, QWidget

LABELS = {
    "Geolocation": "know your location",
    "Notifications": "show notifications",
    "MediaAudioCapture": "use your microphone",
    "MediaVideoCapture": "use your camera",
    "MediaAudioVideoCapture": "use your camera and microphone",
    "DesktopVideoCapture": "share your screen",
    "DesktopAudioVideoCapture": "share your screen and audio",
    "ClipboardReadWrite": "read your clipboard",
    "MouseLock": "lock your mouse pointer",
    "LocalFontsAccess": "see the fonts installed on your computer",
    "StorageAccess": "keep cookies and site data while embedded in another site",
    "TopLevelStorageAccess": "use its cookies and site data across other sites",
}


def describe(permission) -> str:
    name = permission.permissionType().name
    what = LABELS.get(name)
    if what is None:
        words = re.sub(r"(?<!^)(?=[A-Z])", " ", name).lower()
        what = f"use: {words}"
    origin = permission.origin()
    host = origin.host() or origin.toString()
    return f"{host} wants to {what}"


class PermissionBar(QWidget):
    """Site ki permission request ka sawal. Qt ka apna widget hai, page ke andar nahi,
    isliye agent (page ke tools) isko kabhi click nahi kar sakta."""

    def __init__(self, parent=None):
        super().__init__(parent)
        self.setObjectName("PermissionBar")
        self.hide()
        self._queue = []
        self._current = None

        layout = QHBoxLayout(self)
        layout.setContentsMargins(14, 8, 10, 8)
        layout.setSpacing(10)

        self.text = QLabel()
        self.text.setObjectName("PermissionText")

        self.allow_btn = QPushButton("Allow")
        self.allow_btn.setObjectName("PermAllow")
        self.block_btn = QPushButton("Block")
        self.block_btn.setObjectName("PermBlock")
        self.later_btn = QPushButton("Not now")
        self.later_btn.setObjectName("PermBlock")
        for btn in (self.allow_btn, self.block_btn, self.later_btn):
            btn.setCursor(Qt.CursorShape.PointingHandCursor)

        self.allow_btn.clicked.connect(lambda: self._answer(True))
        self.block_btn.clicked.connect(lambda: self._answer(False))
        self.later_btn.clicked.connect(self._dismiss)

        layout.addWidget(self.text, 1)
        layout.addWidget(self.allow_btn)
        layout.addWidget(self.block_btn)
        layout.addWidget(self.later_btn)

    def request(self, permission) -> None:
        print(f"[permission] asked: {describe(permission)}")
        self._queue.append(permission)
        if self._current is None:
            self._next()

    def _next(self) -> None:
        if not self._queue:
            self._current = None
            self.hide()
            return
        self._current = self._queue.pop(0)
        more = f"  (+{len(self._queue)} more)" if self._queue else ""
        self.text.setText(describe(self._current) + more)
        self.show()

    def _answer(self, allow: bool) -> None:
        permission = self._current
        if permission is not None and permission.isValid():
            print(f"[permission] {'allowed' if allow else 'blocked'}: {describe(permission)}")
            if allow:
                permission.grant()
            else:
                permission.deny()
        self._next()

    def _dismiss(self) -> None:
        self._next()
