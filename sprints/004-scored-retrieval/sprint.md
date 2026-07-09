# 004 — scored retrieval

Consume klams 016's scored-hit envelope (homelab-ai WI 269, proposal
korg:300). klams `memory_search` now returns
`[{score, source_rank, memory}, ...]` instead of a bare memory array —
deployed live on kubs0 as of 2026-07-08 (WI 287) — so the sprint-002 eval
harness was parsing a shape the live service no longer emits. Full contract
notes: `sprints/planning/001-cross-project-note.md`.

## What changed

- `src/klams_mind/klams.py`: new `ScoredMemory` model (`score: float`,
  `source_rank: int`, `memory: Memory`); `memory_search()` returns
  `list[ScoredMemory]`. Only two callers existed (eval retriever, smoke
  CLI), so the return type changed in place — no parallel
  `memory_search_scored()`.
- `src/klams_mind/eval/checks.py`: `RetrievedItem` grows optional `kind`,
  `score`, `source_rank`. Checks ignore them; they exist for the report.
- `src/klams_mind/eval/runner.py`: `_to_item` flattens `sm.memory` and
  carries the envelope metadata along; `EvalQueryResult` gains `hits`
  (defaulted, so hand-built results in tests stay valid).
- `src/klams_mind/eval/report.py`: per-hit detail lines under each query
  (`` `score` kind rN — source ``) in markdown, and a `hits` array per
  result in JSON — the whole point of the change: a failing query is now
  diagnosable from the committed report.
- `src/klams_mind/cli.py`: smoke's `search.top` entries read through the
  envelope and include `score`.
- `evals/baselines/homelab-retrieval.md`: refreshed from a live run with
  the richer per-hit report.

## Score-scale caveat (from the klams 016 note)

`score` is NOT normalized across kinds — knowledge is Qdrant cosine
(~0..1), fact/event is Postgres `ts_rank` (typically ≪ 1). The report
prints kind next to score and never aggregates scores across hits; don't
threshold across kinds. If the eval numbers start caring about cross-kind
fusion, that's the signal to file it back to klams.
