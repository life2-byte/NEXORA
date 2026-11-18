import sqlite3
import time
from pathlib import Path


class HistoryStore:
    """GUI thread se use karo (ek connection)."""

    def __init__(self, path):
        self._path = Path(path)
        self._conn = None

    def _db(self) -> sqlite3.Connection:
        if self._conn is None:
            self._path.parent.mkdir(parents=True, exist_ok=True)
            self._conn = sqlite3.connect(str(self._path))
            self._conn.execute(
                "CREATE TABLE IF NOT EXISTS visits ("
                " id INTEGER PRIMARY KEY AUTOINCREMENT,"
                " url TEXT NOT NULL,"
                " title TEXT NOT NULL DEFAULT '',"
                " visited_at INTEGER NOT NULL)"
            )
            self._conn.execute(
                "CREATE INDEX IF NOT EXISTS idx_visits_time ON visits(visited_at DESC)"
            )
            self._conn.commit()
        return self._conn

    def add_visit(self, url: str, title: str = "", dedupe_seconds: int = 20) -> None:
        """Reload/double load pe ek hi entry rahe (dedupe window ke andar)."""
        db = self._db()
        now = int(time.time())
        row = db.execute(
            "SELECT id FROM visits WHERE url = ? AND visited_at > ?",
            (url, now - dedupe_seconds),
        ).fetchone()
        if row:
            db.execute(
                "UPDATE visits SET title = ?, visited_at = ? WHERE id = ?",
                (title, now, row[0]),
            )
        else:
            db.execute(
                "INSERT INTO visits (url, title, visited_at) VALUES (?, ?, ?)",
                (url, title, now),
            )
        db.commit()

    def update_title(self, url: str, title: str) -> None:
        if not title:
            return
        db = self._db()
        db.execute(
            "UPDATE visits SET title = ? WHERE id = ("
            " SELECT id FROM visits WHERE url = ? ORDER BY visited_at DESC LIMIT 1)",
            (title, url),
        )
        db.commit()

    def search(self, query: str = "", limit: int = 300) -> list:
        db = self._db()
        q = query.strip()
        if q:
            esc = q.replace("\\", "\\\\").replace("%", "\\%").replace("_", "\\_")
            like = f"%{esc}%"
            rows = db.execute(
                "SELECT id, url, title, visited_at FROM visits"
                " WHERE title LIKE ? ESCAPE '\\' OR url LIKE ? ESCAPE '\\'"
                " ORDER BY visited_at DESC LIMIT ?",
                (like, like, limit),
            ).fetchall()
        else:
            rows = db.execute(
                "SELECT id, url, title, visited_at FROM visits"
                " ORDER BY visited_at DESC LIMIT ?",
                (limit,),
            ).fetchall()
        return [
            {"id": r[0], "url": r[1], "title": r[2], "visited_at": r[3]} for r in rows
        ]

    def top_sites(self, limit: int = 8, days: int = 90) -> list:
        """Sab se zyada visit hui sites (origin ke hisaab se): [{'url': origin, 'host': ..., 'count': n}]"""
        from urllib.parse import urlsplit

        since = int(time.time()) - days * 86400
        rows = self._db().execute(
            "SELECT url FROM visits WHERE visited_at > ? ORDER BY visited_at DESC LIMIT 5000", (since,)
        ).fetchall()
        counts: dict = {}
        for (url,) in rows:
            parts = urlsplit(url)
            if parts.scheme not in ("http", "https") or not parts.hostname:
                continue
            origin = f"{parts.scheme}://{parts.netloc}"
            counts[origin] = counts.get(origin, 0) + 1
        ranked = sorted(counts.items(), key=lambda kv: kv[1], reverse=True)[:limit]
        return [
            {"url": o + "/", "host": (urlsplit(o).hostname or o).removeprefix("www."), "count": n}
            for o, n in ranked
        ]

    def delete(self, visit_id: int) -> None:
        db = self._db()
        db.execute("DELETE FROM visits WHERE id = ?", (visit_id,))
        db.commit()

    def clear(self) -> None:
        db = self._db()
        db.execute("DELETE FROM visits")
        db.commit()