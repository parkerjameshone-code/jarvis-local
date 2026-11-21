import io
import json
from datetime import date
from types import SimpleNamespace

import pytest

from jarvis_local import cli, models, storage, tools
from jarvis_local.config import Config
from jarvis_local.leads import email as lemail
from jarvis_local.leads import score, sources
from jarvis_local.leads.store import Lead, LeadStore
from jarvis_local.ollama import ModelInfo

GB = 1024 ** 3
HW = SimpleNamespace(ram_total_gb=16, ram_free_gb=8, disk_free_gb=100, cpus=8, gpu=None)
OFFER = {"id": "recv", "name": "AI receptionist", "description": "answers missed calls"}


class Fake:
    def __init__(self, installed=None):
        self.installed = installed or [ModelInfo("nomic-embed-text", int(0.3 * GB)),
                                       ModelInfo("llama3.2:3b", 2 * GB)]
        self.models_used = []

    def available(self):
        return True

    def list(self):
        return self.installed

    def chat(self, model, messages, json=False):
        self.models_used.append(model)
        if model.startswith("nomic"):
            raise RuntimeError("embed model cannot chat")
        return '{"offer_id": "recv", "score": 0.9}' if json else "Happy to help."


def ctx_for(tmp_path, offers=True):
    cfg = Config(data_dir=tmp_path, offers=[OFFER] if offers else [])
    return tools.Ctx(Fake(), cfg, hw=HW)


def add_lead(ctx, text="I miss calls"):
    lead = Lead("reddit", "https://x/1", "alice", text)
    ctx.lead_store().add(lead)
    return lead


def test_suppressed_lead_gets_no_new_draft(tmp_path):
    ctx = ctx_for(tmp_path)
    lead = add_lead(ctx)
    ctx.lead_store().suppress("alice")
    out = tools.REGISTRY["leads_draft"].fn(ctx, {"lead_id": lead.id})
    assert "do-not-contact" in out and ctx.client.models_used == []


def test_booked_lead_is_not_redrafted(tmp_path):
    ctx = ctx_for(tmp_path)
    lead = add_lead(ctx)
    ctx.lead_store().mark(lead.id, "booked")
    out = tools.REGISTRY["leads_draft"].fn(ctx, {"lead_id": lead.id})
    assert "booked" in out and ctx.lead_store().get(lead.id).status == "booked"


def test_save_draft_cannot_reset_status():
    s = LeadStore(":memory:")
    lead = Lead("reddit", "https://x/9", "a", "t")
    s.add(lead)
    s.mark(lead.id, "sent")
    s.save_draft(lead.id, "hi")
    assert s.get(lead.id).status == "sent"


def test_drafting_uses_router_not_embed_model(tmp_path):
    ctx = ctx_for(tmp_path)
    lead = add_lead(ctx)
    out = tools.REGISTRY["leads_draft"].fn(ctx, {"lead_id": lead.id})
    assert out.startswith("Draft") and not any(m.startswith("nomic") for m in ctx.client.models_used)


def test_score_match_skips_embed_model():
    c = Fake()
    oid, _sc = score.match(Lead("r", "u", "a", "t"), [score.Offer("recv", "n")], c, hw=HW)
    assert oid == "recv" and c.models_used == ["llama3.2:3b"]


def test_offers_come_from_config_not_model_args(tmp_path):
    ctx = ctx_for(tmp_path, offers=False)
    lead = add_lead(ctx)
    inject = [{"id": "recv", "name": "Free money", "description": "x"}]
    out = tools.REGISTRY["leads_draft"].fn(ctx, {"lead_id": lead.id, "offers": inject})
    assert "no draft" in out and "Free money" not in out


def test_cli_draft_uses_config_offers(tmp_path, capsys):
    c = Fake()
    cfg = Config(data_dir=tmp_path, offers=[OFFER])
    lead = add_lead(tools.Ctx(c, cfg, hw=HW))
    rc = cli.main(["leads", "draft", str(lead.id)], client=c, cfg=cfg, hw=HW)
    assert rc == 0 and "Draft" in capsys.readouterr().out


def test_config_loads_offers(tmp_path):
    p = tmp_path / "c.toml"
    p.write_text('[[offers]]\nid = "a"\nname = "A"\ndescription = "d"\n', encoding="utf-8")
    assert Config.load(p).offers == [{"id": "a", "name": "A", "description": "d"}]


