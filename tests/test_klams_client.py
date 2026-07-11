"""klams client: typed wrappers over /healthz (REST) and the MCP tools.

Fixtures are recorded from the live service / the klams source contract
(klams repo `crates/klams-mcp/src/tools/`); the MCP transport is faked
by injecting a tool-caller. The live round-trip test at the bottom is
marked `live` and skipped unless KLAMS_URL and KLAMS_TOKEN are set.
"""

import json
import os
from typing import Any

import httpx
import pytest
from mcp.types import CallToolResult, TextContent

from klams_mind.config import KlamsConfig
from klams_mind.klams import (
    DissentProposed,
    FactMemory,
    KlamsClient,
    KlamsError,
    KnowledgeMemory,
    connect,
)

# Recorded 2026-07-06 from live kubs0:7777/healthz.
HEALTHZ_OK = {
    "status": "Ok",
    "postgres": {"state": "Ok"},
    "qdrant": {"state": "Ok"},
    "embeddings": {"state": "Ok"},
    "queue": {"depth": 0, "capacity": 1024, "workers": 4},
    "version": "0.1.0",
    "uptime_seconds": 652643,
    "maintenance": {"active": False},
}

REGISTER_AUTHOR_OUT = {
    "author_id": "01980000-0000-7000-8000-000000000042",
    "agent_name": "klams-mind",
    "created_at": "2026-07-06T12:00:00Z",
}

FACT_MEMORY = {
    "id": "01980000-0000-7000-8000-00000000000a",
    "kind": "fact",
    "type": "EnvFact",
    "payload": {"host": "kubs0", "service": "klams"},
    "tags": ["homelab"],
    "author": {"agent_name": "system"},
    "created_at": "2026-07-01T00:00:00Z",
    "updated_at": "2026-07-01T00:00:00Z",
}

KNOWLEDGE_MEMORY = {
    "id": "01980000-0000-7000-8000-00000000000b",
    "kind": "knowledge",
    "text": "kvllm serves OpenAI-compatible models on kai:8000",
    "source_path": "README.md",
    "repo": "/home/ken/src/ai/kvllm",
    "tags": ["homelab", "kvllm"],
    "author": {"agent_name": "claude-code", "model": "claude-fable-5"},
    "created_at": "2026-07-02T00:00:00Z",
    "updated_at": "2026-07-02T00:00:00Z",
}


def scored(memory: dict[str, Any], score: float = 0.71, source_rank: int = 0) -> dict[str, Any]:
    """Wrap a memory fixture in the klams-016 scored-hit envelope."""
    return {"score": score, "source_rank": source_rank, "memory": memory}


class FakeToolCaller:
    """Stands in for the MCP session: records calls, replays results."""

    def __init__(self, result: CallToolResult) -> None:
        self.result = result
        self.calls: list[tuple[str, dict[str, Any]]] = []

    async def __call__(self, name: str, args: dict[str, Any]) -> CallToolResult:
        self.calls.append((name, args))
        return self.result


def tool_ok(payload: Any) -> CallToolResult:
    return CallToolResult(content=[TextContent(type="text", text=json.dumps(payload))])


def tool_error(code: str, message: str) -> CallToolResult:
    return CallToolResult(
        content=[TextContent(type="text", text=message)],
        isError=True,
        _meta={"error_code": code},
    )


def make_client(
    caller: FakeToolCaller | None = None,
    handler: httpx.MockTransport | None = None,
) -> KlamsClient:
    cfg = KlamsConfig(base_url="http://kubs0:7777", token="test-token")
    http = httpx.AsyncClient(transport=handler) if handler else None
    return KlamsClient(cfg, tool_caller=caller, http=http)


# --- healthz ---------------------------------------------------------------


