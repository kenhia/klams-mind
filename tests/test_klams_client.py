"""klams client: typed wrappers over /healthz (REST) and the MCP tools.

Fixtures are recorded from the live service / the klams source contract
(klams repo `crates/klams-mcp/src/tools/`); the MCP transport is faked
by injecting a tool-caller. That is the gap #2249 measured — the suite
validates klams-mind against klams-mind's own idea of the contract — so
the round-trip test at the bottom is marked `live` and is the one thing
here that refers to the world. `just gate` deselects it; `just gate-live`
runs it, and an unreachable klams fails that gate rather than skipping.
"""

import json
import warnings
from contextlib import asynccontextmanager
from datetime import timedelta
from typing import Any
from uuid import UUID

import httpx
import pytest
from mcp.types import CallToolResult, TextContent

from klams_mind.config import KlamsConfig, load_config
from klams_mind.klams import (
    TESTED_KLAMS_MAX,
    TESTED_KLAMS_MIN,
    DissentProposed,
    FactMemory,
    KlamsClient,
    KlamsError,
    KlamsVersionWarning,
    KnowledgeMemory,
    _fmt_version,
    connect,
    parse_version,
    untested_version_note,
    version_warning,
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
    cfg = KlamsConfig(base_url="http://kubs0:7777")
    http = httpx.AsyncClient(transport=handler) if handler else None
    return KlamsClient(cfg, tool_caller=caller, http=http)


def _capture(seen: dict[str, Any]) -> Any:
    """A `streamablehttp_client` stand-in that records what it was handed."""

    @asynccontextmanager
    async def fake(url: str, headers: dict[str, str] | None = None) -> Any:
        seen["url"] = url
        seen["headers"] = headers
        yield (None, None, None)

    return fake


class _FakeSession:
    """A `ClientSession` stand-in: `connect` only initializes it."""

    def __init__(self, *_args: Any) -> None: ...

    async def __aenter__(self) -> "_FakeSession":
        return self

    async def __aexit__(self, *_exc: Any) -> None: ...

    async def initialize(self) -> None: ...


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


async def test_memory_get_carries_the_supersession_links() -> None:
    """A superseded record still resolves, and names both neighbours.

    WI 2247, measured against klams 0.1.52: `memory_supersede` HIDES the
    old record from search rather than deleting it, and `memory_get`
    serves it with `supersedes` (backward) and `superseded_by` (forward).
    That pair is the whole basis for an eval check that follows a
    lineage instead of pinning a leaf — klams-mind simply never declared
    the fields, so pydantic dropped data that had been arriving all along.
    """
    superseded = KNOWLEDGE_MEMORY | {
        "supersedes": "019fa04a-ceac-7253-9420-ea3a39cd0ef2",
        "superseded_by": "019fb6b1-1c9a-7850-9822-79ef941025f2",
    }
    client = make_client(FakeToolCaller(tool_ok(superseded)))

    memory = await client.memory_get("019fb1c9-7c16-7513-9ad4-f067611afbf1")

    assert isinstance(memory, KnowledgeMemory)
    assert str(memory.supersedes) == "019fa04a-ceac-7253-9420-ea3a39cd0ef2"
    assert str(memory.superseded_by) == "019fb6b1-1c9a-7850-9822-79ef941025f2"


async def test_memory_search_full_carries_supersedes() -> None:
    """The `full` envelope carries it too — not only the compact hit.

    The eval harness is the documented `full` caller, so a field present
    only on the compact shape would be useless to the suite. Measured
    present on both against klams 0.1.52.
    """
    envelope = [
        {
            "score": 0.9,
            "source_rank": 0,
            "memory": KNOWLEDGE_MEMORY | {"supersedes": "019fb1c9-7c16-7513-9ad4-f067611afbf1"},
        }
    ]
    client = make_client(FakeToolCaller(tool_ok(envelope)))

    (hit,) = await client.memory_search_full("q")

    assert isinstance(hit.memory, KnowledgeMemory)
    assert str(hit.memory.supersedes) == "019fb1c9-7c16-7513-9ad4-f067611afbf1"


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


# --- the declared identity on the wire (sprint 010, korg:2423) --------------


async def test_connect_declares_the_agent_name_as_a_header(monkeypatch: Any) -> None:
    """klams keys `[[auth.identities]]` off `X-Homelab-Agent`, so the name
    has to reach the transport — a config field nobody sends is the bug."""
    seen: dict[str, Any] = {}

    monkeypatch.setattr("klams_mind.klams.streamablehttp_client", _capture(seen))
    monkeypatch.setattr("klams_mind.klams.ClientSession", _FakeSession)

    async with connect(KlamsConfig(base_url="http://k:7777", agent_name="klams-mind-eval")):
        pass

    assert seen["url"] == "http://k:7777/mcp"
    assert seen["headers"] == {"X-Homelab-Agent": "klams-mind-eval"}


async def test_connect_sends_no_authorization_header(monkeypatch: Any) -> None:
    """Sprint 010: the bearer path is gone, not merely unused."""
    seen: dict[str, Any] = {}

    monkeypatch.setattr("klams_mind.klams.streamablehttp_client", _capture(seen))
    monkeypatch.setattr("klams_mind.klams.ClientSession", _FakeSession)

    async with connect(KlamsConfig()):
        pass

    assert "Authorization" not in (seen["headers"] or {})


async def test_connect_sends_no_header_when_no_identity_is_configured(
    monkeypatch: Any,
) -> None:
    """An empty name is a config error; declaring "" would be a lie klams
    404s on anyway. Send nothing and let klams answer 401 honestly."""
    seen: dict[str, Any] = {}

    monkeypatch.setattr("klams_mind.klams.streamablehttp_client", _capture(seen))
    monkeypatch.setattr("klams_mind.klams.ClientSession", _FakeSession)

    async with connect(KlamsConfig(agent_name="")):
        pass

    assert seen["headers"] is None


# --- live round-trip --------------------------------------------------------


@pytest.mark.live
async def test_live_round_trip() -> None:
    """The contract tier: `just gate-live`, never `just gate`.

    No `skipif` (sprint 011 D-1) — `addopts` deselects this from the
    ordinary gate, so when it runs it runs, and an unreachable klams is
    a red gate rather than a green skip.

    The URL comes from the repo's own config chain (D-2), so a plain
    checkout on kubs0 works off its `.env` with nothing exported, and
    `KLAMS_URL=…` still wins because the real environment beats `.env`.
    """
    cfg = load_config().klams
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

        # The supersession contract (#2247, sprint 012). `memory_id`
        # checks now follow a `supersedes` chain, so this client depends
        # on three facts about real klams that every unit test above
        # fakes — which is #2249's shape exactly, and the reason this
        # lives in the contract tier instead of the ordinary gate.
        #
        # `019fa04a-ceac…` is a SUPERSEDED record, and that is what makes
        # it a safe fixture rather than a new instance of the fuse this
        # sprint removed: supersession is terminal, so its state cannot
        # regress. The chain may grow past it; it can never un-supersede.
        superseded_id = "019fa04a-ceac-7253-9420-ea3a39cd0ef2"
        hidden = await client.memory_get(superseded_id)

        # 1. A superseded record is HIDDEN, not deleted — memory_get
        #    still serves it. Without this the ancestry walk dead-ends.
        assert str(hidden.id) == superseded_id
        # 2. It names both neighbours. `supersedes` is what the walk
        #    follows backward; `superseded_by` is what proves it is dead.
        assert hidden.superseded_by is not None
        assert hidden.supersedes is not None
        # 3. And it is genuinely absent from search, which is the
        #    invariant the eval suite's paraphrase query exists to prove.
        page = await client.memory_search_full(
            "klams memory_search score field behavior ranking", top_k=8
        )
        assert all(str(h.memory.id) != superseded_id for h in page)
        # 4. `supersedes` rides on a search hit too, in the `full`
        #    envelope the eval harness uses — not only on `memory_get`.
        #    A field present only on the compact shape would be useless
        #    to the suite, and this is the assertion that says so.
        assert any(h.memory.supersedes is not None for h in page)

        # The paged corpus read (sprint 013, WI 272) — REST rather than
        # MCP, and consolidation's only way to see the whole set. A
        # two-second window around the marker keeps it to one page even
        # while a scanner is writing hundreds of chunks a minute.
        second = timedelta(seconds=1)
        walked = [
            m
            async for m in client.walk_memories(
                since=added.created_at - second,
                until=added.created_at + second,
                kinds=["knowledge"],
            )
        ]
        assert any(m.id == added.id for m in walked)

    # Last, and a WARNING rather than an assertion (sprint 011 D-3, as
    # revised by the overseer). Everything above this line is the drift
    # signal and fails hard. This is only the "nobody has re-proved it
    # this far yet" note: klams ships often, and a tier that goes red on
    # a patch bump carrying no contract change is a tier people learn to
    # ignore — the exact failure #2249 exists to stop. It runs last so
    # it can say the contract held, which is what makes it actionable.
    note = untested_version_note(snap.version)
    if note is not None:
        # stacklevel=1 on purpose: inside an async test, 2 attributes the
        # warning to asyncio's event loop rather than to this line.
        warnings.warn(f"ACTION: {note}", KlamsVersionWarning, stacklevel=1)


# --- contract version range (sprint 011) ------------------------------------


def test_parse_version_reads_dotted_integers() -> None:
    assert parse_version("0.1.52") == (0, 1, 52)


def test_parse_version_returns_none_for_nonsense() -> None:
    assert parse_version("") is None
    assert parse_version("0.1.52-rc1") is None
    assert parse_version("unknown") is None


def test_no_warning_inside_the_tested_range() -> None:
    assert version_warning(_fmt_version(TESTED_KLAMS_MIN)) is None
    assert version_warning(_fmt_version(TESTED_KLAMS_MAX)) is None


def test_warns_below_the_floor_and_names_the_compact_envelope() -> None:
    """The floor is real: `{hits, more}` landed in klams 0.1.46, so an
    older klams breaks this client as surely as a newer one."""
    warning = version_warning("0.1.30")
    assert warning is not None
    assert "0.1.30" in warning
    assert "older" in warning
    assert _fmt_version(TESTED_KLAMS_MIN) in warning


def test_warns_above_the_ceiling_and_names_the_next_action() -> None:
    """WI 2249's own example: sixteen versions of drift, found by hand."""
    warning = version_warning("9.9.9")
    assert warning is not None
    assert "9.9.9" in warning
    assert "newer" in warning
    assert "gate-live" in warning


def test_unparseable_version_warns_rather_than_raising() -> None:
    warning = version_warning("who-knows")
    assert warning is not None
    assert "who-knows" in warning


# --- the gate-live note: a warning, never a failure (overseer ruling) --------


def test_untested_note_is_silent_inside_the_range() -> None:
    assert untested_version_note(_fmt_version(TESTED_KLAMS_MAX)) is None
    assert untested_version_note(_fmt_version(TESTED_KLAMS_MIN)) is None


def test_untested_note_above_the_ceiling_says_the_contract_held() -> None:
    """The whole point of running it last: an out-of-range answer here
    means a stale constant, not drift, and the note must say so and
    name the constant to move."""
    note = untested_version_note("0.1.99")
    assert note is not None
    assert "contract holds" in note
    assert "TESTED_KLAMS_MAX" in note
    assert "(0, 1, 99)" in note
    assert "src/klams_mind/klams.py" in note


def test_untested_note_below_the_floor_names_the_other_constant() -> None:
    note = untested_version_note("0.1.30")
    assert note is not None
    assert "TESTED_KLAMS_MIN" in note
    assert "TESTED_KLAMS_MAX" not in note


def test_untested_note_handles_an_uncomparable_version() -> None:
    note = untested_version_note("0.1.53-rc1")
    assert note is not None
    assert "0.1.53-rc1" in note


def test_klams_version_warning_is_a_warning_not_an_error() -> None:
    """The overseer's ruling in one assertion: klams ships often, so a
    version past the ceiling must not turn `gate-live` red. Only the
    round-trip's contract assertions may do that."""
    assert issubclass(KlamsVersionWarning, Warning)

    with pytest.warns(KlamsVersionWarning, match="contract holds"):
        warnings.warn(
            f"ACTION: {untested_version_note('0.1.99')}",
            KlamsVersionWarning,
            stacklevel=1,
        )
