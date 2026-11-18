"""Bookmarks ka storage (SQLite). Qt ka koi code nahi."""

import sqlite3
import time
from pathlib import Path


class BookmarkStore:
    """GUI thread se use karo (ek connection)."""

    def __init__(self, path):
        self._path = Path(path)
        self._conn = None

    def _db(self) -> sqlite3.Connection:
        if self._conn is None:
            self._path.parent.mkdir(parents=True, exist_ok=True)
            self._conn = sqlite3.connect(str(self._path))
            self._conn.execute(
                "CREATE TABLE IF NOT EXISTS bookmarks ("
                " id INTEGER PRIMARY KEY AUTOINCREMENT,"
                " url TEXT NOT NULL UNIQUE,"
                " title TEXT NOT NULL DEFAULT '',"
                " created_at INTEGER NOT NULL)"
            )
            cols = [r[1] for r in self._conn.execute("PRAGMA table_info(bookmarks)")]
            if "folder" not in cols:  # purani database: folder column add karo
                self._conn.execute("ALTER TABLE bookmarks ADD COLUMN folder TEXT NOT NULL DEFAULT ''")
            self._conn.commit()
        return self._conn

    @staticmethod
    def normalize(url: str) -> str:
        """#fragment hata do, taake same page ek hi bookmark rahe."""
        return url.split("#", 1)[0]

    def add(self, url: str, title: str = "", folder: str = "") -> bool:
        """True = naya bookmark bana, False = pehle se tha."""
        url = self.normalize(url)
        db = self._db()
        cur = db.execute(
            "INSERT OR IGNORE INTO bookmarks (url, title, created_at, folder) VALUES (?, ?, ?, ?)",
            (url, title or url, int(time.time()), folder.strip()[:60]),
        )
        db.commit()
        return cur.rowcount > 0

    def remove_by_url(self, url: str) -> None:
        db = self._db()
        db.execute("DELETE FROM bookmarks WHERE url = ?", (self.normalize(url),))
        db.commit()

    def is_bookmarked(self, url: str) -> bool:
        row = self._db().execute(
            "SELECT 1 FROM bookmarks WHERE url = ?", (self.normalize(url),)
        ).fetchone()
        return row is not None

    def search(self, query: str = "", limit: int = 500, folder=None) -> list:
        """folder=None: sab, folder='': bina folder wale, folder='X': sirf X."""
        db = self._db()
        where, args = [], []
        q = query.strip()
        if q:
            esc = q.replace("\\", "\\\\").replace("%", "\\%").replace("_", "\\_")
            like = f"%{esc}%"
            where.append("(title LIKE ? ESCAPE '\\' OR url LIKE ? ESCAPE '\\')")
            args += [like, like]
        if folder is not None:
            where.append("folder = ?")
            args.append(folder)
        sql = "SELECT id, url, title, created_at, folder FROM bookmarks"
        if where:
            sql += " WHERE " + " AND ".join(where)
        sql += " ORDER BY created_at DESC, id DESC LIMIT ?"
        rows = db.execute(sql, args + [limit]).fetchall()
        return [
            {"id": r[0], "url": r[1], "title": r[2], "created_at": r[3], "folder": r[4]} for r in rows
        ]

    def folders(self) -> list:
        rows = self._db().execute(
            "SELECT folder, COUNT(*) FROM bookmarks WHERE folder != '' GROUP BY folder ORDER BY folder COLLATE NOCASE"
        ).fetchall()
        return [{"name": r[0], "count": r[1]} for r in rows]

    def set_folder(self, bookmark_id: int, folder: str) -> None:
        db = self._db()
        db.execute("UPDATE bookmarks SET folder = ? WHERE id = ?", (folder.strip()[:60], bookmark_id))
        db.commit()

    def rename_folder(self, old: str, new: str) -> None:
        db = self._db()
        db.execute("UPDATE bookmarks SET folder = ? WHERE folder = ?", (new.strip()[:60], old))
        db.commit()

    def delete_folder(self, name: str, with_bookmarks: bool = False) -> None:
        db = self._db()
        if with_bookmarks:
            db.execute("DELETE FROM bookmarks WHERE folder = ?", (name,))
        else:
            db.execute("UPDATE bookmarks SET folder = '' WHERE folder = ?", (name,))
        db.commit()

    # ---------- import / export (Chrome, Firefox, Edge ki bookmarks.html) ----------
    def import_html(self, path) -> tuple:
        """(naye bookmarks, pehle se maujood)"""
        from html.parser import HTMLParser

        found: list = []

        class Parser(HTMLParser):
            def __init__(self):
                super().__init__()
                self.stack: list = []      # har <DL> level ka folder naam
                self.pending = ""          # <H3> ka text abhi aane wala
                self.mode = ""             # "h3" ya "a"
                self.href = ""
                self.text = ""

            def handle_starttag(self, tag, attrs):
                tag = tag.lower()
                if tag == "h3":
                    self.mode, self.text = "h3", ""
                elif tag == "a":
                    self.mode, self.text = "a", ""
                    self.href = dict(attrs).get("href", "") or ""
                elif tag == "dl":
                    self.stack.append(self.pending)
                    self.pending = ""

            def handle_endtag(self, tag):
                tag = tag.lower()
                if tag == "h3" and self.mode == "h3":
                    self.pending = self.text.strip()
                    self.mode = ""
                elif tag == "a" and self.mode == "a":
                    if self.href.startswith(("http://", "https://")):
                        folder = next((f for f in reversed(self.stack) if f), "")
                        found.append((self.href, self.text.strip(), folder))
                    self.mode = ""
                elif tag == "dl" and self.stack:
                    self.stack.pop()

            def handle_data(self, data):
                if self.mode:
                    self.text += data

        raw = Path(path).read_bytes().decode("utf-8", errors="replace")
        Parser().feed(raw)
        new = 0
        for url, title, folder in found:
            if folder.lower() in ("bookmarks bar", "bookmarks toolbar", "other bookmarks", "bookmarks menu"):
                folder = ""
            if self.add(url, title, folder):
                new += 1
        return new, len(found) - new

    def export_html(self, path) -> int:
        from html import escape

        rows = self.search(limit=100000)
        by_folder: dict = {}
        for r in rows:
            by_folder.setdefault(r["folder"], []).append(r)

        def item(r):
            return f'    <DT><A HREF="{escape(r["url"], quote=True)}" ADD_DATE="{r["created_at"]}">{escape(r["title"])}</A>\n'

        out = ['<!DOCTYPE NETSCAPE-Bookmark-file-1>\n<META HTTP-EQUIV="Content-Type" CONTENT="text/html; charset=UTF-8">\n',
               "<TITLE>Bookmarks</TITLE>\n<H1>Bookmarks</H1>\n<DL><p>\n"]
        for r in by_folder.pop("", []):
            out.append(item(r))
        for name in sorted(by_folder, key=str.lower):
            out.append(f"    <DT><H3>{escape(name)}</H3>\n    <DL><p>\n")
            out.extend("    " + item(r) for r in by_folder[name])
            out.append("    </DL><p>\n")
        out.append("</DL><p>\n")
        Path(path).write_text("".join(out), encoding="utf-8")
        return len(rows)

    def delete(self, bookmark_id: int) -> None:
        db = self._db()
        db.execute("DELETE FROM bookmarks WHERE id = ?", (bookmark_id,))
        db.commit()