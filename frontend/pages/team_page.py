from frontend.pages.base_page import BasePage
from frontend.widgets.card import Card


class TeamPage(BasePage):
    def __init__(self, parent=None):
        super().__init__("Team", "Members, shared workflows aur activity.", parent)
        self.add_cards(
            [
                Card("Members", "Team members ki list yahan dikhegi."),
                Card("Invite", "Naye member ko link se invite karo."),
                Card("Shared Workflows", "Jo workflows team ke saath share hain."),
                Card("Activity", "Kis ne kya run kiya, ek timeline mein."),
            ],
            columns=2,
        )
        self.body.addStretch(1)