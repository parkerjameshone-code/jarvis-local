"""SQLite lead store with dedupe-by-url and a suppression list."""
from __future__ import annotations

import sqlite3
import time
import urllib.parse
from dataclasses import dataclass, field
from pathlib import Path

STATUSES = ("new", "drafted", "sent", "skipped", "replied", "booked")
_COLS = "id,source,url,author,text,found_at,status,offer_id,score,draft"


@dataclass
class Lead:
    source: str
    url: str
    author: str
    text: str
    found_at: float = field(default_factory=time.time)
    id: int | None = None
    status: str = "new"
    offer_id: str | None = None
    score: float | None = None
    draft: str | None = None


def _norm(s: str) -> str:
    return (s or "").strip().lower().rstrip("/")


def canonical_url(url: str) -> str:
    """Same post, same key: drop fragment, tracking params and the trailing slash."""
    u = urllib.parse.urlsplit((url or "").strip())
    q = [(k, v) for k, v in urllib.parse.parse_qsl(u.query, keep_blank_values=True)
         if not k.lower().startswith("utm_") and k.lower() not in ("ref", "share_id")]
    path = u.path.rstrip("/")
    return urllib.parse.urlunsplit((u.scheme.lower(), u.netloc.lower(), path,
                                    urllib.parse.urlencode(q), ""))


class LeadStore:
    def __init__(self, db):
        if str(db) != ":memory:":
            Path(db).parent.mkdir(parents=True, exist_ok=True)
        self.con = sqlite3.connect(str(db))
        self.con.executescript("""
        CREATE TABLE IF NOT EXISTS leads(
          id INTEGER PRIMARY KEY, source TEXT, url TEXT UNIQUE, author TEXT, text TEXT,
          found_at REAL, status TEXT DEFAULT 'new', offer_id TEXT, score REAL, draft TEXT);
        CREATE TABLE IF NOT EXISTS suppressed(key TEXT PRIMARY KEY);
        """)

    def suppress(self, key: str) -> None:
        """Never lead/draft for this author handle or url."""
        self.con.execute("INSERT OR IGNORE INTO suppressed(key) VALUES(?)", (_norm(key),))
        self.con.commit()

    def is_suppressed(self, lead: Lead) -> bool:
        row = self.con.execute("SELECT 1 FROM suppressed WHERE key IN (?,?)",
                               (_norm(lead.url), _norm(lead.author))).fetchone()
        return row is not None

    def add(self, lead: Lead) -> bool:
        """True if stored; False for a duplicate url or a suppressed lead."""
        if not lead.url or self.is_suppressed(lead):
            return False
        lead.url = canonical_url(lead.url)
        cur = self.con.execute(
            "INSERT OR IGNORE INTO leads(source,url,author,text,found_at) VALUES(?,?,?,?,?)",
            (lead.source, lead.url, lead.author, lead.text, lead.found_at))
        self.con.commit()
        if cur.rowcount:
            lead.id = cur.lastrowid
        return bool(cur.rowcount)

    @staticmethod
    def _row(r) -> Lead:
        return Lead(source=r[1], url=r[2], author=r[3], text=r[4], found_at=r[5], id=r[0],
                    status=r[6], offer_id=r[7], score=r[8], draft=r[9])

    def queue(self) -> list[Lead]:
        """Leads still needing attention (new or drafted), newest first."""
        rows = self.con.execute(
            f"SELECT {_COLS} FROM leads WHERE status IN ('new','drafted') "
            "ORDER BY found_at DESC, id DESC").fetchall()
        leads = [self._row(r) for r in rows]
        return [l for l in leads if not self.is_suppressed(l)]

    def get(self, lead_id: int) -> Lead | None:
        r = self.con.execute(f"SELECT {_COLS} FROM leads WHERE id=?", (lead_id,)).fetchone()
        return self._row(r) if r else None

    def mark(self, lead_id: int, status: str) -> None:
        if status not in STATUSES:
            raise ValueError(f"bad status {status!r}")
        self.con.execute("UPDATE leads SET status=? WHERE id=?", (status, lead_id))
        self.con.commit()

    def save_match(self, lead_id: int, offer_id: str | None, score: float) -> None:
        self.con.execute("UPDATE leads SET offer_id=?, score=? WHERE id=?", (offer_id, score, lead_id))
        self.con.commit()

    def save_draft(self, lead_id: int, text: str) -> None:
        self.con.execute("UPDATE leads SET draft=?, status='drafted' WHERE id=? AND status IN ('new','drafted')",
                         (text, lead_id))
        self.con.commit()
