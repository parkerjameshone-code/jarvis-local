from datetime import date, timedelta
from types import SimpleNamespace

from jarvis_local.leads.email import (EmailStore, Template, approve_template,
                                      send_due, warmup)


class FakeSMTP:
    def __init__(self):
        self.sent = []

    def send_message(self, msg):
        self.sent.append(msg)

    def __enter__(self):
        return self

    def __exit__(self, *a):
        return False


def make(tmp_path, n=3, cap=20):
    store = EmailStore(tmp_path / "e.db")
    for i in range(n):
        store.add_contact(f"p{i}@example.test")
    cfg = SimpleNamespace(email_daily_cap=cap, postal_address="1 Test St, Testville",
                          email_from="me@example.test")
    smtp = FakeSMTP()
    return store, cfg, smtp, (lambda: smtp)


T = Template("Hello", "Body text")
D = date(2026, 1, 1)


def ready(store):
    store.set_template(T)
    approve_template(T, store)


def test_unapproved_sends_nothing(tmp_path):
    store, cfg, smtp, f = make(tmp_path)
    store.set_template(T)
    assert send_due(store, f, cfg, D).sent == 0 and not smtp.sent


def test_edited_after_approval_sends_nothing(tmp_path):
    store, cfg, smtp, f = make(tmp_path)
    ready(store)
    edited = Template("Hello", "Body text EDITED")
    store.set_template(edited)
    assert send_due(store, f, cfg, D).sent == 0
    approve_template(edited, store)
    assert send_due(store, f, cfg, D).sent == 3


def test_cap_stops(tmp_path):
    store, cfg, smtp, f = make(tmp_path, n=5, cap=2)
    ready(store)
    assert send_due(store, f, cfg, D).sent == 2 and len(smtp.sent) == 2
    assert send_due(store, f, cfg, D).sent == 0
    assert send_due(store, f, cfg, D + timedelta(days=1)).sent == 2


def test_warmup_curve():
    assert warmup(0) == 20 and warmup(7) == 30 and warmup(100) == 100


def test_footer_and_suppressed(tmp_path):
    store, cfg, smtp, f = make(tmp_path, n=2)
    store.suppress("p0@example.test")
    ready(store)
    r = send_due(store, f, cfg, D)
    assert r.sent == 1 and r.skipped == 1
    body = smtp.sent[0].get_content()
    assert "1 Test St, Testville" in body and "unsubscribe" in body.lower()
    assert smtp.sent[0]["To"] == "p1@example.test"


def test_no_postal_address_refuses(tmp_path):
    store, cfg, smtp, f = make(tmp_path)
    cfg.postal_address = ""
    ready(store)
    assert send_due(store, f, cfg, D).sent == 0 and not smtp.sent


def test_followups_at_3_and_7_days(tmp_path):
    store, cfg, smtp, f = make(tmp_path, n=1)
    ready(store)
    assert send_due(store, f, cfg, D).sent == 1
    assert send_due(store, f, cfg, D + timedelta(days=2)).sent == 0
    assert send_due(store, f, cfg, D + timedelta(days=3)).sent == 1
    assert smtp.sent[-1]["Subject"].startswith("Re:")
    assert send_due(store, f, cfg, D + timedelta(days=6)).sent == 0
    assert send_due(store, f, cfg, D + timedelta(days=7)).sent == 1
    assert send_due(store, f, cfg, D + timedelta(days=30)).sent == 0


def test_unsubscribe_stops_followups(tmp_path):
    store, cfg, smtp, f = make(tmp_path, n=1)
    ready(store)
    send_due(store, f, cfg, D)
    store.suppress("p0@example.test")
    assert send_due(store, f, cfg, D + timedelta(days=3)).sent == 0
