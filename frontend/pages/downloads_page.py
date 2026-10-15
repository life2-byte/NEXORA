from frontend.core.settings_manager import settings
from frontend.pages.base_page import BasePage
from frontend.widgets.card import Card


class DownloadsPage(BasePage):
    def __init__(self, parent=None):
        super().__init__("Downloads", "Downloaded files ka hisaab.", parent)
        self.add_cards(
            [
                Card("Save folder", f"Files yahan save hoti hain: {settings.get('download_dir')}"),
                Card("Recent downloads", "List ka UI agle step mein aayega."),
            ],
            columns=2,
        )
        self.body.addStretch(1)