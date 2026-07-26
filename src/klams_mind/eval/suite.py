"""Eval suite format: a TOML file of queries, each with retrieval checks.

Mirrors krag's suite loader (`~/src/ai/krag/src/krag/evaluation/loader.py`)
but typed with pydantic and adapted to klams retrieval checks. The file
is the suite's identity; there are no per-query ids.

    name = "homelab-retrieval"
    description = "..."

    [[queries]]
    query = "what runs the klams service"
    top_k = 5

    [[queries.checks]]
    type = "source_cited"
    value = "klams/deploy/docker-compose.yml"
"""

import tomllib
from pathlib import Path
from typing import Literal

from pydantic import BaseModel, ValidationError

CheckType = Literal[
    "substring",
    "source_cited",
    "no_hallucination",
    # klams sprint 026 (#643). The three original checks all pass on
    # scanner chunks, which is why the suite scored 4/4 while every
    # real-world failure in klams#628 was happening. These measure the
    # things that were actually broken.
    "no_duplicates",
    "min_body_chars",
    "memory_id",
]


class EvalLoadError(Exception):
    """A suite file is missing, unparseable, or structurally invalid."""


class Check(BaseModel, extra="forbid"):
    type: CheckType
    value: str | None = None
    # `min_body_chars`: shortest acceptable chunk body, breadcrumb
    # stripped. klams sprint 026 (#643) — 6,125 chunks in the corpus are
    # under 100 chars, and a content-free fragment measured 0.956 cosine,
    # so junk outranks real answers.
    min_chars: int | None = None
    # `memory_id`: cap on where the memory may rank (0-based, inclusive).
    # Presence alone is a weak assertion — klams#628's whole point was
    # that the right memory existed and lost.
    max_rank: int | None = None
    # `min_body_chars` / `no_duplicates`: how deep into the page to look.
    # The junk ceiling is a top-5 claim, not a whole-page claim.
    top_n: int | None = None


class EvalQuery(BaseModel, extra="forbid"):
    query: str
    top_k: int = 10
    checks: list[Check] = []
    # klams sprint 026 (#643). A measurement suite has to be able to
    # encode "this is broken and we know it" — otherwise it either omits
    # the failures (and measures nothing that matters, which is exactly
    # how the original 4 queries scored 4/4 while klams#628 was live) or
    # sits permanently red and stops working as a gate.
    #
    #   pass       — must pass; a failure is a regression and fails the run
    #   known_open — currently fails by design; tracked by `tracking`.
    #                Does not fail the run. If it starts passing, the run
    #                says so loudly: the fix landed, promote it to `pass`.
    expect: Literal["pass", "known_open"] = "pass"
    # Why a `known_open` query is open — a WI or sprint reference. Keeps
    # the suite honest: no unexplained permanent failures.
    tracking: str | None = None


class Suite(BaseModel, extra="forbid"):
    name: str
    description: str = ""
    queries: list[EvalQuery] = []


def load_suite(path: Path) -> Suite:
    path = Path(path)
    try:
        with path.open("rb") as fh:
            data = tomllib.load(fh)
    except FileNotFoundError as exc:
        raise EvalLoadError(f"suite not found: {path}") from exc
    except tomllib.TOMLDecodeError as exc:
        raise EvalLoadError(f"invalid TOML in {path}: {exc}") from exc

    try:
        return Suite.model_validate(data)
    except ValidationError as exc:
        raise EvalLoadError(f"invalid suite {path}: {exc}") from exc
