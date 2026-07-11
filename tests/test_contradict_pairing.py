"""Candidate pairing: similarity buckets from klams search, no O(n^2)."""

import json
from typing import Any

from mcp.types import CallToolResult, TextContent

from klams_mind.config import KlamsConfig
from klams_mind.contradict.pairing import fact_text, find_candidate_pairs
from klams_mind.klams import FactMemory, KlamsClient
from tests.test_klams_client import FACT_MEMORY, KNOWLEDGE_MEMORY, scored


def make_fact(suffix: str, payload: dict[str, Any], fact_type: str = "EnvFact") -> dict[str, Any]:
    return {
        **FACT_MEMORY,
        "id": f"01980000-0000-7000-8000-0000000000{suffix}",
        "type": fact_type,
        "payload": payload,
    }


class SearchRouter:
    """Fakes memory_search, returning per-query canned scored hits."""

    def __init__(self, by_query: dict[str, list[dict[str, Any]]]) -> None:
        self.by_query = by_query
        self.queries: list[str] = []

    async def __call__(self, name: str, args: dict[str, Any]) -> CallToolResult:
        assert name == "memory_search"
        self.queries.append(args["query"])
        hits = self.by_query.get(args["query"], [])
        return CallToolResult(content=[TextContent(type="text", text=json.dumps(hits))])


def client_for(router: SearchRouter) -> KlamsClient:
    return KlamsClient(KlamsConfig(), tool_caller=router)


def as_fact(d: dict[str, Any]) -> FactMemory:
    return FactMemory.model_validate(d)


def test_fact_text_is_stable_and_carries_type_and_payload() -> None:
    f = as_fact(make_fact("a0", {"service": "klams", "host": "kubs0"}))
    text = fact_text(f)
    assert "EnvFact" in text
    assert "kubs0" in text and "klams" in text
    # key order does not affect the rendered text
    g = as_fact(make_fact("a1", {"host": "kubs0", "service": "klams"}))
    assert fact_text(f).split(":", 1)[1] == fact_text(g).split(":", 1)[1]


async def test_pairs_a_seed_fact_with_its_neighbours() -> None:
    a = make_fact("a0", {"host": "kubs0", "service": "klams"})
    b = make_fact("b0", {"host": "kai", "service": "klams"})
    seed = as_fact(a)
    router = SearchRouter({fact_text(seed): [scored(a), scored(b)]})

    pairs = await find_candidate_pairs(client_for(router), [seed], neighbours=5)

    assert len(pairs) == 1
    ids = {str(pairs[0].a.id), str(pairs[0].b.id)}
    assert ids == {a["id"], b["id"]}


async def test_excludes_self_and_dedupes_unordered_pairs() -> None:
    a = make_fact("a0", {"host": "kubs0", "service": "klams"})
    b = make_fact("b0", {"host": "kai", "service": "klams"})
    fa, fb = as_fact(a), as_fact(b)
    # both seeds surface each other as a neighbour (plus themselves)
    router = SearchRouter(
        {
            fact_text(fa): [scored(a), scored(b)],
            fact_text(fb): [scored(b), scored(a)],
        }
    )

    pairs = await find_candidate_pairs(client_for(router), [fa, fb], neighbours=5)

    assert len(pairs) == 1  # (a,b) not double-counted, no (a,a)


async def test_ignores_non_fact_hits() -> None:
    a = make_fact("a0", {"host": "kubs0", "service": "klams"})
    seed = as_fact(a)
    router = SearchRouter({fact_text(seed): [scored(a), scored(KNOWLEDGE_MEMORY)]})

    pairs = await find_candidate_pairs(client_for(router), [seed], neighbours=5)

    assert pairs == []  # only a knowledge neighbour → nothing to pair with


async def test_bounds_search_calls_to_one_per_seed() -> None:
    seeds = [as_fact(make_fact(f"{i:02x}", {"host": f"h{i}", "service": "s"})) for i in range(4)]
    router = SearchRouter({})
    await find_candidate_pairs(client_for(router), seeds, neighbours=3)
    assert len(router.queries) == 4
