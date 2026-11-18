"""Ek profile ki ek hi window-process. Dobara chalane ya link kholne par maujooda window ko URL bhej dete hain."""

import getpass
import json

from PyQt6.QtCore import QObject, pyqtSignal
from PyQt6.QtNetwork import QLocalServer, QLocalSocket

from frontend.core.settings_manager import settings


def _name(profile_id: str) -> str:
    return f"nexora-{getpass.getuser()}-{profile_id}"


def forward(urls: list, profile_id: str | None = None) -> bool:
    """True = us profile ki chalti hui window mil gayi aur usay urls (ya sirf 'samne aao') bhej diya."""
    socket = QLocalSocket()
    socket.connectToServer(_name(profile_id or settings.profile_id))
    if not socket.waitForConnected(400):
        return False
    socket.write(json.dumps({"urls": urls}).encode("utf-8") + b"\n")
    socket.flush()
    socket.waitForBytesWritten(1000)
    socket.disconnectFromServer()
    return True


class InstanceServer(QObject):
    urls_received = pyqtSignal(list)  # khali list = sirf window samne lao

    def __init__(self):
        super().__init__()
        self._server = QLocalServer(self)
        self._server.newConnection.connect(self._on_connection)

    def start(self) -> bool:
        name = _name(settings.profile_id)
        QLocalServer.removeServer(name)  # pichli crash ki bachi hui file
        return self._server.listen(name)

    def _on_connection(self) -> None:
        socket = self._server.nextPendingConnection()
        if socket is None:
            return
        socket.readyRead.connect(lambda s=socket: self._read(s))
        socket.disconnected.connect(socket.deleteLater)

    def _read(self, socket: QLocalSocket) -> None:
        try:
            data = json.loads(bytes(socket.readAll()).decode("utf-8").strip().splitlines()[0])
            urls = [u for u in data.get("urls", []) if isinstance(u, str)]
        except (ValueError, IndexError):
            return
        self.urls_received.emit(urls)