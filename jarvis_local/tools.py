"""The tools the agent may call. Each has a risk level:
read  = runs freely; ask = needs a yes from the owner; never = always refused.
Tool functions take (ctx, args) and return a short text result."""
from __future__ import annotations

import os
import smtplib
from dataclasses import dataclass, field
from datetime import date
from pathlib import Path
from typing import Any, Callable

from . import catalog, hardware, log, models, packs, router, shell, storage
from .leads import drafts, score, sources
from .leads import email as lemail
from .leads.store import LeadStore
from .memory import Memory


@dataclass
class Tool:
    fn: Callable[["Ctx", dict], str]
    risk: str  # "read" | "ask" | "never"
    doc: str = ""
    args: str = ""


@dataclass
class Ctx:
    client: Any
    cfg: Any
    approved: bool = False          # set right before an "ask" tool runs, only after a yes
    hw: Any = None
    smtp_factory: Callable | None = None
    _stores: dict = field(default_factory=dict)

    def hardware(self):
        return self.hw or hardware.snapshot()

    def lead_store(self) -> LeadStore:
        return self._stores.setdefault("leads", LeadStore(Path(self.cfg.data_dir) / "leads.db"))

    def email_store(self) -> lemail.EmailStore:
        return self._stores.setdefault("email", lemail.EmailStore(Path(self.cfg.data_dir) / "email.db"))

    def memory(self) -> Memory:
        return self._stores.setdefault("mem", Memory(Path(self.cfg.data_dir) / "memory.db", self.client))

    def smtp(self):
        if self.smtp_factory:
            return self.smtp_factory
        if not self.cfg.smtp_host:
            raise RuntimeError("No smtp_host in config.")
        cfg = self.cfg

        class _S:
            def __enter__(s):
                s.c = smtplib.SMTP(cfg.smtp_host, cfg.smtp_port, timeout=30)
                s.c.starttls()
                user, pw = os.environ.get("JARVIS_SMTP_USER"), os.environ.get("JARVIS_SMTP_PASSWORD")
                if user and pw:
                    s.c.login(user, pw)
                return s.c

            def __exit__(s, *a):
                s.c.quit()
        return _S


def _need(args: dict, key: str):
    if key not in args or args[key] in (None, ""):
        raise ValueError(f"missing argument: {key}")
    return args[key]


def _hardware(ctx, a):
    h = ctx.hardware()
    return (f"RAM {h.ram_total_gb} GB ({h.ram_free_gb} free), disk free {h.disk_free_gb} GB, "
            f"{h.cpus} CPUs, GPU {h.gpu or 'none'}")


def _models_list(ctx, a):
    ms = ctx.client.list()
    return "\n".join(f"{m.name} {m.size_bytes / 1024**3:.1f} GB" for m in ms) or "No models installed."


def _models_pull(ctx, a):
    name = _need(a, "name")
    rec = catalog.find(name)
    if rec is None:
        return f"{name} is not in the recommended catalog; pull it by hand."
    ok, why = models.can_pull(rec, ctx.hardware(), ctx.client.list(), ctx.cfg)
    if not ok:
        return "refused: " + why
    try:
        models.pull(name, ctx.cfg, client=ctx.client, hw=ctx.hardware(), installed=ctx.client.list())
    except models.PullTooBig as e:
        log.event("models_pull", cfg=ctx.cfg, name=name, result="refused", reason=str(e))
        return "refused: " + str(e)
    log.event("models_pull", cfg=ctx.cfg, name=name, result="pulled")
    return f"pulled {name}. {why}"


def _models_remove(ctx, a):
    name = _need(a, "name")
    ctx.client.remove(name)
    log.event("models_remove", cfg=ctx.cfg, name=name)
    return f"removed {name}"


def _storage_report(ctx, a):
    root = a.get("path") or Path.home()
    rows = storage.report(root, int(a.get("top", 15)))
    return "\n".join(f"{gb:6.2f} GB  {p}" for p, gb in rows) or "empty"


def _storage_caches(ctx, a):
    rows = storage.known_caches()  # slow on big Temp folders; only runs when asked
    return "\n".join(f"{c.gb:.2f} GB  {c.path}  (clear: {c.how_to_clear})" for c in rows) or "none found"


def _storage_trash(ctx, a):
    paths = _need(a, "paths")
    if isinstance(paths, str):
        paths = [paths]
    prot = [Path(ctx.cfg.data_dir), *ctx.cfg.project_dirs]
    results = storage.trash(paths, approved=ctx.approved, protected=prot)
    log.event("trash", cfg=ctx.cfg, results=results)
    return "\n".join(results)


def _shell_run(ctx, a):
    cmd = _need(a, "cmd")
    # The agent cannot ask for a hidden run: commands always show in a window.
    r = shell.run(cmd, approved=ctx.approved, visible=True, cfg=ctx.cfg)
    return f"exit {r.code}\n{r.out[:4000]}"


def _memory_add(ctx, a):
    return f"saved memory #{ctx.memory().add(_need(a, 'text'), a.get('meta'))}"


