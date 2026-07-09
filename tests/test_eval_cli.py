"""`klams-mind eval run <suite>` — output modes and exit codes."""

import json
from contextlib import asynccontextmanager
from pathlib import Path

from typer.testing import CliRunner

from klams_mind.cli import app, run_eval
from klams_mind.config import Config
from klams_mind.eval.checks import RetrievedItem
from klams_mind.eval.report import Report
from klams_mind.eval.runner import EvalQueryResult
from klams_mind.eval.suite import load_suite

SUITE_TOML = """\
name = "smoke-suite"

[[queries]]
query = "what runs klams"
top_k = 3

[[queries.checks]]
type = "substring"
value = "image: klams"
"""


def write_suite(tmp_path: Path) -> Path:
    p = tmp_path / "suite.toml"
    p.write_text(SUITE_TOML)
    return p


class _Retr:
    def __init__(self, hits: list[RetrievedItem]) -> None:
        self.hits = hits

    async def search(self, query: str, top_k: int) -> list[RetrievedItem]:
        return self.hits


async def test_run_eval_passes_against_matching_hits(tmp_path: Path) -> None:
    suite = load_suite(write_suite(tmp_path))
    hits = [RetrievedItem(content="services: image: klams:dev", source="dc.yml")]

    @asynccontextmanager
    async def fake_connect(cfg):  # type: ignore[no-untyped-def]
        yield None  # client unused; retriever injected below

    report = await run_eval(
        suite, Config(), connect=fake_connect, retriever_factory=lambda _c: _Retr(hits)
    )
    assert report.total == 1
    assert report.failed == 0


def _report(failed: int) -> Report:
    checks: list = []
    results = [EvalQueryResult("q", 0, [], checks, passed=(i >= failed)) for i in range(2)]
    from klams_mind.eval.report import build_report

    return build_report("s", results)


def test_cli_exit_zero_when_all_pass(tmp_path: Path, monkeypatch) -> None:  # type: ignore[no-untyped-def]
    async def fake_run_eval(suite, cfg, **kw):  # type: ignore[no-untyped-def]
        return _report(failed=0)

    monkeypatch.setattr("klams_mind.cli.run_eval", fake_run_eval)
    result = CliRunner().invoke(app, ["eval", "run", str(write_suite(tmp_path))])
    assert result.exit_code == 0


def test_cli_exit_one_when_any_fail(tmp_path: Path, monkeypatch) -> None:  # type: ignore[no-untyped-def]
    async def fake_run_eval(suite, cfg, **kw):  # type: ignore[no-untyped-def]
        return _report(failed=1)

    monkeypatch.setattr("klams_mind.cli.run_eval", fake_run_eval)
    result = CliRunner().invoke(app, ["eval", "run", str(write_suite(tmp_path))])
    assert result.exit_code == 1


def test_cli_json_output(tmp_path: Path, monkeypatch) -> None:  # type: ignore[no-untyped-def]
    async def fake_run_eval(suite, cfg, **kw):  # type: ignore[no-untyped-def]
        return _report(failed=0)

    monkeypatch.setattr("klams_mind.cli.run_eval", fake_run_eval)
    result = CliRunner().invoke(app, ["eval", "run", str(write_suite(tmp_path)), "--json"])
    assert result.exit_code == 0
    assert json.loads(result.stdout)["suite"] == "s"


def test_cli_writes_markdown_out_file(tmp_path: Path, monkeypatch) -> None:  # type: ignore[no-untyped-def]
    async def fake_run_eval(suite, cfg, **kw):  # type: ignore[no-untyped-def]
        return _report(failed=0)

    monkeypatch.setattr("klams_mind.cli.run_eval", fake_run_eval)
    out = tmp_path / "report.md"
    result = CliRunner().invoke(
        app, ["eval", "run", str(write_suite(tmp_path)), "--out", str(out)]
    )
    assert result.exit_code == 0
    assert "Retrieval eval — s" in out.read_text()


def test_cli_bad_suite_exits_two(tmp_path: Path) -> None:
    result = CliRunner().invoke(app, ["eval", "run", str(tmp_path / "nope.toml")])
    assert result.exit_code == 2
