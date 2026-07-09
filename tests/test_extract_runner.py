"""Extraction runner: citation gate, dedupe, propose-first writes."""

import json
from typing import Any

from langchain_core.language_models.fake_chat_models import FakeListChatModel
from mcp.types import CallToolResult

from klams_mind.config import KlamsConfig
from klams_mind.extract.chain import build_extraction_chain
from klams_mind.extract.runner import extract_windows, is_cited
from klams_mind.klams import KlamsClient
from tests.test_klams_client import KNOWLEDGE_MEMORY, scored, tool_ok


class ToolRouter:
    """Replays per-tool canned results; records calls."""

    def __init__(self, results: dict[str, CallToolResult]) -> None:
        self.results = results
        self.calls: list[tuple[str, dict[str, Any]]] = []

    async def __call__(self, name: str, args: dict[str, Any]) -> CallToolResult:
        self.calls.append((name, args))
        return self.results[name]


def reply(*facts: dict[str, Any]) -> str:
    return json.dumps(list(facts))


def make_client(router: ToolRouter) -> KlamsClient:
    return KlamsClient(KlamsConfig(), tool_caller=router)


WINDOW = "USER: for the record, klams listens on kubs0:7777\n\nASSISTANT: Noted."
CITED = {"text": "klams listens on kubs0:7777", "evidence": "klams listens on kubs0:7777"}
UNCITED = {"text": "made-up fact", "evidence": "this quote appears nowhere"}


def test_is_cited_normalizes_whitespace_and_case() -> None:
    assert is_cited("KLAMS  listens on\nkubs0:7777", WINDOW)
    assert not is_cited("klams listens on kai:7777", WINDOW)
    assert not is_cited("   ", WINDOW)


async def test_dry_run_proposes_cited_and_flags_uncited() -> None:
    router = ToolRouter({"memory_search": tool_ok([])})
    chain = build_extraction_chain(FakeListChatModel(responses=[reply(CITED, UNCITED)]))

    result = await extract_windows([WINDOW], chain, make_client(router), transcript="t.jsonl")

    statuses = [(c.fact.text, c.status) for c in result.candidates]
    assert statuses == [(CITED["text"], "proposed"), (UNCITED["text"], "uncited")]
    assert result.written == 0
    # only the cited candidate reached dedupe; nothing was written
    assert [name for name, _ in router.calls] == ["memory_search"]


async def test_duplicate_detected_by_normalized_containment() -> None:
    existing = {**KNOWLEDGE_MEMORY, "text": "Klams   LISTENS on kubs0:7777 (MCP + REST)."}
    router = ToolRouter({"memory_search": tool_ok([scored(existing)])})
    chain = build_extraction_chain(FakeListChatModel(responses=[reply(CITED)]))

    result = await extract_windows([WINDOW], chain, make_client(router), transcript="t.jsonl")

    (c,) = result.candidates
    assert c.status == "duplicate"
    assert str(KNOWLEDGE_MEMORY["id"]) in c.detail


async def test_apply_writes_with_tags_and_source_path() -> None:
    router = ToolRouter({"memory_search": tool_ok([]), "memory_add": tool_ok(KNOWLEDGE_MEMORY)})
    fact = {**CITED, "tags": ["klams", "homelab"]}
    chain = build_extraction_chain(FakeListChatModel(responses=[reply(fact)]))

    result = await extract_windows(
        [WINDOW],
        chain,
        make_client(router),
        transcript="/logs/t.jsonl",
        apply=True,
        author_id="author-1",
    )

    (c,) = result.candidates
    assert c.status == "written"
    assert result.written == 1
    name, args = router.calls[-1]
    assert name == "memory_add"
    assert args["author_id"] == "author-1"
    assert args["tags"] == ["session-extract", "klams", "homelab"]
    assert args["source_path"] == "/logs/t.jsonl"


async def test_parse_failure_recorded_per_window_and_run_continues() -> None:
    router = ToolRouter({"memory_search": tool_ok([])})
    chain = build_extraction_chain(FakeListChatModel(responses=["not json at all", reply(CITED)]))

    result = await extract_windows(
        ["USER: nothing here", WINDOW], chain, make_client(router), transcript="t.jsonl"
    )

    assert len(result.parse_failures) == 1 and "window 1" in result.parse_failures[0]
    assert [c.status for c in result.candidates] == ["proposed"]