async def test_healthz_parses_snapshot() -> None:
    transport = httpx.MockTransport(lambda req: httpx.Response(200, json=HEALTHZ_OK))
    client = make_client(handler=transport)

    snap = await client.healthz()

    assert snap.status == "Ok"
    assert snap.postgres.state == "Ok"
    assert snap.queue.workers == 4
    assert snap.version == "0.1.0"


async def test_healthz_degraded_503_still_returns_snapshot() -> None:
    body = {**HEALTHZ_OK, "status": "Degraded"}
    transport = httpx.MockTransport(lambda req: httpx.Response(503, json=body))
    client = make_client(handler=transport)

    snap = await client.healthz()

    assert snap.status == "Degraded"


# --- register_author -------------------------------------------------------


async def test_register_author_calls_tool_and_parses() -> None:
    caller = FakeToolCaller(tool_ok(REGISTER_AUTHOR_OUT))
    client = make_client(caller)

    author = await client.register_author(agent_name="klams-mind", model="gemma-4-31b-it-awq")

    name, args = caller.calls[0]
    assert name == "register_author"
    assert args["agent_name"] == "klams-mind"
    assert args["model"] == "gemma-4-31b-it-awq"
    assert "session_title" not in args  # unset optionals stay off the wire
    assert str(author.author_id) == REGISTER_AUTHOR_OUT["author_id"]
    assert author.agent_name == "klams-mind"


# --- memory_search ----------------------------------------------------------


async def test_memory_search_parses_scored_kinds() -> None:
    caller = FakeToolCaller(tool_ok([scored(FACT_MEMORY, 0.31, 1), scored(KNOWLEDGE_MEMORY)]))
    client = make_client(caller)

    hits = await client.memory_search("kvllm endpoint", top_k=5)

    name, args = caller.calls[0]
    assert name == "memory_search"
    assert args == {"query": "kvllm endpoint", "top_k": 5}
    assert hits[0].score == 0.31
    assert hits[0].source_rank == 1
    assert isinstance(hits[0].memory, FactMemory)
    assert hits[0].memory.type == "EnvFact"
    assert hits[1].score == 0.71
    assert isinstance(hits[1].memory, KnowledgeMemory)
    assert "kai:8000" in hits[1].memory.text
    assert hits[1].memory.author.agent_name == "claude-code"


async def test_memory_search_passes_filters() -> None:
    caller = FakeToolCaller(tool_ok([]))
    client = make_client(caller)

    hits = await client.memory_search("anything", kinds=["knowledge"], tags=["homelab"])

    _, args = caller.calls[0]
    assert args["kinds"] == ["knowledge"]
    assert args["tags"] == ["homelab"]
    assert hits == []


# --- memory_add -------------------------------------------------------------


async def test_add_knowledge_builds_flattened_payload() -> None:
    caller = FakeToolCaller(tool_ok(KNOWLEDGE_MEMORY))
    client = make_client(caller)

    memory = await client.add_knowledge(
        author_id=REGISTER_AUTHOR_OUT["author_id"],
        text="kvllm serves OpenAI-compatible models on kai:8000",
        tags=["homelab", "kvllm"],
    )

    name, args = caller.calls[0]
    assert name == "memory_add"
    assert args["kind"] == "knowledge"
    assert args["author_id"] == REGISTER_AUTHOR_OUT["author_id"]
    assert args["tags"] == ["homelab", "kvllm"]
    assert isinstance(memory, KnowledgeMemory)


async def test_add_fact_builds_flattened_payload() -> None:
    caller = FakeToolCaller(tool_ok(FACT_MEMORY))
    client = make_client(caller)

    memory = await client.add_fact(
        author_id=REGISTER_AUTHOR_OUT["author_id"],
        fact_type="EnvFact",
        payload={"host": "kubs0", "service": "klams"},
    )

    _, args = caller.calls[0]
    assert args["kind"] == "fact"
    assert args["fact_type"] == "EnvFact"
    assert isinstance(memory, FactMemory)


# --- dissent_propose --------------------------------------------------------

