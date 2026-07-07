# Sprint 002 — Retrieval-quality eval harness

**Branch:** `002-retrieval-eval-harness`
**Started:** 2026-07-07
**Status:** In progress
**Roadmap entry:** 002 (moved out of the queue when this doc landed).
**Reference:** krag eval harness at `~/src/ai/krag/src/krag/evaluation/`
(loader / checks / runner / reporter, four modules + a Typer `eval`
command).

## Goal

Port the krag retrieval-eval design to klams: TOML query suites run
against klams retrieval, with per-query checks, so retrieval changes
are *measured, not vibed*. This harness becomes the regression bar for
klams retrieval work (feeds klams sprint 016). A committed baseline
report is the deliverable's proof.

## Central design decision — klams is retrieval-only

krag is RAG-over-documents: its `QueryEngine.query()` returns a
synthesized **`answer` string** plus `sources` (each with a
`file_path`). Its three checks are answer-centric:

- `substring` — expected text is `in answer.lower()`
- `source_cited` — expected path fragment appears in some `source.file_path`
- `no_hallucination` — the answer admits insufficiency, or is grounded
  in non-empty sources

klams has **no synthesized answer**. `memory_search` (MCP) returns
ranked `PublicMemory` rows (fact/knowledge/event); `memory_context`
(REST `POST /memory/context`) returns a token-budgeted `ContextBundle`
with `facts`/`knowledge`/`events` sections. Both are *retrieved
memories*, not generated prose.

So the port keeps krag's **structure** (four modules, dataclass shapes,
`if/elif` check dispatch, exit-0/1 CLI contract) but **redefines the
checks around retrieved memories**:

| Check | krag (RAG) | klams-mind (retrieval) |
|-------|-----------|------------------------|
| `substring` | text in the LLM answer | text appears in the concatenated content of retrieved memories (knowledge `text`, fact `payload`, event `payload`) — tests content recall |
| `source_cited` | fragment in a `source.file_path` | an expected memory is present in results, matched on knowledge `source_path`, a `tag`, or a memory-id fragment |
| `no_hallucination` | answer admits insufficiency | **negative/out-of-corpus check**: a known off-topic query returns nothing above a relevance bar — retrieval doesn't surface spurious matches. (krag's own example was the off-topic "quantum computing" query.) |

**Recommendation (to confirm with Ken before building checks):** make
this a *retrieval* eval — deterministic, no LLM in the loop — because
the sprint's stated purpose is a regression bar for klams retrieval,
and pulling kvllm into the assertion path adds nondeterminism a
retrieval baseline shouldn't carry. An LLM-synthesis ("does the model
answer faithfully from retrieved context") eval is a natural *later*
sprint that builds on this one; it is explicitly out of scope here.

**Backend surface to settle early:** `memory_search` (MCP) is the
primary target but its `PublicMemory` output carries **no relevance
score**, which the `no_hallucination` bar wants. Options: (a) define
the bar as result-count/expected-absence without scores, or (b) use
REST `POST /memory/search` (returns `SearchHit` with `score` 0..1) for
the score-aware check. Lean (a) first — fewer moving parts, and it
keeps the whole harness on the MCP surface the client already speaks.

## Scope

1. **`eval` package** mirroring krag's split:
   - `suite` loader — parse a TOML suite (list of queries, each with
     checks) into typed models; validate required fields, raise a clear
     `EvalLoadError`.
   - `checks` — the three checks above as pure functions over a
     retrieval result, dispatched by `type`; unknown type → failing
     result (not a crash).
   - `runner` — for each query, call the klams backend via a thin
     adapter (duck-typed `search(query, top_k) -> results`), run its
     checks, aggregate per-query and overall pass/fail.
   - `reporter` — **markdown** report per run (the roadmap asks for
     markdown; krag emits JSON+stderr, so this is net-new), plus
     `--json` for programmatic use. Include a per-check-type breakdown
     (krag has none).
2. **Backend adapter** wrapping the sprint-001 `KlamsClient` so the
   runner depends on a small retrieval protocol, not the whole client
   (keeps checks/runner testable with a fake).
3. **CLI**: `klams-mind eval run <suite>` — human summary + `--json`,
   exit 0 if all pass / 1 if any check fails (preserve krag's CI
   contract).
4. **Initial suite** seeded from real homelab questions klams
   demonstrably contains (machines, services, sprint history), plus at
   least one deliberately out-of-corpus query to exercise
   `no_hallucination`, and one deliberately-broken expectation to
   demonstrate a failing check (acceptance requirement).
5. **Committed baseline** — a report from a live run checked in under
   the sprint dir as the regression reference.

### Prerequisite folded in: `.env` auto-load

Live eval runs need klams-mind's own scoped token without manual
exporting. Ken added a `klams-mind` klams token to `.env`. This sprint
teaches `load_config` to auto-load `./.env` (via `python-dotenv`, added
as an explicit dep) and standardizes the key as `KLAMS_TOKEN`
(env/`.env` still override TOML, per sprint 001). Small, but it's the
first sprint that runs live klams from a non-interactive CLI, so it
belongs here.

## Out of scope

- LLM-synthesis / faithfulness eval (answer generated from retrieved
  context) — a later sprint.
- Reranking experiments (roadmap "later").
- Scheduled/CI-wired runs — the harness just needs to *exit 0/1* so CI
  *could* gate on it later.

## Acceptance criteria

- `klams-mind eval run <suite>` produces a committed baseline report
  (markdown), against live kubs0.
- A deliberately-broken query/expectation demonstrates a failing check
  (non-zero exit).
- `just gate` green; new dep `python-dotenv` justified here.

## Dependencies added

| Dependency | Why |
|------------|-----|
| `python-dotenv` | Auto-load `./.env` so live runs pick up `KLAMS_TOKEN` without manual export. Already present transitively; pinned as a direct dep since we import it. |

## Chronicle

- **2026-07-07** — Sprint opened. Scouted krag's harness (four modules,
  dataclasses, `if/elif` dispatch, Typer `eval`, exit-0/1, JSON+stderr
  output — no markdown, no per-check breakdown). Confirmed klams is
  retrieval-only: `memory_context` is REST `POST /memory/context`
  returning a `ContextBundle` (facts/knowledge/events sections), not a
  synthesized answer; `memory_search` (MCP) returns scoreless
  `PublicMemory` rows. Central decision recorded above: keep krag's
  shape, redefine the three checks around retrieved memories, and (pending
  Ken's nod) make this a deterministic retrieval eval with no LLM in the
  assertion path.
- **`.env` auto-load landed** (config + tests + `python-dotenv` dep).
  Real env still beats `.env`; injected-`env` test paths stay isolated
  (no accidental `./.env` pickup). Key standardized as `KLAMS_TOKEN`.
- **Blocker for the live baseline: the `klams-mind` token 401s.** Ken
  added a scoped `klams-mind` token to `.env`; klams rejects it with
  `401 {"code":"unauthorized","message":"missing or invalid bearer
  token"}` on both `/mcp` and `/v1/authors`. A raw urllib probe (not our
  MCP client) gets the same 401, so the client is fine — the matching
  `[[auth.tokens]]` grant just isn't provisioned in klams's `klams.toml`
  on kubs0 yet (this is klams **sprint 015** companion-enablement:
  `token` + `scopes=["read","write"]` + `agent_name="klams-mind"`, then
  reload klams). Until that lands, live eval runs (and the committed
  baseline) are blocked; the whole harness is built and tested offline
  against a fake backend in the meantime, and the baseline is generated
  once the grant exists.
