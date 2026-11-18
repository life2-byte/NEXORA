from backend.storage.history_store import HistoryStore
from frontend.core.settings_manager import settings

# poori app mein ek hi store (sirf GUI thread se use hota hai)
history = HistoryStore(settings.config_dir / "history.db")