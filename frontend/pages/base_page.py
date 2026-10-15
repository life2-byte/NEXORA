from PyQt6.QtWidgets import (
    QFrame,
    QGridLayout,
    QLabel,
    QScrollArea,
    QVBoxLayout,
    QWidget,
)

from frontend.widgets.card import Card


class BasePage(QWidget):
    def __init__(self, title: str, subtitle: str = "", parent=None):
        super().__init__(parent)
        self.setObjectName("Page")

        outer = QVBoxLayout(self)
        outer.setContentsMargins(0, 0, 0, 0)

        scroll = QScrollArea()
        scroll.setObjectName("PageScroll")
        scroll.setWidgetResizable(True)
        scroll.setFrameShape(QFrame.Shape.NoFrame)

        inner = QWidget()
        inner.setObjectName("PageInner")
        self.body = QVBoxLayout(inner)
        self.body.setContentsMargins(32, 28, 32, 28)
        self.body.setSpacing(18)

        title_label = QLabel(title)
        title_label.setObjectName("PageTitle")
        self.body.addWidget(title_label)

        if subtitle:
            sub_label = QLabel(subtitle)
            sub_label.setObjectName("PageSubtitle")
            self.body.addWidget(sub_label)

        scroll.setWidget(inner)
        outer.addWidget(scroll)

    def add_cards(self, cards: list[Card], columns: int = 3) -> None:
        container = QWidget()
        grid = QGridLayout(container)
        grid.setContentsMargins(0, 0, 0, 0)
        grid.setSpacing(14)
        for i, card in enumerate(cards):
            grid.addWidget(card, i // columns, i % columns)
        for c in range(columns):
            grid.setColumnStretch(c, 1)
        self.body.addWidget(container)

    def add_section(self, title: str) -> None:
        label = QLabel(title)
        label.setObjectName("SectionTitle")
        self.body.addWidget(label)