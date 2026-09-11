# klams-mind — roadmap

**Status:** Active — this is the pointer document: the top entry under
"Sprint queue" is the next sprint.  
**Date:** 2026-09-10 (001–009 shipped; 008 went to the kprojects
harness chore and 009 to an unplanned klams contract migration, so
consolidation slid to 010. Queue was renumbered 005+
after the
unplanned 003 client-lib and 004 scored-retrieval sprints consumed the
numbers it had penciled in, and again at 007 when klams#676 was pulled
forward off proposal korg:654 to land before klams sprint 028.)  
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

### 007 — Eval provenance (shipped)

klams#676, pulled out of proposal korg:654. Stamp every report and
baseline with run date, the klams version it ran against, and the suite
file + content hash; flag a klams-version difference against the
baseline in one line. Small, and it lands before klams 028 so that
sprint's "capture the baseline before the corpus wipe, compare after"
story is falsifiable. See
[007-eval-provenance/sprint.md](../007-eval-provenance/sprint.md) —
including the test-set leakage it uncovered (klams#677: the eval suite
had been scanned into the corpus it queries).

### 008 — kprojects harness (shipped, off-queue)

Chore from proposal korg:1251 / work item #1248 — batch 3 of the
kprojects rollout. Managed agent block in `CLAUDE.md` and
`.github/copilot-instructions.md`, standard layout dirs, and the
`just check` alias for `gate`. No behaviour change; it consumed the
number the queue had penciled for consolidation. See
[008-kprojects-harness/sprint.md](../008-kprojects-harness/sprint.md).

### 009 — klams compact-contract migration, eval identity, smoke hint (shipped)

Proposal korg:2221, which had *planned* to be consolidation. The
premise check found klams-mind broken outright against live klams:
klams sprint 046 (#1178) shipped the **compact response contract** and
this repo was still a 0.1.30-era client, so smoke, the eval suite,
extraction's duplicate check and contradiction pairing all raised
`ValidationError`. Consolidation reads the corpus, so it had no sound
footing to be built on; the migration became the sprint.

Shipped: `memory_search` (compact) / `memory_search_full` (`full: true`,
bodies inline) / `memory_get`; the eval harness on the `full` path so
the retrieval baseline stayed comparable; `KLAMS_EVAL_TOKEN` +
`Caller` in report provenance (#735's client half); `smoke` failure
diagnosis (#831). Rebaselined at klams 0.1.46 — 26/27, 0 regressions.
See [009-consolidation/sprint.md](../009-consolidation/sprint.md).

### 010 — Consolidation (next)

Decay-informed maintenance passes: merge near-duplicates, summarize
stale clusters, propose prunes. Propose-first like extraction; uses
klams paging (`GET /v1/memories`) and decay/trust signals.

**Two things to settle first**, both surfaced by 009 (see homelab-ai
272's comment):

1. **The paged corpus read does not exist yet.** `KlamsClient` has no
   `GET /v1/memories`. Consolidation must *walk* the corpus, not sample
   it through search — search is top-k and rank-ordered, the wrong
   shape for "find every near-duplicate cluster".
2. **klams now collapses some duplicates server-side, at query time.**
   The compact hit carries `copies` ("how many duplicate copies this
   hit absorbed"). Design against that rather than around it: part of
   what this entry originally imagined may already be handled, and the
   remainder may want a different cut.

**What 006 learned:** the live corpus on kubs0 is *entirely*
`knowledge` — zero `fact`/`event` memories (extraction writes
knowledge; facts arrive via klams's Ansible/structured paths). Two
consequences: (1) consolidation should target knowledge
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
- **A contract tier against live klams** (korg:2249). 009's break sat
  undetected across 16 klams versions because every klams-facing test
  fakes the transport and the one live test is opt-in. The live test
  now pins compact + `full` + `memory_get`; it needs somewhere that
  actually runs it.
- `memory_id` eval pins rot when a memory is superseded (korg:2247).
  13 of the suite's 34 checks are `memory_id`, so this recurs; klams'
  `supersedes` field may support a check that follows the chain.

## How to start the next sprint

Per [AGENTS.md](../../AGENTS.md): take the top queue entry, create
branch + `sprints/###-<short-stub>/` (next number), write `sprint.md`
seeded from the entry above, build test-first, ship behind
`just gate`. Move the entry out of this queue when its sprint doc
exists.
