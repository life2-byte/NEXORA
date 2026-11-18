"""Downloads ki history (SQLite). Qt ka koi code nahi."""

import sqlite3
import time
from pathlib import Path


class DownloadStore:
    """GUI thread se use karo (ek connection)."""

    def __init__(self, path):
        self._path = Path(path)
        self._conn = None

    def _db(self) -> sqlite3.Connection:
        if self._conn is None:
            self._path.parent.mkdir(parents=True, exist_ok=True)
            self._conn = sqlite3.connect(str(self._path))
            self._conn.execute(
                "CREATE TABLE IF NOT EXISTS downloads ("
                " id INTEGER PRIMARY KEY AUTOINCREMENT,"
                " name TEXT NOT NULL,"
                " folder TEXT NOT NULL,"
                " path TEXT NOT NULL,"
                " url TEXT NOT NULL DEFAULT '',"
                " state TEXT NOT NULL,"
                " received INTEGER NOT NULL DEFAULT 0,"
                " total INTEGER NOT NULL DEFAULT 0,"
                " created_at INTEGER NOT NULL)"
            )
            self._conn.commit()
        return self._conn

    def add(self, name: str, folder: str, path: str, url: str) -> int:
        db = self._db()
        cur = db.execute(
            "INSERT INTO downloads (name, folder, path, url, state, created_at)"
            " VALUES (?, ?, ?, ?, 'downloading', ?)",
            (name, folder, path, url, int(time.time())),
        )
        db.commit()
        return int(cur.lastrowid)

    def update(self, item_id: int, state: str, received: int, total: int) -> None:
        db = self._db()
        db.execute(
            "UPDATE downloads SET state = ?, received = ?, total = ? WHERE id = ?",
            (state, received, total, item_id),
        )
        db.commit()

    def mark_interrupted(self) -> None:
        """Pichli baar app band hone par jo adhoore the, unko failed maan lo."""
        db = self._db()
        db.execute("UPDATE downloads SET state = 'failed' WHERE state = 'downloading'")
        db.commit()

    def load(self, limit: int = 200) -> list:
        rows = self._db().execute(
            "SELECT id, name, folder, path, url, state, received, total FROM downloads"
            " ORDER BY id DESC LIMIT ?",
            (limit,),
        ).fetchall()
        keys = ("id", "name", "folder", "path", "url", "state", "received", "total")
        return [dict(zip(keys, row)) for row in rows]

    def delete(self, item_id: int) -> None:
        db = self._db()
        db.execute("DELETE FROM downloads WHERE id = ?", (item_id,))
        db.commit()

    def delete_finished(self) -> None:
        db = self._db()
        db.execute("DELETE FROM downloads WHERE state != 'downloading'")
        db.commit()