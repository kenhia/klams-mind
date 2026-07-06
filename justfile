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
