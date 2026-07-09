"""`klams-mind smoke` — orchestration tested with faked klams + model."""

import json
from contextlib import asynccontextmanager

import httpx
from langchain_core.language_models.fake_chat_models import FakeListChatModel
from typer.testing import CliRunner

from klams_mind.cli import app, run_smoke
from klams_mind.config import Config
from klams_mind.klams import KlamsClient
from tests.test_klams_client import (
    HEALTHZ_OK,
    KNOWLEDGE_MEMORY,
    REGISTER_AUTHOR_OUT,
    FakeToolCaller,
    scored,
    tool_ok,
)


class SmokeToolCaller(FakeToolCaller):
    """Replays per-tool canned results."""

    def __init__(self) -> None:
        super().__init__(tool_ok(None))
        self.results = {
            "register_author": tool_ok(REGISTER_AUTHOR_OUT),
            "memory_search": tool_ok([scored(KNOWLEDGE_MEMORY)]),
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
    assert report["search"]["hits"] == 1
    assert report["search"]["top"][0]["kind"] == "knowledge"
    assert report["search"]["top"][0]["score"] == 0.71
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
