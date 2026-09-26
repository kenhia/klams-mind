"""Consolidation, propose-only (sprint 013, WI 272): curate, pair through
klams search, judge with the model, report — and never write to klams."""

import json
from typing import Any

from langchain_core.language_models.fake_chat_models import FakeListChatModel
from mcp.types import CallToolResult, TextContent

from klams_mind.config import KlamsConfig
from klams_mind.consolidate.chain import build_merge_chain, parse_verdict
from klams_mind.consolidate.pairing import (
    QUERY_MAX,
    CandidatePair,
    curated,
    find_near_duplicates,
)
from klams_mind.consolidate.report import to_json, to_markdown
from klams_mind.consolidate.runner import ConsolidationResult, judge_pairs
from klams_mind.klams import KlamsClient, KnowledgeMemory, Memory, _memory
from tests.test_klams_client import FACT_MEMORY, KNOWLEDGE_MEMORY, scored


def agent_note(suffix: str, text: str, **over: Any) -> KnowledgeMemory:
    raw = {
        **KNOWLEDGE_MEMORY,
        "id": f"01980000-0000-7000-8000-0000000000{suffix}",
        "text": text,
        "source_path": None,
        "repo": None,
        "author": {"agent_name": "claude"},
        **over,
    }
    mem = _memory.validate_python(raw)
    assert isinstance(mem, KnowledgeMemory)
    return mem


A = agent_note("a0", "kvllm serves one model at a time on kai:8000.")
B = agent_note("b0", "kai:8000 is kvllm; it serves exactly one model.")
C = agent_note("c0", "klams listens on 127.0.0.1:7777 and the tailnet IP.")


class SearchRouter:
    """Fakes `memory_search` (full), returning canned hits per query."""

    def __init__(self, by_query: dict[str, list[dict[str, Any]]]) -> None:
        self.by_query = by_query
        self.calls: list[dict[str, Any]] = []

    async def __call__(self, name: str, args: dict[str, Any]) -> CallToolResult:
        assert name == "memory_search", f"consolidation must only search, not call {name}"
        self.calls.append(args)
        hits = self.by_query.get(args["query"], [])
        return CallToolResult(content=[TextContent(type="text", text=json.dumps(hits))])


def hit(mem: Memory, raw: float) -> dict[str, Any]:
    return {**scored(json.loads(mem.model_dump_json(exclude_none=True))), "raw_score": raw}


# --- curation --------------------------------------------------------------


def test_curated_keeps_only_agent_authored_knowledge() -> None:
    scanner = _memory.validate_python(KNOWLEDGE_MEMORY)  # has a source_path
    fact = _memory.validate_python(FACT_MEMORY)
    assert curated([A, scanner, fact, C]) == [A, C]


# --- pairing ---------------------------------------------------------------


async def test_pairs_curated_neighbours_over_the_threshold_best_first() -> None:
    scanner = _memory.validate_python(KNOWLEDGE_MEMORY)
    router = SearchRouter(
        {
            A.text: [hit(A, 1.0), hit(scanner, 0.95), hit(B, 0.91), hit(C, 0.86)],
            B.text: [hit(B, 1.0), hit(A, 0.93)],
            C.text: [hit(C, 1.0), hit(A, 0.84)],
        }
    )
    pairs = await find_near_duplicates(
        KlamsClient(KlamsConfig(), tool_caller=router), [A, B, C], threshold=0.85
    )

    # A-B seen from both sides keeps the higher score; scanner is not curated;
    # C-A at 0.84 from C's side loses to 0.86 from A's side, which qualifies.
    assert [(p.a.id, p.b.id, p.score) for p in pairs] == [
        (A.id, B.id, 0.93),
        (A.id, C.id, 0.86),
    ]
    assert {c["kinds"][0] for c in router.calls} == {"knowledge"}
    assert all(c["full"] is True and c["top_k"] == 30 for c in router.calls)


async def test_query_is_truncated_under_klams_limit() -> None:
    long = agent_note("d0", "x" * 3000)
    router = SearchRouter({})
    await find_near_duplicates(
        KlamsClient(KlamsConfig(), tool_caller=router), [long], threshold=0.85
    )
    assert len(router.calls[0]["query"]) == QUERY_MAX < 1024


# --- judge -----------------------------------------------------------------


def test_parse_verdict_tolerates_fences() -> None:
    v = parse_verdict('```json\n{"verdict": "merge", "keep": "a", "merged_text": "t"}\n```')
    assert v.verdict == "merge" and v.keep == "a" and v.merged_text == "t"


def reply(**kw: object) -> str:
    return json.dumps(kw)


async def judge(*replies: str, pairs: list[CandidatePair], max_pairs: int = 25) -> Any:
    chain = build_merge_chain(FakeListChatModel(responses=list(replies)))
    return await judge_pairs(pairs, chain, max_pairs=max_pairs)


async def test_duplicate_proposes_retiring_the_other() -> None:
    [p], failures = await judge(
        reply(verdict="duplicate", keep="b", reason="same claim"),
        pairs=[CandidatePair(A, B, 0.93)],
    )
    assert failures == []
    assert (p.status, p.keep_id, p.retire_id, p.text) == ("duplicate", str(B.id), str(A.id), None)


