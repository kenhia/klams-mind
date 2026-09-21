# klams-mind — working agreement

Guidance for anyone (human or agent — Claude Code, GitHub Copilot,
local models) making changes in this repo. Mirrors the klams working
agreement (`~/src/ai/klams/AGENTS.md`), adapted for Python.

klams-mind is the LLM-smart companion to the klams memory service:
extraction, semantic contradiction detection, consolidation, and
retrieval evals. Two hard boundaries:

- klams-mind is a **client** of klams. All reads/writes go through the
  klams MCP/REST surface with klams-mind's own scoped token and author
  identity — never through klams's Postgres/Qdrant directly.
- Model access goes through **OpenAI-compatible endpoints** (vLLM via
  kvllm, or whatever the config points at) — no in-process model
  loading, no llama-cpp/sentence-transformers weight management here.

Purpose-built for Ken's homelab (`kubs0`, `kai`); don't generalize
paths, hostnames, or assumptions "for portability."

## Harness

This repo is on the [kproject minimal harness](https://github.com/kenhia/kprojects).
`kproject-install` manages a marked block (`kproject:begin`/`kproject:end`)
in `CLAUDE.md` and `.github/copilot-instructions.md`; **don't hand-edit
inside those markers** — a re-run overwrites them.

**This file is not managed by the installer, and it wins on repo
specifics.** The block states the harness's general conventions; where
it and this file differ, the difference is deliberate:

- **`just check` is an alias for `just gate`.** The block tells agents
  `just check` runs the gates, so that name has to exist. `gate` stays
  the single definition CI invokes.
- **Agent scratch goes in `.scratch-agent/`, not `.scratch/`.** The
  block's one-directory shorthand predates this repo's split; keep the
  split.
- **Sprint records are directories** (`sprints/###-<stub>/`), which is
  the block's directory variant. Don't switch to flat `###-<stub>.md`.

## Sprint workflow

Work is organized into **sprints**, where a sprint is simply *the work
that fits in one PR* — some are an afternoon, some are substantial.

1. **Pick the next sprint number** (sequential, zero-padded: `001`,
   `002`, …). Create a branch and a sprint directory with the same
   name: branch `###-<short-stub>`, directory `sprints/###-<short-stub>/`.
2. **Write intent before code**: open `sprints/###-<short-stub>/sprint.md`
   stating the goal, scope, and acceptance criteria. A few paragraphs
   is fine; heavyweight ceremony is not required.
3. **Chronicle as you go**: decisions, surprises, contract changes,
   and outcomes get recorded in markdown inside the sprint directory
   (in `sprint.md` or sibling files as the work warrants). The sprint
   dir is the durable record of *why*, not a scratchpad.
4. **Ship**: gate passes, docs updated, PR merges to `main`, sprint
   doc reflects what actually happened (not just what was planned).

Cross-sprint planning documents live in `sprints/planning/` —
[roadmap.md](sprints/planning/roadmap.md) is the queue; the top entry
is the next sprint. Ad-hoc changes too small for a sprint dir still
get a line in the PR description explaining intent.

## Principles

### Test-Driven Development

TDD is mandatory for new code: write the failing test, make it pass,
refactor green. Tests exist before or alongside the code they
validate; coverage must not decrease. LLM-dependent paths get tested
against recorded/faked responses by default; live-endpoint tests are
marked `live` and **deselected** from the ordinary gate — not skipped
inside it. A skip cannot fail, so a contract test guarded by a
`skipif` reports success on a host where the service is unreachable,
which is exactly how klams-mind missed sixteen klams versions of
contract drift (#2249). They run in their own tier, where absence is
a red gate.

### Code standards gate

Every commit must pass the gate — `just gate` runs exactly what CI
runs (`just check` is an alias for it, for agents following the
harness block):

```bash
uv run ruff format --check .
uv run ruff check .
uv run ty check
uv run pytest
```

This applies to existing code touched in passing, not just new code —
no broken windows.

The second tier is **`just gate-live`**, which runs the `live` tests
against a real klams. It is not part of `just gate` and cannot be:
klams is on kubs0 behind the tailnet, so no hosted runner reaches it.
Run it where klams is reachable, and after either side deploys — it is
this repo's only assertion about the real klams contract. See
[README.md](README.md#two-test-tiers).

### Documentation is part of done

If a change alters how the system is built, configured, or used, the
docs reflect it **within the same sprint**: `README.md` plus `docs/`
(created when there's something to document).

### Quality & observability

- CLI output: errors to stderr, results to stdout, `--json` where
  programmatic use is plausible, `NO_COLOR` respected.
- Errors are actionable — what went wrong and what to do about it; no
  raw tracebacks outside debug mode.
- Anything that writes to klams must be **attributable** (its own
  author identity) and **reviewable** (dry-run/propose modes before
  destructive or bulk writes).
- Exit codes: 0 success, non-zero failure.

### Simplicity (YAGNI)

Every addition must justify its complexity. No features, abstractions,
or config options for hypothetical futures. Prefer explicit over
implicit. Defensive coding at system boundaries only (klams API, model
endpoints, session-log parsing) — trust internal code.

## Directory structure

| Directory | Purpose | Tracked |
|-----------|---------|---------|
| `sprints/` | Sprint records (`###-<stub>/`) + `planning/` + `review/` | Yes |
| `src/klams_mind/` | Package source | Yes |
| `tests/` | pytest suite | Yes |
| `docs/` | Docs (when they exist) | Yes |
| `.scratch/` | User scratch space | No |
| `.scratch-agent/` | Agent scratch space | No |
