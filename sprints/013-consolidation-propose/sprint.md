# Sprint 013 — consolidation, propose-only

Branch `013-consolidation-propose` · proposal korg:3312 · covers WI 272 ·
one leg of overseen program korg:3314 (low-hanging fruit, run 4). Ran
as karc leg `klams-mind-5f408f` on kubs0.

(The proposal is titled "klams-mind 010"; that number was penciled in
before sprints 010–012 took it. This is the same work at the next free
number.)

## Goal

WI 272's consolidation pass, cut to its propose half: walk the corpus,
find memories that say the same thing, and emit a **reviewable
proposal** of what a later apply step would supersede — never touching
live klams. Scheduled runs stay deferred (272's own body), and so does
apply.

Acceptance:

- `KlamsClient` can walk the corpus through `GET /v1/memories`, not
  sample it through search.
- The two questions in 272's 2026-09-11 comment are answered here, with
  measurements, before the pass is designed.
- `klams-mind consolidate run` prints a markdown (or `--json`) proposal
  of candidate pairs with a verdict, a reason, and the exact
  `memory_supersede` call an apply step would make. There is no
  `--apply`. The LLM pass is bounded, and the report says by what.
- `just gate` green; docs updated.

## The two questions, answered first

Measured from kubs0 against live klams 0.1.55, 2026-09-25 ~20:00 PDT.
Source citations are `~/src/ai/klams/crates/…`.

### 1. The paged read

`GET /v1/memories` (`klams-api/src/router.rs:212`) exists and is the
right surface. Its shape is narrower than the roadmap assumed:

- **Auth:** `X-Homelab-Agent`, `read` scope. Both `klams-mind` and
  `klams-mind-eval` got 200.
- **Params:** `since`/`until` (RFC3339), `kinds`, `state`
  (`live|deleted|all`, default `live`), `authors` (UUIDs), `limit`
  (1–200, default 50), `cursor`. No offset.
- **A window, not a corpus.** `until` defaults to now, `since` to
  `until − 24h`, and the span may be **at most 30 days**
  (`memories_max_window_days`). Walking the corpus therefore means
  walking 30-day windows backwards *and* paging each by cursor.
- **End:** `next_cursor` absent. The page before the end can be empty.
- **No embeddings, trust or decay data** on this surface — stripped on
  purpose (`klams-types/src/memory.rs:4-7`). So the paged read gives the
  *set*; similarity has to come from search.
- Order is newest-first by `(created_at, id)`; items carry `state`.

Walking all live knowledge from 2026-05-25 (oldest record) took **1,020
requests** and returned **202,454** memories, no id seen twice across
windows.

### 2. What server-side `copies` already covers

There are three "copies" in klams, and **all three key on
`content_hash` — exact text after normalization** (NFC, trailing
whitespace, blank-line runs):

- **Write time, scanner chunks:** a chunk whose hash already exists is
  not re-embedded; its `(machine, file, repo)` is appended to the
  existing point.
- **Write time, `memory_add`:** an exact hash match returns the existing
  record and writes nothing. Near-matches (cosine ≥ **0.85**, up to 5)
  come back as the informational `similar_existing` — *after* the new
  memory is written. Nothing ever merges them.
- **Query time:** `collapse_duplicates` folds same-hash hits within one
  result set into the best-ranked one (`copies: [...]` in full,
  `copies: <n>` in compact).

Measured against that corpus:

| | live knowledge | exact-hash groups > 1 |
|---|---:|---:|
| scanner chunks (`source_path` set) | 202,142 | 44 (44 extra records) |
| agent-authored (no `source_path`) | 312 | **0** |

So **exact duplication is solved**; the remaining 44 scanner leaks are
collapsed at query time and are klams' own invariant, not this repo's
work. What nothing in klams handles is **semantic near-duplication** —
two notes saying the same thing in different words — and that is where
the `similar_existing` warnings go to die.

## Design — what consolidation targets

**Only agent-authored knowledge** (no `source_path`), for three
independent reasons:

1. That is where the unhandled problem is (the table above).
2. Scanner chunks are derived from files; the file is the truth, and a
   rescan would recreate anything consolidation retired.
3. `memory_supersede` refuses anything but live agent-authored
   knowledge (`klams-mcp/src/tools/memory_supersede.rs:91-125`), so a
   proposal about a scanner chunk could never be applied.

**Pairing through search, not O(n²).** `/v1/memories` has no vectors,
so each curated memory's text is a `memory_search` query (knowledge,
`full`, top_k 30); neighbours that are also curated and whose raw cosine
is ≥ the threshold become candidate pairs. Measured on a 25-seed
sample: the seed was its own top hit 24/25 times, agent neighbours
surfaced through the scanner mass, and the best agent-agent cosines were
0.92. Two constraints surfaced by running it:

- klams rejects a query over **1,024 characters** (`SCHEMA_VALIDATION_FAILED`);
  the median agent memory is 1,580. The query is the first 1,000.
- Top_k must be deep (30), because 99.8% of the corpus is scanner
  chunks competing for the same slots.

**Threshold 0.85 by default** — klams' own `SIMILAR_ON_WRITE_THRESHOLD`,
so "near-duplicate" means the same thing on both sides of the boundary.

**The judge** (kvllm, whatever it serves — never switched) gets both
texts and answers one of:

- `duplicate` — one note adds nothing the other lacks, or its claims are
  wholly replaced by the other's (an unrecorded supersession). Names
  which to `keep`; the other is retired.
- `merge` — same subject, mostly overlapping, each has something the
  other lacks, and one note can hold both. Names `keep` and returns
  `merged_text`.
- `distinct` — anything else. Refute-by-default, like contradiction:
  a missed merge is cheap, a wrong one destroys a record.

