from frontend.pages.base_page import BasePage
from frontend.widgets.card import Card


class BookmarksPage(BasePage):
    def __init__(self, parent=None):
        super().__init__("Bookmarks", "Save kiye hue pages.", parent)
        self.add_cards(
            [
                Card("Saved pages", "Bookmark storage agle step mein judega."),
                Card("Collections", "Folders mein bookmarks organize karo."),
            ],
            columns=2,
        )
        self.body.addStretch(1)