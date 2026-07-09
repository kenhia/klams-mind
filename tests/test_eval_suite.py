"""Eval suite loader: TOML -> typed Suite/EvalQuery/Check."""

from pathlib import Path

import pytest

from klams_mind.eval.suite import EvalLoadError, load_suite

SUITE = """\
name = "homelab-retrieval"
description = "real questions klams demonstrably contains"

[[queries]]
query = "what runs the klams service"
top_k = 5

[[queries.checks]]
type = "source_cited"
value = "klams/deploy/docker-compose.yml"

[[queries.checks]]
type = "substring"
value = "image: klams"

[[queries]]
query = "unrelated cooking question"

[[queries.checks]]
type = "no_hallucination"
value = "docker-compose"
"""


def _write(tmp_path: Path, text: str) -> Path:
    p = tmp_path / "suite.toml"
    p.write_text(text)
    return p


def test_loads_suite_shape(tmp_path: Path) -> None:
    suite = load_suite(_write(tmp_path, SUITE))

    assert suite.name == "homelab-retrieval"
    assert "demonstrably" in suite.description
    assert len(suite.queries) == 2

    q0 = suite.queries[0]
    assert q0.query == "what runs the klams service"
    assert q0.top_k == 5
    assert [c.type for c in q0.checks] == ["source_cited", "substring"]
    assert q0.checks[0].value == "klams/deploy/docker-compose.yml"


def test_top_k_defaults_when_omitted(tmp_path: Path) -> None:
    suite = load_suite(_write(tmp_path, SUITE))
    assert suite.queries[1].top_k == 10  # default


def test_missing_query_text_raises(tmp_path: Path) -> None:
    bad = 'name = "x"\n[[queries]]\ntop_k = 3\n'
    with pytest.raises(EvalLoadError) as exc:
        load_suite(_write(tmp_path, bad))
    assert "query" in str(exc.value)


def test_unknown_check_type_raises(tmp_path: Path) -> None:
    bad = 'name = "x"\n[[queries]]\nquery = "q"\n[[queries.checks]]\ntype = "vibes"\n'
    with pytest.raises(EvalLoadError):
        load_suite(_write(tmp_path, bad))


def test_missing_name_raises(tmp_path: Path) -> None:
    bad = '[[queries]]\nquery = "q"\n'
    with pytest.raises(EvalLoadError):
        load_suite(_write(tmp_path, bad))


def test_missing_file_raises(tmp_path: Path) -> None:
    with pytest.raises(EvalLoadError):
        load_suite(tmp_path / "nope.toml")


def test_malformed_toml_raises(tmp_path: Path) -> None:
    with pytest.raises(EvalLoadError):
        load_suite(_write(tmp_path, "this is = = not toml ["))
