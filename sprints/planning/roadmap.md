# klams-mind — roadmap

**Status:** Active — this is the pointer document: the top entry under
"Sprint queue" is the next sprint.  
**Date:** 2026-07-08 (001–004 shipped; 005 extraction moved out — in
flight on `005-extraction`; queue was renumbered 005+ after the
unplanned 003 client-lib and 004 scored-retrieval sprints consumed the
numbers it had penciled in)  
**Related:** klams repo `sprints/planning/roadmap.md` (the two queues
cross-reference each other) · decision record: klams repo
`sprints/planning/wi259-recommendation.md` · salvage inventory (krag
eval harness, prompt presets, retrieval lessons): klams repo
`sprints/planning/wi259-three-project-review.md` §4.

## Charter

klams-mind is the intelligence layer klams deliberately excludes from
its core: extraction, semantic contradiction detection, consolidation,
and retrieval evals. It is a **client** of klams (own scoped token +
author identity) and consumes models through **OpenAI-compatible
endpoints** (vLLM via kvllm on kai; klams keeps embeddings local to
kubs0). Orchestration is LangChain — this project is also the
designated playground for learning it properly.

**Which klams surface for what** (learned in 001; mirrored in the
klams roadmap 015 entry): the *agent* surface is **MCP-only**
(`kubs0:7777/mcp`, Streamable HTTP — `register_author`, `memory_add`,
`memory_search`, `event_search`, …, all `PublicMemory`-projected;
there is deliberately no REST `memory_add`). REST is the
controller/operator surface — klams-mind uses it only for bulk paged
reads (`GET /v1/memories`) and `/healthz`. New agent capabilities
klams grows for us (dissent proposal) arrive as MCP tools.

Anything klams-mind needs klams to grow (dissent-proposal API, paging,
tokens) is filed against klams sprint 015 "Companion enablement" — see
that queue.

## Sprint queue

### 006 — Semantic contradiction detection (next)

The headline feature: find memories that contradict in *meaning*.

1. Candidate pairing (embedding-similarity buckets via klams search;
   don't O(n²) the corpus), then LLM judgment with a
   refute-by-default prompt.
2. File dissents through the klams **MCP dissent-proposal tool**
   (klams sprint 015 shipped it; `dissent_propose` is live on kubs0 as
   of the 2026-07-08 deploy — contract: target fact + proposed
   correction + reason, optionally citing the contradicting memory;
   write scope).
3. Resolution stays human, in the klams viewport `/dissents` page.

Acceptance: seeded contradictory facts are detected and appear as
pending dissents in the viewport; false-positive rate on a
non-contradictory sample is measured and recorded.

### 007 — Consolidation

Decay-informed maintenance passes: merge near-duplicates, summarize
stale clusters, propose prunes. Propose-first like extraction; uses
klams paging (`GET /v1/memories`) and decay/trust signals. Scope
deliberately vague until the eval, extraction, and contradiction
sprints teach us what the corpus needs.

### Later / unscheduled

- Usefulness feedback ("this helped") writer, paired with klams's
  decay-boost backlog item.
- Scheduled runs (systemd timer on kubs0) once propose→apply loops are
  trusted.
- GHCP session-log extraction; other log sources.
- Whatever the eval baseline demands (reranking experiments live here
  first, klams adopts what wins).

## How to start the next sprint

Per [AGENTS.md](../../AGENTS.md): take the top queue entry, create
branch + `sprints/###-<short-stub>/` (next number), write `sprint.md`
seeded from the entry above, build test-first, ship behind
`just gate`. Move the entry out of this queue when its sprint doc
exists.
