import inspect
import json
from pathlib import Path
from types import SimpleNamespace

from jarvis_local.leads import drafts, score, sources, store
from jarvis_local.leads.score import Offer
from jarvis_local.leads.store import Lead, LeadStore
from jarvis_local.ollama import ModelInfo

HW = SimpleNamespace(ram_total_gb=16, ram_free_gb=8, disk_free_gb=100, cpus=8, gpu=None)
OFFERS = [Offer("recv", "AI receptionist", "answers missed calls")]


class FakeClient:
    def __init__(self, reply):
        self.reply, self.calls = reply, []

    def list(self):
        return [ModelInfo("llama3.2:1b", int(1.3 * 1024 ** 3)), ModelInfo("llama3.2:3b", 2 * 1024 ** 3)]

    def chat(self, model, messages, json=False):
        self.calls.append(model)
        return self.reply


def L(url="https://x/1", author="a"):
    return Lead("reddit", url, author, "I miss calls", 1.0)


def test_dedupe_and_suppression():
    s = LeadStore(":memory:")
    assert s.add(L()) is True
    assert s.add(L()) is False
    s.suppress("Bad_Author")
    assert s.add(L("https://x/2", "bad_author")) is False
    s.suppress("https://x/3/")
    assert s.add(L("https://x/3")) is False
    assert len(s.queue()) == 1


def test_suppress_after_add_hides_from_queue():
    s = LeadStore(":memory:")
    s.add(L())
    s.suppress("a")
    assert s.queue() == []


def test_mark_and_queue():
    s = LeadStore(":memory:")
    lead = L()
    s.add(lead)
    s.mark(lead.id, "sent")
    assert s.queue() == []
    try:
        s.mark(lead.id, "bogus")
        assert False
    except ValueError:
        pass


def test_reddit_parser_sample():
    data = json.loads((Path(__file__).parent / "data" / "reddit_sample.json").read_text())
    leads = sources.parse_reddit(data)
    assert len(leads) == 1
    assert leads[0].url.startswith("https://www.reddit.com/r/smallbusiness")
    assert leads[0].author == "shopguy" and "Missing calls" in leads[0].text


def test_reddit_search_uses_fetch_no_network():
    got = []
    sources.reddit_search("q", 5, fetch=lambda u: got.append(u) or {"data": {"children": []}})
    assert "search.json" in got[0]


def test_score_match_and_threshold():
    c = FakeClient('{"offer_id":"recv","score":0.9}')
    assert score.match(L(), OFFERS, c, hw=HW) == ("recv", 0.9)
    assert c.calls == ["llama3.2:1b"]  # fast tier
    low = FakeClient('{"offer_id":"recv","score":0.3}')
    assert score.match(L(), OFFERS, low, hw=HW)[0] is None
    assert score.match(L(), OFFERS, FakeClient("not json"), hw=HW) == (None, 0.0)
    assert score.match(L(), OFFERS, FakeClient('{"offer_id":"zzz","score":0.9}'), hw=HW)[0] is None


def test_below_threshold_no_draft():
    c = FakeClient("hi")
    assert drafts.suggest(L(), OFFERS[0], c, score=0.4, hw=HW) is None
    assert drafts.suggest(L(), None, c, score=0.9, hw=HW) is None
    assert c.calls == []
    d = drafts.suggest(L(), OFFERS[0], c, score=0.8, hw=HW)
    assert d.text == "hi" and d.url == "https://x/1" and c.calls == ["llama3.2:3b"]  # balanced tier


def test_no_function_sends_a_social_message():
    for mod in (drafts, sources, score, store):
        for name, _ in inspect.getmembers(mod, inspect.isfunction):
            assert "send" not in name.lower(), (mod.__name__, name)
        for _, cls in inspect.getmembers(mod, inspect.isclass):
            for name, _ in inspect.getmembers(cls, inspect.isfunction):
                assert "send" not in name.lower(), (cls, name)
