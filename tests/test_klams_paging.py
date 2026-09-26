"""`GET /v1/memories` — the paged corpus read (sprint 013, WI 272).

Fixtures follow the klams source contract
(`klams-api/src/handlers/memories.rs`) and a live response recorded
from kubs0 on 2026-09-25 (klams 0.1.55). The transport is an
`httpx.MockTransport`, so every request the walk makes is inspectable.
"""

from datetime import UTC, datetime, timedelta
from typing import Any
from urllib.parse import parse_qs

import httpx
import pytest

from klams_mind.config import KlamsConfig
from klams_mind.klams import KlamsClient, KlamsError, KnowledgeMemory

# Recorded 2026-09-25 from live kubs0:7777/v1/memories (text trimmed).
SCANNER_ITEM = {
    "author": {"agent_name": "klams-scanner", "id": "019eb25b-ff68-7cc3-b1ac-02ef62e50047"},
    "chunk_index": 22,
    "content_hash": "52e6ba10235a190788aeffd0dac4ebec4cdae5fad44e91b6779e6ccc14ba8d17",
    "created_at": "2026-09-26T01:49:05.847501338Z",
    "host": "kubs0",
    "id": "01a0db66-d9b0-73f2-bab8-1face86b9105",
    "kind": "knowledge",
    "repo": "agent-skills",
    "source_path": "/home/ken/src/ai-agents/agent-skills/fleet.yml",
    "tags": [],
    "text": "# Skills that deliberately reach no host.\nunmapped:",
    "updated_at": "2026-09-26T01:49:05.847501338Z",
    "state": "live",
}


def item(n: int, **over: Any) -> dict[str, Any]:
    return {**SCANNER_ITEM, "id": f"01a0db66-d9b0-73f2-b000-{n:012d}", **over}


def client_for(handler: Any, agent_name: str = "klams-mind") -> KlamsClient:
    cfg = KlamsConfig(base_url="http://kubs0:7777", agent_name=agent_name)
    return KlamsClient(cfg, http=httpx.AsyncClient(transport=httpx.MockTransport(handler)))


def params(req: httpx.Request) -> dict[str, str]:
    return {k: v[0] for k, v in parse_qs(req.url.query.decode()).items()}


NOW = datetime(2026, 9, 26, tzinfo=UTC)


async def test_list_memories_builds_the_query_and_parses_a_page() -> None:
    seen: list[httpx.Request] = []

    def handler(req: httpx.Request) -> httpx.Response:
        seen.append(req)
        return httpx.Response(200, json={"memories": [SCANNER_ITEM], "next_cursor": "c1"})

    page = await client_for(handler).list_memories(
        since=NOW - timedelta(days=30), until=NOW, kinds=["knowledge"], limit=200
    )

    assert page.next_cursor == "c1"
    [mem] = page.memories
    assert isinstance(mem, KnowledgeMemory)
    assert mem.source_path == "/home/ken/src/ai-agents/agent-skills/fleet.yml"
    [req] = seen
    assert req.url.path == "/v1/memories"
    assert req.headers["X-Homelab-Agent"] == "klams-mind"
    assert params(req) == {
        "since": "2026-08-27T00:00:00Z",
        "until": "2026-09-26T00:00:00Z",
        "kinds": "knowledge",
        "limit": "200",
    }


async def test_list_memories_passes_the_cursor_and_ends_without_one() -> None:
    seen: list[httpx.Request] = []

    def handler(req: httpx.Request) -> httpx.Response:
        seen.append(req)
        return httpx.Response(200, json={"memories": []})

    page = await client_for(handler).list_memories(
        since=NOW - timedelta(days=1), until=NOW, cursor="abc"
    )

    assert page.memories == []
    assert page.next_cursor is None
    assert params(seen[0])["cursor"] == "abc"
    assert "kinds" not in params(seen[0])


async def test_list_memories_raises_an_actionable_error_on_refusal() -> None:
    def handler(req: httpx.Request) -> httpx.Response:
        return httpx.Response(401, json={"error": "unknown agent"})

    with pytest.raises(KlamsError, match=r"GET /v1/memories returned 401"):
        await client_for(handler).list_memories(since=NOW - timedelta(days=1), until=NOW)


async def test_walk_follows_cursors_then_steps_back_a_window() -> None:
    """Two windows over 40 days; the newer one is two pages long."""
    seen: list[dict[str, str]] = []

    def handler(req: httpx.Request) -> httpx.Response:
        p = params(req)
        seen.append(p)
        if p["until"] == "2026-09-26T00:00:00Z":
            if "cursor" not in p:
                return httpx.Response(200, json={"memories": [item(1)], "next_cursor": "n"})
            return httpx.Response(200, json={"memories": [item(2)]})
        return httpx.Response(200, json={"memories": [item(3)]})

    walked = [
        m
        async for m in client_for(handler).walk_memories(
            since=NOW - timedelta(days=40), until=NOW, kinds=["knowledge"]
        )
    ]

    assert [str(m.id)[-1] for m in walked] == ["1", "2", "3"]
    assert [(p["since"], p["until"], p.get("cursor")) for p in seen] == [
        ("2026-08-27T00:00:00Z", "2026-09-26T00:00:00Z", None),
        ("2026-08-27T00:00:00Z", "2026-09-26T00:00:00Z", "n"),
        ("2026-08-17T00:00:00Z", "2026-08-27T00:00:00Z", None),
    ]
    assert all(p["limit"] == "200" for p in seen)


async def test_walk_rejects_an_inverted_range() -> None:
    def handler(req: httpx.Request) -> httpx.Response:  # pragma: no cover - never called
        raise AssertionError("no request expected")

    with pytest.raises(ValueError, match="since"):
        [m async for m in client_for(handler).walk_memories(since=NOW, until=NOW)]
