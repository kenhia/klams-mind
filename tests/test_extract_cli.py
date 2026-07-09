"""`klams-mind extract run <transcript>` — output modes and exit codes."""

import json
from pathlib import Path

from typer.testing import CliRunner

from klams_mind.cli import app
from klams_mind.extract.chain import CandidateFact
from klams_mind.extract.runner import ExtractionResult, VettedCandidate

TRANSCRIPT_LINE = json.dumps(
    {"type": "user", "message": {"role": "user", "content": "klams listens on kubs0:7777"}}
)


def write_transcript(tmp_path: Path) -> Path:
    p = tmp_path / "session.jsonl"
    p.write_text(TRANSCRIPT_LINE + "\n")
    return p


def canned_result() -> ExtractionResult:
    fact = CandidateFact(
        text="klams listens on kubs0:7777", evidence="klams listens on kubs0:7777"
    )
    return ExtractionResult(
        transcript="session.jsonl",
        windows=1,
        candidates=[VettedCandidate(fact, "proposed", "dry-run", 1)],
    )


def test_cli_dry_run_prints_markdown(tmp_path: Path, monkeypatch) -> None:  # type: ignore[no-untyped-def]
    async def fake_run_extract(wins, cfg, **kw):  # type: ignore[no-untyped-def]
        assert kw["apply"] is False
        return canned_result()

    monkeypatch.setattr("klams_mind.cli.run_extract", fake_run_extract)
    result = CliRunner().invoke(app, ["extract", "run", str(write_transcript(tmp_path))])
    assert result.exit_code == 0
    assert "# Extraction — session.jsonl" in result.stdout
    assert "klams listens on kubs0:7777" in result.stdout


def test_cli_json_output_and_out_file(tmp_path: Path, monkeypatch) -> None:  # type: ignore[no-untyped-def]
    async def fake_run_extract(wins, cfg, **kw):  # type: ignore[no-untyped-def]
        return canned_result()

    monkeypatch.setattr("klams_mind.cli.run_extract", fake_run_extract)
    out = tmp_path / "report.md"
    result = CliRunner().invoke(
        app, ["extract", "run", str(write_transcript(tmp_path)), "--json", "--out", str(out)]
    )
    assert result.exit_code == 0
    payload = json.loads(result.stdout)
    assert payload["windows"] == 1
    assert payload["candidates"][0]["status"] == "proposed"
    assert "# Extraction" in out.read_text()


def test_cli_apply_flag_threads_through(tmp_path: Path, monkeypatch) -> None:  # type: ignore[no-untyped-def]
    seen: dict = {}

    async def fake_run_extract(wins, cfg, **kw):  # type: ignore[no-untyped-def]
        seen.update(kw)
        return canned_result()

    monkeypatch.setattr("klams_mind.cli.run_extract", fake_run_extract)
    result = CliRunner().invoke(
        app, ["extract", "run", str(write_transcript(tmp_path)), "--apply"]
    )
    assert result.exit_code == 0
    assert seen["apply"] is True


def test_cli_bad_transcript_exits_two(tmp_path: Path) -> None:
    result = CliRunner().invoke(app, ["extract", "run", str(tmp_path / "nope.jsonl")])
    assert result.exit_code == 2

    empty = tmp_path / "empty.jsonl"
    empty.write_text(json.dumps({"type": "mode", "mode": "normal"}) + "\n")
    result = CliRunner().invoke(app, ["extract", "run", str(empty)])
    assert result.exit_code == 2
