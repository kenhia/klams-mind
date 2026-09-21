# Sprint 011 — a live gate and a version-range warning

Proposal: korg:2989 (`LHF — a live gate and a version-range warning so
klams contract drift is noticed`), slice 3.7 of program korg:2981
(*Low-hanging fruit — experiment 1*). Covered work item: **korg:2249**.

Run as an overseen karc leg (`klams-mind-08b8eb`) on kubs0. The ship is
gated on an overseer green light; this record is the durable *why*.

## Goal

klams-mind is a client of klams, and it has no automated signal when
klams' contract moves under it. WI 2249 measured the cost: klams sprint
046 changed `memory_search`'s MCP envelope from a bare list to
`{hits, more}`, klams-mind broke completely — smoke, evals, extraction's
duplicate check, contradiction pairing — and **`just gate` stayed green
through sixteen klams versions**, because every klams-facing test fakes
the MCP transport by injecting a tool-caller. The break was found by a
human happening to run `smoke`.

Three things, from WI 2249's own options list (its (1) and (3), which it
says compose well):

1. **`just gate-live`** — a contract tier that runs `-m live` against a
   reachable klams, outside the ordinary gate.
2. **A version-range warning in `smoke`** — it already reads `/healthz`;
   make it say "klams is 0.1.52, this client was tested against 0.1.46"
   instead of waiting for a `ValidationError` to say the same thing
   less clearly.
3. **Docs** — the live tier is local-only, and why.

Explicitly **not** in scope (proposal says so): WI 2247, the superseded
pinned id — a suite-design decision held for a later sprint.

## Acceptance

- `just gate` is unchanged in what it proves, and no longer *collects*
  live tests at all.
- `just gate-live` runs the live round-trip against real klams and
  **fails** when klams is unreachable or the contract has moved. A tier
  that can only skip is not a gate.
- `smoke` warns, in both human and `--json` output, when klams' version
  is outside the range this client's contract fixtures were recorded
  against.
- README documents both, accurately.
- `just gate` green; `just gate-live` green against live klams on kubs0.

## Premise check (start-sprint Step 5)

WI 2249's falsifiable claims, checked against the repo and the live
service on 2026-09-21:

| Claim | Verdict |
|---|---|
| Every klams-facing test fakes the MCP transport | **holds** — `tests/test_klams_client.py` injects a `tool_caller` throughout |
| `test_live_round_trip` is `@pytest.mark.live`, skipped unless the env var is set | **holds** — `tests/test_klams_client.py:498` |
| `smoke` already reads the `/healthz` version | **holds** — `cli.py` puts `snap.version` in the report |
| The compact fixture is dated and sourced | **holds** — "Recorded 2026-09-10 from live kubs0:7777 at klams 0.1.46" |
| No `gate-live` recipe exists | **holds** |
| "…which CI does not set" | **drifted — same direction.** There is no GitHub CI in this repo and there never has been (`git log --all -- .github/workflows` is empty; `.github/` holds only `copilot-instructions.md`). The gate is run by hand and by agents. That makes the finding *stronger*, not weaker: nothing at all runs on a schedule, so nothing at all would have caught the envelope change. |
| "`KLAMS_URL`/`KLAMS_TOKEN`" | **drifted — one half is gone.** Sprint 010 removed klams-mind's token entirely; the identity is a name in `X-Homelab-Agent` and there is no secret to set. Only `KLAMS_URL` gates the live test. |

Measured alongside: **klams on kubs0 is at 0.1.52** today, against
fixtures recorded at 0.1.46. WI 2249's hypothetical warning text —
"klams is 0.1.52, this client was tested against 0.1.46" — is literally
true as written, six versions of undetected drift after the last one.

No premise gone. Scope proceeds as written.

## Cross-project plan

`klams-mind` is not in `kai:~/src/tools/cross-project-planning/index.md`.
No plan applies.

## Decisions

### D-1 — `-m 'not live'` in `addopts`, not a `skipif`

The live test was kept out of the ordinary gate by
`@pytest.mark.skipif(not os.environ.get("KLAMS_URL"))`. That is the
wrong mechanism for a repo that now has two tiers, for one reason:
**a `skipif` cannot fail.** `just gate-live` on a shell without
`KLAMS_URL` exported would print `1 skipped`, exit 0, and report a
contract gate as passing having asserted nothing — the exact shape of
failure WI 2249 is about, rebuilt one layer up.

So the deselection moves to `addopts = ["-m", "not live"]` in
`pyproject.toml`, which the ordinary `pytest` run inherits and
`pytest -m live` overrides (pytest takes the last `-m`). The live test
keeps its marker and loses its `skipif`: when `gate-live` runs it, it
runs, and an unreachable klams is a red gate.

### D-2 — the live test resolves its URL through `load_config()`

`os.environ["KLAMS_URL"]` ignored this repo's own config chain. The
checkout already carries a `.env` with `KLAMS_URL` in it, which
`load_config()` auto-loads on the real-run path precisely so "live runs
pick up local overrides without exporting them" — and the live test was
the one live thing that did not benefit. Routing it through
`load_config()` means `just gate-live` works from a plain checkout on
kubs0 with no exported variable, and `KLAMS_URL=…` still wins because
the real environment beats `.env`.

### D-3 — the tested range is a constant in `klams.py`, and `gate-live` is what maintains it

