# klams-mind task runner. Install `just` once, then `just --list`.

# Default recipe shows the menu so a bare `just` is friendly.
default:
    @just --list

# Format the codebase in place.
fmt:
    uv run ruff format .
    uv run ruff check --fix .

# Lint without modifying.
lint:
    uv run ruff check .

# Type-check with ty.
typecheck:
    uv run ty check

# Run the test suite.
test:
    uv run pytest

# The single gate definition (no inline duplication). The `live` tier is
# deselected here by pytest's addopts — see `gate-live`.
#
# fmt-check + lint + typecheck + tests (the one gate; no live services)
gate:
    uv run ruff format --check .
    uv run ruff check .
    uv run ty check
    uv run pytest

# The contract tier (#2249). Local-only by nature: klams lives on kubs0
# behind the tailnet, so no GitHub-hosted runner could ever reach it.
# Run it where klams is reachable, and after deploying either side.
#
# `-m live` overrides `gate`'s `-m "not live"` because pytest takes the
# last `-m`. This gate FAILS on an unreachable klams rather than
# skipping — #2249 is a story about a green gate that asserted nothing.
#
# The klams round-trip, against a real klams (not part of `gate`)
gate-live:
    uv run pytest -m live -v

# Re-resolve the suite's memory_id pins against the live corpus and report
# drift (klams-mind #2247). Deliberately outside `gate`: pin rot is a fact
# about klams' corpus, which moves with no commit here, so a hosted runner
# could not see it and a red gate would misattribute it. Exits 1 on drift.
#
# The pin-refresh recipe, against live klams (not part of the gate)
refresh-pins *ARGS:
    uv run klams-mind eval pins evals/suites/homelab-retrieval.toml {{ ARGS }}

# Prove the plumbing against live klams + kvllm (not part of the gate).
smoke *ARGS:
    uv run klams-mind smoke {{ ARGS }}

# Added by kproject-install: the managed block tells every agent that
# `just check` runs the gates, so this repo needs that name. An alias rather
# than a second recipe, so `gate` stays the single definition CI invokes.

# Run CI gates (alias for `gate`)
check: gate
