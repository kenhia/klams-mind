"""Run a suite against a retrieval backend, collecting per-query results.

The runner depends only on a small `Retriever` protocol
(`search(query, top_k) -> list[RetrievedItem]`), so it's exercised with a
fake in tests. `KlamsRetriever` is the concrete adapter over the sprint-001
`KlamsClient`, mapping klams memories to the backend-neutral `RetrievedItem`
the checks consume.
"""

import json
from dataclasses import dataclass
from typing import Protocol

from klams_mind.eval.checks import CheckResult, RetrievedItem, evaluate_check
from klams_mind.eval.suite import Suite
from klams_mind.klams import KlamsClient, Memory


class Retriever(Protocol):
    async def search(self, query: str, top_k: int) -> list[RetrievedItem]: ...


@dataclass
class EvalQueryResult:
    query: str
    hit_count: int
    sources: list[str]
    checks: list[CheckResult]
    passed: bool


async def run_suite(suite: Suite, retriever: Retriever) -> list[EvalQueryResult]:
    results: list[EvalQueryResult] = []
    for q in suite.queries:
        hits = await retriever.search(q.query, q.top_k)
        checks = [evaluate_check(c, hits) for c in q.checks]
        results.append(
            EvalQueryResult(
                query=q.query,
                hit_count=len(hits),
                sources=[h.source for h in hits],
                checks=checks,
                passed=all(cr.passed for cr in checks),
            )
        )
    return results


def _to_item(m: Memory) -> RetrievedItem:
    """Flatten a klams memory into what a retrieval check inspects."""
    if m.kind == "knowledge":
        return RetrievedItem(m.text, m.source_path or "", list(m.tags))
    if m.kind == "fact":
        return RetrievedItem(
            content=f"{m.type} {json.dumps(m.payload)}",
            source=f"fact:{m.type}",
            tags=list(m.tags),
        )
    return RetrievedItem(
        content=f"{m.category} {json.dumps(m.payload)}",
        source=f"event:{m.category}",
        tags=list(m.tags),
    )


class KlamsRetriever:
    def __init__(self, client: KlamsClient) -> None:
        self._client = client

    async def search(self, query: str, top_k: int) -> list[RetrievedItem]:
        hits = await self._client.memory_search(query, top_k=top_k)
        return [_to_item(h) for h in hits]
