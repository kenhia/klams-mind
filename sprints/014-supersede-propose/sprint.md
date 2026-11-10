# Sprint 014 — consolidation files supersede proposals

Branch `014-supersede-propose` · proposal korg:4430 · covers WI 3331
(the klams-mind half) · one slice of overseen program korg:4368 (the
November 2026 backlog drawdown). Ran as karc leg `klams-mind-b20415` on
kubs0.

## Goal

Sprint 013 shipped `klams-mind consolidate run`, which was propose-only:
it printed what a later apply step would do and wrote nothing. WI 3331
named three decisions that apply needed. Ken made the first on
2026-10-23: the propose-merge path. klams 058 (korg:4373, klams
`f0801e7`, deployed as 0.1.58) built it and made the other two (D2 and D3,
handoffs korg:4401 and korg:4412):

- `supersede_propose` needs `write` scope.
- `supersede_proposals_list` needs `read`.
- `supersede_proposal_resolve` needs `manage`. That is not klams-mind's
  scope.

This sprint makes klams-mind file the consolidations it already detects
through `supersede_propose`, and never resolve them.

Acceptance (the proposal's notes, from the overseer):

- Duplicates and merges are filed, each with a reason a human can judge
  without opening both records.
- What one run files is capped at a small number, chosen and recorded
  here.
- Stale proposals are re-filed against the survivor where the cluster
  still stands.
- Proven live by a hand-run trigger, not a timer. The proposals stay
  **pending** for Ken.

## Premise check

WI 3331's klams-mind half **holds**:
- klams 0.1.58 is live on kubs0 (`/healthz`).
- The three tools match handoff korg:4401 field for field
  (`crates/klams-mcp/src/tools/supersede_*.rs`,
  `crates/klams-types/src/supersede.rs` at `f0801e7`).
- klams-mind had no client for any of them.

## Design

- **Client.** `KlamsClient` gains `supersede_propose` and
  `supersede_proposals_list`. It has **no** `supersede_proposal_resolve`,
  and a test pins its absence: klams-mind holds `read,write`, so the call
  would be refused anyway.
- **Dry-run stays the default.** `consolidate run --file` files proposals
  (AGENTS.md: a reviewable mode before bulk writes). `--file` and not
  `--apply`: nothing is applied, and the old test that `--apply` does not
  exist still stands.
- **Judging stays write-free.** `consolidate/runner.py` still takes no
  klams client. Filing lives in `consolidate/filing.py` and runs on a
  fresh MCP session after the judge pass, which takes minutes.

## Decisions

- **D-1 Cap: 5 new proposals per run** (`FILE_CAP`, `--max-file`).
  - A run that files 60 would be a run nobody reviews.
  - Sprint 013's full run found 8 actionable pairs. This sprint's run
    found 5, so a cap of 5 lets one run clear today's backlog and
    nothing more.
  - `deduped` re-files do not count against the cap.
- **D-2 One pair, one proposal.** Duplicates that share a keeper are
  not grouped into one multi-retiree proposal, although klams 058 D2
  allows up to 20 retirees. Grouping only pays when several duplicates
  share a keeper, and the corpus has not shown that yet (YAGNI).
- **D-3 Do not re-judge what the queue already answers.** A pair whose
  two ids both sit inside a **pending** proposal is skipped before the
  judge. A merge is re-judged each run, its text varies, and klams'
  exact-match dedupe would let a second pending copy through. A pair
  inside a **rejected** proposal is never proposed again, because a
  rejection is an answer.
- **D-4 No overlap within a run.** A second actionable proposal that
  shares a record with one already filed in the same run is
  **deferred**, not filed. Under klams 058 D3 it would go `stale` the
  moment the first was accepted, so filing it would spend the cap on a
  proposal likely to die. The next run re-detects it against whatever
  survived.
- **D-5 Stale proposals are re-filed by re-detection, not rewritten.**
  The brief: list your own `stale` proposals and re-propose where the
  cluster still stands. Re-filing a stale merge mechanically would carry
  merged text written against a keeper that no longer exists. So:
  - Each run re-detects from the live corpus, where retired records no
    longer appear and the survivor does.
  - Pairs touching a stale proposal's records are judged **first**.
  - The report says per stale proposal whether it was `re-filed` (and
    as what) or `not re-filed` (with its live ids). A stale proposal
    with no retiree left live is counted as `settled`.
  - Not filtered by author. Only klams-mind proposes today, and giving
    another proposer's stale cluster priority costs nothing.
- **D-6 The reason is the reviewer's whole case.** Within klams' 2,000
  characters it gives:
  - the verdict, the cosine and the judge's sentence;
  - each note's id, date, author and a whitespace-collapsed excerpt;
  - what acceptance would do.

## Live proof — the trigger, run by hand on kubs0

Model `qwen3.8-27b-nvfp4` (what kvllm was serving, not switched), klams
0.1.58.

**Run 1: `consolidate run --file`.** 2026-11-10 02:53:49 to 03:02:26 UTC,
8m37s.

- 225,651 memories walked, 402 curated.
- 70 pairs at cosine ≥ 0.85. 60 judged, 10 left unjudged by the cap.
- Verdicts: 4 merge, 1 duplicate, 55 distinct.
- **4 filed**, all `pending`, author `klams-mind` (`019f4ac5…`):

| proposal | kind | keeper ← retired | subject |
|---|---|---|---|
| `01a1c368-2a34` | merge | `01a0daa9` ← `01a0daab-bdf4` | where agent config lives (agent-skills) |
| `01a1c368-2a5a` | merge | `019f9c03` ← `019f9a83` | Pi 4 vs Pi 5 on rpidash3 |
| `01a1c368-2a65` | merge | `019f9a36` ← `019f95dc` | MCP tools missing from the tool list |
| `01a1c368-2a6f` | duplicate | `01a09dbb` ← `01a09dbc` | self-described superseded kaed stub |

- **1 deferred** (D-4): merge `01a0daa9` ← `01a0daab-b529`, which shares
  its keeper with the first row. It is sprint 013's merge #3, the
  overlapping cluster WI 3331 decision 3 was about.

These are the same four merges and the same stub duplicate that sprint
013 found. The three kmon snapshot duplicates are gone; kmon now
supersedes its own observations (WI 3332).

`supersede_proposals_list(status: "all")` returned exactly these four
`pending` rows. The list call was made from Claude Code's klams tools as
`claude`, a separate identity. Nothing was accepted or rejected.

**Run 2: dry, `--max-pairs 0`** (no judge), right after run 1.

- Same 70 candidate pairs.
- **The 4 pairs now pending were skipped** before the judge (D-3), each
  naming its proposal.
- 66 pairs were left unjudged, nothing was filed, and no list was
  truncated.

That is the "nothing twice" rule, shown live.

## Repaired in passing

The live gate (`just gate-live`, which AGENTS.md says to run after
either side deploys) went red against 0.1.58. Two defects, both in this
repo, both fixed mechanically, both proven by that gate:

- **The eval's lineage walk was silently truncated by klams 0.1.58.**
  - Cause: WI 4331 made `memory_get` answer `NOT_FOUND` for superseded
    records. Sprint 012's `KlamsRetriever._parent_of` followed
    `supersedes` back through `memory_get`, so every chain stopped after
    one hop.
  - Why it was silent: the defensive catch was there on purpose, so the
    walk did not fail. Pins that name an older ancestor (`019fa04a-ceac`
    in `homelab-retrieval.toml`) quietly stopped matching.
  - Fix: a new `KlamsClient.knowledge_lineage` reads REST
    `GET /memory/knowledge/{id}`, which klams 058 D1 deliberately keeps
    serving for superseded records.
  - Proof: the eval tests now refuse `memory_get` the way klams does,
    and the live round-trip asserts both halves.
  - Live, on the real suite (`eval run homelab-retrieval.toml`, both
    26/27): on `main` the pin reads `019fa04a-ceac absent from 8
    result(s)`. On this branch it resolves: `019fa04a-ceac (superseded —
    now 019fb6b1-1c9a) surfaced at rank 2`.
- **`KlamsError.error_code` was `None` on every live error.** klams sends
  its whole error envelope as JSON inside the text content. The unit
  fixtures put the code in the result's `_meta`, where klams does not
  put it. `_call` now reads the nested envelope, with a test on the
  recorded live shape. Filing failures depend on this to name their
  code (`NOT_FOUND`, `NOT_AGENT_AUTHORED`).
- **Tested range set to 0.1.58–0.1.58.** `gate-live` passed against
  0.1.58. The floor also rose, because `consolidate run` reads the
  proposal queue (new in 0.1.58) and the round-trip now asserts
  0.1.58's `memory_get` behaviour. README's example was updated to
  match.

## The eval suite back to 27/27 (overseer ruling)

The lineage repair left the suite at 26/27, failing for a reason this
repo caused.

- **The check.** The score-field paraphrase query, with `max_rank 1`,
  pins the lineage that `019fa04a-ceac` belongs to. The lineage now
  resolved, but at rank 2.
- **What sat at rank 1.** A scanner chunk of this repo's own
  `tests/test_klams_client.py`. Since sprint 012 the live round-trip had
  searched with the eval's query verbatim.
- **Why it ranked.** klams' lexical arm (0.1.37) surfaces any chunk
  containing every query token, so the fixture competed with the very
  note the check pins.

**Ruling (overseer):** rephrase the test's query. Do not loosen
`max_rank`, which is doing its job; the fixture was polluting the
corpus.

- **The new query** reaches the same lineage through the 0.1.41 head's
  other subject, the tags-filter fix, and shares none of the eval
  query's distinctive tokens. Measured live before the change, it
  returns the head `019fb6b1` at rank 0 with `supersedes` set. That is
  what the round-trip asserts.
- **Re-index.** A comment at the call site says why the query must never
  copy an eval query. The scanner re-indexes this checkout hourly, so
  the old chunk was flushed by starting `klams-scanner.service` by hand.
- **This record.** It names the eval query by description rather than
  quoting it, so the record does not become the next polluter.

**Result, measured live on kubs0 on 2026-11-10:**

- **The scanner run** (03:08:53–03:09:00 UTC) cleared 52 stale chunks of
  `tests/test_klams_client.py` and re-indexed the file. The embed queue
  then drained to 0.
- **The suite:** `eval run homelab-retrieval.toml` exits 0 at **27/27**,
  with no regressions.
- **The pinned check** now reads `019fa04a-ceac (superseded — now
  019fb6b1-1c9a) at rank 1`, and the test-file chunk has left the top
  of that query's results.
- **The gates:** `just gate` and `just gate-live` are both green on the
  new query.

## Not done here

- **Scheduled runs.** Still deferred. Ken's 2026-10-23 comment on WI 3331
  set the condition: both halves of WI 3331 have shipped. They now have,
  but trusting the loop means seeing how these first proposals are
  resolved. klams-mind has no timer today.
- **Grouping duplicates by keeper** (D-2).
