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

# CI invokes exactly this recipe (no inline duplication).
gate:
    uv run ruff format --check .
    uv run ruff check .
    uv run ty check
    uv run pytest

# Prove the plumbing against live klams + kvllm (not part of the gate).
smoke *ARGS:
    uv run klams-mind smoke {{ ARGS }}

# Added by kproject-install: the managed block tells every agent that
# `just check` runs the gates, so this repo needs that name. An alias rather
# than a second recipe, so `gate` stays the single definition CI invokes.

# Run CI gates (alias for `gate`)
check: gate
