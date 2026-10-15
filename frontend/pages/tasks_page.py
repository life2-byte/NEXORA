from frontend.pages.base_page import BasePage
from frontend.widgets.card import Card


class TasksPage(BasePage):
    def __init__(self, parent=None):
        super().__init__("Tasks", "Agent ke chalte hue aur mukammal kaam.", parent)
        self.add_cards(
            [
                Card("Running", "Abhi koi task nahi chal raha."),
                Card("Completed", "Mukammal tasks ki history yahan aayegi."),
                Card("Scheduled", "Baad mein chalne wale tasks."),
            ]
        )
        self.body.addStretch(1)