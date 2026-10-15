from frontend.pages.base_page import BasePage
from frontend.widgets.card import Card


class MemoryPage(BasePage):
    def __init__(self, parent=None):
        super().__init__("Memory", "Agent ko jo yaad rakhna hai (backend ke saath judega).", parent)
        self.add_cards(
            [
                Card("This session", "Is session mein agent ne jo seekha."),
                Card("Preferences", "Teri pasand, jo har task mein kaam aaye."),
                Card("Past workflows", "Pehle kamyab hue workflows dobara chalao."),
            ]
        )
        self.body.addStretch(1)