import json

from jarvis_local import tools
from test_agent import mk


def _run(tmp_path, cmd, approve):
    ran = []
    orig = tools.REGISTRY["shell_run"]
    tools.REGISTRY["shell_run"] = tools.Tool(lambda ctx, a: ran.append(a) or "x", "ask")
    try:
        _c, a = mk([json.dumps({"tool": "shell_run", "args": {"cmd": cmd}}),
                    json.dumps({"final": "ok"}), "c"], tmp_path)
        rep = a.run("go", approve)
    finally:
        tools.REGISTRY["shell_run"] = orig
    return rep, ran


def test_approval_shows_full_arguments(tmp_path):
    shown = []
    cmd = "echo " + "A" * 400 + " & powershell -c Start-Process calc"
    rep, ran = _run(tmp_path, cmd, lambda s: shown.append(s) or True)
    assert shown and cmd in json.loads(shown[0].split(" ", 1)[1])["cmd"] and "Start-Process calc" in shown[0]
    assert ran


def test_too_long_to_review_is_refused_not_cut(tmp_path):
    shown = []
    rep, ran = _run(tmp_path, "A" * 3000, lambda s: shown.append(s) or True)
    assert shown == [] and ran == [] and rep.steps[0].status == "refused"
