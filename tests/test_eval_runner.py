"""Runner aggregation + the klams retrieval adapter."""

import json

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

    assert caller.calls[0] == ("memory_search", {"query": "kvllm", "top_k": 5})
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