# klams serializes the ids as simple (dash-less) UUIDs; pydantic parses both.
DISSENT_OUT = {
    "dissent_id": "01980000000070008000000000000cd0",
    "fact_id": "019800000000700080000000000000a0",
    "status": "pending",
    "deduped": False,
}


async def test_dissent_propose_builds_args_and_parses() -> None:
    caller = FakeToolCaller(tool_ok(DISSENT_OUT))
    client = make_client(caller)

    out = await client.dissent_propose(
        fact_id="019800000000700080000000000000a0",
        proposed_payload={"host": "kai", "service": "klams"},
        reason="a newer fact places klams on kai, not kubs0",
        author_id=REGISTER_AUTHOR_OUT["author_id"],
        contradicting_memory_id="019800000000700080000000000000b0",
    )

    name, args = caller.calls[0]
    assert name == "dissent_propose"
    assert args["fact_id"] == "019800000000700080000000000000a0"
    assert args["proposed_payload"] == {"host": "kai", "service": "klams"}
    assert args["reason"].startswith("a newer fact")
    assert args["author_id"] == REGISTER_AUTHOR_OUT["author_id"]
    assert args["contradicting_memory_id"] == "019800000000700080000000000000b0"
    assert isinstance(out, DissentProposed)
    assert out.status == "pending"
    assert out.deduped is False
    assert str(out.fact_id) == "01980000-0000-7000-8000-0000000000a0"


async def test_dissent_propose_omits_unset_optionals() -> None:
    caller = FakeToolCaller(tool_ok(DISSENT_OUT))
    client = make_client(caller)

    await client.dissent_propose(
        fact_id="019800000000700080000000000000a0",
        proposed_payload={"host": "kai"},
        reason="correction",
    )

    _, args = caller.calls[0]
    assert "author_id" not in args
    assert "contradicting_memory_id" not in args


# --- memory_delete ----------------------------------------------------------


async def test_memory_delete_passes_author_and_id() -> None:
    caller = FakeToolCaller(tool_ok({"deleted": True}))
    client = make_client(caller)

    await client.memory_delete(
        author_id=REGISTER_AUTHOR_OUT["author_id"], memory_id=str(FACT_MEMORY["id"])
    )

    name, args = caller.calls[0]
    assert name == "memory_delete"
    assert args == {"author_id": REGISTER_AUTHOR_OUT["author_id"], "id": str(FACT_MEMORY["id"])}


# --- errors -----------------------------------------------------------------


async def test_tool_error_raises_klams_error_with_code() -> None:
    caller = FakeToolCaller(tool_error("EMPTY_QUERY", "query must be non-empty"))
    client = make_client(caller)

    with pytest.raises(KlamsError) as exc:
        await client.memory_search("")

    assert exc.value.error_code == "EMPTY_QUERY"
    assert "non-empty" in str(exc.value)


# --- live round-trip --------------------------------------------------------


@pytest.mark.live
@pytest.mark.skipif(
    not (os.environ.get("KLAMS_URL") and os.environ.get("KLAMS_TOKEN")),
    reason="KLAMS_URL/KLAMS_TOKEN not set",
)
async def test_live_round_trip() -> None:
    cfg = KlamsConfig(base_url=os.environ["KLAMS_URL"], token=os.environ["KLAMS_TOKEN"])
    async with connect(cfg) as client:
        snap = await client.healthz()
        assert snap.status in {"Ok", "Degraded"}

        author = await client.register_author(
            agent_name="klams-mind", session_title="sprint 001 live round-trip"
        )
        added = await client.add_knowledge(
            author_id=str(author.author_id),
            text="klams-mind sprint 001 live round-trip marker",
            tags=["klams-mind", "smoke-test"],
        )
        hits = await client.memory_search("klams-mind sprint 001 live round-trip marker", top_k=10)
        assert any(h.memory.id == added.id for h in hits)