async def test_merge_proposes_a_supersede_with_merged_text() -> None:
    [p], _ = await judge(
        reply(verdict="merge", keep="a", reason="overlap", merged_text="  both  "),
        pairs=[CandidatePair(A, B, 0.93)],
    )
    assert (p.status, p.keep_id, p.retire_id, p.text) == ("merge", str(A.id), str(B.id), "both")


async def test_merge_without_text_is_unactionable() -> None:
    [p], _ = await judge(
        reply(verdict="merge", keep="a", reason="overlap"), pairs=[CandidatePair(A, B, 0.9)]
    )
    assert p.status == "unactionable" and p.keep_id is None


async def test_distinct_and_parse_failures_are_reported() -> None:
    judged, failures = await judge(
        reply(verdict="distinct", reason="different subjects"),
        "not json",
        pairs=[CandidatePair(A, C, 0.9), CandidatePair(B, C, 0.88)],
    )
    assert [p.status for p in judged] == ["distinct"]
    assert len(failures) == 1 and failures[0].startswith("pair 2:")


async def test_the_llm_pass_stops_at_max_pairs() -> None:
    judged, _ = await judge(
        reply(verdict="distinct", reason="r"),
        pairs=[CandidatePair(A, B, 0.95), CandidatePair(A, C, 0.9)],
        max_pairs=1,
    )
    assert [p.pair.score for p in judged] == [0.95]


# --- report ----------------------------------------------------------------


async def canned() -> ConsolidationResult:
    judged, failures = await judge(
        reply(verdict="merge", keep="a", reason="same subject", merged_text="merged"),
        reply(verdict="distinct", reason="different"),
        pairs=[CandidatePair(A, B, 0.93), CandidatePair(A, C, 0.86)],
    )
    return ConsolidationResult(
        walked=1000,
        curated=3,
        threshold=0.85,
        max_pairs=2,
        candidates=5,
        judged=judged,
        judge_failures=failures,
    )


async def test_markdown_states_bounds_and_the_apply_call() -> None:
    md = to_markdown(await canned())
    assert "**Propose-only**" in md
    assert "1000 memories walked, 3 curated" in md
    assert "5 pair(s) at cosine ≥ 0.85; 2 judged (cap 2), 3 left unjudged" in md
    assert f'memory_supersede(id="{A.id}", text=…)' in md
    assert f"retire `{B.id}`" in md
    assert "> merged" in md


async def test_json_carries_every_proposal() -> None:
    data = json.loads(to_json(await canned()))
    assert data["unjudged"] == 3
    assert [p["status"] for p in data["proposals"]] == ["merge", "distinct"]
    assert data["proposals"][0]["text"] == "merged"
    assert data["proposals"][0]["score"] == 0.93


# --- CLI -------------------------------------------------------------------


def test_cli_prints_the_proposal_and_threads_bounds(monkeypatch: Any) -> None:
    from typer.testing import CliRunner

    from klams_mind.cli import app

    seen: dict[str, Any] = {}

    async def fake_run(cfg: Any, **kw: Any) -> ConsolidationResult:
        seen.update(kw)
        return ConsolidationResult(walked=3, curated=3, threshold=0.9, max_pairs=4, candidates=0)

    monkeypatch.setattr("klams_mind.cli.run_consolidate", fake_run)
    result = CliRunner().invoke(
        app, ["consolidate", "run", "--threshold", "0.9", "--max-pairs", "4", "--json"]
    )
    assert result.exit_code == 0, result.output
    assert json.loads(result.stdout)["max_pairs"] == 4
    assert (seen["threshold"], seen["max_pairs"], seen["top_k"]) == (0.9, 4, 30)


def test_cli_has_no_apply_flag() -> None:
    from typer.testing import CliRunner

    from klams_mind.cli import app

    result = CliRunner().invoke(app, ["consolidate", "run", "--apply"])
    assert result.exit_code != 0


async def test_run_consolidate_walks_curates_pairs_and_judges(monkeypatch: Any) -> None:
    from contextlib import asynccontextmanager
    from datetime import UTC, datetime

    import httpx

    from klams_mind.cli import run_consolidate
    from klams_mind.config import Config

    scanner = json.loads(_memory.validate_python(KNOWLEDGE_MEMORY).model_dump_json())
    page = [json.loads(m.model_dump_json()) for m in (A, B)] + [scanner]
    rest = httpx.MockTransport(lambda req: httpx.Response(200, json={"memories": page}))
    router = SearchRouter({A.text: [hit(B, 0.9)], B.text: [hit(A, 0.9)]})
    client = KlamsClient(KlamsConfig(), tool_caller=router, http=httpx.AsyncClient(transport=rest))

    @asynccontextmanager
    async def fake_connect(_cfg: Any) -> Any:
        yield client

    async def fake_resolve(_cfg: Any) -> str:
        return "served-model"

    chat = FakeListChatModel(responses=[reply(verdict="duplicate", keep="a", reason="same")])
    result = await run_consolidate(
        Config(),
        threshold=0.85,
        max_pairs=25,
        top_k=30,
        since=datetime(2026, 9, 1, tzinfo=UTC),
        now=lambda: datetime(2026, 9, 26, tzinfo=UTC),
        connect=fake_connect,
        resolve_model_name=fake_resolve,
        build_chat=lambda cfg: chat,
    )
    assert (result.walked, result.curated, result.candidates) == (3, 2, 1)
    [p] = result.judged
    assert (p.status, p.keep_id, p.retire_id) == ("duplicate", str(A.id), str(B.id))
