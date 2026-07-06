# klams-mind — roadmap

**Status:** Active — this is the pointer document: the top entry under
"Sprint queue" is the next sprint.
**Date:** 2026-07-05
**Related:** klams repo `sprints/planning/roadmap.md` (the two queues
cross-reference each other) · decision record: klams repo
`sprints/planning/wi259-recommendation.md` · salvage inventory (krag
eval harness, prompt presets, retrieval lessons): klams repo
`sprints/planning/wi259-three-project-review.md` §4.

## Charter

klams-mind is the intelligence layer klams deliberately excludes from
its core: extraction, semantic contradiction detection, consolidation,
and retrieval evals. It is a **client** of klams (MCP/REST at
`kubs0:7777`, own scoped token + author identity) and consumes models
through **OpenAI-compatible endpoints** (vLLM via kvllm on kai; klams
keeps embeddings local to kubs0). Orchestration is LangChain — this
project is also the designated playground for learning it properly.

Anything klams-mind needs klams to grow (dissent-proposal API, paging,
tokens) is filed against klams sprint 015 "Companion enablement" — see
that queue.

## Sprint queue

### 001 — Bootstrap & first light (next)

Prove the full plumbing with the thinnest possible vertical slice.

1. Config (`klams_mind.config`): klams base URL + token, model
   endpoint(s) + names. TOML + env overrides; secrets never committed.
2. klams client wrapping the REST/MCP surface actually needed now:
   `register_author`, `memory_search`, `memory_add`, `/healthz`.
   Typed responses (pydantic), tested against recorded fixtures; live
   round-trip test marked and skipped without `KLAMS_URL`.
3. LangChain + OpenAI-compatible chat wired (`langchain-openai`
   pointed at kvllm): one trivial chain proving model access.
4. CLI entry (`klams-mind smoke`): health-check klams, register
   author, run one search, one LLM call; human-readable + `--json`.

Acceptance: `klams-mind smoke` passes against live kubs0 + kvllm;
`just gate` green; deps added this sprint: httpx, pydantic,
langchain-core/langchain-openai, typer (each justified in sprint.md).

### 002 — Retrieval-quality eval harness

Port the krag eval design (TOML query suites; `substring`,
`source_cited`, `no_hallucination` checks — see krag
`src/krag/evaluation/` for the reference implementation) against klams
`memory_search` / `memory_context`.

1. Suite loader, runner, reporter (markdown report per run).
2. An initial suite seeded from real homelab questions (machines,
   services, sprint history — things klams demonstrably contains).
3. Baseline report committed; this becomes the regression bar for
   klams retrieval changes (feeds klams sprint 016).

Acceptance: `klams-mind eval run <suite>` produces a committed
baseline; a deliberately-broken query demonstrates a failing check.

### 003 — Memory extraction

Distill durable facts from agent session logs (start with Claude Code
JSONL transcripts; GHCP sessions later) into klams.

1. Log reader + candidate-fact extraction chain (LangChain), with the
   krag lesson baked in: cite-or-refuse prompting, no free-form
   fabrication.
2. **Propose-first workflow**: dry-run mode outputs candidates for
   review; `--apply` writes via `memory_add` under the klams-mind
   author. Dedupe against existing memories via `memory_search` before
   writing.
3. Scheduled operation deferred until the manual loop proves value.

Acceptance: a real session log yields reviewed facts landed in klams,
visible in the viewport under the klams-mind author.

### 004 — Semantic contradiction detection

The headline feature: find memories that contradict in *meaning*.

1. Candidate pairing (embedding-similarity buckets via klams search;
   don't O(n²) the corpus), then LLM judgment with a
   refute-by-default prompt.
2. File dissents through the klams companion-enablement API
   (**depends on klams sprint 015** — design the contract together).
3. Resolution stays human, in the klams viewport `/dissents` page.

Acceptance: seeded contradictory facts are detected and appear as
pending dissents in the viewport; false-positive rate on a
non-contradictory sample is measured and recorded.

### 005 — Consolidation

Decay-informed maintenance passes: merge near-duplicates, summarize
stale clusters, propose prunes. Propose-first like extraction; uses
klams paging (`GET /v1/memories`) and decay/trust signals. Scope
deliberately vague until 002–004 teach us what the corpus needs.

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
