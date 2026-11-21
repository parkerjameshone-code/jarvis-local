from pathlib import Path

import pytest

from jarvis_local import storage


@pytest.fixture
def bin_calls(monkeypatch):
    calls = []
    monkeypatch.setattr(storage, "_send2trash", lambda p: calls.append(p))
    return calls


def test_trash_without_approval_refused(tmp_path, bin_calls):
    f = tmp_path / "a.bin"
    f.write_bytes(b"x")
    out = storage.trash([f], approved=False)
    assert "refused" in out[0] and bin_calls == []


def test_trash_approved_goes_to_bin(tmp_path, monkeypatch, bin_calls):
    home = tmp_path / "home"
    home.mkdir()
    monkeypatch.setattr(Path, "home", classmethod(lambda cls: home))
    f = tmp_path / "a.bin"
    f.write_bytes(b"x")
    out = storage.trash([f], approved=True)
    assert out[0].startswith("trashed") and bin_calls == [str(f)]


def test_protected_refused_even_when_approved(tmp_path, monkeypatch, bin_calls):
    home = tmp_path / "home"
    (home / "Documents" / "x").mkdir(parents=True)
    (home / "proj" / "sub").mkdir(parents=True)
    monkeypatch.setattr(Path, "home", classmethod(lambda cls: home))
    out = storage.trash([home, home / "Documents", home / "Documents" / "x",
                         home / "proj" / "sub"], approved=True, protected=[home / "proj"])
    assert all("protected" in o for o in out)
    assert bin_calls == []


def test_report_sorted_and_top(tmp_path):
    (tmp_path / "big").mkdir()
    (tmp_path / "big" / "f").write_bytes(b"x" * 5000)
    (tmp_path / "small").write_bytes(b"x")
    rows = storage.report(tmp_path, top=1)
    assert len(rows) == 1 and rows[0][0].name == "big"


def test_known_caches_shape(tmp_path, monkeypatch):
    home = tmp_path / "home"
    (home / ".cache").mkdir(parents=True)
    (home / ".cache" / "f").write_bytes(b"x" * 10)
    monkeypatch.setattr(Path, "home", classmethod(lambda cls: home))
    monkeypatch.setenv("LOCALAPPDATA", str(tmp_path / "local"))
    caches = storage.known_caches()
    assert len(caches) == 1 and caches[0].how_to_clear and caches[0].gb > 0
