# Models and tiers

jarvis-local picks the best installed model for each job, within what your RAM can hold
(a model needs about 1.3x its file size in memory, and at most 80% of RAM is used).

| Tier | Jobs | Hosted-model analogy | Catalog examples |
|---|---|---|---|
| fast | scoring a lead, extracting fields | Haiku | `llama3.2:1b`, `qwen2.5:1.5b`, `gemma2:2b` |
| balanced | chat, drafting replies | Sonnet | `llama3.2:3b`, `qwen2.5:3b` |
| deep | planning, checking answers, code | Opus | `qwen3:4b`, `gemma3:4b` |

Rules:

- A job never goes up a tier on its own. If only a bigger model is installed, scoring falls back to the balanced one.
- Embedding models (like `nomic-embed-text`, used by memory) are never used for chat.
- A pull is refused if it would leave less than your disk reserve, go over your model budget,
  or not fit in RAM. The real download size reported by Ollama is checked too.
- Other models can be pulled by hand with `ollama pull`. Tier is then guessed from file size.

Using hosted models (Opus, Sonnet, Haiku and similar) is a separate choice: this core is built
so the tiers map to those roles, but it only talks to local Ollama.
