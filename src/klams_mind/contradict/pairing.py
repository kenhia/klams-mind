"""Candidate pairing: turn a working set of facts into the pairs worth
judging, using klams' own similarity search as the bucketer.

The corpus is never compared O(n^2). For each seed fact we ask klams
for its nearest fact-neighbours (one `memory_search`, kind `fact`) and
pair the seed with each — so work is bounded at
`len(seeds) x neighbours`. Pairs are unordered and de-duplicated by the
two fact ids, and ordered within a pair by id so the output is
deterministic regardless of which seed surfaced the pair.
"""

import json
from dataclasses import dataclass

from klams_mind.klams import FactMemory, KlamsClient


def fact_text(fact: FactMemory) -> str:
    """Render a fact as a stable string for search queries and the judge.

    Payload keys are sorted so two facts with the same content but
    different key order render identically (and hit the same search).
    """
    payload = json.dumps(fact.payload, sort_keys=True, ensure_ascii=False)
    return f"{fact.type}: {payload}"


@dataclass(frozen=True)
class CandidatePair:
    a: FactMemory
    b: FactMemory


async def find_candidate_pairs(
    client: KlamsClient,
    seeds: list[FactMemory],
    *,
    neighbours: int = 5,
) -> list[CandidatePair]:
    """Pair each seed fact with its fact-neighbours from klams search."""
    pairs: dict[frozenset[str], CandidatePair] = {}
    for seed in seeds:
        # +1 so the seed itself (usually its own top hit) doesn't cost a slot.
        hits = await client.memory_search(fact_text(seed), kinds=["fact"], top_k=neighbours + 1)
        for hit in hits:
            other = hit.memory
            if not isinstance(other, FactMemory) or other.id == seed.id:
                continue
            key = frozenset({str(seed.id), str(other.id)})
            if key in pairs:
                continue
            lo, hi = sorted((seed, other), key=lambda f: str(f.id))
            pairs[key] = CandidatePair(a=lo, b=hi)
    return list(pairs.values())