`TESTED_KLAMS_MIN`/`TESTED_KLAMS_MAX` live next to the client whose
contract they describe, not in the CLI that happens to print them.

The min is not decoration: below 0.1.46 the compact envelope does not
exist, so an *old* klams breaks this client as surely as a new one.

The max needs a maintenance story or it becomes the stale fixture again.
The story is: **the live round-trip asserts it, last, after the
substantive assertions have passed.** A newer klams therefore fails
`gate-live` with the evidence already in hand — "the round-trip passed
at 0.1.53; bump `TESTED_KLAMS_MAX`" — which is a one-line edit made with
proof rather than a constant nobody revisits. Ordering matters: asserting
the range *first* would tell you the version moved and never tell you
whether the contract still held.

This is the one piece of the sprint that is a design call rather than a
transcription of the proposal, and it is flagged for the overseer.

### D-4 — the warning is advisory in `smoke`, fatal in `gate-live`

`smoke` is a plumbing check a human runs; an out-of-range version is
information, not a failure, so it goes to stderr and into the JSON
report and `smoke` still exits 0 when everything worked. `gate-live` is
a gate; there the same fact is an assertion failure. Same constant, two
appropriate severities.

## What shipped

**A second test tier.** `pyproject.toml` gains
`addopts = ["-m", "not live"]`; `just gate` now *deselects* the live
test (189 passed, 1 deselected) rather than collecting and skipping it.
`just gate-live` runs `pytest -m live -v`, which overrides the addopts
because pytest takes the last `-m`. The live round-trip lost its
`skipif` and resolves its URL via `load_config()`.

**A version-range warning.** `klams_mind/klams.py` gains
`TESTED_KLAMS_MIN`/`TESTED_KLAMS_MAX`, `parse_version` and
`version_warning`. `run_smoke` puts `version_warning` in
`report["klams"]`; `_warn_version` echoes it to **stderr in both output
modes**, so a `--json` consumer reads the field and a human piping to
`jq` still sees the line. Six new unit tests on the helper, four on the
CLI wiring.

**Docs.** README gains a *Two test tiers* section (with the table, the
no-`skipif` reasoning, and why the tier is local-only) and a *tested
version range* subsection under the search contract. AGENTS.md's TDD
principle and gate section are corrected to match — the old text said
live tests are "marked and skipped when the endpoint is absent", which
this sprint makes false.

### The mechanism proved itself on the first run

`just gate-live`, first execution, against live klams on kubs0
(probed from kubs0 — the host the leg runs on and the host klams runs
on, so the probe measures the right fact):

```
AssertionError: the round-trip above passed against klams 0.1.52, but
TESTED_KLAMS_MAX is 0.1.46 — bump it to 0.1.52 so `smoke` stops warning
about a combination this gate has now proven
```

Every contract assertion — compact envelope, `full`, `memory_get` —
passed against 0.1.52; only the ceiling was stale, and it failed with
the evidence in hand. `TESTED_KLAMS_MAX` was raised to `(0, 1, 52)` as
a proven claim rather than a guess, and `gate-live` went green. That is
D-3 working on the day it was written, and it is the first time this
repo has asserted anything about a klams newer than 0.1.46.

### Verification

| Check | Result |
|---|---|
| `just gate` | green — 189 passed, 1 deselected |
| `just gate-live` (live klams 0.1.52, from kubs0) | green — 1 passed, 189 deselected |
| `just smoke` (live klams + kvllm on kai) | green, no warning (0.1.52 in range) |
| warning path, end to end | forced by temporarily lowering the ceiling: the line appeared on **stderr** in both modes, `--json` stdout still parsed as JSON, exit 0 — then reverted |
| `just --list` | both new/changed descriptions read correctly |

## Repaired in passing

- **`just --list` descriptions, self-inflicted and caught before
  commit.** `just` takes the *last* contiguous comment line as a
  recipe's description, so the explanatory comments this sprint added
  left `gate` described as "`live` tier via pytest's addopts" and
  `gate-live` as "(#2249 is a story about a green gate that asserted
  nothing)". Both blocks were restructured to end on a one-line
  summary. Proven by `just --list`.
- **README claimed a CI that does not exist.** The Development block
  described `just gate` as "(what CI runs)". There is no GitHub Actions
  workflow in this repo and `git log --all -- .github/workflows` shows
  there never has been. Corrected to "the single gate", and the new
  README section states plainly that the gate is run before every
  commit and that no hosted runner could reach klams anyway. Mechanical,
  unambiguous, and in the exact section this sprint was rewriting.

## Follow-ups

None filed, deliberately. The two things WI 2249 raises that this
sprint does not close are both already accounted for elsewhere, and
filing them again would make the record worse:

- **Its option (2)**, a recorded-cassette refresh recipe for the faked
  fixtures. The proposal explicitly holds the suite-design question for
  WI 2247 / klams-mind 010; this sprint stayed inside its scope.
- **Its closing suggestion**, that klams carry a client-visible contract
  version or name klams-mind as a consumer in its release path. That is
  another repo's contract and therefore a decision this sprint cannot
  make (Branch B) — raised in the wrap-up handoff for the overseer's
  ruling rather than filed unilaterally as a klams work item.

No cross-repo changes were made: everything landed inside klams-mind.
