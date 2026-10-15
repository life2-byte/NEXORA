from frontend.pages.base_page import BasePage
from frontend.widgets.card import Card


class FilesPage(BasePage):
    def __init__(self, parent=None):
        super().__init__("Files", "Downloads aur agent ka nikala hua data.", parent)
        self.add_cards(
            [
                Card("Downloads", "Browser se download hui files."),
                Card("Extracted Data", "JSON / CSV jo agent ne pages se nikala."),
                Card("Screenshots", "Pages ke screenshots."),
                Card("Saved Pages", "Offline save kiye hue pages."),
            ],
            columns=2,
        )
        self.body.addStretch(1)