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

CheckType = Literal["substring", "source_cited", "no_hallucination"]


class EvalLoadError(Exception):
    """A suite file is missing, unparseable, or structurally invalid."""


class Check(BaseModel, extra="forbid"):
    type: CheckType
    value: str | None = None


class EvalQuery(BaseModel, extra="forbid"):
    query: str
    top_k: int = 10
    checks: list[Check] = []


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
