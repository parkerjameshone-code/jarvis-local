import pytest

from jarvis_local.hardware import Hardware
from jarvis_local.ollama import ModelInfo
from jarvis_local.router import NoModel, TASK_TIER, TIERS, choose

GB = 1024 ** 3


def M(name, gb):
    return ModelInfo(name, int(gb * GB))


def hw(ram):
    return Hardware(ram, ram / 2, 100, 8)


def test_task_tiers():
    assert set(TASK_TIER.values()) <= TIERS
    assert TASK_TIER["classify"] == "fast" and TASK_TIER["chat"] == "balanced" and TASK_TIER["code"] == "deep"


def test_picks_largest_in_tier_that_fits():
    inst = [M("qwen3:4b", 2.6), M("gemma3:4b", 3.3), M("llama3.2:1b", 1.3)]
    assert choose("plan", inst, hw(16)) == "gemma3:4b"


def test_skips_too_big_for_ram():
    # 5 GB RAM -> limit 4.0 / 1.3 = 3.07 GB: gemma3:4b (3.3) is out, qwen3:4b (2.6) fits
    inst = [M("gemma3:4b", 3.3), M("qwen3:4b", 2.6)]
    assert choose("plan", inst, hw(5)) == "qwen3:4b"


def test_falls_back_to_lower_tier():
    assert choose("plan", [M("llama3.2:1b", 1.3)], hw(16)) == "llama3.2:1b"


def test_never_goes_up_a_tier():
    with pytest.raises(NoModel):
        choose("classify", [M("gemma3:4b", 3.3)], hw(16))


def test_nomodel_when_nothing_fits_or_installed():
    with pytest.raises(NoModel) as e:
        choose("chat", [M("gemma3:4b", 3.3)], hw(2))
    assert "GB" in str(e.value)
    with pytest.raises(NoModel):
        choose("chat", [], hw(16))


def test_embed_models_ignored():
    with pytest.raises(NoModel):
        choose("classify", [M("nomic-embed-text", 0.3)], hw(16))
