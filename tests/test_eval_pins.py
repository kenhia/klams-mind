"""The pin-refresh recipe: re-resolve every `memory_id` pin, report drift.

WI 2247's second half. Following the supersedes chain stops a dated pin
from *failing*, but it does not make the pin any less dated — the suite
would quietly measure a lineage while its text still named a record
nobody can find. This is the maintenance side: run the suite's own
queries, say for each pin whether it still names a live record, and make
the drift cheap to see rather than something a red gate discovers months
later.
"""

import json

from klams_mind.eval.checks import RetrievedItem
from klams_mind.eval.pins import (
    drifted,
    resolve_pins,
    to_json,
    to_markdown,
)
from klams_mind.eval.suite import Check, EvalQuery, Suite


class QueryKeyedRetriever:
    """Canned hits per query, so a multi-query suite can be exercised."""

    def __init__(self, pages: dict[str, list[RetrievedItem]]) -> None:
        self.pages = pages

    async def search(self, query: str, top_k: int) -> list[RetrievedItem]:
        return self.pages.get(query, [])[:top_k]


def hit(memory_id: str, ancestry: tuple[str, ...] = ()) -> RetrievedItem:
    return RetrievedItem(
        content="body", source="/s.md", kind="knowledge", memory_id=memory_id, ancestry=ancestry
    )


def suite_of(*queries: EvalQuery) -> Suite:
    return Suite(name="t", queries=list(queries))


def pinned(query: str, value: str, max_rank: int | None = None) -> EvalQuery:
    return EvalQuery(
        query=query, top_k=5, checks=[Check(type="memory_id", value=value, max_rank=max_rank)]
    )


async def test_a_pin_that_still_names_a_live_record_is_current() -> None:
    rows = await resolve_pins(
        suite_of(pinned("q", "019f95dc-df08")),
        QueryKeyedRetriever({"q": [hit("019f95dc-df08-70e3-bce0-f209cb7402c4")]}),
    )

    (row,) = rows
    assert row.state == "current"
    assert row.rank == 0
    assert row.live_id == "019f95dc-df08-70e3-bce0-f209cb7402c4"
    assert not drifted(rows)


async def test_a_pin_whose_record_was_superseded_reports_its_successor() -> None:
    # WI 2247's own shape. The check passes via the chain; the pin is
    # still stale, and this is the tool that says so.
    rows = await resolve_pins(
        suite_of(pinned("q", "019fa04a-ceac")),
        QueryKeyedRetriever(
            {"q": [hit("019fb6b1-1c9a-7850", ancestry=("019fb1c9-7c16", "019fa04a-ceac"))]}
        ),
    )

    (row,) = rows
    assert row.state == "superseded"
    assert row.live_id == "019fb6b1-1c9a-7850"
    # The whole lineage, so a maintainer can see how far the pin has drifted.
    assert row.chain == ("019fb1c9-7c16", "019fa04a-ceac")
    assert drifted(rows) == 1


async def test_a_pin_with_no_witness_at_all_is_absent() -> None:
    rows = await resolve_pins(
        suite_of(pinned("q", "019fa04a-ceac")),
        QueryKeyedRetriever({"q": [hit("deadbeef-0000-0000")]}),
    )

    (row,) = rows
    assert row.state == "absent"
    assert row.rank is None and row.live_id is None
    assert drifted(rows) == 1


async def test_max_rank_is_reported_separately_from_staleness() -> None:
    # A live pin that has lost its slot is a RANKING regression, not pin
    # rot. Conflating them is how a suite ends up re-pinning to hide a
    # retrieval problem.
    rows = await resolve_pins(
        suite_of(pinned("q", "019f95dc-df08", max_rank=0)),
        QueryKeyedRetriever({"q": [hit("aaaa0000-0000-0000"), hit("019f95dc-df08-70e3")]}),
    )

    (row,) = rows
    assert row.state == "current"
    assert row.rank == 1
    assert not row.within_rank
    # Still not drift: the pin is fine, the ranking is not.
    assert drifted(rows) == 0


async def test_only_memory_id_checks_are_collected() -> None:
    q = EvalQuery(
        query="q",
        checks=[Check(type="substring", value="x"), Check(type="memory_id", value="aaaa")],
    )
    rows = await resolve_pins(suite_of(q), QueryKeyedRetriever({"q": [hit("aaaa1111")]}))
    assert [r.pin for r in rows] == ["aaaa"]


async def test_each_query_is_searched_once_for_all_its_pins() -> None:
    calls: list[str] = []

    class Counting(QueryKeyedRetriever):
        async def search(self, query: str, top_k: int) -> list[RetrievedItem]:
            calls.append(query)
            return await super().search(query, top_k)

    q = EvalQuery(
        query="q",
        checks=[Check(type="memory_id", value="aaaa"), Check(type="memory_id", value="bbbb")],
    )
    await resolve_pins(suite_of(q), Counting({"q": [hit("aaaa1"), hit("bbbb1")]}))

    assert calls == ["q"]


async def test_markdown_names_the_stale_pins_and_their_successors() -> None:
    rows = await resolve_pins(
        suite_of(pinned("score field behavior", "019fa04a-ceac")),
        QueryKeyedRetriever(
            {"score field behavior": [hit("019fb6b1-1c9a-7850", ancestry=("019fa04a-ceac",))]}
        ),
    )

    md = to_markdown(rows)

    assert "019fa04a-ceac" in md and "019fb6b1-1c9a-7850" in md
    assert "superseded" in md
    assert "1 of 1" in md  # the headline count
    # Repointing is a legibility call, not a repair — the report must not
    # read as an instruction to undo the thing that made the check robust.
    assert "still **pass**" in md


async def test_json_round_trips() -> None:
    rows = await resolve_pins(
        suite_of(pinned("q", "019f95dc-df08")),
        QueryKeyedRetriever({"q": [hit("019f95dc-df08-70e3")]}),
    )

    payload = json.loads(to_json(rows))

    assert payload["pins"] == 1
    assert payload["drifted"] == 0
    assert payload["rows"][0]["state"] == "current"
