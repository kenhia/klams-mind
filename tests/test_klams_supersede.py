"""The propose-supersede tools (klams 058, WI 3331): klams-mind files and
lists consolidation proposals. It never resolves them — that is `manage`
scope, which klams-mind does not hold and this client does not wrap."""

from uuid import UUID

import pytest

from klams_mind.klams import KlamsClient, KlamsError, SupersedeProposal
from tests.test_klams_client import FakeToolCaller, make_client, tool_error, tool_ok

KEEP = "01980000-0000-7000-8000-0000000000a0"
RETIRE = "01980000-0000-7000-8000-0000000000b0"

# Shape from klams `crates/klams-types/src/supersede.rs` at f0801e7.
PROPOSAL = {
    "id": "01980000-0000-7000-8000-0000000000c0",
    "author_id": "01980000-0000-7000-8000-000000000042",
    "keeper_id": KEEP,
    "retire_ids": [RETIRE],
    "text": "merged",
    "reason": "same subject",
    "status": "pending",
    "submission_count": 1,
    "submitted_at": "2026-11-10T03:00:00Z",
    "last_seen_at": "2026-11-10T03:00:00Z",
    "resolved_at": None,
}


async def test_supersede_propose_sends_the_typed_args_and_parses() -> None:
    caller = FakeToolCaller(tool_ok({"proposal": PROPOSAL, "deduped": False}))
    out = await make_client(caller).supersede_propose(
        keeper_id=KEEP, retire_ids=[RETIRE], reason="same subject", text="merged"
    )
    name, args = caller.calls[0]
    assert name == "supersede_propose"
    assert args == {
        "keeper_id": KEEP,
        "retire_ids": [RETIRE],
        "reason": "same subject",
        "text": "merged",
    }
    assert out.deduped is False
    assert out.proposal.status == "pending"
    assert out.proposal.keeper_id == UUID(KEEP)
    assert out.proposal.retire_ids == [UUID(RETIRE)]


async def test_supersede_propose_omits_text_for_a_duplicate() -> None:
    caller = FakeToolCaller(tool_ok({"proposal": {**PROPOSAL, "text": None}, "deduped": True}))
    out = await make_client(caller).supersede_propose(
        keeper_id=KEEP, retire_ids=[RETIRE], reason="dup"
    )
    assert "text" not in caller.calls[0][1]
    assert out.deduped is True and out.proposal.text is None


async def test_supersede_propose_surfaces_the_error_code() -> None:
    caller = FakeToolCaller(tool_error("NOT_AGENT_AUTHORED", "scanner-ingested"))
    with pytest.raises(KlamsError) as exc:
        await make_client(caller).supersede_propose(
            keeper_id=KEEP, retire_ids=[RETIRE], reason="r"
        )
    assert exc.value.error_code == "NOT_AGENT_AUTHORED"


async def test_supersede_proposals_list_passes_status_and_limit() -> None:
    resolved = {
        **PROPOSAL,
        "status": "stale",
        "resolved_at": "2026-11-10T04:00:00Z",
        "resolved_by_author_id": "01980000-0000-7000-8000-000000000043",
    }
    caller = FakeToolCaller(tool_ok({"proposals": [resolved]}))
    [p] = await make_client(caller).supersede_proposals_list(status="stale", limit=200)
    assert caller.calls[0] == ("supersede_proposals_list", {"status": "stale", "limit": 200})
    assert isinstance(p, SupersedeProposal)
    assert p.status == "stale" and p.ids == {UUID(KEEP), UUID(RETIRE)}


def test_the_client_cannot_resolve_its_own_proposals() -> None:
    # Acceptance is `manage` scope (klams 058 D5); klams-mind holds read,write.
    assert not hasattr(KlamsClient, "supersede_proposal_resolve")


# --- lineage over REST (klams 0.1.58 hides superseded records from memory_get)


async def test_knowledge_lineage_reads_rest_with_the_identity_header() -> None:
    import httpx

    seen: list[httpx.Request] = []

    def handler(request: httpx.Request) -> httpx.Response:
        seen.append(request)
        return httpx.Response(
            200, json={"id": KEEP, "text": "…", "supersedes": RETIRE, "superseded_by": None}
        )

    out = await make_client(handler=httpx.MockTransport(handler)).knowledge_lineage(KEEP)
    assert seen[0].url.path == f"/memory/knowledge/{KEEP}"
    assert out.supersedes == UUID(RETIRE) and out.superseded_by is None


async def test_knowledge_lineage_raises_on_a_miss() -> None:
    import httpx

    transport = httpx.MockTransport(lambda r: httpx.Response(404, json={"error": "nope"}))
    with pytest.raises(KlamsError, match="404"):
        await make_client(handler=transport).knowledge_lineage(KEEP)


async def test_error_code_is_read_from_the_envelope_klams_actually_sends() -> None:
    # Recorded live from klams 0.1.58 (memory_get on a superseded id): the
    # whole error envelope arrives as JSON inside the text content, with no
    # `_meta` on the result — so the code was None on every live error.
    from mcp.types import CallToolResult, TextContent

    envelope = (
        '{"isError":true,"content":[{"type":"text","text":"no live memory with id X"}],'
        '"_meta":{"error_code":"NOT_FOUND"}}'
    )
    result = CallToolResult(content=[TextContent(type="text", text=envelope)], isError=True)
    with pytest.raises(KlamsError) as exc:
        await make_client(FakeToolCaller(result)).memory_get(KEEP)
    assert exc.value.error_code == "NOT_FOUND"
    assert str(exc.value) == "no live memory with id X"