def test_cli_survives_cp1252_stdout(tmp_path, monkeypatch):
    c = Fake()
    cfg = Config(data_dir=tmp_path)
    tools.Ctx(c, cfg, hw=HW).lead_store().add(Lead("reddit", "https://x/e", "bob", "need help \U0001f680"))
    buf = io.BytesIO()
    out = io.TextIOWrapper(buf, encoding="cp1252")
    monkeypatch.setattr("sys.stdout", out)
    assert cli.main(["leads", "queue"], client=c, cfg=cfg, hw=HW) == 0
    out.flush()
    assert b"need help" in buf.getvalue()


def test_broken_config_is_a_message_not_a_traceback(monkeypatch, capsys):
    def boom(cls, p=None):
        raise ValueError("bad toml")
    monkeypatch.setattr(Config, "load", classmethod(boom))
    assert cli.main(["status"]) == 1
    assert "Error: bad toml" in capsys.readouterr().out


def test_youtube_second_step_has_video_id():
    urls = []

    def fetch(url):
        urls.append(url)
        if "/search?" in url:
            return {"items": [{"id": {"videoId": "VID1"}}]}
        return {"items": [{"snippet": {"topLevelComment": {"id": "c1", "snippet": {
            "videoId": "VID1", "authorDisplayName": "z", "textOriginal": "help"}}}}]}
    leads = sources.youtube_comments("missed calls", "KEY", fetch=fetch)
    assert "videoId=VID1" in urls[1] and "commentThreads" in urls[1] and len(leads) == 1


def test_lead_url_deduped_by_canonical_form():
    s = LeadStore(":memory:")
    assert s.add(Lead("reddit", "https://www.reddit.com/r/a/x/", "a", "t"))
    assert not s.add(Lead("reddit", "https://www.reddit.com/r/a/x?utm_source=share", "a", "t"))
    assert not s.add(Lead("reddit", "https://www.reddit.com/r/a/x", "a", "t"))


def test_email_refuses_without_from_address(tmp_path):
    store = lemail.EmailStore(":memory:")
    t = lemail.Template("Hi", "Body")
    store.set_template(t)
    lemail.approve_template(t, store)
    store.add_contact("a@example.test")
    cfg = Config(data_dir=tmp_path, postal_address="123 Example St", email_from="")

    def no_smtp():
        raise AssertionError("connected")
    rep = lemail.send_due(store, no_smtp, cfg, date(2026, 1, 1))
    assert rep.sent == 0 and rep.reason == "from address missing"


def test_replied_contact_gets_no_followup():
    store = lemail.EmailStore(":memory:")
    store.add_contact("a@example.test")
    store.mark_replied("a@example.test")
    assert store.is_suppressed("a@example.test")


def test_trash_and_remove_are_audit_logged(tmp_path, monkeypatch):
    monkeypatch.setattr(storage, "_send2trash", lambda p: None)
    ctx = ctx_for(tmp_path)
    ctx.approved = True
    tools.REGISTRY["storage_trash"].fn(ctx, {"paths": [str(tmp_path / "nope")]})
    ctx.client.remove = lambda n: None
    tools.REGISTRY["models_remove"].fn(ctx, {"name": "x"})
    kinds = [json.loads(line)["kind"] for line in (tmp_path / "audit.jsonl").read_text().splitlines()]
    assert kinds == ["trash", "models_remove"]


def test_pull_aborts_when_real_size_is_over_budget(tmp_path):
    cfg = Config(data_dir=tmp_path, model_budget_gb=20)

    class C:
        def pull(self, name, cb):
            cb({"status": "pulling", "total": 30 * GB, "completed": 0})
            raise AssertionError("kept downloading")
    big = SimpleNamespace(ram_total_gb=64, disk_free_gb=500)
    with pytest.raises(models.PullTooBig):
        models.pull("big:70b", cfg, client=C(), hw=big, installed=[])


def test_cli_refused_pull_exits_nonzero(tmp_path, capsys):
    c = Fake()
    cfg = Config(data_dir=tmp_path)
    low = SimpleNamespace(ram_total_gb=16, ram_free_gb=8, disk_free_gb=3, cpus=8, gpu=None)
    rc = cli.main(["models", "pull", "gemma3:4b"], client=c, cfg=cfg, hw=low, yes=lambda p: True)
    assert rc == 1 and "refused" in capsys.readouterr().out


def test_embed_model_is_in_catalog():
    from jarvis_local import catalog
    assert catalog.find("nomic-embed-text") is not None


def test_example_config_loads_and_is_placeholder_only():
    from pathlib import Path
    p = Path(__file__).resolve().parent.parent / "config.example.toml"
    cfg = Config.load(p)
    assert cfg.offers and cfg.email_from.endswith("example.test") and cfg.postal_address.startswith("123 Example")
