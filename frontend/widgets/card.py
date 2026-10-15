from PyQt6.QtWidgets import QFrame, QLabel, QVBoxLayout, QWidget


class Card(QFrame):
    def __init__(self, title: str, subtitle: str = "", parent=None):
        super().__init__(parent)
        self.setObjectName("Card")

        self._layout = QVBoxLayout(self)
        self._layout.setContentsMargins(16, 14, 16, 14)
        self._layout.setSpacing(6)

        title_label = QLabel(title)
        title_label.setObjectName("CardTitle")
        self._layout.addWidget(title_label)

        if subtitle:
            sub_label = QLabel(subtitle)
            sub_label.setObjectName("CardSub")
            sub_label.setWordWrap(True)
            self._layout.addWidget(sub_label)

    def add_widget(self, widget: QWidget) -> None:
        self._layout.addWidget(widget)