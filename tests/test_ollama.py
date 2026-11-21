import json

import pytest

from jarvis_local.config import Config
from jarvis_local import log
from jarvis_local.ollama import ModelInfo, OllamaClient, OllamaDown


def test_list_parses_names_and_sizes(fake_ollama):
    fake_ollama.routes[("GET", "/api/tags")] = {
        "models": [{"name": "a:1b", "size": 1000}, {"name": "b:3b", "size": 3000}]}
    c = OllamaClient(fake_ollama.url)
    assert c.list() == [ModelInfo("a:1b", 1000), ModelInfo("b:3b", 3000)]
    assert c.available() is True


def test_connection_refused_raises_ollama_down(dead_url):
    c = OllamaClient(dead_url)
    assert c.available() is False
    with pytest.raises(OllamaDown):
        c.list()
    with pytest.raises(OllamaDown):
        c.chat("m", [{"role": "user", "content": "hi"}])


def test_chat_and_json_mode(fake_ollama):
    fake_ollama.routes[("POST", "/api/chat")] = {"message": {"content": "hello"}}
    c = OllamaClient(fake_ollama.url)
    assert c.chat("m", [{"role": "user", "content": "x"}], json=True) == "hello"
    body = json.loads(fake_ollama.seen[-1][2])
    assert body["format"] == "json" and body["stream"] is False


def test_embed(fake_ollama):
    fake_ollama.routes[("POST", "/api/embed")] = {"embeddings": [[1.0, 0.0], [0.0, 1.0]]}
    assert OllamaClient(fake_ollama.url).embed("e", ["a", "b"]) == [[1.0, 0.0], [0.0, 1.0]]


def test_pull_reports_progress_and_remove(fake_ollama):
    fake_ollama.routes[("POST", "/api/pull")] = (
        '{"status":"pulling","completed":5,"total":10}\n{"status":"success"}\n')
    fake_ollama.routes[("DELETE", "/api/delete")] = {}
    c = OllamaClient(fake_ollama.url)
    got = []
    c.pull("m", got.append)
    assert got[0]["completed"] == 5 and got[-1]["status"] == "success"
    c.remove("m")
    assert fake_ollama.seen[-1][0] == "DELETE"


def test_config_defaults_and_load(tmp_path):
    cfg = Config.load(tmp_path / "missing.toml")
    assert cfg.ollama_url == "http://127.0.0.1:11434"
    assert (cfg.model_budget_gb, cfg.disk_reserve_gb, cfg.email_daily_cap) == (20, 5, 20)
    p = tmp_path / "c.toml"
    p.write_text('ollama_url = "http://x:1"\ndata_dir = "%s"\nemail_daily_cap = 7\n'
                 % str(tmp_path).replace("\\", "/"))
    cfg = Config.load(p)
    assert cfg.ollama_url == "http://x:1" and cfg.email_daily_cap == 7
    assert cfg.data_dir == tmp_path


def test_audit_log_appends_jsonl_and_never_raises_on_unicode(tmp_path):
    cfg = Config(data_dir=tmp_path)
    log.event("test", cfg=cfg, msg="café ☃")
    log.event("test2", cfg=cfg, n=1)
    lines = (tmp_path / "audit.jsonl").read_text(encoding="utf-8").splitlines()
    assert json.loads(lines[0])["kind"] == "test" and json.loads(lines[1])["n"] == 1
