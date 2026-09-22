# Sprint 012 — an eval check that follows the supersedes chain

Branch `012-supersedes-chain` · proposal korg:3056 · covers WI 2247 ·
one leg of overseen program korg:3062 (low-hanging fruit, run 2).

## Goal

Remove the fuse in the retrieval suite's `memory_id` checks. A pinned
memory id is a ticking assertion in a corpus designed for supersession:
13 of the suite's 34 checks carry one, and the first has already gone
off (WI 2247). Make the pin name a *lineage* rather than a leaf, and
give the suite a way to see drift coming.

Two deliverables, both named in the proposal's ruling:

1. **Follow the chain.** A `memory_id` pin matches a hit that *is* the
   pinned memory, or a hit that descends from it through
   `memory_supersede`. Applied to all 13 checks, not just the failing
   one.
2. **A refresh recipe** that re-resolves every pin against the live
   corpus and reports drift, so rot is visible and cheap rather than
   discovered by a red gate months later.

## Premise check (start of sprint)

WI 2247's falsifiable claims, checked against the code and against live
klams 0.1.52 on kubs0 (probed from kubs0, the host the eval runs on):

| Claim | Verdict |
|---|---|
| Suite pins `019fa04a-ceac` with `max_rank = 0` | **holds** — `evals/suites/homelab-retrieval.toml:418-420` |
| 13 of 34 checks are `memory_id` | **holds** — exactly 13 and 34 |
| Query is marked `expect = "known_open"` / `tracking = "korg:2247"` | **holds** — lines 415-416 |
| `019fa04a-ceac` is absent from the corpus at top_k 50 | **holds** — absent as a hit at top_k 50 across four phrasings |
| klams exposes the supersedes chain to the suite | **holds, and more richly than the item knew** — see below |
| `019fa04a-ceac` was superseded by `019fbc9c-5c74` | **GONE — the item names the wrong successor** |

### The successor named in WI 2247 is wrong

`019fbc9c-5c74` carries **no `supersedes` edge at all**; it is an
independent note on an adjacent subject, not the head of this chain.
The real lineage, read off klams:

```
019fa04a-ceac  →  019fb1c9-7c16  →  019fb6b1-1c9a   (live head)
```

This retroactively strengthens the "do not re-pin" ruling: re-pinning
to `019fbc9c-5c74` would have pinned an unrelated record and called it
a fix. It is also the clearest possible argument for deliverable 2 —
the successor was identified by eye, and eye got it wrong.

### What klams actually exposes (measured, klams 0.1.52)

- `memory_search` returns **`supersedes`** (backward: "I replaced X") on
  a hit, in **both** the compact and the `full` envelope. klams-mind's
  `KnowledgeMemory` model simply never declared the field, so pydantic
  dropped it silently — the data has been arriving all along.
- `memory_get` on a **superseded** record resolves (it is hidden from
  search, not deleted) and carries **`superseded_by`** as well as
  `supersedes`, plus `volatility`.
- `memory_get` requires a **full UUID**; the suite pins 12-char
  prefixes, so resolution has to run from hits outward, not from the pin
  inward.

That last point sets the design: walk *backward* from each hit's
ancestry and match the prefix there, rather than trying to resolve a
prefix forward.

## Decisions

Recorded as they were taken; see `decisions.md`.

## What shipped

### 1. `memory_id` follows the supersedes chain

A pin now names a **lineage**. A hit satisfies it when it *is* the pinned
memory, or when it descends from it through `memory_supersede`. A direct
hit wins over a descendant, so nothing that passed before changes
meaning, and `max_rank` keeps its teeth either way — a lineage that
surfaces but loses its slot is still a failure.

- `KnowledgeMemory` (and every kind, via `_MemoryBase`) now declares
  `supersedes` and `superseded_by`. klams has been sending `supersedes`
  on search hits in **both** envelopes since long before this sprint;
  the client simply never declared the fields, so pydantic dropped them.
- `KlamsRetriever` resolves each hit's ancestry once and hands it to the
  check, so `evaluate_check` stays a pure function of the page (D-4).
  Free for an ordinary hit — `supersedes` rides on the search result, so
  only a hit that carries one costs a `memory_get`.

### 2. `just refresh-pins` — the drift report

`klams-mind eval pins <suite>` re-resolves every pin against the live
corpus, one search per query, and reports `current` / `superseded` /
`absent` per pin with the whole lineage printed. Exit 1 on drift,
`--json`, `--out`. Outside `just gate` by design (D-5).

First run against live klams 0.1.52 — and it immediately paid for
itself:

```
**1 of 13 pin(s) have drifted.** 1 witness(es) fell outside `max_rank`.
019fa04a-ceac — superseded; lineage
  019f9d5a-539d → 019f9fba-f1bc → 019fa04a-ceac
                → 019fb1c9-7c16 → 019fb6b1-1c9a
```

The lineage is **five records deep** — the 0.1.28 → 0.1.29 → 0.1.30 →
0.1.37 → 0.1.41 chain the query's own comment described, which nobody
had ever actually traced. Twelve of thirteen pins are clean.

### 3. The "score field behavior" query is green, and no longer `known_open`

`max_rank` lowered 0 → 1 on the measurement in D-3, `expect =
"known_open"` and `tracking = "korg:2247"` removed.

**The suite is 27/27 (100%) for the first time** — it was 26/27 with one
known-open. 13/13 `memory_id`. Baseline refreshed deliberately
(`evals/baselines/homelab-retrieval.md`, klams 0.1.52), since leaving
the regression bar at 26/27 would record a failure that no longer exists.

## Repaired in passing

**The live tier had no assertion about the supersession contract.** This
sprint made the client depend on three facts about real klams —
`supersedes` on a `full` search hit, `memory_get` serving a *hidden*
superseded record, and `superseded_by` on it — and every unit test fakes
the transport. Landing that with no live assertion is #2249's shape
exactly, so `test_live_round_trip` now asserts all four (the fourth
being that the superseded record is genuinely absent from search).

The fixture is `019fa04a-ceac…`, chosen because it is **already
superseded**: supersession is terminal, so its state cannot regress and
this is not a new instance of the fuse the sprint just removed.

Verified the assertions bite rather than decorate: with the two model
fields removed, the live tier fails and 8 unit tests fail; restored, both
tiers are green.

## Not filed, and why

- **`volatility` is another field klams sends and this client drops**
  (seen on the superseded record). Same class as `supersedes` was, but
  nothing needs it — adding it would be speculative. Noted here so the
  next reader knows it was seen and passed over, not missed.

## Gates

| Gate | Result |
|---|---|
| `just gate` | green — 218 passed, 1 deselected |
| `just gate-live` | green against klams 0.1.52 (run on kubs0, where klams is) |
| `klams-mind eval run` | **27/27 (100%)**, 0 regressions, 0 known-open |
| `just refresh-pins` | 1 of 13 drifted (reported, by design) |

All probes and both live tiers were run **on kubs0**, which is the host
klams runs on and the host the eval runs from.
