"""Runner aggregation + the klams retrieval adapter."""

import json
from typing import Literal

from mcp.types import CallToolResult, TextContent

from klams_mind.config import KlamsConfig
from klams_mind.eval.checks import RetrievedItem
from klams_mind.eval.runner import KlamsRetriever, run_suite
from klams_mind.eval.suite import Check, EvalQuery, Suite
from klams_mind.klams import KlamsClient


class FakeRetriever:
    """Returns canned hits regardless of query; records calls."""

    def __init__(self, hits: list[RetrievedItem]) -> None:
        self.hits = hits
        self.calls: list[tuple[str, int]] = []

    async def search(self, query: str, top_k: int) -> list[RetrievedItem]:
        self.calls.append((query, top_k))
        return self.hits


def suite_with(*checks: Check, top_k: int = 4) -> Suite:
    return Suite(
        name="t",
        queries=[EvalQuery(query="q", top_k=top_k, checks=list(checks))],
    )


async def test_run_suite_passes_when_all_checks_pass() -> None:
    hits = [RetrievedItem(content="image: klams", source="a/docker-compose.yml")]
    retr = FakeRetriever(hits)

    results = await run_suite(
        suite_with(
            Check(type="substring", value="image: klams"),
            Check(type="source_cited", value="docker-compose.yml"),
        ),
        retr,
    )

    assert retr.calls == [("q", 4)]  # top_k threaded through
    assert len(results) == 1
    r = results[0]
    assert r.passed
    assert r.hit_count == 1
    assert r.sources == ["a/docker-compose.yml"]


async def test_run_suite_fails_when_any_check_fails() -> None:
    hits = [RetrievedItem(content="image: klams", source="a/docker-compose.yml")]
    results = await run_suite(
        suite_with(
            Check(type="substring", value="image: klams"),
            Check(type="substring", value="not present"),
        ),
        FakeRetriever(hits),
    )
    assert not results[0].passed
    assert [c.passed for c in results[0].checks] == [True, False]


# --- adapter: klams Memory -> RetrievedItem --------------------------------


def tool_ok(payload: object) -> CallToolResult:
    return CallToolResult(content=[TextContent(type="text", text=json.dumps(payload))])


class FakeCaller:
    def __init__(self, result: CallToolResult) -> None:
        self.result = result
        self.calls: list[tuple[str, dict]] = []

    async def __call__(self, name: str, args: dict) -> CallToolResult:
        self.calls.append((name, args))
        return self.result


KNOWLEDGE = {
    "id": "01980000-0000-7000-8000-00000000000b",
    "kind": "knowledge",
    "text": "kvllm serves models on kai:8000",
    "source_path": "/home/ken/src/ai/kvllm/README.md",
    "tags": ["homelab"],
    "author": {"agent_name": "system"},
    "created_at": "2026-07-02T00:00:00Z",
    "updated_at": "2026-07-02T00:00:00Z",
}
FACT = {
    "id": "01980000-0000-7000-8000-00000000000a",
    "kind": "fact",
    "type": "EnvFact",
    "payload": {"host": "kubs0", "service": "klams"},
    "tags": [],
    "author": {"agent_name": "system"},
    "created_at": "2026-07-01T00:00:00Z",
    "updated_at": "2026-07-01T00:00:00Z",
}


async def test_klams_retriever_maps_scored_knowledge_and_fact() -> None:
    envelopes = [
        {"score": 0.71, "source_rank": 0, "memory": KNOWLEDGE},
        {"score": 0.04, "source_rank": 2, "memory": FACT},
    ]
    caller = FakeCaller(tool_ok(envelopes))
    client = KlamsClient(KlamsConfig(), tool_caller=caller)
    retr = KlamsRetriever(client)

    items = await retr.search("kvllm", top_k=5)

    # klams 046: the eval harness is the documented `full` caller — checks
    # assert on bodies, and a 320-char snippet is not a body.
    assert caller.calls[0] == (
        "memory_search",
        {"query": "kvllm", "top_k": 5, "full": True},
    )
    know, fact = items
    assert know.content == "kvllm serves models on kai:8000"
    assert know.source == "/home/ken/src/ai/kvllm/README.md"
    assert know.tags == ["homelab"]
    # scored-envelope metadata rides along for the report.
    assert (know.kind, know.score, know.source_rank) == ("knowledge", 0.71, 0)
    # fact payload is searchable content; source carries the fact type.
    assert "kubs0" in fact.content and "EnvFact" in fact.source
    assert (fact.kind, fact.score, fact.source_rank) == ("fact", 0.04, 2)


async def test_run_suite_carries_hits_into_result() -> None:
    hits = [RetrievedItem(content="x", source="s", kind="knowledge", score=0.5, source_rank=0)]
    results = await run_suite(suite_with(Check(type="substring", value="x")), FakeRetriever(hits))
    assert results[0].hits == hits


# --- klams sprint 026 (#643): expect / known_open gating -------------------
#
# Without this, a measurement suite can only contain queries that already
# pass — which is exactly how the original four scored 4/4 while klams#628
# was live. `known_open` lets a real failure stay IN the suite, tracked,
# without leaving the gate permanently red.


def _suite(
    expect: Literal["pass", "known_open"], check: Check, tracking: str | None = None
) -> Suite:
    return Suite(
        name="t",
        queries=[EvalQuery(query="q", top_k=4, checks=[check], expect=expect, tracking=tracking)],
    )


async def test_a_failing_known_open_query_is_not_a_regression() -> None:
    retr = FakeRetriever([RetrievedItem(content="unrelated", source="x")])
    results = await run_suite(
        _suite("known_open", Check(type="substring", value="absent"), "klams#628"),
        retr,
    )
    r = results[0]
    assert not r.passed
    assert not r.is_regression
    assert r.tracking == "klams#628"


