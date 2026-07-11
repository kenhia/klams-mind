# klams-mind — roadmap

**Status:** Active — this is the pointer document: the top entry under
"Sprint queue" is the next sprint.  
**Date:** 2026-07-09 (001–006 shipped; 007 consolidation is next.
Queue was renumbered 005+ after the unplanned 003 client-lib and 004
scored-retrieval sprints consumed the numbers it had penciled in.)  
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

### 007 — Consolidation (next)

Decay-informed maintenance passes: merge near-duplicates, summarize
stale clusters, propose prunes. Propose-first like extraction; uses
klams paging (`GET /v1/memories`) and decay/trust signals. Scope
deliberately vague until the eval, extraction, and contradiction
sprints teach us what the corpus needs.

**What 006 learned:** the live corpus on kubs0 is *entirely*
`knowledge` — zero `fact`/`event` memories (extraction writes
knowledge; facts arrive via klams's Ansible/structured paths). Two
consequences for 007: (1) consolidation should target knowledge
near-duplicates, since that is what actually exists; (2) contradiction
detection has nothing live to run on until facts start landing — worth
raising with klams whether extraction should also emit facts, or
whether knowledge-vs-knowledge contradiction (which has no
`dissent_propose` path) needs a different surface.

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
