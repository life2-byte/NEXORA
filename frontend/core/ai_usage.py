"""Tokens ka hisaab: is session ka (memory mein), poori history (sqlite) aur provider ki limit (headers se)."""

from datetime import datetime
from typing import Optional

from PyQt6.QtCore import QObject, pyqtSignal

from backend.ai.base import RateLimits, Usage
from backend.ai.usage_store import UsageStore
from frontend.core.settings_manager import settings


def _n(value: int) -> str:
    return f"{value:,}"


def _wait(seconds: float) -> str:
    seconds = max(0, int(round(seconds)))
    return f"{seconds}s" if seconds < 120 else f"{seconds // 60}m"


class AiUsage(QObject):
    changed = pyqtSignal()

    def __init__(self) -> None:
        super().__init__()
        self.store = UsageStore(settings.config_dir / "ai_usage.db")
        self.started = datetime.now()
        self.calls = 0
        self.prompt_tokens = 0
        self.completion_tokens = 0
        self.limits: Optional[RateLimits] = None
        self.label = ""
        settings.changed.connect(lambda key, _v: self.changed.emit() if key.startswith("ai_budget") else None)

    # ---------- record ----------
    def record(self, usage: Usage, limits: Optional[RateLimits], label: str = "", agent: str = "", task: str = "") -> None:
        self.calls += 1
        self.prompt_tokens += usage.prompt_tokens
        self.completion_tokens += usage.completion_tokens
        if limits is not None and limits.known():
            self.limits = limits
        self.label = label or self.label
        try:
            self.store.add(usage.prompt_tokens, usage.completion_tokens, "", label, agent, task)
        except Exception:  # disk ka masla token ginti ki wajah se kaam na roke
            pass
        self.changed.emit()

    def reset(self) -> None:
        """Sirf is session ka counter (history wahin rehti hai)."""
        self.calls = self.prompt_tokens = self.completion_tokens = 0
        self.limits = None
        self.started = datetime.now()
        self.changed.emit()

    def clear_history(self) -> None:
        self.store.clear()
        self.changed.emit()

    # ---------- budget (tumhari apni limit) ----------
    def budget_status(self) -> Optional[dict]:
        period = settings.get("ai_budget_period")
        limit = int(settings.get("ai_budget_tokens") or 0)
        if period not in ("day", "month") or limit <= 0:
            return None
        used = self.store.period_used(period)
        return {
            "period": period,
            "limit": limit,
            "used": used,
            "remaining": max(0, limit - used),
            "fraction_used": min(1.0, used / limit),
        }

    def over_budget(self) -> bool:
        status = self.budget_status()
        return bool(status and status["used"] >= status["limit"])

    # ---------- text ----------
    def limit_text(self, limits: Optional[RateLimits] = None) -> str:
        lim = limits or self.limits
        if lim is None or not lim.known():
            return ""
        parts = []
        if lim.tokens_remaining is not None:
            part = f"tokens baaki {_n(lim.tokens_remaining)}"
            if lim.tokens_limit:
                part += f" / {_n(lim.tokens_limit)}"
            parts.append(part)
        if lim.requests_remaining is not None:
            part = f"requests baaki {_n(lim.requests_remaining)}"
            if lim.requests_limit:
                part += f" / {_n(lim.requests_limit)}"
            parts.append(part)
        text = ", ".join(parts)
        if lim.reset_seconds:
            text += f" (reset: {_wait(lim.reset_seconds)})"
        return text

    def status_text(self) -> str:
        if not self.calls:
            return "Tokens: abhi koi AI call nahi hui."
        text = f"Tokens (is session): {_n(self.prompt_tokens)} in / {_n(self.completion_tokens)} out, {self.calls} calls"
        limit = self.limit_text()
        if limit:
            text += f"\nLimit: {limit}"
        budget = self.budget_status()
        if budget:
            where = "aaj" if budget["period"] == "day" else "is mahine"
            text += f"\nTumhari limit ({where}): {_n(budget['used'])} / {_n(budget['limit'])} tokens"
        return text

    def fraction_left(self) -> Optional[float]:
        lim = self.limits
        if lim and lim.tokens_remaining is not None and lim.tokens_limit:
            return max(0.0, min(1.0, lim.tokens_remaining / lim.tokens_limit))
        if lim and lim.requests_remaining is not None and lim.requests_limit:
            return max(0.0, min(1.0, lim.requests_remaining / lim.requests_limit))
        return None


ai_usage = AiUsage()