def _memory_search(ctx, a):
    rows = ctx.memory().search(_need(a, "query"), int(a.get("k", 5)))
    return "\n".join(f"{s:.2f} {t}" for s, t, _m in rows) or "nothing remembered yet"


def _pack(a):
    name = str(_need(a, "name"))
    if not name.replace("-", "").replace("_", "").replace(".", "").isalnum() or name.startswith("."):
        raise ValueError("bad pack name")
    return packs.Pack.load(Path(a.get("root") or "packs") / name)


def _pack_build(ctx, a):
    return "built " + packs.build(_pack(a), ctx.client)


def _pack_eval(ctx, a):
    p = _pack(a)
    r = packs.evaluate(p, ctx.client, a.get("model") or p.model_name)
    return f"{r.passed}/{r.total} passed" + ("; " + "; ".join(r.fails) if r.fails else "")


def _pack_promote(ctx, a):
    p = _pack(a)
    r = packs.evaluate(p, ctx.client, p.model_name)
    return ("promoted" if packs.promote(p, r) else "not promoted") + f" ({r.passed}/{r.total})"


def _leads_find(ctx, a):
    found = sources.reddit_search(str(_need(a, "query")), int(a.get("limit", 25)))
    store = ctx.lead_store()
    return f"{sum(store.add(lead) for lead in found)} new leads of {len(found)} found"


def _leads_queue(ctx, a):
    rows = ctx.lead_store().queue()
    return "\n".join(f"#{x.id} [{x.status}] {x.author}: {x.text[:80]} {x.url}" for x in rows) or "no leads waiting"


def _leads_draft(ctx, a):
    store = ctx.lead_store()
    lead = store.get(int(_need(a, "lead_id")))
    if lead is None:
        return "no such lead"
    if store.is_suppressed(lead):
        return "refused: this person is on the do-not-contact list"
    if lead.status not in ("new", "drafted"):
        return f"no draft: lead is already {lead.status}"
    # Offers come only from the owner's private config, never from the model's arguments.
    offers = [score.Offer(str(o.get("id", "")), str(o.get("name", "")), str(o.get("description", "")))
              for o in (ctx.cfg.offers or []) if isinstance(o, dict)]
    installed, hw = ctx.client.list(), ctx.hardware()
    oid, sc = score.match(lead, offers, ctx.client, model=score.scoring_model(installed, hw))
    store.save_match(lead.id, oid, sc)
    offer = next((o for o in offers if o.id == oid), None)
    d = drafts.suggest(lead, offer, ctx.client, sc, model=router.choose("draft", installed, hw))
    if d is None:
        return f"score {sc:.2f}: no draft (below threshold)"
    store.save_draft(lead.id, d.text)
    return f"Draft (copy it, then send it yourself at {d.url}):\n{d.text}"


def _email_send_due(ctx, a):
    rep = lemail.send_due(ctx.email_store(), ctx.smtp(), ctx.cfg, date.today())
    log.event("email_send_due", cfg=ctx.cfg, sent=rep.sent, skipped=rep.skipped, reason=rep.reason)
    return f"sent {rep.sent}, skipped {rep.skipped}" + (f" ({rep.reason})" if rep.reason else "")


def _never(ctx, a):  # pragma: no cover - callers refuse before this
    return "refused"


REGISTRY: dict[str, Tool] = {
    "hardware": Tool(_hardware, "read", "RAM, disk, CPU, GPU."),
    "models_list": Tool(_models_list, "read", "Installed models."),
    "models_pull": Tool(_models_pull, "ask", "Download a catalog model.", "name"),
    "models_remove": Tool(_models_remove, "ask", "Delete an installed model.", "name"),
    "storage_report": Tool(_storage_report, "read", "Biggest folders.", "path?, top?"),
    "storage_caches": Tool(_storage_caches, "read", "Known cache folders and sizes."),
    "storage_trash": Tool(_storage_trash, "ask", "Send paths to the Recycle Bin.", "paths"),
    "shell_run": Tool(_shell_run, "ask", "Run a terminal command.", "cmd"),
    "memory_add": Tool(_memory_add, "read", "Remember a fact.", "text"),
    "memory_search": Tool(_memory_search, "read", "Search memory.", "query, k?"),
    "pack_build": Tool(_pack_build, "ask", "Build a skill pack into a model.", "name"),
    "pack_eval": Tool(_pack_eval, "read", "Score a pack against its evals.", "name"),
    "pack_promote": Tool(_pack_promote, "ask", "Promote a pack if it passes.", "name"),
    "leads_find": Tool(_leads_find, "read", "Search Reddit for leads.", "query, limit?"),
    "leads_queue": Tool(_leads_queue, "read", "Leads waiting."),
    "leads_draft": Tool(_leads_draft, "read", "Suggest a reply (never sends).", "lead_id"),
    "email_send_due": Tool(_email_send_due, "ask", "Send approved, capped outreach email."),
    "social_send": Tool(_never, "never", "Sending social messages is never automatic."),
}


def describe() -> str:
    return "\n".join(f"- {n}({t.args}) [{t.risk}]: {t.doc}" for n, t in REGISTRY.items() if t.risk != "never")
