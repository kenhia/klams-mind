# Sprint 009 — the compact-contract migration, eval-run identity, and the smoke hint

**Proposal:** [korg:2221](https://korg/2221) — "klams-mind 007: consolidation,
plus eval-run marking and the smoke failure hint"
**Program:** korg:2233 — Backlog drain 3 of 3 (slice 8)
**Branch:** `009-consolidation` · **Leg:** karc `klams-mind-870a89` (kubs0, headless)
**Covered:** klams-mind 735, klams-mind 831, plus homelab-ai 272 by relation

> Sprint number is 009, not the proposal's "007": repo numbering drifted from
> the plan's when 003/004 landed unplanned and 008 went to the kprojects
> harness. The roadmap's queue already called this one 009.

## Goal as proposed

Consolidation (homelab-ai 272, M) bundled with two XS debts — mark eval runs
so `search_sample` mining stops feeding the suite its own queries (735), and
make `smoke` tell connect-refused apart from 401 (831).

## What the premise check found (and why this sprint is not that sprint)

The program's standing rule is that every slice verifies before it works.
Doing that here changed the sprint, so the verification is recorded first.

### 272's park condition is gone — but a bigger one replaced it

272 was parked 2026-08-21 because kai had no GPU (card out for RMA). Verified
2026-09-10: **the GPU is back** — `nvidia-smi` on kai reports an RTX 5090
(32,607 MiB), vllm is live on `100.97.109.60:8000`, and klams-mind resolves a
model name against it. The park condition is spent.

What replaced it is worse, and it was found by simply running the smoke:

**klams-mind's `memory_search` is completely broken against the live klams.**
Every klams retrieval path in this repo — smoke, the eval suite, extraction's
duplicate check, contradiction pairing — fails with
`ValidationError: Input should be a valid list`.

The cause is not a klams bug. klams **sprint 046 / WI #1178** deliberately
shipped the *compact response contract* (`crates/klams-mcp/src/contract.rs`,
ported from khound): `memory_search` now returns

```json
{"hits": [{"id","kind","snippet","score","raw_score","source_rank",
           "age_seconds","tags","author", …typed metadata…}],
 "more": {"fetch": "memory_get", "truncated": true}}
```

instead of a bare `list[{score, source_rank, raw_score, memory}]`. The
motive is measured: 9,599 → 4,193 tokens per answered query (2.29×), with a
follow-up `memory_get` charged whenever a snippet fell short. klams is at
0.1.46; klams-mind was last exercised against 0.1.30. **klams-mind is simply
a stale client of a contract that changed under it**, and fixing that is the
prerequisite for everything else in the proposal — consolidation included.

### The eval baseline is preserved, and klams already designed for it

The worry was that snippets would silently change what the eval suite
measures. Of the suite's 34 checks across 27 queries, 16 need the full record
(11 `substring`, 3 `no_duplicates` on `content_hash`, 2 `min_body_chars` on
the breadcrumb-stripped body) — a ≤320-char match window would have made those
measure snippet windowing rather than retrieval, and the 21/21 @ 0.1.30
baseline would have become incomparable for reasons unrelated to retrieval
quality.

It does not come to that. `memory_search` grew a **`full`** parameter in the
same sprint, and its own description names the caller it is for:

> "this exists for the callers that genuinely want bodies in bulk
> (**eval harnesses**, exports), not as the ordinary path."

Probed live: `full: true` returns **exactly the pre-046 shape** — a bare list
of `{score, source_rank, raw_score, memory{id, kind, text, content_hash, …}}`.
So the eval path keeps its semantics *and* its baseline by passing one flag,
and no `memory_get` hydration fan-out is needed.

**Decision (D-1): compact stays the default; the four body-dependent callers
opt into `full`.** Two methods rather than a flag with a union return type —
`memory_search` (compact, what agents get) and `memory_search_full` (bodies
inline). `smoke` deliberately uses the compact path, so the shape agents
actually receive is the one the health check exercises.

### Premise verdicts

| Item | Verdict |
|---|---|
| **735** eval self-traffic | **holds**, but the fix route is not klams-mind's alone — see below |
| **831** smoke hint | **holds, and worse than filed**: reproduced live. The leaf cause does not surface even *with* `--debug` (rich renders the `SmokeError` chain and swallows the `ExceptionGroup`), so the WI's "never surfaces without `--debug`" understates it |
| **272** consolidation | park condition **gone** (GPU back); blocked instead on the contract migration above |

### 735 splits, and only half is mine

735's own decision comment (2026-08-15) already established the fix: a
**read-scoped `[[auth.tokens]]` grant** in `/etc/klams/klams.toml` with an
explicit `agent_name = "klams-mind-eval"`, because `search_sample`'s `caller`
comes from the *token's* grant, not from `register_author`. klams-mind cannot
change its own caller identity; no amount of client code does it.

That half mints a credential in another repo's config and wants a krot
registry entry — and it collides with two live slices in this same program
(korg:2220 "klams-token in the deploy path", korg:2230 "registering kmon's
klams grant"). By the overseen-sprint cross-repo test that is **Branch B**:
new decisions, another repo's deploy path, a registry artifact. So this sprint
builds and tests everything klams-mind needs in order to *use* such a grant
the moment it exists, and hands the grant itself up rather than reaching for
it. See "Handed up" below.

## Scope actually shipped

### 1. The compact-contract migration (unplanned; became the sprint's body)

`src/klams_mind/klams.py` — new `CompactHit`, `More`, `SearchResponse`
models, and the search surface split in two rather than one method with a
flag and a union return type:

| Method | Returns | For |
|---|---|---|
| `memory_search` | `SearchResponse` (`hits`, `more`) | The ordinary agent path |
| `memory_search_full` | `list[ScoredMemory]` (bodies inline) | Bodies/payloads: evals, extraction dedup, fact pairing |
| `memory_get(id)` | `Memory` | The single-record follow-up `more.fetch` names |

Call sites moved to `memory_search_full` because each asserts on a body or
a fact payload: `eval/runner.py` (`KlamsRetriever`), `extract/runner.py`
(`find_duplicate` normalises and substring-matches full text),
`contradict/pairing.py` and the `contradict` CLI (both need `payload`).

`smoke` deliberately stays on the **compact** path, so the health check
exercises the shape agents actually receive — and it now reports
`more.truncated`.

`CompactHit` makes every field below the score block optional, matching
klams' "omitted, not faked" rule. Tested both ways: an agent-added
knowledge hit has no `source_path`/`heading_path`; a scanner chunk has
both, plus `repo` and `copies`.

### 2. Smoke failure diagnosis (#831)

`leaf_cause()` walks the *two* nested `ExceptionGroup`s the MCP
streamable-http client wraps everything in; `diagnose(step, exc, cfg)`
picks one actionable line from the leaf type — unreachable (naming the
URL tried), token rejected (with the status), other HTTP status, or
**could-not-parse**, which is what version skew between the two projects
looks like and is the hint that would have short-circuited this sprint's
own first hour.

Two refinements past the ask: the hint follows the failing *step*, so
model-endpoint failures stop naming klams; and when the URL's host is
this machine, it prints the loopback override — the exact trap #831 was
filed from (`kubs0` → 127.0.1.1, klams binds 127.0.0.1 + tailnet).

All three acceptance criteria verified live, none needing `--debug`.

### 3. Eval-run identity — klams-mind's half (#735)

`KLAMS_EVAL_TOKEN` / `KLAMS_EVAL_AGENT_NAME`, `eval_klams_config()`
(swaps the grant without mutating the caller's config, and reports
whether the identity is genuinely distinct), `run_eval` connecting with
it, a stderr warning when there is no grant, and — the piece that makes
it auditable — **the run's caller stamped into report provenance**, on
the klams#676 machinery. Any report now says which `search_sample` rows
it produced.

The grant itself is Branch B and went up as **WI 2257**.

### 4. Rebaselined at klams 0.1.46

`evals/baselines/homelab-retrieval.md` — 26/27 (96%), **0 regressions**,
1 known-open. Exit 0.

The evidence that the migration preserved eval semantics is in the
per-check-type table: `substring` 11/11, `min_body_chars` 2/2,
`no_duplicates` 3/3, `source_cited` 2/2 — every body-dependent class at
full marks, identical to the 0.1.30 baseline's. Those are precisely the
checks a 320-char snippet would have broken.

The one non-passing query is a **rotted id pin**, not a retrieval
regression: the suite pins `019fa04a-ceac`, which is itself now
superseded by `019fbc9c-5c74` (same subject, re-measured at klams 0.1.41)
and absent from the corpus at top_k 50. Its sibling `no_hallucination`
check still passes, which is consistent. Marked `expect = "known_open"`
with `tracking = "korg:2247"` rather than silently re-pointed —
**re-pinning an eval check changes what the suite measures**, and that is
a ruling, not a cleanup.

Note the baseline had already drifted independently of this sprint: it
recorded 21 queries at suite `801c3790e61b`, and the suite has since
grown to 27. The provenance block flags the mismatch in as many words.

### 5. The live round-trip test now pins the contract

`test_live_round_trip` asserts compact (`more.fetch == "memory_get"`,
`hits[].id`), `full` (`.memory.id`), **and** `memory_get`. This is the
test that was missing when 0.1.46 landed: every other klams-facing test
fakes the transport, so the suite validated klams-mind against its own
idea of the contract. Run green against live klams 0.1.46.

That gap is the sprint's most valuable finding and is filed as **WI 2249**
— `just gate` was green through all sixteen versions of drift.

## Gate

```
uv run ruff format --check .   ✓
uv run ruff check .            ✓
uv run ty check                ✓
uv run pytest                  ✓  172 passed, 1 skipped
uv run pytest -m live          ✓  1 passed (against live klams 0.1.46)
```

Live end-to-end: `klams-mind smoke` → klams Ok (v0.1.46) at
localhost:7777, author registered, 3 hits, model `qwen3.8-27b-nvfp4` on
kai → `'pong'`.

## Docs

`README.md` — a new "The klams search contract" section (the table above,
the token measurement, and the tell that a `ValidationError` means
version skew), the three new eval check types, the `full` rationale, the
eval-identity block, and the smoke-diagnosis behaviour.
`config.example.toml` — the eval grant keys, the `agent_name` gotcha, and
the loopback note for kubs0.

## Work items

| Item | State |
|---|---|
| 831 smoke hint | **resolved** |
| 735 eval-run marking | **resolved** (client half; grant → 2257) |
| homelab-ai 272 consolidation | **still open** — unparked, deferred to klams-mind 010 |
| 2247 rotted eval pin | filed, open — needs a re-pin ruling |
| 2249 no CI signal for contract drift | filed, open — the systemic finding |
| 2257 read-scoped eval grant | filed, open — Branch B, suggest folding into korg:2230 |

## Handed up to the overseer

1. **homelab-ai 272 did not close, though the proposal said it would.** The
   park condition (kai's GPU) is genuinely gone — RTX 5090 present, vllm
   live, model pings. What blocked it instead was the contract break, and
   after fixing that the remaining gap is real: `KlamsClient` has no paged
   corpus read (`GET /v1/memories`), and klams now collapses some
   duplicates server-side at query time (`copies`), which changes the
   design. Consolidation is a better-founded sprint now than it was this
   morning, and it is klams-mind 010.
2. **Decision D-1** (compact default, four callers opt into `full`) shapes
   what the eval suite measures, which is a shared artifact — flagged
   rather than buried.
3. **WI 2247 wants a ruling**, not work: re-pin to the successor memory, or
   drop the id pin and keep the absence check.
4. **WI 2257 wants routing.** korg:2230 already registers a klams grant;
   folding it there avoids two legs inventing one credential convention.

## Cross-repo changes made

**None.** The klams repo was read only — `crates/klams-mcp/src/contract.rs`,
`crates/klams-types/src/auth.rs` and `sprints/046-mcp-correctness/sprint.md`
— to establish that the contract change was deliberate and to find the
documented migration path. No file outside klams-mind was written, and the
one action that would have required it (the eval grant) was parked as 2257
per the Branch B rule.
