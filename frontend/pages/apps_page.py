from frontend.pages.base_page import BasePage
from frontend.widgets.card import Card


class AppsPage(BasePage):
    def __init__(self, parent=None):
        super().__init__("Apps", "Agent ke built-in tools aur mini apps.", parent)
        self.add_cards(
            [
                Card("Page Reader", "Current page ko samajh kar summary deta hai."),
                Card("Extraction Engine", "Messy page se structured JSON banata hai."),
                Card("Workflow Builder", "Multi-step tasks design karo."),
                Card("Research Agent", "Web pe search karke compare karta hai."),
                Card("Price Tracker", "Products ki prices pe nazar rakhta hai."),
                Card("Job Finder", "Job sites se matching jobs nikalta hai."),
            ]
        )
        self.body.addStretch(1)