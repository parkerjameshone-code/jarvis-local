# jarvis-local

A local-first assistant core that runs on [Ollama](https://ollama.com) models on your own machine.
It can look at your hardware and storage, manage models, run terminal commands with guardrails,
remember things, build skill packs into models, and help you find and answer leads.

Nothing leaves your machine except what you explicitly set up (for example your own SMTP server
for capped outreach email, or a public-site search for leads).

## What it does

| Area | Command | Notes |
|---|---|---|
| Status | `jarvis status` | RAM, disk, CPU, GPU, installed models |
| Models | `jarvis models list / pull NAME / remove NAME` | Checks disk, RAM and your size budget before a pull, and again against the real download size |
| Storage | `jarvis storage report [PATH]`, `jarvis storage caches` | Biggest folders and known caches. Deleting only goes to the Recycle Bin, with approval |
| Terminal | `jarvis shell COMMAND` | Every command is classified allow / ask / block and audit-logged |
| Memory | `jarvis memory add TEXT`, `jarvis memory search TEXT` | Local vector memory (needs `nomic-embed-text`) |
| Packs | `jarvis pack build / eval / promote NAME` | Prompt + examples built into a named model, scored before it is promoted |
| Leads | `jarvis leads find QUERY`, `queue`, `draft ID` | Public posts, suggested replies you copy and send yourself |
| Agent | `jarvis run "goal"` | Plans with tools, asks before anything risky, then double-checks its answer |

## Install

```
pip install -e .[dev]
ollama pull llama3.2:3b
pytest -q
jarvis status
```

Copy `config.example.toml` to `~/.jarvis/config.toml` and fill in your own values.
Private values live there, never in this repo.

## Read these

- [BOUNDARIES.md](BOUNDARIES.md): what it will and will never do.
- [MODELS.md](MODELS.md): which model tier does which job.
- [TRAINING.md](TRAINING.md): how to build and train, and what a CPU can and cannot do.

## Design rules in short

- Risky actions need your yes, shown in full. Some commands are blocked even with a yes.
- It never sends a social message by itself: it drafts, you tap send.
- Email is opt-in, capped, warmed up slowly, carries an unsubscribe line, and only sends a template you approved.
- Everything it runs in the terminal, deletes, pulls or emails is written to `~/.jarvis/audit.jsonl`.

## License

MIT. See [LICENSE](LICENSE).
