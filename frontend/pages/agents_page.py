from frontend.pages.base_page import BasePage
from frontend.widgets.card import Card


class AgentsPage(BasePage):
    def __init__(self, parent=None):
        super().__init__("Agents", "Tere AI agents yahan manage honge (backend ke saath judega).", parent)
        self.add_cards(
            [
                Card("Browser Agent", "Pages parhta hai, click/type karta hai aur tasks chalata hai."),
                Card("Research Agent", "Web pe search karke sources compare karta hai."),
                Card("Custom Agent", "Apna agent banao: goal, tools aur rules khud set karo."),
            ]
        )
        self.body.addStretch(1)