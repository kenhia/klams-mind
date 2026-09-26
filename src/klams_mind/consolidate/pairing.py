"""Curate the corpus to what consolidation may touch, then pair near-duplicates
through klams' own similarity search.

Curation keeps **agent-authored knowledge** only (no `source_path`).
klams already collapses exact duplicates (same `content_hash`) at write
and query time, and measured on 2026-09-25 the agent-authored set had
none left; scanner chunks are derived from files a rescan would restore,
and `memory_supersede` refuses them anyway. What remains unhandled is the
semantic near-duplicate — see sprints/013-consolidation-propose.

`GET /v1/memories` carries no vectors, so similarity comes from one
`memory_search` per curated memory, seeded with its own text. The search
must be deep: 99.8% of the corpus is scanner chunks competing for the
same top-k slots.
"""

from collections.abc import Iterable
from dataclasses import dataclass

from klams_mind.klams import KlamsClient, KnowledgeMemory, Memory

# klams rejects a `memory_search` query over 1,024 characters
# (SCHEMA_VALIDATION_FAILED); the median agent memory is ~1,580.
QUERY_MAX = 1000

# klams' own `SIMILAR_ON_WRITE_THRESHOLD` (memory_add's `similar_existing`),
# so "near-duplicate" means the same thing on both sides of the boundary.
DEFAULT_THRESHOLD = 0.85


def curated(memories: Iterable[Memory]) -> list[KnowledgeMemory]:
    """The memories consolidation may propose changes to."""
    return [m for m in memories if isinstance(m, KnowledgeMemory) and m.source_path is None]


@dataclass(frozen=True)
class CandidatePair:
    a: KnowledgeMemory
    b: KnowledgeMemory
    score: float  # raw cosine from klams, the higher of the two directions


async def find_near_duplicates(
    client: KlamsClient,
    memories: list[KnowledgeMemory],
    *,
    threshold: float = DEFAULT_THRESHOLD,
    top_k: int = 30,
) -> list[CandidatePair]:
    """Pair each curated memory with curated neighbours at cosine ≥ threshold.

    Pairs are unordered and ordered within by id; the result is sorted
    best-first (score descending, then ids) so a capped judge sees the
    likeliest merges.
    """
    by_id = {m.id: m for m in memories}
    best: dict[frozenset, float] = {}
    for seed in memories:
        hits = await client.memory_search_full(
            seed.text[:QUERY_MAX], kinds=["knowledge"], top_k=top_k
        )
        for hit in hits:
            other = by_id.get(hit.memory.id)
            if other is None or other.id == seed.id or hit.raw_score is None:
                continue
            if hit.raw_score < threshold:
                continue
            key = frozenset({seed.id, other.id})
            best[key] = max(best.get(key, 0.0), hit.raw_score)
    pairs = []
    for key, score in best.items():
        lo, hi = sorted((by_id[i] for i in key), key=lambda m: str(m.id))
        pairs.append(CandidatePair(lo, hi, score))
    pairs.sort(key=lambda p: (-p.score, str(p.a.id), str(p.b.id)))
    return pairs
