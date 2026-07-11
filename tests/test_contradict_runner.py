"""Detection runner: refute-by-default judging, propose-first filing."""

import json
from typing import Any

import pytest
from langchain_core.language_models.fake_chat_models import FakeListChatModel
from mcp.types import CallToolResult

from klams_mind.config import KlamsConfig
from klams_mind.contradict.chain import build_contradiction_chain
from klams_mind.contradict.pairing import CandidatePair
from klams_mind.contradict.runner import detect_contradictions
from klams_mind.klams import KlamsClient
from tests.test_contradict_pairing import as_fact, make_fact
from tests.test_klams_client import DISSENT_OUT, tool_ok


class ToolRouter:
    def __init__(self, results: dict[str, CallToolResult]) -> None:
        self.results = results
        self.calls: list[tuple[str, dict[str, Any]]] = []

    async def __call__(self, name: str, args: dict[str, Any]) -> CallToolResult:
        self.calls.append((name, args))
        return self.results[name]


def client_for(router: ToolRouter) -> KlamsClient:
    return KlamsClient(KlamsConfig(), tool_caller=router)


def verdict(**kw: object) -> str:
    return json.dumps(kw)


# a and b are the same service on two different hosts — a real contradiction.
A = as_fact(make_fact("a0", {"host": "kubs0", "service": "klams"}))
B = as_fact(make_fact("b0", {"host": "kai", "service": "klams"}))
PAIR = CandidatePair(a=A, b=B)  # ids already sorted (a0 < b0)


def chain_replying(*responses: str):
    return build_contradiction_chain(FakeListChatModel(responses=list(responses)))


async def test_clear_pair_files_nothing() -> None:
    router = ToolRouter({})
    chain = chain_replying(verdict(contradicts=False, reason="different services entirely"))

    result = await detect_contradictions([PAIR], chain, client_for(router), query="q")

    (jp,) = result.judged
    assert jp.status == "clear"
    assert result.filed == 0
    assert router.calls == []  # nothing written


async def test_contradiction_is_proposed_but_not_filed_in_dry_run() -> None:
    router = ToolRouter({})
    chain = chain_replying(
        verdict(
            contradicts=True,
            reason="one service cannot run on two hosts",
            target="a",
            proposed_payload={"host": "kai", "service": "klams"},
        )
    )

    result = await detect_contradictions([PAIR], chain, client_for(router), query="q")

    (jp,) = result.judged
    assert jp.status == "contradiction"
    assert jp.target_id == str(A.id)
    assert jp.contradicting_id == str(B.id)
    assert result.filed == 0
    assert router.calls == []


async def test_apply_files_dissent_against_target_citing_other() -> None:
    router = ToolRouter({"dissent_propose": tool_ok(DISSENT_OUT)})
    chain = chain_replying(
        verdict(
            contradicts=True,
            reason="one service cannot run on two hosts",
            target="b",
            proposed_payload={"host": "kubs0", "service": "klams"},
        )
    )

    result = await detect_contradictions(
        [PAIR], chain, client_for(router), query="q", apply=True, author_id="author-1"
    )

    (jp,) = result.judged
    assert jp.status == "filed"
    assert result.filed == 1
    # client parses the dash-less wire id to a canonical UUID string
    assert jp.dissent_id == "01980000-0000-7000-8000-000000000cd0"
    name, args = router.calls[-1]
    assert name == "dissent_propose"
    assert args["fact_id"] == str(B.id)  # target = b
    assert args["contradicting_memory_id"] == str(A.id)
    assert args["proposed_payload"] == {"host": "kubs0", "service": "klams"}
    assert args["author_id"] == "author-1"


async def test_claimed_contradiction_without_correction_is_unactionable() -> None:
    router = ToolRouter({})
    # contradicts=True but no target/payload → refused, never filed.
    chain = chain_replying(verdict(contradicts=True, reason="they feel wrong somehow"))

    result = await detect_contradictions(
        [PAIR], chain, client_for(router), query="q", apply=True, author_id="a1"
    )

    (jp,) = result.judged
    assert jp.status == "unactionable"
    assert result.filed == 0
    assert router.calls == []


async def test_empty_payload_or_reason_is_unactionable() -> None:
    router = ToolRouter({})
    chain = chain_replying(
        verdict(contradicts=True, reason="", target="a", proposed_payload={"host": "kai"}),
        verdict(contradicts=True, reason="ok", target="a", proposed_payload={}),
    )
    p2 = CandidatePair(a=A, b=as_fact(make_fact("c0", {"host": "cleo", "service": "klams"})))

    result = await detect_contradictions(
        [PAIR, p2], chain, client_for(router), query="q", apply=True, author_id="a1"
    )

    assert [jp.status for jp in result.judged] == ["unactionable", "unactionable"]
    assert result.filed == 0


async def test_judge_parse_failure_recorded_and_run_continues() -> None:
    router = ToolRouter({})
    chain = chain_replying(
        "not a verdict at all",
        verdict(contradicts=False, reason="fine"),
    )
    p2 = CandidatePair(a=A, b=as_fact(make_fact("c0", {"host": "cleo", "service": "klams"})))

    result = await detect_contradictions([PAIR, p2], chain, client_for(router), query="q")

    assert len(result.judge_failures) == 1
    assert "pair 1" in result.judge_failures[0]
    assert [jp.status for jp in result.judged] == ["clear"]


async def test_apply_requires_author_id() -> None:
    chain = chain_replying(verdict(contradicts=False, reason="x"))
    with pytest.raises(ValueError, match="author_id"):
        await detect_contradictions(
            [PAIR], chain, client_for(ToolRouter({})), query="q", apply=True
        )
