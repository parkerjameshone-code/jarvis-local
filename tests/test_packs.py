import json
from pathlib import Path

from jarvis_local import packs
from jarvis_local.packs import EvalResult, Pack

EXAMPLE = Path(__file__).parent.parent / "packs" / "example-reply"


class Chat:
    def __init__(self, out):
        self.out, self.created = out, []

    def chat(self, model, messages, json=False):
        return self.out

    def create(self, name, modelfile):
        self.created.append((name, modelfile))


def test_modelfile():
    mf = Pack.load(EXAMPLE).modelfile()
    assert mf.startswith("FROM ") and "SYSTEM " in mf
    assert mf.count("MESSAGE user") == 2 and mf.count("MESSAGE assistant") == 2
    assert "PARAMETER temperature 0.4" in mf


def test_build():
    c = Chat("x")
    assert packs.build(Pack.load(EXAMPLE), c) == "jarvis-example-reply"
    assert c.created[0][0] == "jarvis-example-reply"


def _mk(tmp_path, cases):
    (tmp_path / "pack.toml").write_text('name="t"\nbase="b"\nsystem="s"\n')
    (tmp_path / "evals.jsonl").write_text("\n".join(json.dumps(c) for c in cases))
    return Pack.load(tmp_path)


def test_evaluate_counts(tmp_path):
    p = _mk(tmp_path, [
        {"prompt": "a", "checks": [{"type": "contains", "value": "HELLO"}]},
        {"prompt": "b", "checks": [{"type": "regex", "value": "^hel+o"}]},
        {"prompt": "c", "checks": [{"type": "json"}]},
        {"prompt": "d", "checks": [{"type": "max_words", "value": 1}]},
    ])
    r = packs.evaluate(p, Chat("hello there"), "m")
    assert (r.passed, r.total) == (2, 4) and len(r.fails) == 2


def test_evaluate_json_ok(tmp_path):
    p = _mk(tmp_path, [{"prompt": "p", "checks": [{"type": "json"}]}])
    assert packs.evaluate(p, Chat('{"ok":1}'), "m").passed == 1


def test_promote_threshold(tmp_path):
    p = Pack.load(EXAMPLE)
    p.path = tmp_path
    assert packs.promote(p, EvalResult(3, 5)) is False
    assert not (tmp_path / "promoted.json").exists()
    assert packs.promote(p, EvalResult(4, 5)) is True
    assert packs.promote(p, EvalResult(0, 0)) is False
