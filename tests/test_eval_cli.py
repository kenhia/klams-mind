"""`klams-mind eval run <suite>` — output modes and exit codes."""

import json
from contextlib import asynccontextmanager
from pathlib import Path
from types import SimpleNamespace

from typer.testing import CliRunner

from klams_mind.cli import app, run_eval
from klams_mind.config import Config, KlamsConfig
from klams_mind.eval.checks import RetrievedItem
from klams_mind.eval.provenance import Provenance, suite_digest
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


class _HealthyClient:
    async def healthz(self) -> SimpleNamespace:
        return SimpleNamespace(version="0.1.26")


async def test_run_eval_passes_against_matching_hits(tmp_path: Path) -> None:
    path = write_suite(tmp_path)
    hits = [RetrievedItem(content="services: image: klams:dev", source="dc.yml")]

    @asynccontextmanager
    async def fake_connect(cfg):  # type: ignore[no-untyped-def]
        yield _HealthyClient()

    report = await run_eval(
        load_suite(path),
        Config(),
        suite_path=path,
        connect=fake_connect,
        retriever_factory=lambda _c: _Retr(hits),
    )
    assert report.total == 1
    assert report.failed == 0


def _report(failed: int, provenance: Provenance | None = None) -> Report:
    checks: list = []
    results = [EvalQueryResult("q", 0, [], checks, passed=(i >= failed)) for i in range(2)]
    from klams_mind.eval.report import build_report

    return build_report("s", results, provenance=provenance)


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


# --- klams#676: stamp the run, and notice a stale baseline -----------------

OLD = Provenance("2026-07-08T00:00:00Z", "suite.toml", "sha256:ab12cd34ef56", "0.1.19")
NEW = Provenance("2026-07-26T04:10:27Z", "suite.toml", "sha256:ab12cd34ef56", "0.1.26")
DRIFT = "Baseline captured against klams 0.1.19; running against 0.1.26"


async def test_run_eval_stamps_the_klams_version_and_suite_digest(tmp_path: Path) -> None:
    path = write_suite(tmp_path)

    @asynccontextmanager
    async def fake_connect(cfg):  # type: ignore[no-untyped-def]
        yield _HealthyClient()

    report = await run_eval(
        load_suite(path),
        Config(),
        suite_path=path,
        connect=fake_connect,
        retriever_factory=lambda _c: _Retr([]),
        now=lambda: "2026-07-26T04:10:27Z",
    )
    assert report.provenance == Provenance(
        run_at="2026-07-26T04:10:27Z",
        suite_file="suite.toml",
        suite_hash=suite_digest(path),
        klams_version="0.1.26",
        # #735: the report stamps the identity the run actually
        # declared. Sprint 010 made that identity a name with a default,
        # so a bare `Config()` is now the *distinct* eval identity —
        # before, with no token minted, it fell back to the main one.
        caller="klams-mind-eval",
    )


async def test_run_eval_stamps_the_main_identity_when_the_eval_one_is_disabled(
    tmp_path: Path,
) -> None:
    """Opting out is now what costs a config line, not opting in."""
    path = write_suite(tmp_path)

    @asynccontextmanager
    async def fake_connect(cfg):  # type: ignore[no-untyped-def]
        yield _HealthyClient()

    report = await run_eval(
        load_suite(path),
        Config(klams=KlamsConfig(eval_agent_name="")),
        suite_path=path,
        connect=fake_connect,
        retriever_factory=lambda _c: _Retr([]),
        now=lambda: "2026-07-26T04:10:27Z",
    )
    assert report.provenance is not None
    assert report.provenance.caller == "klams-mind"


async def test_run_eval_survives_an_unreadable_healthz(tmp_path: Path) -> None:
    """/healthz is advisory here — losing it degrades provenance, not the run."""
    path = write_suite(tmp_path)

    class _Broken:
        async def healthz(self) -> SimpleNamespace:
            raise RuntimeError("connection refused")

    @asynccontextmanager
    async def fake_connect(cfg):  # type: ignore[no-untyped-def]
        yield _Broken()

    report = await run_eval(
        load_suite(path),
        Config(),
        suite_path=path,
        connect=fake_connect,
        retriever_factory=lambda _c: _Retr([]),
    )
    assert report.total == 1
    assert report.provenance is not None
    assert report.provenance.klams_version is None


def _stamp(path: Path, prov: Provenance) -> Path:
    path.write_text("# Retrieval eval — s\n\n" + "\n".join(prov.markdown_lines()) + "\n")
    return path


def test_cli_treats_an_existing_out_file_as_the_baseline(tmp_path: Path, monkeypatch) -> None:  # type: ignore[no-untyped-def]
    out = _stamp(tmp_path / "baseline.md", OLD)

    async def fake_run_eval(suite, cfg, **kw):  # type: ignore[no-untyped-def]
        return _report(failed=0, provenance=NEW)

    monkeypatch.setattr("klams_mind.cli.run_eval", fake_run_eval)
    result = CliRunner().invoke(
        app, ["eval", "run", str(write_suite(tmp_path)), "--out", str(out)]
    )
    assert result.exit_code == 0
    assert DRIFT in result.stdout
    # The refreshed baseline must not carry a note about the one it replaced.
    refreshed = out.read_text()
    assert "Baseline captured against" not in refreshed
    assert "0.1.26" in refreshed


def test_cli_baseline_flag_compares_without_writing(tmp_path: Path, monkeypatch) -> None:  # type: ignore[no-untyped-def]
    baseline = _stamp(tmp_path / "checked-in.md", OLD)
    before = baseline.read_text()

    async def fake_run_eval(suite, cfg, **kw):  # type: ignore[no-untyped-def]
        return _report(failed=0, provenance=NEW)

    monkeypatch.setattr("klams_mind.cli.run_eval", fake_run_eval)
    result = CliRunner().invoke(
        app, ["eval", "run", str(write_suite(tmp_path)), "--baseline", str(baseline)]
    )
    assert result.exit_code == 0
    assert DRIFT in result.stdout
    assert baseline.read_text() == before, "--baseline is read-only"


def test_cli_tolerates_a_missing_or_unstamped_baseline(tmp_path: Path, monkeypatch) -> None:  # type: ignore[no-untyped-def]
    unstamped = tmp_path / "old.md"
    unstamped.write_text("# Retrieval eval — s\n\n**OK — 4/4 passed.**\n")

    async def fake_run_eval(suite, cfg, **kw):  # type: ignore[no-untyped-def]
        return _report(failed=0, provenance=NEW)

    monkeypatch.setattr("klams_mind.cli.run_eval", fake_run_eval)
    suite_arg = str(write_suite(tmp_path))
    for baseline in (str(unstamped), str(tmp_path / "absent.md")):
        result = CliRunner().invoke(app, ["eval", "run", suite_arg, "--baseline", baseline])
        assert result.exit_code == 0
        assert "Baseline captured against" not in result.stdout
