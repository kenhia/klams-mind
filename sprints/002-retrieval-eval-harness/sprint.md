# Sprint 002 — Retrieval-quality eval harness

**Branch:** `002-retrieval-eval-harness`
**Started:** 2026-07-07
**Status:** Done — harness built + tested; live baseline 4/4 green; gate green
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
| `no_hallucination` | answer admits insufficiency | **absence/precision check**: a forbidden fragment must be *absent* from all retrieved content and sources — the system didn't surface spurious content. (See note: MCP search is scoreless and always returns `top_k`, so a "returns nothing above a bar" framing isn't measurable on the agent path; absence is the honest scoreless analog and the precision dual of `source_cited`.) |

**Recommendation (to confirm with Ken before building checks):** make
this a *retrieval* eval — deterministic, no LLM in the loop — because
the sprint's stated purpose is a regression bar for klams retrieval,
and pulling kvllm into the assertion path adds nondeterminism a
retrieval baseline shouldn't carry. An LLM-synthesis ("does the model
answer faithfully from retrieved context") eval is a natural *later*
sprint that builds on this one; it is explicitly out of scope here.

**Backend surface — settled: MCP `memory_search`.** Its `PublicMemory`
output carries **no relevance score**, and (verified live) it always
returns `top_k` nearest neighbours even for gibberish queries — so a
score/count-threshold `no_hallucination` isn't expressible here. REST
`POST /memory/search` *does* return scores, but using it would (a)
contradict the pinned surface split (MCP is the agent surface; REST is
operator/bulk-read only) and (b) measure a different code path than
agents actually use — wrong target for a retrieval regression bar. So
the harness stays on MCP `memory_search`, and `no_hallucination` is an
**absence** check (forbidden fragment must not appear in any hit).

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
- **Unblocked (2026-07-07):** the grant had been edited into the wrong
  config copy; once corrected and klams reloaded, the scoped `klams-mind`
  token authenticates (`/v1/authors` and `/mcp` → 200) and a full
  `klams-mind smoke` passes under the klams-mind identity via `.env`
  auto-load. Live baseline unblocked. **Design locked: retrieval-only**
  eval — deterministic, no LLM in the assertion path (per Ken).
- **Harness built (TDD, 4 modules mirroring krag + a CLI):**
  `eval/suite.py` (pydantic-typed TOML loader, `extra="forbid"` so typos
  raise), `eval/checks.py` (the three checks over a backend-neutral
  `RetrievedItem`, `if/elif` dispatch), `eval/runner.py` (`Retriever`
  protocol + `run_suite` + `KlamsRetriever` adapter mapping klams
  fact/knowledge/event memories to `RetrievedItem`), `eval/report.py`
  (markdown **and** JSON, plus a per-check-type breakdown krag lacks).
  CLI: `klams-mind eval run <suite>` (`--json`, `--out`), exit **0**
  all-pass / **1** any-fail / **2** bad suite. 37 new tests, all against
  fakes; gate green (58 passed total).
- **Suites + baseline live in `evals/`** (durable assets, not sprint-
  scoped — they feed klams sprint 016). `evals/suites/homelab-retrieval.toml`
  is the baseline suite; `evals/baselines/homelab-retrieval.md` is its
  committed report (**4/4, 100%** against live kubs0). `evals/suites/
  failing-demo.toml` proves the failing path (exit 1) with intentionally
  false expectations.

## Outcome

Acceptance met: `klams-mind eval run evals/suites/homelab-retrieval.toml`
produces a committed markdown baseline (4/4 green) against live kubs0;
`evals/suites/failing-demo.toml` demonstrates a failing check with a
non-zero exit; `just gate` green; `python-dotenv` justified above.
`no_hallucination` was reframed to a precision/absence check (documented
in the design table) because MCP `memory_search` is scoreless and always
returns `top_k` — the honest scoreless-retrieval analog, staying on the
agent surface a retrieval regression bar should measure.
