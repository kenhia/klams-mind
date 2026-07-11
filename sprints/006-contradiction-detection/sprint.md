# Sprint 006 — Semantic contradiction detection

**Work item:** korg #271 (`klams-mind 006: contradiction detection`,
WS2). Depends on #270 (extraction, shipped in 005) — satisfied.
Unblocks #272.

**Branch:** `006-contradiction-detection` ·
**Roadmap entry:** [roadmap.md](../planning/roadmap.md) §006.

## Goal

The headline feature: find memories that **contradict in meaning**,
and surface each as a pending dissent for a human to resolve. klams
detects contradictions only on *same-fact* trust conflicts at write
time; the interesting case — two independently-stored facts that
cannot both be true — is exactly what klams excludes and delegates to
this companion.

## Scope

1. **Candidate pairing** — don't O(n²) the corpus. A seed query pulls
   a working set of facts from klams search; for each fact we pull its
   embedding-similarity neighbours (another `memory_search`, kind
   `fact`) and form unordered candidate pairs. Bounded at
   `len(working_set) × neighbours`.
2. **LLM judgment, refute-by-default** — each pair goes to a judge
   prompted to default to *not a contradiction*. Different-but-
   compatible facts are not contradictions; only genuine mutual
   exclusivity counts. The verdict names the fact believed wrong
   (`target`) and a corrected `proposed_payload` (a JSON object, per
   the `dissent_propose` contract). A claimed contradiction with no
   concrete, object-shaped correction is **unactionable** — refused,
   not filed (the extraction sprint's cite-or-refuse discipline,
   applied to corrections).
3. **File dissents** — propose-first, mirroring extraction. Dry-run is
   the default and prints the review surface; `--apply` files via the
   klams MCP `dissent_propose` tool (target fact + proposed payload +
   reason, citing the contradicting memory) under klams-mind's own
   registered author. Dissents land as lowest-trust `AgentProposal`s;
   resolution stays human in the viewport `/dissents` page.

## Contract notes (from klams source, read 2026-07-09)

`crates/klams-mcp/src/tools/dissent_propose.rs`:
- `proposed_payload` **must be a JSON object** (`SCHEMA_VALIDATION_FAILED`
  otherwise) — so the corrected payload is `dict`, never a scalar.
- `reason` is 1..=2000 chars.
- `author_id` defaults to the bearer identity (WI #62) but we register
  and pass klams-mind's author explicitly, for attributable writes.
- returns `{dissent_id, fact_id, status: "pending", deduped}`; `deduped`
  is true when the same `(fact_id, payload)` was already pending.
- `NOT_FOUND` if the target fact is missing/soft-deleted.

## Acceptance

- Seeded contradictory facts are detected and appear as pending
  dissents in the viewport (live `--apply` run).
- False-positive rate on a non-contradictory sample is measured and
  recorded here.
- `just gate` green; docs updated.

## Chronicle

**Shape.** New `contradict/` package mirroring `extract/`:
`chain.py` (refute-by-default judge + strict verdict parse),
`pairing.py` (`fact_text` + `find_candidate_pairs` — one search per
seed, unordered de-dupe, deterministic a<b ordering), `runner.py`
(`detect_contradictions`, propose-first), `report.py` (markdown review
surface + JSON). Client grew `dissent_propose`, `DissentProposed`, and
`memory_delete` (all TDD). CLI gained `contradict run QUERY` with
`--apply/--top/--neighbours/--json/--out`.

**Design call — unactionable is a refusal, not a file.** The judge
must return a `target` and an object `proposed_payload`; a
contradiction claimed without a concrete, object-shaped correction (or
with an empty reason) is `unactionable` and never filed. This is
extraction's cite-or-refuse applied to corrections, and it also
front-runs the server's `SCHEMA_VALIDATION_FAILED` (payload must be an
object, reason 1..2000). Target selection is the judge's call (which
fact is wrong), not a recency heuristic — the human resolves anyway.

**Surprise — the live corpus has zero facts.** Everything in klams on
kubs0 is `knowledge` (the extraction sprint writes knowledge, and
`kinds=["fact"]`/`["event"]` both return nothing). `dissent_propose`
targets canonical *facts*, so there is nothing live to detect over
until facts start landing. The feature is correct to the roadmap
contract; the demonstration therefore seeds facts, exactly as the
acceptance anticipated ("seeded contradictory facts").

**Acceptance — false-positive rate (measured 2026-07-09,
`gemma-4-31b-it-awq` via kvllm).** Curated non-contradictory sample of
8 realistic homelab fact pairs (different services/hosts, complementary
attributes, duplicates, unrelated user/task facts): **0/8 false
positives = 0.0%**. True-positive sanity check on 3 genuine
contradictions (same service two hosts / two ports; one setting two
values): **3/3 = 100%**. The refute-by-default prompt holds on gemma.
(Harness: a throwaway driver over the real model — no live writes.)

**Acceptance — seeded contradiction → dissent, end to end (live).**
Seeded two contradictory `EnvFact`s (`service=klams-mind-selftest-006`
on kubs0 vs kai) under the klams-mind author, ran detection `--apply`
(pairing them directly to sidestep embedding-index latency). Judge
verdict: contradiction, reason "The same service cannot be hosted on
two different hosts simultaneously"; a real dissent was filed
(`dissent_id 019f4ac5-8a82-…`, status pending) against the kai fact,
proposing the kubs0 payload and citing the kubs0 fact. This exercises
the real `dissent_propose` tool (unit tests fake it). Cleaned up by
soft-deleting both seed facts, which orphans the demo dissent so it
does not linger in the viewport.

**Outcome.** `just gate` green (ruff format + check, ty, pytest — 20
new tests across client/chain/pairing/runner/report/cli). Docs: README
gained a "Contradiction detection" section. Resolves WI #271; unblocks
#272.
