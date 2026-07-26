# Sprint 007 — Eval provenance

**Work item:** klams#676 — *Eval reports carry no provenance — a stale
baseline reads as a regression*. Filed under the klams project but
scoped, in its pinned comment, to **klams-mind only**: no klams change,
no dependency on any other WI. Part of proposal korg:654 (the
consolidated debt breather), which stays `proposed` and untouched —
this sprint took one item out of it, not the whole bundle.

**Branch:** `007-eval-provenance` from `main @ 1f60203`.

## Goal

Make every eval report and baseline state what it was run against, so a
stale artifact announces itself instead of being reverse-engineered.

### The failure this exists to prevent

Sprint 026's first live run of the rewritten suite reported **2
regressions**. Both were false. The checked-in baseline was from
2026-07-08 — five klams sprints earlier (021 corpus hygiene, 022
re-chunking, 023 multi-host scanning, 024 RRF, 025 authz) — and its two
`source_cited` assertions pinned documents that had legitimately been
superseded:

- `klams.service` — still exists, but a legacy path; live units are
  `deploy/klams-service.service`, and 024 replaced raw-score sort with
  RRF.
- `klams.example.toml` for "where does kvllm serve models" — the best
  answer available in July only because **kai wasn't scanned until 023**;
  the kvllm repo wasn't in the corpus at all. Retrieval had improved and
  the assertion was pinning the inferior document.

The only thing that eventually proved the baseline was ancient: it
recorded `score` values around **0.84** — raw cosine, impossible after
024. An accidental fingerprint, not a design.

Beyond tidiness: sprint 029 is eval-gated and sprint 028's safety story
is "capture the eval baseline before the corpus wipe, compare after." An
artifact that can't say which binary, corpus, or date it describes makes
that before/after unfalsifiable, precisely when the stakes are a
destructive reset.

## Scope

**In:**

1. Stamp every report — markdown header *and* JSON — with UTC run
   timestamp, the klams `/healthz` `version` it ran against, and the
   suite file name + a content hash of it.
2. Show the same provenance in the baseline file, so a diff makes
   staleness obvious instead of requiring forensics on score magnitudes.
3. On a run, if the baseline's recorded klams version differs from the
   live one, say so in the report summary — one line, not a failure.

**Out, deliberately:**

- **Corpus point count.** The original WI text said "total corpus point
  count if cheaply available". It is not: klams-mind talks to klams over
  MCP and no tool or REST route exposes a total, so getting one would
  mean reaching Qdrant directly (no config for it, and Qdrant is
  loopback-only on kubs0) or adding a klams endpoint — which would also
  collide with sprint 027 running in that repo.
- **Auto-refreshing the baseline, or failing a run on baseline age.**
  Refreshing stays a deliberate act; an eval that silently rebaselines
  measures nothing.

## Acceptance

A report and a baseline both state the date, the klams version, and the
suite hash they correspond to; a run against a klams version different
from the baseline's says so in its summary. **Met** — see Verification.

## What was built

`src/klams_mind/eval/provenance.py` — a frozen `Provenance` record
(`run_at`, `suite_file`, `suite_hash`, `klams_version`), `now_stamp()`,
`suite_digest()`, and `parse_provenance()`.

Rendering and parsing live in the same module on purpose: the block is
written into the markdown report *and* read back out of it, so a run can
compare against the checked-in baseline with no sidecar file to keep in
sync. A round-trip test pins that contract.

### Decisions

**The digest hashes the suite file's bytes**, comments and whitespace
included. A whitespace-only edit changing the digest is intended: the
claim is "this exact file", not "an equivalent set of queries".

**`/healthz` failure degrades provenance, it does not fail the run.**
Retrieval already proves klams is up; failing an otherwise-good eval
because the health probe hiccuped would trade a real signal for a label.
Unknown renders as `unknown` and round-trips back to `None`.

**The drift note describes the run, not the artifact.** `--out` is
written *before* the baseline is attached to the report, so a refreshed
baseline never carries a note about the baseline it replaced. Confirmed
by a test that asserts the line is in stdout and absent from the file.

