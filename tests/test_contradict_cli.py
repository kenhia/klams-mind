"""`klams-mind contradict run <query>` — output modes and flag threading."""

import json

from typer.testing import CliRunner

from klams_mind.cli import app
from klams_mind.contradict.pairing import CandidatePair
from klams_mind.contradict.runner import DetectionResult, JudgedPair
from tests.test_contradict_pairing import as_fact, make_fact

A = as_fact(make_fact("a0", {"host": "kubs0", "service": "klams"}))
B = as_fact(make_fact("b0", {"host": "kai", "service": "klams"}))


def canned_result() -> DetectionResult:
    return DetectionResult(
        query="homelab services",
        judged=[
            JudgedPair(
                CandidatePair(a=A, b=B),
                "contradiction",
                "one service cannot run on two hosts",
                "dry-run",
                target_id=str(A.id),
                contradicting_id=str(B.id),
                proposed_payload={"host": "kai", "service": "klams"},
            )
        ],
    )


def test_cli_dry_run_prints_markdown(monkeypatch) -> None:  # type: ignore[no-untyped-def]
    async def fake_run(query, cfg, **kw):  # type: ignore[no-untyped-def]
        assert kw["apply"] is False
        return canned_result()

    monkeypatch.setattr("klams_mind.cli.run_contradict", fake_run)
    result = CliRunner().invoke(app, ["contradict", "run", "homelab services"])
    assert result.exit_code == 0
    assert "# Contradiction detection — homelab services" in result.stdout
    assert "one service cannot run on two hosts" in result.stdout


def test_cli_json_output_and_out_file(tmp_path, monkeypatch) -> None:  # type: ignore[no-untyped-def]
    async def fake_run(query, cfg, **kw):  # type: ignore[no-untyped-def]
        return canned_result()

    monkeypatch.setattr("klams_mind.cli.run_contradict", fake_run)
    out = tmp_path / "report.md"
    result = CliRunner().invoke(
        app, ["contradict", "run", "homelab services", "--json", "--out", str(out)]
    )
    assert result.exit_code == 0
    payload = json.loads(result.stdout)
    assert payload["pairs"] == 1
    assert payload["contradictions"] == 1
    assert "# Contradiction detection" in out.read_text()


def test_cli_apply_and_tuning_flags_thread_through(monkeypatch) -> None:  # type: ignore[no-untyped-def]
    seen: dict = {}

    async def fake_run(query, cfg, **kw):  # type: ignore[no-untyped-def]
        seen.update(kw)
        seen["query"] = query
        return canned_result()

    monkeypatch.setattr("klams_mind.cli.run_contradict", fake_run)
    result = CliRunner().invoke(
        app,
        ["contradict", "run", "homelab services", "--apply", "--neighbours", "3", "--top", "20"],
    )
    assert result.exit_code == 0
    assert seen["apply"] is True
    assert seen["neighbours"] == 3
    assert seen["top"] == 20
    assert seen["query"] == "homelab services"
