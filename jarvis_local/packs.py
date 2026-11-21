"""Skill packs: a base model + system prompt + examples, built into a named
Ollama model, then scored against evals before it is promoted."""
from __future__ import annotations

import json
import re
import tomllib
from dataclasses import dataclass, field
from pathlib import Path


def _q(text: str) -> str:
    return '"""' + str(text).replace('"""', '\\"\\"\\"') + '"""'


@dataclass
class Pack:
    name: str
    base: str
    system: str
    examples: list[dict] = field(default_factory=list)   # {"user", "assistant"}
    parameters: dict = field(default_factory=dict)
    path: Path | None = None

    @classmethod
    def load(cls, directory) -> "Pack":
        d = Path(directory)
        with (d / "pack.toml").open("rb") as f:
            data = tomllib.load(f)
        name = data.get("name") or d.name
        if not re.fullmatch(r"[a-z0-9][a-z0-9._-]*", name):
            raise ValueError(f"Bad pack name: {name!r}")
        if not data.get("base") or not data.get("system"):
            raise ValueError("pack.toml needs 'base' and 'system'.")
        return cls(name=name, base=data["base"], system=data["system"],
                   examples=list(data.get("examples", [])),
                   parameters=dict(data.get("parameters", {})), path=d)

    @property
    def model_name(self) -> str:
        return f"jarvis-{self.name}"

    def modelfile(self) -> str:
        lines = [f"FROM {self.base}", f"SYSTEM {_q(self.system)}"]
        for ex in self.examples:
            lines.append(f"MESSAGE user {_q(ex['user'])}")
            lines.append(f"MESSAGE assistant {_q(ex['assistant'])}")
        for k, v in self.parameters.items():
            lines.append(f"PARAMETER {k} {v}")
        return "\n".join(lines) + "\n"

    def evals(self) -> list[dict]:
        p = (self.path or Path(".")) / "evals.jsonl"
        if not p.exists():
            return []
        return [json.loads(ln) for ln in p.read_text(encoding="utf-8").splitlines() if ln.strip()]


@dataclass
class EvalResult:
    passed: int
    total: int
    fails: list[str] = field(default_factory=list)

    @property
    def score(self) -> float:
        return self.passed / self.total if self.total else 0.0


def build(pack: Pack, client) -> str:
    """Create the Ollama model `jarvis-<name>` (like `ollama create`)."""
    name = pack.model_name
    if hasattr(client, "create"):
        client.create(name, pack.modelfile())
    else:
        body = {"model": name, "from": pack.base, "system": pack.system, "stream": False,
                "messages": [m for ex in pack.examples for m in (
                    {"role": "user", "content": ex["user"]},
                    {"role": "assistant", "content": ex["assistant"]})]}
        if pack.parameters:
            body["parameters"] = pack.parameters
        client._json("POST", "/api/create", body, timeout=600)
    return name


def _check(kind: str, value, out: str) -> bool:
    if kind == "contains":
        return str(value).lower() in out.lower()
    if kind == "regex":
        return re.search(str(value), out) is not None
    if kind == "json":
        try:
            json.loads(out)
            return True
        except ValueError:
            return False
    if kind == "max_words":
        return len(out.split()) <= int(value)
    return False


def evaluate(pack: Pack, client, model: str) -> EvalResult:
    cases = pack.evals()
    passed, fails = 0, []
    for i, case in enumerate(cases):
        want_json = any(c.get("type") == "json" for c in case.get("checks", []))
        out = client.chat(model, [{"role": "user", "content": case["prompt"]}], json=want_json)
        bad = [c.get("type", "?") for c in case.get("checks", [])
               if not _check(c.get("type", ""), c.get("value"), out)]
        if bad:
            fails.append(f"case {i + 1}: failed {', '.join(bad)}")
        else:
            passed += 1
    return EvalResult(passed, len(cases), fails)


def promote(pack: Pack, result: EvalResult, threshold: float = 0.8) -> bool:
    if result.total == 0 or result.score < threshold:
        return False
    if pack.path is not None:
        (pack.path / "promoted.json").write_text(
            json.dumps({"model": pack.model_name, "score": result.score}), encoding="utf-8")
    return True
