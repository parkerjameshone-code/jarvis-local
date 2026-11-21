from pathlib import Path

import pytest

from jarvis_local import storage


@pytest.fixture
def world(tmp_path, monkeypatch):
    home = tmp_path / "Users" / "me"
    for d in ("AppData/Local/Temp/junk", "AppData/Roaming", "OneDrive/Documents", ".ollama",
              "Videos", "proj/.git", "plain/sub", "gitparent/x/.git"):
        (home / d).mkdir(parents=True)
    (tmp_path / "Users" / "Public").mkdir()
    (tmp_path / "ProgramData").mkdir()
    (home / "proj" / "src.py").write_text("x")
    monkeypatch.setattr(Path, "home", classmethod(lambda cls: home))
    calls = []
    monkeypatch.setattr(storage, "_send2trash", lambda p: calls.append(p))
    return tmp_path, home, calls


@pytest.mark.parametrize("rel", [
    "AppData", "AppData/Local", "AppData/Roaming", "OneDrive", "OneDrive/Documents", ".ollama",
    "Videos", "proj", "proj/src.py", "gitparent"])
def test_user_and_project_paths_refused(world, rel):
    _root, home, calls = world
    out = storage.trash([home / rel], approved=True)
    assert "protected" in out[0] and calls == []


def test_system_and_sibling_profiles_refused(world):
    root, home, calls = world
    out = storage.trash([root / "Users", root / "Users" / "Public"], approved=True)
    assert all("protected" in o for o in out) and calls == []


@pytest.mark.skipif(not hasattr(__import__("os"), "startfile"), reason="Windows paths")
def test_programdata_refused(world):
    assert storage._is_protected(Path("C:/ProgramData/Foo"), [])


def test_real_junk_still_allowed(world):
    _root, home, calls = world
    junk = home / "AppData" / "Local" / "Temp" / "junk"
    out = storage.trash([junk, home / "plain" / "sub"], approved=True)
    assert all(o.startswith("trashed") for o in out) and len(calls) == 2
