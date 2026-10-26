"""Single-instance guard: a second launch asks the first one to show its window."""

from __future__ import annotations

import getpass
import re
from functools import partial

from PySide6.QtCore import QObject, Signal
from PySide6.QtNetwork import QLocalServer, QLocalSocket

CONNECT_TIMEOUT_MS = 500
SHOW_MESSAGE = b"show"


def instance_key(app_id: str) -> str:
    user = re.sub(r"[^A-Za-z0-9_-]", "_", getpass.getuser())
    return f"{app_id}-{user}"


class SingleInstance(QObject):
    activation_requested = Signal()

    def __init__(self, key: str, parent: QObject | None = None) -> None:
        super().__init__(parent)
        self._key = key
        self._server: QLocalServer | None = None
        self._clients: set[QLocalSocket] = set()

    def notify_existing(self) -> bool:
        """True if another instance is running (and has been asked to show itself)."""
        socket = QLocalSocket()
        socket.connectToServer(self._key)
        if not socket.waitForConnected(CONNECT_TIMEOUT_MS):
            return False
        socket.write(SHOW_MESSAGE)
        socket.flush()
        socket.waitForBytesWritten(CONNECT_TIMEOUT_MS)
        # Let the running instance read the message and close the pipe itself.
        if not socket.waitForDisconnected(CONNECT_TIMEOUT_MS * 4):
            socket.disconnectFromServer()
        return True

    def listen(self) -> bool:
        server = QLocalServer(self)
        server.setSocketOptions(QLocalServer.SocketOption.UserAccessOption)
        if not server.listen(self._key):
            # A crashed instance can leave a stale endpoint behind; clear it once and retry.
            QLocalServer.removeServer(self._key)
            if not server.listen(self._key):
                return False
        server.newConnection.connect(self._on_connection)
        self._server = server
        return True

    def _on_connection(self) -> None:
        assert self._server is not None
        while (socket := self._server.nextPendingConnection()) is not None:
            # Data arrives asynchronously; read it when it is ready, never block the UI.
            # Keep a Python reference until the message is handled; delete only afterwards.
            self._clients.add(socket)
            socket.readyRead.connect(partial(self._on_ready_read, socket))

    def _on_ready_read(self, socket: QLocalSocket) -> None:
        if socket not in self._clients:
            return
        self._clients.discard(socket)
        if bytes(socket.readAll().data()).startswith(SHOW_MESSAGE):
            self.activation_requested.emit()
        socket.readyRead.disconnect()
        socket.disconnectFromServer()
        socket.deleteLater()
