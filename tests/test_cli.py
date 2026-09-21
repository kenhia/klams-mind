"""`klams-mind smoke` — orchestration tested with faked klams + model."""

import json
from contextlib import asynccontextmanager

import httpx
from langchain_core.language_models.fake_chat_models import FakeListChatModel
from typer.testing import CliRunner

from klams_mind.cli import _print_human, app, run_smoke
from klams_mind.config import Config
from klams_mind.klams import KlamsClient
from tests.test_klams_client import (
    COMPACT_SEARCH_OUT,
    HEALTHZ_OK,
    REGISTER_AUTHOR_OUT,
    FakeToolCaller,
    tool_ok,
)


class SmokeToolCaller(FakeToolCaller):
    """Replays per-tool canned results."""

    def __init__(self) -> None:
        super().__init__(tool_ok(None))
        self.results = {
            "register_author": tool_ok(REGISTER_AUTHOR_OUT),
            # smoke uses the compact path deliberately (klams 046).
            "memory_search": tool_ok(COMPACT_SEARCH_OUT),
        }

    async def __call__(self, name, args):  # type: ignore[no-untyped-def]
        self.calls.append((name, args))
        return self.results[name]


def fake_wiring() -> dict:
    caller = SmokeToolCaller()
    http = httpx.AsyncClient(
        transport=httpx.MockTransport(lambda req: httpx.Response(200, json=HEALTHZ_OK))
    )

    @asynccontextmanager
    async def fake_connect(cfg):  # type: ignore[no-untyped-def]
        yield KlamsClient(cfg, tool_caller=caller, http=http)

    async def fake_resolve(cfg, http=None):  # type: ignore[no-untyped-def]
        return "fake-model"

    return {
        "connect": fake_connect,
        "resolve_model_name": fake_resolve,
        "build_chat": lambda cfg: FakeListChatModel(responses=["pong"]),
        "caller": caller,
    }


async def test_run_smoke_exercises_all_four_steps() -> None:
    wiring = fake_wiring()
    caller = wiring.pop("caller")

    report = await run_smoke(Config(), **wiring)

    assert report["ok"] is True
    assert report["klams"]["status"] == "Ok"
    assert report["author"]["agent_name"] == "klams-mind"
    assert report["search"]["hits"] == 2
    assert report["search"]["top"][0]["kind"] == "knowledge"
    assert report["search"]["top"][0]["score"] == 0.032786883
    # klams 046: smoke reports the compact envelope's truncation flag, so
    # a health check says whether snippets were elided.
    assert report["search"]["truncated"] is True
    assert report["model"]["name"] == "fake-model"
    assert report["model"]["reply"] == "pong"
    tool_names = [name for name, _ in caller.calls]
    assert tool_names == ["register_author", "memory_search"]


def test_smoke_command_json_output(monkeypatch) -> None:  # type: ignore[no-untyped-def]
    async def fake_run_smoke(cfg, **overrides):  # type: ignore[no-untyped-def]
        return {"ok": True, "klams": {"status": "Ok"}}

    monkeypatch.setattr("klams_mind.cli.run_smoke", fake_run_smoke)
    result = CliRunner().invoke(app, ["smoke", "--json"])

    assert result.exit_code == 0
    assert json.loads(result.stdout) == {"ok": True, "klams": {"status": "Ok"}}


# --- klams version-range warning (#2249, sprint 011) ------------------------


async def test_run_smoke_reports_a_version_warning_when_klams_is_out_of_range() -> None:
    """HEALTHZ_OK is the 2026-07-06 recording at klams 0.1.0 — below the
    0.1.46 floor where the compact envelope landed. The health check
    should say so in as many words rather than leave it to a later
    ValidationError."""
    wiring = fake_wiring()
    wiring.pop("caller")

    report = await run_smoke(Config(), **wiring)

    assert report["klams"]["version"] == "0.1.0"
    warning = report["klams"]["version_warning"]
    assert warning is not None
    assert "0.1.0" in warning and "older" in warning


def test_print_human_puts_the_version_warning_on_stderr(capsys) -> None:  # type: ignore[no-untyped-def]
    _print_human(
        {
            "klams": {
                "status": "Ok",
                "version": "0.1.99",
                "url": "http://kubs0:7777",
                "version_warning": "klams is 0.1.99, newer than ...",
            },
            "author": {"agent_name": "klams-mind", "author_id": "abc"},
            "search": {"query": "q", "hits": 1},
            "model": {"name": "m", "endpoint": "e", "reply": "pong"},
        }
    )

    captured = capsys.readouterr()
    assert "klams is 0.1.99, newer than ..." in captured.err
    assert "klams is 0.1.99, newer than ..." not in captured.out
    assert "smoke: all steps passed" in captured.out


def test_print_human_is_silent_when_the_version_is_in_range(capsys) -> None:  # type: ignore[no-untyped-def]
    _print_human(
        {
            "klams": {
                "status": "Ok",
                "version": "0.1.46",
                "url": "http://kubs0:7777",
                "version_warning": None,
            },
            "author": {"agent_name": "klams-mind", "author_id": "abc"},
            "search": {"query": "q", "hits": 1},
            "model": {"name": "m", "endpoint": "e", "reply": "pong"},
        }
    )

    assert capsys.readouterr().err == ""


def test_smoke_json_keeps_stdout_pure_and_warns_on_stderr(monkeypatch) -> None:  # type: ignore[no-untyped-def]
    """A `--json` consumer reads the field; a human piping to jq still
    sees the warning, because it never touches stdout."""

    async def fake_run_smoke(cfg, **overrides):  # type: ignore[no-untyped-def]
        return {"ok": True, "klams": {"status": "Ok", "version_warning": "drifted!"}}

    monkeypatch.setattr("klams_mind.cli.run_smoke", fake_run_smoke)
    result = CliRunner().invoke(app, ["smoke", "--json"])

    assert result.exit_code == 0
    assert json.loads(result.stdout)["klams"]["version_warning"] == "drifted!"
    assert "drifted!" in result.stderr
