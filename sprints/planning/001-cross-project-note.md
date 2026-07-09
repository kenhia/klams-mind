# Cross-project note — klams `memory_search` result shape changed (klams sprint 016)

**From:** klams sprint 016 "Retrieval diagnostics"
(`~/src/ai/klams/sprints/016-retrieval-diagnostics/`)
**Date:** 2026-07-07
**Affects:** klams-mind's klams client + eval runner. Pick this up on
the next klams-mind touch (likely folded into eval work); it is a
**breaking** wire-shape change to the `memory_search` MCP tool.

## What changed

`memory_search` used to return a bare JSON array of `PublicMemory`
objects. As of klams sprint 016 it returns an array of **scored-hit
envelopes** (klams calls the Rust wire type `ScoredMemory`; the JSON
shape is what matters below) so retrieval evals can see *why* a hit
ranked where it did:

```jsonc
// before
[ { /* PublicMemory */ }, ... ]

// after
[
  { "score": 0.71, "source_rank": 0, "memory": { /* PublicMemory */ } },
  { "score": 0.04, "source_rank": 2, "memory": { /* PublicMemory */ } }
]
```

- `score` — raw per-source relevance score.
- `source_rank` — 0-based rank the hit held within its own source's
  result list, before cross-source fusion (global rank is the array
  index).
- `memory` — the same `PublicMemory` as before, unchanged. Its `kind`
  field still tells you fact / knowledge / event (there is no separate
  `source_kind` — it would duplicate `memory.kind`).

**Important scale caveat when you use `score`:** it is *not* normalized
across kinds. Knowledge scores are Qdrant cosine similarity (~0..1);
fact/event scores are Postgres `ts_rank` (unbounded, typically ≪1). So
raw scores are only comparable *within the same `memory.kind`*. Don't
threshold or compare scores across kinds without normalizing first.
klams deliberately did not fix this fusion mismatch — it's exposed so
the eval numbers can decide whether it's worth fixing. If your eval
report starts caring, that's the signal to file it back to klams.

## What klams-mind needs to change

1. **`src/klams_mind/klams.py` — `memory_search()`**: it currently does
   `return _memories.validate_python(await self._call("memory_search", args))`,
   parsing each element as a `Memory`. Each element is now
   `{score, source_rank, memory}`. Options: parse into a new
   `ScoredMemory` model (`score: float`, `source_rank: int`,
   `memory: Memory`) and return `list[ScoredMemory]`, or keep returning
   `list[Memory]` for callers that don't care and add a separate
   `memory_search_scored()` — your call, but the model in the eval
   runner should get at `score`.
2. **`src/klams_mind/eval/runner.py`**: `search()` calls
   `self._client.memory_search(...)` then `_to_item(h)` reads `h.text`
   etc. directly off a `Memory`. Update to read `h.memory.text` (and
   optionally carry `h.score` / `h.source_rank` into `RetrievedItem`
   so the report can show them).
3. **`src/klams_mind/eval/report.py`**: the "N hit(s)" line
   (`homelab-retrieval.md` baseline) can now include per-hit score +
   kind + source_rank — the whole point of this change. Consider a
   per-query hit table so a future failing query is diagnosable.
4. **`src/klams_mind/cli.py`** (`smoke`, line ~72) also calls
   `memory_search` — update if it reads hit fields directly.
5. Re-run the eval and **refresh the committed baseline**
   (`evals/baselines/homelab-retrieval.md`) with the richer report.

## Verifying against live klams

Once klams sprint 016 is deployed to kubs0, a raw check:

```sh
# via the MCP tool through your client, or inspect the JSON:
uv run klams-mind eval run evals/suites/homelab-retrieval.toml --json
# each hit should now carry score + source_rank
```

If klams 016 is not yet deployed (still on the branch / in PR), the
old bare-array shape is still live — coordinate the deploy with the
client update so they flip together.
