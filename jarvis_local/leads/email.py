"""Compliant, capped email outreach.

Auto-send happens only when the current template's hash equals the approved
hash and today's cap is not reached. Every message carries a postal address
and an unsubscribe line; suppressed addresses are never mailed.
"""
from __future__ import annotations

import hashlib
import sqlite3
from dataclasses import dataclass
from datetime import date, timedelta
from email.message import EmailMessage
from pathlib import Path

FOLLOWUP_DAYS = (0, 3, 7)  # days after the first send for steps 0, 1, 2


@dataclass
class Template:
    subject: str
    body: str

    def hash(self) -> str:
        raw = f"{self.subject}\n\x00\n{self.body}".encode("utf-8")
        return hashlib.sha256(raw).hexdigest()


@dataclass
class SendReport:
    sent: int = 0
    skipped: int = 0
    reason: str = ""


def warmup(day: int) -> int:
    """20/day to start, +10 per full week, max 100."""
    return min(100, 20 + 10 * (max(day, 0) // 7))


_SCHEMA = """
CREATE TABLE IF NOT EXISTS contacts(email TEXT PRIMARY KEY);
CREATE TABLE IF NOT EXISTS suppressed(email TEXT PRIMARY KEY);
CREATE TABLE IF NOT EXISTS sent(email TEXT, step INTEGER, day TEXT,
                                PRIMARY KEY(email, step));
CREATE TABLE IF NOT EXISTS kv(k TEXT PRIMARY KEY, v TEXT);
"""


class EmailStore:
    def __init__(self, db: Path | str):
        self.db = sqlite3.connect(str(db))
        self.db.executescript(_SCHEMA)

    def _get(self, k):
        r = self.db.execute("SELECT v FROM kv WHERE k=?", (k,)).fetchone()
        return r[0] if r else None

    def _put(self, k, v):
        self.db.execute("INSERT OR REPLACE INTO kv VALUES(?,?)", (k, v))
        self.db.commit()

    def add_contact(self, email: str) -> None:
        self.db.execute("INSERT OR IGNORE INTO contacts VALUES(?)",
                        (email.strip().lower(),))
        self.db.commit()

    def suppress(self, email: str) -> None:
        self.db.execute("INSERT OR IGNORE INTO suppressed VALUES(?)",
                        (email.strip().lower(),))
        self.db.commit()

    def is_suppressed(self, email: str) -> bool:
        return self.db.execute("SELECT 1 FROM suppressed WHERE email=?",
                               (email.strip().lower(),)).fetchone() is not None

    def set_template(self, t: Template) -> None:
        self._put("subject", t.subject)
        self._put("body", t.body)

    def template(self) -> Template | None:
        s, b = self._get("subject"), self._get("body")
        return None if s is None or b is None else Template(s, b)

    def approve_hash(self, h: str) -> None:
        self._put("approved_hash", h)

    def approved_hash(self) -> str | None:
        return self._get("approved_hash")

    def contacts(self) -> list[str]:
        return [r[0] for r in self.db.execute("SELECT email FROM contacts ORDER BY rowid")]

    def steps(self, email: str) -> dict[int, date]:
        return {s: date.fromisoformat(d) for s, d in self.db.execute(
            "SELECT step, day FROM sent WHERE email=?", (email,))}

    def record_send(self, email: str, step: int, day: date) -> None:
        self.db.execute("INSERT OR IGNORE INTO sent VALUES(?,?,?)",
                        (email, step, day.isoformat()))
        self.db.commit()

    def sent_on(self, day: date) -> int:
        return self.db.execute("SELECT COUNT(*) FROM sent WHERE day=?",
                               (day.isoformat(),)).fetchone()[0]

    def first_send_day(self) -> date | None:
        r = self.db.execute("SELECT MIN(day) FROM sent").fetchone()[0]
        return date.fromisoformat(r) if r else None


def approve_template(t: Template, store: EmailStore) -> None:
    store.approve_hash(t.hash())


def _next_step(done: dict[int, date], today: date) -> int | None:
    if 0 not in done:
        return 0
    for step in (1, 2):
        if step not in done:
            due = done[0] + timedelta(days=FOLLOWUP_DAYS[step])
            return step if today >= due else None
    return None


def _build(t: Template, step: int, to: str, cfg) -> EmailMessage:
    msg = EmailMessage()
    msg["From"] = getattr(cfg, "email_from", "")
    msg["To"] = to
    msg["Subject"] = t.subject if step == 0 else f"Re: {t.subject}"
    unsub = getattr(cfg, "unsubscribe_email", "") or getattr(cfg, "email_from", "")
    footer = (f"\n\n--\n{cfg.postal_address}\n"
              "To unsubscribe, reply with \"unsubscribe\""
              + (f" or write to {unsub}." if unsub else "."))
    msg.set_content(t.body + footer)
    return msg


def send_due(store: EmailStore, smtp_factory, cfg, today: date) -> SendReport:
    rep = SendReport()
    t = store.template()
    if t is None or store.approved_hash() != t.hash():
        rep.reason = "template not approved"
        return rep
    if not str(getattr(cfg, "postal_address", "") or "").strip():
        rep.reason = "postal address missing"
        return rep
    first = store.first_send_day()
    cap = min(cfg.email_daily_cap, warmup((today - first).days if first else 0))
    left = cap - store.sent_on(today)
    if left <= 0:
        rep.reason = "daily cap reached"
        return rep
    todo = []
    for email in store.contacts():
        if store.is_suppressed(email):
            rep.skipped += 1
            continue
        step = _next_step(store.steps(email), today)
        if step is not None:
            todo.append((email, step))
    if not todo:
        return rep
    with smtp_factory() as smtp:
        for email, step in todo[:left]:
            smtp.send_message(_build(t, step, email, cfg))
            store.record_send(email, step, today)
            rep.sent += 1
    return rep
