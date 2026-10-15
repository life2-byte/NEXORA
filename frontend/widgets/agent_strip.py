from PyQt6.QtCore import QTimer, pyqtSignal
from PyQt6.QtWidgets import (
    QHBoxLayout,
    QLabel,
    QProgressBar,
    QToolButton,
    QVBoxLayout,
    QWidget,
)

from frontend.assets.icons import get_icon
from frontend.styles.theme import COLORS


class AgentStrip(QWidget):
    stop_requested = pyqtSignal()

    def __init__(self, parent=None):
        super().__init__(parent)
        self.setObjectName("AgentStrip")
        self.hide()

        outer = QVBoxLayout(self)
        outer.setContentsMargins(0, 0, 0, 0)
        outer.setSpacing(0)

        row = QHBoxLayout()
        row.setContentsMargins(14, 6, 10, 6)
        row.setSpacing(10)

        icon = QLabel()
        icon.setPixmap(get_icon("agent", COLORS["accent"]).pixmap(16, 16))

        self.task_label = QLabel()
        self.task_label.setObjectName("AgentTask")
        self.step_label = QLabel()
        self.step_label.setObjectName("AgentStep")

        self.stop_btn = QToolButton()
        self.stop_btn.setObjectName("AgentStop")
        self.stop_btn.setText("Stop")
        self.stop_btn.clicked.connect(self.stop_requested.emit)

        row.addWidget(icon)
        row.addWidget(self.task_label)
        row.addWidget(self.step_label, 1)
        row.addWidget(self.stop_btn)
        outer.addLayout(row)

        self.progress = QProgressBar()
        self.progress.setRange(0, 0)
        self.progress.setTextVisible(False)
        self.progress.setFixedHeight(2)
        outer.addWidget(self.progress)

        self._hide_timer = QTimer(self)
        self._hide_timer.setSingleShot(True)
        self._hide_timer.timeout.connect(self.hide)

    def start(self, task: str) -> None:
        self._hide_timer.stop()
        short = task if len(task) <= 60 else task[:57] + "..."
        self.task_label.setText(f"AI · {short}")
        self.step_label.setText("Starting...")
        self.progress.show()
        self.stop_btn.show()
        self.show()

    def set_step(self, text: str) -> None:
        self.step_label.setText(text)

    def finish(self, text: str = "Done") -> None:
        self.step_label.setText(text)
        self.progress.hide()
        self.stop_btn.hide()
        self._hide_timer.start(2500)