import json
from types import SimpleNamespace

from jarvis_local import agent, tools
from jarvis_local.config import Config
from jarvis_local.ollama import ModelInfo

GB = 1024 ** 3
HW = SimpleNamespace(ram_total_gb=16, ram_free_gb=8, disk_free_gb=100, cpus=8, gpu=None)


class Fake:
    def __init__(self, replies):
        self.replies = list(replies)
        self.calls = []

    def list(self):
        return [ModelInfo("qwen3:4b", int(2.6 * GB)), ModelInfo("llama3.2:3b", 2 * GB)]

    def chat(self, model, messages, json=False):
        self.calls.append(messages)
        return self.replies.pop(0) if self.replies else "ok"


def mk(replies, tmp_path):
    cfg = Config(data_dir=tmp_path)
    c = Fake(replies)
    return c, agent.Agent(c, cfg, hw=HW)


def test_tool_call_runs(tmp_path):
    c, a = mk([json.dumps({"tool": "models_list", "args": {}}), json.dumps({"final": "done"}), "looks right"], tmp_path)
    rep = a.run("what models", lambda s: False)
    assert rep.steps[0].status == "ran" and "qwen3:4b" in rep.steps[0].output
    assert rep.final == "done" and rep.checked == "looks right"


def test_ask_tool_skipped_when_not_approved(tmp_path):
    ran = []
    orig = tools.REGISTRY["shell_run"]
    tools.REGISTRY["shell_run"] = tools.Tool(lambda ctx, a: ran.append(1) or "x", "ask")
    try:
        c, a = mk([json.dumps({"tool": "shell_run", "args": {"cmd": "pip install x"}}),
                   json.dumps({"final": "ok"}), "c"], tmp_path)
        rep = a.run("go", lambda s: False)
    finally:
        tools.REGISTRY["shell_run"] = orig
    assert not ran and rep.steps[0].status == "skipped" and rep.skipped


def test_ask_tool_runs_when_approved_and_flag_resets(tmp_path):
    seen = []
    orig = tools.REGISTRY["shell_run"]
    tools.REGISTRY["shell_run"] = tools.Tool(lambda ctx, a: seen.append(ctx.approved) or "x", "ask")
    try:
        c, a = mk([json.dumps({"tool": "shell_run", "args": {}}), json.dumps({"final": "ok"}), "c"], tmp_path)
        a.run("go", lambda s: True)
    finally:
        tools.REGISTRY["shell_run"] = orig
    assert seen == [True] and a.ctx.approved is False


def test_unknown_and_never_tools_refused(tmp_path):
    c, a = mk([json.dumps({"tool": "rm_rf", "args": {}}), json.dumps({"tool": "social_send", "args": {}}),
               json.dumps({"final": "ok"}), "c"], tmp_path)
    rep = a.run("go", lambda s: True)
    assert [s.status for s in rep.steps] == ["refused", "refused"]


def test_step_limit_and_bad_json(tmp_path):
    c, a = mk(["not json"] + [json.dumps({"tool": "hardware", "args": {}})] * 20, tmp_path)
    rep = a.run("loop", lambda s: False)
    assert len(rep.steps) <= agent.MAX_STEPS and "limit" in rep.final


def test_tool_error_is_reported_not_raised(tmp_path):
    c, a = mk([json.dumps({"tool": "models_remove", "args": {}}), json.dumps({"final": "ok"}), "c"], tmp_path)
    rep = a.run("go", lambda s: True)
    assert rep.steps[0].status == "error"


def test_registry_has_no_social_send_path():
    assert tools.REGISTRY["social_send"].risk == "never"
    assert tools.REGISTRY["email_send_due"].risk == "ask"
    assert tools.REGISTRY["shell_run"].risk == "ask"
