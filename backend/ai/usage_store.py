"""AI tokens ki history (sqlite): din ke hisaab se kitne lage. Qt ka koi code nahi."""

import sqlite3
import time
from datetime import date, datetime, timedelta
from pathlib import Path


class UsageStore:
    def __init__(self, path):
        self._path = Path(path)
        self._conn = None

    def _db(self) -> sqlite3.Connection:
        if self._conn is None:
            self._path.parent.mkdir(parents=True, exist_ok=True)
            self._conn = sqlite3.connect(str(self._path))
            self._conn.execute(
                "CREATE TABLE IF NOT EXISTS calls ("
                " id INTEGER PRIMARY KEY AUTOINCREMENT, ts INTEGER NOT NULL, day TEXT NOT NULL,"
                " prompt INTEGER NOT NULL, completion INTEGER NOT NULL,"
                " provider TEXT NOT NULL DEFAULT '', model TEXT NOT NULL DEFAULT '',"
                " agent TEXT NOT NULL DEFAULT '', task TEXT NOT NULL DEFAULT '')"
            )
            self._conn.execute("CREATE INDEX IF NOT EXISTS idx_calls_day ON calls(day)")
            self._conn.commit()
        return self._conn

    def add(self, prompt: int, completion: int, provider: str = "", model: str = "", agent: str = "", task: str = "") -> None:
        db = self._db()
        db.execute(
            "INSERT INTO calls (ts, day, prompt, completion, provider, model, agent, task) VALUES (?,?,?,?,?,?,?,?)",
            (int(time.time()), date.today().isoformat(), max(0, prompt), max(0, completion), provider, model, agent, task),
        )
        db.commit()

    def daily(self, days: int = 14) -> list:
        """Aakhri `days` din (aaj tak), jis din kuch nahi hua uska 0. [{'day', 'prompt', 'completion', 'calls'}]"""
        start = date.today() - timedelta(days=days - 1)
        rows = self._db().execute(
            "SELECT day, SUM(prompt), SUM(completion), COUNT(*) FROM calls WHERE day >= ? GROUP BY day",
            (start.isoformat(),),
        ).fetchall()
        found = {r[0]: r for r in rows}
        out = []
        for i in range(days):
            d = (start + timedelta(days=i)).isoformat()
            r = found.get(d)
            out.append({"day": d, "prompt": r[1] if r else 0, "completion": r[2] if r else 0, "calls": r[3] if r else 0})
        return out

    def _sum(self, where: str, args: tuple) -> dict:
        r = self._db().execute(
            f"SELECT COALESCE(SUM(prompt),0), COALESCE(SUM(completion),0), COUNT(*) FROM calls {where}", args
        ).fetchone()
        return {"prompt": r[0], "completion": r[1], "calls": r[2], "total": r[0] + r[1]}

    def today(self) -> dict:
        return self._sum("WHERE day = ?", (date.today().isoformat(),))

    def this_month(self) -> dict:
        return self._sum("WHERE day >= ?", (date.today().replace(day=1).isoformat(),))

    def all_time(self) -> dict:
        return self._sum("", ())

    def period_used(self, period: str) -> int:
        return (self.today() if period == "day" else self.this_month())["total"]

    def clear(self) -> None:
        db = self._db()
        db.execute("DELETE FROM calls")
        db.commit()