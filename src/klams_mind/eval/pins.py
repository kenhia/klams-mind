"""Re-resolve the suite's `memory_id` pins against the live corpus.

The second half of klams-mind #2247. `evaluate_check` now follows a
supersession chain, so a dated pin no longer *fails* — but it is no less
dated for that, and a suite whose text names records nobody can find has
quietly stopped documenting what it measures. This module is the
maintenance side: run each query once, ask of every pin whether it still
names a live record, and report the drift.

It is deliberately not part of `just gate`. Drift is a fact about the
corpus, which lives on kubs0 behind the tailnet and changes without any
commit here — exactly the thing a hosted runner cannot see and a red
gate would misattribute.

Three states, and the distinction between the first two is the point:

- `current`    — a hit's own id matches the pin. Nothing to do.
- `superseded` — the pin's record is gone from search, but a descendant
                 surfaced. The check passes; the pin should be rewritten
                 to name the live head.
- `absent`     — no hit on this query witnesses the pin at all. Either
                 the lineage left the page, or the pin was never right.

Ranking is reported separately (`within_rank`) and is NOT drift. A live
pin that has lost its slot is a retrieval regression, and folding it in
here is how a suite ends up re-pinning to hide one.
"""

import json
from dataclasses import dataclass, field
from typing import Literal

from klams_mind.eval.checks import RetrievedItem
from klams_mind.eval.runner import Retriever
from klams_mind.eval.suite import Suite

PinState = Literal["current", "superseded", "absent"]


@dataclass(frozen=True)
class PinResolution:
    """What one `memory_id` pin resolves to right now."""

    query: str
    pin: str
    state: PinState
    max_rank: int | None = None
    # Where the witness landed, and which record it was. None when absent.
    rank: int | None = None
    live_id: str | None = None
    # The lineage between the pin and the live record, nearest first.
    # Empty unless `state == "superseded"`.
    chain: tuple[str, ...] = ()
    # Whether the witness satisfied `max_rank`. True when none is set.
    within_rank: bool = True

    @property
    def is_drift(self) -> bool:
        """Whether the PIN needs rewriting — not whether the check passed."""
        return self.state != "current"


@dataclass
class _Page:
    hits: list[RetrievedItem] = field(default_factory=list)


async def resolve_pins(suite: Suite, retriever: Retriever) -> list[PinResolution]:
    """Resolve every `memory_id` pin in `suite`, one search per query."""
    rows: list[PinResolution] = []
    for q in suite.queries:
        pins = [c for c in q.checks if c.type == "memory_id" and c.value]
        if not pins:
            continue
        hits = await retriever.search(q.query, q.top_k)
        for check in pins:
            assert check.value is not None  # filtered above; narrows for `ty`
            rows.append(_resolve_one(q.query, check.value, check.max_rank, hits))
    return rows


def _resolve_one(
    query: str, pin: str, max_rank: int | None, hits: list[RetrievedItem]
) -> PinResolution:
    wanted = pin.lower()
    for rank, h in enumerate(hits):
        if h.memory_id.lower().startswith(wanted):
            return PinResolution(
                query=query,
                pin=pin,
                state="current",
                max_rank=max_rank,
                rank=rank,
                live_id=h.memory_id,
                within_rank=max_rank is None or rank <= max_rank,
            )
    for rank, h in enumerate(hits):
        if any(anc.lower().startswith(wanted) for anc in h.ancestry):
            return PinResolution(
                query=query,
                pin=pin,
                state="superseded",
                max_rank=max_rank,
                rank=rank,
                live_id=h.memory_id,
                chain=h.ancestry,
                within_rank=max_rank is None or rank <= max_rank,
            )
    return PinResolution(query=query, pin=pin, state="absent", max_rank=max_rank)


def drifted(rows: list[PinResolution]) -> int:
    return sum(1 for r in rows if r.is_drift)


def outranked(rows: list[PinResolution]) -> int:
    return sum(1 for r in rows if not r.within_rank)


def to_markdown(rows: list[PinResolution]) -> str:
    """A report a maintainer can act on without opening the suite."""
    n = len(rows)
    lines = [
        "# eval pin refresh",
        "",
        f"**{drifted(rows)} of {n} pin(s) have drifted.** "
        f"{outranked(rows)} witness(es) fell outside `max_rank`.",
        "",
        "| query | pin | state | live id | rank |",
        "| --- | --- | --- | --- | --- |",
    ]
    for r in rows:
        rank = "—" if r.rank is None else str(r.rank)
        if not r.within_rank:
            rank += f" (> max_rank {r.max_rank})"
        lines.append(
            f"| {_trim(r.query, 40)} | `{r.pin}` | {r.state} | `{r.live_id or '—'}` | {rank} |"
        )
    stale = [r for r in rows if r.state == "superseded"]
    if stale:
        lines += [
            "",
            "## Pins whose record is no longer live",
            "",
            "These checks still **pass** — `memory_id` follows the chain — so "
            "this is a legibility call, not a repair. Keeping the pin names "
            "the lineage stably through every future supersession; repointing "
            "it to the live head names a record a reader can actually fetch. "
            "Prefer keeping it, and let this report be how the lineage is read.",
            "",
        ]
        for r in stale:
            trail = " → ".join([*reversed(r.chain), r.live_id or "?"])
            lines.append(f"- `{r.pin}` — superseded; lineage `{trail}`")
            lines.append(f"  - live head `{r.live_id}` (query: {_trim(r.query, 60)})")
    missing = [r for r in rows if r.state == "absent"]
    if missing:
        lines += [
            "",
            "## Pins with no witness",
            "",
            "Neither the record nor any descendant surfaced. Re-check the "
            "query before repointing — an absent pin can mean the lineage "
            "left the page rather than that it moved.",
            "",
        ]
        for r in missing:
            lines.append(f"- `{r.pin}` — query: {_trim(r.query, 60)}")
    return "\n".join(lines) + "\n"


def to_json(rows: list[PinResolution]) -> str:
    return json.dumps(
        {
            "pins": len(rows),
            "drifted": drifted(rows),
            "outranked": outranked(rows),
            "rows": [
                {
                    "query": r.query,
                    "pin": r.pin,
                    "state": r.state,
                    "rank": r.rank,
                    "max_rank": r.max_rank,
                    "live_id": r.live_id,
                    "chain": list(r.chain),
                    "within_rank": r.within_rank,
                }
                for r in rows
            ],
        },
        indent=2,
    )


def _trim(text: str, width: int) -> str:
    return text if len(text) <= width else text[: width - 1] + "…"