async def test_a_failing_expected_pass_query_is_a_regression() -> None:
    retr = FakeRetriever([RetrievedItem(content="unrelated", source="x")])
    results = await run_suite(_suite("pass", Check(type="substring", value="absent")), retr)
    assert results[0].is_regression


async def test_a_passing_known_open_query_is_flagged_newly_fixed() -> None:
    # The fix landed. This must be visible, or the query stays marked
    # open forever and the next regression in it goes unnoticed.
    retr = FakeRetriever([RetrievedItem(content="present", source="x")])
    results = await run_suite(_suite("known_open", Check(type="substring", value="present")), retr)
    r = results[0]
    assert r.passed
    assert r.is_newly_fixed
    assert not r.is_regression


async def test_queries_default_to_expect_pass() -> None:
    # A suite author who writes nothing gets the strict bar.
    assert EvalQuery(query="q").expect == "pass"


# --- supersession lineage (WI 2247, sprint 012) ----------------------------
#
# klams returns `supersedes` on a hit (backward: "I replaced X") in both
# envelopes, and `memory_get` on a superseded record still resolves — so
# the whole lineage is reachable by walking backward from each hit. The
# retriever does that walk once, so `evaluate_check` stays pure.


class ScriptedCaller:
    """Answers each tool call from a per-tool script, recording calls."""

    def __init__(self, search: object, gets: dict[str, object]) -> None:
        self.search = search
        self.gets = gets
        self.calls: list[tuple[str, dict]] = []

    async def __call__(self, name: str, args: dict) -> CallToolResult:
        self.calls.append((name, args))
        if name == "memory_search":
            return tool_ok(self.search)
        payload = self.gets.get(str(args["id"]))
        if payload is None:
            return CallToolResult(
                isError=True,
                content=[TextContent(type="text", text="not found")],
            )
        return tool_ok(payload)


def knowledge(mid: str, *, supersedes: str | None = None, text: str = "note") -> dict:
    m = dict(KNOWLEDGE) | {"id": mid, "text": text}
    if supersedes is not None:
        m["supersedes"] = supersedes
    return m


HEAD = "019fb6b1-1c9a-7850-9822-79ef941025f2"
MID = "019fb1c9-7c16-7513-9ad4-f067611afbf1"
ROOT = "019fa04a-ceac-7253-9420-ea3a39cd0ef2"
SIBLING = "019fb6b1-9999-7850-9822-79ef941025f2"


async def test_retriever_walks_the_supersedes_chain_into_ancestry() -> None:
    caller = ScriptedCaller(
        search=[{"score": 0.9, "source_rank": 0, "memory": knowledge(HEAD, supersedes=MID)}],
        gets={MID: knowledge(MID, supersedes=ROOT), ROOT: knowledge(ROOT)},
    )
    retr = KlamsRetriever(KlamsClient(KlamsConfig(), tool_caller=caller))

    (item,) = await retr.search("q", top_k=5)

    assert item.memory_id == HEAD
    # Nearest ancestor first — the pin may name any depth of the chain.
    assert item.ancestry == (MID, ROOT)
    assert [c[0] for c in caller.calls] == ["memory_search", "memory_get", "memory_get"]


async def test_retriever_leaves_ancestry_empty_for_an_ordinary_hit() -> None:
    # The common case by a wide margin: one search, no extra round trips.
    caller = ScriptedCaller(
        search=[{"score": 0.9, "source_rank": 0, "memory": knowledge(HEAD)}], gets={}
    )
    retr = KlamsRetriever(KlamsClient(KlamsConfig(), tool_caller=caller))

    (item,) = await retr.search("q", top_k=5)

    assert item.ancestry == ()
    assert [c[0] for c in caller.calls] == ["memory_search"]


async def test_retriever_stops_at_an_unreadable_ancestor_without_failing() -> None:
    # A boundary, so it is defensive by design: an ancestor klams will
    # not serve truncates the lineage. An eval that dies here measures
    # nothing, which is strictly worse than one that measures less.
    caller = ScriptedCaller(
        search=[{"score": 0.9, "source_rank": 0, "memory": knowledge(HEAD, supersedes=MID)}],
        gets={},
    )
    retr = KlamsRetriever(KlamsClient(KlamsConfig(), tool_caller=caller))

    (item,) = await retr.search("q", top_k=5)

    assert item.ancestry == (MID,)


async def test_retriever_does_not_loop_on_a_cyclic_chain() -> None:
    caller = ScriptedCaller(
        search=[{"score": 0.9, "source_rank": 0, "memory": knowledge(HEAD, supersedes=MID)}],
        gets={MID: knowledge(MID, supersedes=HEAD)},
    )
    retr = KlamsRetriever(KlamsClient(KlamsConfig(), tool_caller=caller))

    (item,) = await retr.search("q", top_k=5)

    assert item.ancestry == (MID,)


async def test_retriever_resolves_each_ancestor_once_across_hits() -> None:
    # Two hits sharing a lineage must not pay for it twice.
    caller = ScriptedCaller(
        search=[
            {"score": 0.9, "source_rank": 0, "memory": knowledge(HEAD, supersedes=MID)},
            {"score": 0.8, "source_rank": 1, "memory": knowledge(SIBLING, supersedes=MID)},
        ],
        gets={MID: knowledge(MID, supersedes=ROOT), ROOT: knowledge(ROOT)},
    )
    retr = KlamsRetriever(KlamsClient(KlamsConfig(), tool_caller=caller))

    items = await retr.search("q", top_k=5)

    assert [i.ancestry for i in items] == [(MID, ROOT), (MID, ROOT)]
    assert [c[0] for c in caller.calls].count("memory_get") == 2