**An existing `--out` file is the default comparison baseline**, read
before it's overwritten. Refreshing is the documented regeneration path
and exactly when "you are replacing something five sprints old" is worth
hearing. `--baseline` names one explicitly and is read-only — that is
the sprint-028 shape (compare without overwriting).

**Suite-hash drift is reported alongside version drift.** The parse is
already free, and a changed suite makes counts incomparable for the same
reason a changed binary does.

**`parse_provenance` returns `None` for an unstamped report** rather than
raising. Pre-#676 artifacts carry no block; that is a fact about them,
not an error.

## Surprise: the eval suite was in the eval corpus

Verifying by regeneration — as the WI insisted — returned **14/21 with 1
regression** instead of the expected 15/21 with 0. Deterministic across
three runs, so not tie-breaking noise.

`evals/suites/homelab-retrieval.toml` appeared **0 times** in the 03:57
UTC baseline and **11 times** in the new one, at rank 0–1 for several
queries. `klams-scanner.timer` last fired at **04:11 UTC** — between
commit `1f60203` (03:57, which rewrote the suite to 21 queries) and the
run (04:23). The scanner had indexed the suite into the corpus it
queries.

A suite file is text engineered to lexically match every query in it, so
it wins those queries outright. The unambiguous tell was a
`no_hallucination` failure whose forbidden term is *the suite's own
assertion value*:

```
✗ no_hallucination `Duke Courses` — forbidden 'Duke Courses' surfaced in
  /home/ken/src/ai/klams-mind/evals/suites/homelab-retrieval.toml
```

`evals/baselines/homelab-retrieval.md` was in there too (5 hits), which
makes it a feedback loop: generated output carrying every query plus the
paths that answered it, scanned back in, contaminating the next run a
little more each cycle.

Same theme as #676 — a quality signal lying to us — but a distinct
defect, and one that lands squarely on the axis this sprint *dropped*:
corpus identity. Provenance did its job here, negatively: identical
klams version and identical suite hash ruled out both explanations and
pointed at the third.

**Fix, entirely in-repo:** a root [`.klamsignore`](../../.klamsignore)
excluding `evals/`. klams's scanner honours a repo-root `.klamsignore`
(`klams-scanner/src/walk.rs`) and its prune pass deletes chunks for files
it no longer walks (`klams-scanner/src/lib.rs`), so it self-heals. A
triggered scan pruned 20 chunks from the suite, 29 from the baseline, and
1 from `failing-demo.toml`. No klams change — parallel-safe with sprint
027 in that repo, per the WI's constraint.

klams's own 2026-07-25 deep review already names per-repo `.klamsignore`
seeding as a remedy for this noise class.

## Verification

`just gate` green. Live regeneration against klams 0.1.26 on kubs0:

```
# Retrieval eval — homelab-retrieval

- **Run:** 2026-07-26T04:32:01Z
- **klams version:** 0.1.26
- **Suite file:** `homelab-retrieval.toml` (`sha256:2409d5b9914b`)

**OK — 15/21 queries passed (71%).**

0 regression(s), 6 known-open, 0 newly fixed.
```

Exit 0, and every per-check-type count matches the pre-contamination
baseline. Drift, demonstrated live against a doctored copy stamped
0.1.19:

```
> **Baseline:** 2026-07-08T00:00:00Z.
> Baseline captured against klams 0.1.19; running against 0.1.26.
```

Still exit 0 — informational, as specified.

### Gotcha for the next runner

The `klams.base_url` default is `http://kubs0:7777`, which does **not**
resolve on kubs0 itself — klams binds loopback plus a tailscale TLS
listener. The repo's gitignored `.env` carries `KLAMS_TOKEN` but no
`KLAMS_URL`, so a local run needs:

```sh
set -a && . ./.env && set +a
KLAMS_URL=http://localhost:7777 uv run klams-mind eval run ...
```

Pre-existing, not touched here — changing a default that is correct from
every other host is not this sprint's call.
