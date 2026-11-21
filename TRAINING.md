# How to train and build

Three levels, cheapest first. Do not skip ahead: most gains come from levels 1 and 2.

## Level 1: Memory (any machine)

`jarvis memory add "fact or example"` stores text with an embedding. `jarvis memory search "question"`
finds the closest matches. Needs `ollama pull nomic-embed-text`. Good for facts, preferences,
notes from videos you watched, and replies that worked.

## Level 2: Skill packs (any machine)

A pack is a folder in `packs/NAME/`:

- `pack.toml`: `base` model, `system` prompt, optional `[[examples]]` (user / assistant pairs) and `[parameters]`.
- `evals.jsonl`: test prompts with simple checks (max words, regex, ...).

```
jarvis pack build NAME     # creates a named Ollama model from base + prompt + examples
jarvis pack eval NAME      # scores it against evals.jsonl
jarvis pack promote NAME   # only promotes if it passes
```

See `packs/example-reply/`. Add real examples from replies you approved, rebuild, re-evaluate.
A pack that scores worse than before should not be promoted.

## Level 3: LoRA fine-tuning (needs a GPU)

Fine-tuning changes the model's weights. Use your best approved examples (a few hundred clean
pairs beat thousands of noisy ones) with a tool such as Unsloth or Axolotl on a GPU with
at least 8 GB VRAM, then convert the result to GGUF and `ollama create` it.
This repo does not run training for you; it provides the data (memory and packs) and the eval gate.

## Honest limits on a CPU-only machine

- Level 1 and 2 work fine on a laptop with 8 GB RAM and small (1-4B) models.
- Level 3 on CPU is impractical: hours to days even for small models, and likely to run out of memory.
  Rent a GPU for an hour or use a free notebook GPU instead.
- Small models are weaker at long, multi-step tasks. Keep tasks short and let the check step review answers.

## Always

Evaluate before you promote. Keep the do-not-contact list. Never put private data in a pack you publish.
