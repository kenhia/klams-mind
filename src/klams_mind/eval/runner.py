"""Run a suite against a retrieval backend, collecting per-query results.

The runner depends only on a small `Retriever` protocol
(`search(query, top_k) -> list[RetrievedItem]`), so it's exercised with a
fake in tests. `KlamsRetriever` is the concrete adapter over the sprint-001
`KlamsClient`, mapping klams scored hits (klams-016 `{score, source_rank,
memory}` envelopes) to the backend-neutral `RetrievedItem` the checks
consume; score metadata rides along for the report.
"""

import json
from dataclasses import dataclass, field
from typing import Protocol

from klams_mind.config import KlamsConfig
from klams_mind.eval.checks import CheckResult, RetrievedItem, evaluate_check
from klams_mind.eval.suite import Suite
from klams_mind.klams import KlamsClient, ScoredMemory


def eval_klams_config(klams: KlamsConfig) -> tuple[KlamsConfig, bool]:
    """The klams config an eval run should use, and whether it is distinct.

    klams-mind #735: `search_sample`'s `caller` is the caller's klams
    identity, so declaring a second, eval-scoped one is the only way a
    client can make its eval traffic distinguishable — `register_author`
    does not touch it. Sprint 010 (korg:2423) made that identity a
    declared `X-Homelab-Agent` name matched against a read-scoped
    `[[auth.identities]]` row, so the swap is a name, not a token.

    Returns `(config, distinct)`; `distinct=False` means the run will
    land in `search_sample` indistinguishable from real agent queries,
    and mining it will feed the suite its own golden queries.

    Falling back is deliberate rather than fatal: an eval that refuses to
    run measures nothing, which is worse than an eval whose rows need a
    date bracket to mine.
    """
    if klams.eval_agent_name and klams.eval_agent_name != klams.agent_name:
        return klams.model_copy(update={"agent_name": klams.eval_agent_name}), True
    return klams.model_copy(), False


class Retriever(Protocol):
    async def search(self, query: str, top_k: int) -> list[RetrievedItem]: ...


@dataclass
class EvalQueryResult:
    query: str
    hit_count: int
    sources: list[str]
    checks: list[CheckResult]
    passed: bool
    hits: list[RetrievedItem] = field(default_factory=list)
    # klams sprint 026 (#643) — see `EvalQuery.expect`.
    expect: str = "pass"
    tracking: str | None = None

    @property
    def is_regression(self) -> bool:
        """A query that was supposed to pass and didn't. Fails the run."""
        return self.expect == "pass" and not self.passed

    @property
    def is_newly_fixed(self) -> bool:
        """A `known_open` query that now passes — the fix landed.

        Not a failure, but it must be surfaced: leaving it marked open
        means the next regression in it goes unnoticed.
        """
        return self.expect == "known_open" and self.passed


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
                hits=hits,
                expect=q.expect,
                tracking=q.tracking,
            )
        )
    return results


def _to_item(sm: ScoredMemory, ancestry: tuple[str, ...] = ()) -> RetrievedItem:
    """Flatten a klams scored hit into what a retrieval check inspects."""
    m = sm.memory
    if m.kind == "knowledge":
        return RetrievedItem(
            content=m.text,
            source=m.source_path or "",
            tags=list(m.tags),
            kind=m.kind,
            score=sm.score,
            source_rank=sm.source_rank,
            memory_id=str(m.id),
            content_hash=m.content_hash,
            heading_path=m.heading_path,
            raw_score=sm.raw_score,
            ancestry=ancestry,
        )
    if m.kind == "fact":
        return RetrievedItem(
            content=f"{m.type} {json.dumps(m.payload)}",
            source=f"fact:{m.type}",
            tags=list(m.tags),
            kind=m.kind,
            score=sm.score,
            source_rank=sm.source_rank,
            memory_id=str(m.id),
            raw_score=sm.raw_score,
            ancestry=ancestry,
        )
    return RetrievedItem(
        content=f"{m.category} {json.dumps(m.payload)}",
        source=f"event:{m.category}",
        tags=list(m.tags),
        kind=m.kind,
        score=sm.score,
        source_rank=sm.source_rank,
        memory_id=str(m.id),
        raw_score=sm.raw_score,
        ancestry=ancestry,
    )


# A lineage deeper than this is a runaway, not a history. klams' longest
# real chain at the time of writing is three records; the cap exists so a
# corrupted link cannot turn one eval query into unbounded round trips.
MAX_LINEAGE_DEPTH = 32


class KlamsRetriever:
    """Adapter over `KlamsClient`, resolving each hit's supersession lineage.

    The ancestry walk lives here rather than in the checks because
    `evaluate_check` is a pure function of the page and is worth keeping
    that way — and because the resolution is per-record, so a cache makes
    it nearly free across a suite. Ancestors are cached for the
    retriever's lifetime: a memory's `supersedes` link is immutable once
    written, so there is nothing to invalidate within a run.
    """

    def __init__(self, client: KlamsClient) -> None:
        self._client = client
        # memory id -> the id it superseded (None = end of the chain).
        self._parent: dict[str, str | None] = {}

    async def search(self, query: str, top_k: int) -> list[RetrievedItem]:
        hits = await self._client.memory_search_full(query, top_k=top_k)
        return [_to_item(h, await self._ancestry(h)) for h in hits]

    async def _ancestry(self, sm: ScoredMemory) -> tuple[str, ...]:
        """Ids this hit has superseded, transitively, nearest first.

        Walks backward from the hit's own `supersedes`, because that is
        the direction klams gives us for free: `supersedes` rides on the
        search hit, so an ordinary hit — which is almost all of them —
        costs no extra call at all.
        """
        chain: list[str] = []
        seen = {str(sm.memory.id)}
        parent = sm.memory.supersedes
        current = str(parent) if parent is not None else None
        while current is not None and len(chain) < MAX_LINEAGE_DEPTH:
            if current in seen:
                break  # a cycle klams should not produce; refuse to spin on it
            seen.add(current)
            chain.append(current)
            current = await self._parent_of(current)
        return tuple(chain)

    async def _parent_of(self, memory_id: str) -> str | None:
        """One hop back, cached. A record klams will not serve ends the walk.

        Defensive at the boundary on purpose: a superseded ancestor can
        be hard-deleted or fall outside this identity's read scope, and
        an eval that dies on that measures nothing — which is strictly
        worse than one that measures a shorter lineage.
        """
        if memory_id in self._parent:
            return self._parent[memory_id]
        try:
            memory = await self._client.memory_get(memory_id)
        except Exception:
            self._parent[memory_id] = None
            return None
        parent = memory.supersedes
        resolved = str(parent) if parent is not None else None
        self._parent[memory_id] = resolved
        return resolved
