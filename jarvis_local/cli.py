"""`jarvis` command line."""
from __future__ import annotations

import argparse
import sys

from . import tools
from .config import Config
from .ollama import OllamaClient, OllamaDown

DOWN = "Ollama isn't running. Start the Ollama app, then try again."


def _yes(prompt: str) -> bool:
    try:
        return input(f"Allow: {prompt}? [y/N] ").strip().lower() in ("y", "yes")
    except EOFError:
        return False


def _parser():
    p = argparse.ArgumentParser(prog="jarvis")
    sub = p.add_subparsers(dest="cmd", required=True)
    sub.add_parser("status")
    m = sub.add_parser("models")
    m.add_argument("action", nargs="?", default="list", choices=["list", "pull", "remove"])
    m.add_argument("name", nargs="?")
    s = sub.add_parser("storage")
    s.add_argument("action", nargs="?", default="report", choices=["report", "caches"])
    s.add_argument("path", nargs="?")
    sh = sub.add_parser("shell")
    sh.add_argument("command", nargs="+")
    me = sub.add_parser("memory")
    me.add_argument("action", choices=["add", "search"])
    me.add_argument("text", nargs="+")
    pk = sub.add_parser("pack")
    pk.add_argument("action", choices=["build", "eval", "promote"])
    pk.add_argument("name")
    pk.add_argument("--root", default="packs")
    ld = sub.add_parser("leads")
    ld.add_argument("action", choices=["find", "queue", "draft"])
    ld.add_argument("arg", nargs="?")
    r = sub.add_parser("run")
    r.add_argument("goal", nargs="+")
    return p


def _tool(ctx, name, args, yes) -> int:
    t = tools.REGISTRY[name]
    ctx.approved = False
    if t.risk == "ask":
        if not yes(f"{name} {args}"):
            print("Skipped (not approved).")
            return 0
        ctx.approved = True
    try:
        out = t.fn(ctx, args)
        print(out)
    finally:
        ctx.approved = False
    return 1 if str(out).startswith("refused") else 0


def main(argv=None, client=None, cfg=None, yes=_yes, hw=None) -> int:
    for s in (sys.stdout, sys.stderr):  # real post text has emoji; never crash on a cp1252 console
        getattr(s, "reconfigure", lambda **k: None)(errors="replace")
    args = _parser().parse_args(argv)
    try:
        cfg = cfg or Config.load()
        client = client or OllamaClient(cfg.ollama_url)
        ctx = tools.Ctx(client, cfg, hw=hw)
        if not client.available():
            print(DOWN)
            return 1
        c = args.cmd
        if c == "status":
            print(tools.REGISTRY["hardware"].fn(ctx, {}))
            print(tools.REGISTRY["models_list"].fn(ctx, {}))
            return 0
        if c == "models":
            fn = {"list": "models_list", "pull": "models_pull", "remove": "models_remove"}[args.action]
            return _tool(ctx, fn, {"name": args.name} if args.name else {}, yes)
        if c == "storage":
            return _tool(ctx, "storage_report" if args.action == "report" else "storage_caches",
                         {"path": args.path} if args.path else {}, yes)
        if c == "shell":
            return _tool(ctx, "shell_run", {"cmd": " ".join(args.command)}, yes)
        if c == "memory":
            text = " ".join(args.text)
            return _tool(ctx, "memory_add" if args.action == "add" else "memory_search",
                         {"text": text} if args.action == "add" else {"query": text}, yes)
        if c == "pack":
            return _tool(ctx, f"pack_{args.action}", {"name": args.name, "root": args.root}, yes)
        if c == "leads":
            if args.action == "find":
                return _tool(ctx, "leads_find", {"query": args.arg or ""}, yes)
            if args.action == "queue":
                return _tool(ctx, "leads_queue", {}, yes)
            return _tool(ctx, "leads_draft", {"lead_id": args.arg}, yes)
        if c == "run":
            from .agent import Agent
            rep = Agent(client, cfg, hw=hw, ctx=ctx).run(" ".join(args.goal), yes)
            for s in rep.steps:
                print(f"- {s.tool}: {s.status}")
            print(rep.final)
            if rep.checked:
                print("Check:", rep.checked)
            return 0
    except OllamaDown:
        print(DOWN)
        return 1
    except Exception as e:  # noqa: BLE001
        print(f"Error: {e}")
        return 1
    return 0


if __name__ == "__main__":  # pragma: no cover
    sys.exit(main())
