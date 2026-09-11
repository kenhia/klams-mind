"""klams client: typed wrappers over /healthz (REST) and the MCP tools.

Fixtures are recorded from the live service / the klams source contract
(klams repo `crates/klams-mcp/src/tools/`); the MCP transport is faked
by injecting a tool-caller. The live round-trip test at the bottom is
marked `live` and skipped unless KLAMS_URL and KLAMS_TOKEN are set.
"""

import json
import os
from typing import Any
from uuid import UUID

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


# Recorded 2026-09-10 from live kubs0:7777 at klams 0.1.46 — the compact
# response contract (klams sprint 046, WI #1178). Typed metadata is
# omitted where it does not apply, so this agent-added knowledge hit
# carries no `source_path`; a scanner chunk would.
COMPACT_SEARCH_OUT = {
    "hits": [
        {
            "id": "019f5330-46b1-7e03-a8a2-503681c52543",
            "kind": "knowledge",
            "snippet": "Homelab HTTPS is now Tailscale (tailnet encke-wahoo.ts.net)\u2026",
            "score": 0.032786883,
            "raw_score": 0.45266056,
            "source_rank": 0,
            "age_seconds": 5297070,
            "tags": ["tailscale", "https", "homelab"],
            "author": "claude",
        },
        {
            "id": "019fd554-bc12-7623-a2f8-de0ee654265c",
            "kind": "knowledge",
            "snippet": "klams-scanner on kai now deploys from the homelab package store.",
            "score": 0.06453292,
            "raw_score": 0.6672274,
            "source_rank": 2,
            "age_seconds": 91234,
            "tags": ["klams", "deploy"],
            "author": "claude",
            "source_path": "sprints/042-scanner-from-store/sprint.md",
            "repo": "klams",
            "heading_path": "Sprint 042 > How to deploy",
            "copies": 2,
        },
    ],
    "more": {"fetch": "memory_get", "truncated": True},
}

# --- memory_search ----------------------------------------------------------


async def test_memory_search_full_parses_scored_kinds() -> None:
    caller = FakeToolCaller(tool_ok([scored(FACT_MEMORY, 0.31, 1), scored(KNOWLEDGE_MEMORY)]))
    client = make_client(caller)

    hits = await client.memory_search_full("kvllm endpoint", top_k=5)

    name, args = caller.calls[0]
    assert name == "memory_search"
    # klams 046: bodies inline are opt-in, and this is the eval-harness path.
    assert args == {"query": "kvllm endpoint", "top_k": 5, "full": True}
    assert hits[0].score == 0.31
    assert hits[0].source_rank == 1
    assert isinstance(hits[0].memory, FactMemory)
    assert hits[0].memory.type == "EnvFact"
    assert hits[1].score == 0.71
    assert isinstance(hits[1].memory, KnowledgeMemory)
    assert "kai:8000" in hits[1].memory.text
    assert hits[1].memory.author.agent_name == "claude-code"


async def test_memory_search_full_passes_filters() -> None:
    caller = FakeToolCaller(tool_ok([]))
    client = make_client(caller)

    hits = await client.memory_search_full("anything", kinds=["knowledge"], tags=["homelab"])

    _, args = caller.calls[0]
    assert args["kinds"] == ["knowledge"]
    assert args["tags"] == ["homelab"]
    assert hits == []


# --- memory_search: the compact contract (klams 046 / #1178) -----------------


async def test_memory_search_parses_the_compact_envelope() -> None:
    """The regression that broke every klams-mind retrieval path.

    klams 0.1.46 returns `{hits, more}`; klams-mind validated the body as
    a bare `list[ScoredMemory]` and raised `ValidationError: Input should
    be a valid list` on smoke, evals, extraction and pairing alike.
    """
    caller = FakeToolCaller(tool_ok(COMPACT_SEARCH_OUT))
    client = make_client(caller)

    resp = await client.memory_search("homelab https", top_k=3)

    name, args = caller.calls[0]
    assert name == "memory_search"
    # Compact is klams' default and klams-mind's: no `full` on the wire.
    assert args == {"query": "homelab https", "top_k": 3}
    assert [h.id for h in resp.hits] == [
        UUID("019f5330-46b1-7e03-a8a2-503681c52543"),
        UUID("019fd554-bc12-7623-a2f8-de0ee654265c"),
    ]
    assert resp.hits[0].snippet.endswith("\u2026")
    assert resp.hits[0].score == 0.032786883
    assert resp.hits[0].raw_score == 0.45266056
    assert resp.hits[0].source_rank == 0
    assert resp.hits[0].age_seconds == 5297070
    assert resp.hits[0].author == "claude"
    assert resp.more.fetch == "memory_get"
    assert resp.more.truncated is True


async def test_compact_hit_omits_metadata_that_does_not_apply() -> None:
    """klams omits rather than fakes, so these are None/absent, not ""."""
    caller = FakeToolCaller(tool_ok(COMPACT_SEARCH_OUT))
    client = make_client(caller)

    agent_written, scanned = (await client.memory_search("q")).hits

    assert agent_written.source_path is None
    assert agent_written.heading_path is None
    assert agent_written.repo is None
    assert agent_written.copies is None
    assert scanned.source_path == "sprints/042-scanner-from-store/sprint.md"
    assert scanned.heading_path == "Sprint 042 > How to deploy"
    assert scanned.repo == "klams"
    assert scanned.copies == 2


async def test_memory_search_compact_passes_filters() -> None:
    caller = FakeToolCaller(
        tool_ok({"hits": [], "more": {"fetch": "memory_get", "truncated": False}})
    )
    client = make_client(caller)

    resp = await client.memory_search("anything", kinds=["fact"], tags=["homelab"])

    _, args = caller.calls[0]
    assert args["kinds"] == ["fact"]
    assert args["tags"] == ["homelab"]
    assert resp.hits == []
    assert resp.more.truncated is False


# --- memory_get -------------------------------------------------------------


async def test_memory_get_fetches_the_full_record() -> None:
    """`more.fetch` names this tool; it is the compact path's follow-up."""
    caller = FakeToolCaller(tool_ok(KNOWLEDGE_MEMORY))
    client = make_client(caller)

    memory = await client.memory_get("01980000-0000-7000-8000-00000000000b")

    name, args = caller.calls[0]
    assert name == "memory_get"
    assert args == {"id": "01980000-0000-7000-8000-00000000000b"}
    assert isinstance(memory, KnowledgeMemory)
    assert "kai:8000" in memory.text


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
        marker = "klams-mind sprint 001 live round-trip marker"

        # Compact is the default agent path (klams 046 / #1178). This
        # assertion is the one that was missing when klams 0.1.46 landed:
        # the unit tests all faked the transport, so nothing in the suite
        # noticed the envelope change until smoke failed in sprint 009.
        compact = await client.memory_search(marker, top_k=10)
        assert compact.more.fetch == "memory_get"
        assert any(h.id == added.id for h in compact.hits)

        # Bodies inline — the eval harness's path, and what keeps the
        # retrieval baseline comparable across the contract change.
        full = await client.memory_search_full(marker, top_k=10)
        assert any(h.memory.id == added.id for h in full)

        # And the follow-up `more.fetch` names.
        fetched = await client.memory_get(str(added.id))
        assert fetched.id == added.id