A claimed merge with no merged text, or a keep that is not `a`/`b`, is
`unactionable` — reported, never proposed.

**The proposal names the apply calls** — `memory_supersede(id=<keep>,
text=<merged or kept text>)` plus the retired id — because
`memory_supersede` takes replacement *text*, not an existing record to
point at. What apply does with the retired half is deliberately not
decided here (see Follow-ups).

**Bounds:** the corpus walk is complete (the set must be); the search
pass is one query per curated memory (312 today); the **LLM pass is
capped at `--max-pairs` (default 25) pairs, highest cosine first**, and
the report states how many qualifying pairs the cap left unjudged.

## Log

- Premise check: WI 272's two claims both **hold** — `KlamsClient` had no
  paged read, and `copies` exists. The second drifted in the direction
  of *less* work: it only covers exact hashes, so consolidation is
  narrower than 272 imagined.
- `kubs0` resolves to `127.0.1.1` on kubs0 and klams listens on
  `127.0.0.1` + tailnet; the repo's `.env` already overrides
  `KLAMS_URL=http://localhost:7777`. Not new, but it cost a probe.
- Built test-first: `list_memories`/`walk_memories` on `KlamsClient`
  (`tests/test_klams_paging.py`), then `consolidate/{pairing,chain,runner,report}`
  and `klams-mind consolidate run` (`tests/test_consolidate.py`, including
  a test that the CLI has no `--apply` and a fake that fails on any tool
  but `memory_search`). The runner takes no klams client at all, so the
  judging half cannot write even by mistake.
- The live tier gained a paged-read assertion (the marker memory must
  appear in a two-second window around its `created_at`). **Not run by
  this sprint:** `just gate-live`'s round-trip *writes* a marker memory,
  and this leg's brief forbids any live klams write. So
  `TESTED_KLAMS_MAX` stays at 0.1.52 while klams is at 0.1.55; the
  paged read itself is proven live by the two consolidation runs below.

## What the first live runs found

Two read-only runs from kubs0 against klams 0.1.55, model
`qwen3.8-27b-nvfp4` (what kvllm was already serving — not switched).
The full proposals are in the wrap-up handoff on korg:3312, not here:
this repo is public and they quote memory bodies.

| run | cap | wall | verdicts |
|---|---:|---:|---|
| default at the time | 25 | 4m09s | 2 duplicate, 23 distinct |
| everything | 55 | 8m35s | 4 merge, 4 duplicate, 47 distinct |

**The cap of 25 missed every proposal worth having.** kmon owns 16 of
the 312 curated notes and, because they share one format string, they
produce 47 of the 55 pairs and fill the top of a best-cosine-first
order. All four merges and the most useful duplicate (an agent note
that calls itself a superseded stub — a supersession written with
`memory_add` instead of `memory_supersede`) sat below the cap.
**Default raised to 60**, which covers today's whole candidate set at
~9 s per pair; the report still says what any cap left unjudged.

Actionable proposals from the full run (ids abbreviated):

| verdict | keep | retire | subject |
|---|---|---|---|
| merge | `01a0daa9` | `01a0daab-bdf4` | where agent config lives (agent-skills) |
| merge | `019f9c03` | `019f9a83` | Pi 4 vs Pi 5 findings on rpidash3 |
| merge | `01a0daa9` | `01a0daab-b529` | agent-skills source of truth (same keeper as row 1) |
| merge | `019f9a36` | `019f95dc` | MCP tools missing from the tool list |
| duplicate | `01a09dbb` | `01a09dbc` | self-described superseded stub |
| duplicate ×3 | — | — | kmon kubs0 `undeclared_longstanding` snapshots |

Spot-read: the merged texts keep both notes' content; the host-level
`distinct` calls on kmon notes (komarchy vs kstudio, …) are all right.
**The judge is not stable on one question** — whether a newer snapshot
of the same kmon observation replaces the older one: the 09-11/09-12
pair was `distinct` in run 1 and `duplicate` in run 2, at temperature 0
(vLLM batching is not bit-deterministic). That is a real ambiguity, and
its owner is kmon, not this judge — WI 3332.

## Decisions

- **D-1 Curate to agent-authored knowledge.** Reasons in the Design
  section; the short form is that it is the only set with an unhandled
  problem and the only set `memory_supersede` accepts.
- **D-2 Pair through search, threshold 0.85.** Matches klams'
  `similar_existing`; no vectors on the paged read.
- **D-3 Three verdicts, refute-by-default.** `duplicate` folds "adds
  nothing" and "wholly replaced" together because the proposed action
  is the same.
- **D-4 Cap 60, best cosine first.** Measured above.
- **D-5 No apply path at all** — not a flag defaulting off, no code. What
  apply needs is three decisions, none of them this repo's alone (WI 3331).
- **D-6 kmon notes stay in scope.** Excluding them is one filter, but
  whether their snapshots *should* be consolidated is kmon's call (WI
  3332); until then the judge's verdicts on them are advice, as every
  verdict here is.

## Follow-ups

- **WI 3331** (klams-mind) — consolidation apply: authority
  (`manage` scope or a human), how to retire the second record given
  `memory_supersede(id, text)`, and clusters.
- **WI 3332** (kmon) — time series or current state for kmon's klams
  observations.
- Run `just gate-live` on kubs0 (writes one marker memory) and bump
  `TESTED_KLAMS_MAX` to 0.1.55 — flagged to the overseer rather than done,
  because this leg may not write to live klams.

## Not filed

- The 44 exact-hash groups among scanner chunks are consistent with
  klams' deliberate per-file keying (#324/#408: identical chunks in
  different files are separate points) and are collapsed at query time.
  Nothing to do on either side.
