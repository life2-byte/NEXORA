"""Connection test background thread mein chalata hai (UI nahi atakti)."""

import threading

from PyQt6.QtCore import QObject, pyqtSignal

from backend.ai.base import ConnectionReport, ProviderError, hint_for
from frontend.core.ai_provider import build_provider
from frontend.core.ai_usage import ai_usage


class ConnectionTester(QObject):
    finished = pyqtSignal(object)  # ConnectionReport (GUI thread par aata hai)

    def __init__(self) -> None:
        super().__init__()
        self.running = False

    def start(self) -> None:
        if self.running:
            return
        self.running = True
        threading.Thread(target=self._work, daemon=True).start()

    def _work(self) -> None:
        try:
            report = build_provider().test_connection()
        except ProviderError as e:
            report = ConnectionReport(False, "Setup poora nahi", f"{e.message}\n\n{hint_for(e.kind)}".strip())
        except Exception as e:  # koi anjaani galti bhi popup ban kar aaye, crash na ho
            report = ConnectionReport(False, "Test nahi ho saka", str(e))
        self.running = False
        self.finished.emit(report)