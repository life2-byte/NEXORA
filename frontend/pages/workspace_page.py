from frontend.pages.base_page import BasePage
from frontend.widgets.card import Card


class WorkspacePage(BasePage):
    def __init__(self, parent=None):
        super().__init__(
            "Workspace", "Dashboard, agent status aur research ek jagah.", parent
        )
        self.add_cards(
            [
                Card("Data Analysis", "Extracted data ke charts aur trends yahan aayenge."),
                Card("Agent Status", "Agent abhi idle hai. Koi task nahi chal raha."),
                Card("Research Queries", "Latest 5 queries ki history."),
                Card("News Feed", "Tere topics ki fresh khabrein."),
                Card("Workflows", "Saved multi-step workflows."),
                Card("Collaborate", "Team ke saath shared tasks."),
            ]
        )
        self.body.addStretch(1)