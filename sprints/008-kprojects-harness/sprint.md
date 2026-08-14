# Sprint 008 — onto the kprojects harness

korg proposal [#1251](korg:1251), work item #1248 (chore/S). Batch 3 of
the kprojects rollout (korg #737) — the actively-developed repos that
had no harness at all.

## Goal

Apply the kproject minimal harness to klams-mind: the managed agent
block, the standard layout directories, and the `just check` entry
point the block tells every agent to use. Behaviour-neutral — no source
changes, no service touched.

## Scope

- `uvx --refresh --from git+https://github.com/kenhia/kprojects kproject-install --agent both .`
- Verify (not author) the `check` alias the installer now appends.
- Decide explicitly what happens to `AGENTS.md`, which the installer
  does not manage.
- Docs updated in the same sprint.

## Acceptance

- `just check` green and reaching the same work as `just gate`.
- `just --list` reads cleanly.
- No contradiction between the managed block and `AGENTS.md`.

## What happened

### The dirty tree (the flagged blocker)

The proposal flagged uncommitted changes to `README.md` and `justfile`
as an in-flight blocker. It turned out to be a coherent, self-contained
change unrelated to the harness: a `just smoke` recipe wrapping
`uv run klams-mind smoke`, plus README lines for it and a live-test
example retargeted from `kubs0` to `localhost`. Per the work item's own
instruction ("if unrelated to the harness, commit it on main first"),
it was committed to `main` as `69d4a09` before branching — not stashed,
not discarded. The migration branch started clean.

Numbering note: the work item's procedure named branch
`006-kprojects-harness`, written before sprints 006 and 007 shipped.
This is **008**.

### The installer handled the `check` alias unaided — the fix works

This sprint was the first time kprojects `366a594` (#1254, sprint 004)
met a real repo rather than the synthetic one it was smoke-tested
against. It behaved exactly as designed:

```
stack    : python (detected)
justfile : added `check: gate` alias
```

Verified rather than hand-written, as instructed:

- The alias targets **`gate`**, not `test` — correct. (`test` is
  excluded from `GATE_RECIPES` on purpose: aliasing `check` to it would
  skip lint and typecheck while still looking like a pass.)
- `just check` exits 0 and runs the full gate — ruff format/check, ty,
  148 passed / 1 skipped, identical to `just gate`.
- `just --list` reads cleanly. The installer's three-line explanatory
  comment is separated from the `# Run CI gates (alias for gate)` doc
  comment by a blank line, so only the doc comment reaches the listing
  — the fragment-leak an early draft of the fix had is not present.
- No hand-written alias was added. Nothing to report back to kprojects.

`--refresh` confirmed the build came from `366a594` itself, not a
cached pre-fix one.

### `AGENTS.md`: kept, and made explicit about the block

Both files the installer manages (`CLAUDE.md`, which was a single
`@AGENTS.md` import line, and `.github/copilot-instructions.md`) were
already thin pointers at `AGENTS.md`, so the block appended below them
cleanly — nothing needed demoting under a `## Project` heading, which
the procedure had anticipated for a fatter `CLAUDE.md`.

That left `AGENTS.md` — unmanaged, substantive, and the thing both
managed files defer to. Rather than leave it to drift into
contradicting the block, it gained a `## Harness` section naming the
harness, warning off hand-edits inside the markers, and stating that
**AGENTS.md wins on repo specifics**, with the three real divergences
called out:

| Block says | This repo does | Why |
|---|---|---|
| `just check` runs the gates | `just gate` is the definition | `check` is an alias; `gate` is what CI invokes |
| `.scratch/` for user *and* agent | `.scratch/` + `.scratch-agent/` | the split predates the block's shorthand |
| sprint records `.md` *or* directory | directories | the block's directory variant, already in use |

The two frictions batch 1 hit did not arise here: `ty` is already
adopted (it runs inside `gate`), and `sprints/` was already
`###-<stub>/`.

### Layout

`sprints/review/`, `docs/` and `.scratch/` were created. `.scratch/` is
already gitignored; the other two are empty, so git carries no trace of
them until they hold something. `sprints/review/` was added to the
directory table in `AGENTS.md`.

## Follow-ups

None. The one finding worth reporting upstream — whether `366a594`
holds up against a real repo — is that it does.
