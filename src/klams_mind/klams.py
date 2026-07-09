"""Typed client for the klams memory service.

`/healthz` is plain REST; `register_author`, `memory_search`, and
`memory_add` exist only as MCP tools on `{base_url}/mcp` (Streamable
HTTP, bearer auth). Contract source: klams repo
`crates/klams-mcp/src/tools/` and `crates/klams-types/`.

Use `connect(cfg)` to get a session-backed client; tests inject a
`tool_caller` instead of opening a transport.
"""

import json
from collections.abc import AsyncIterator, Awaitable, Callable, Sequence
from contextlib import asynccontextmanager
from datetime import datetime
from typing import Annotated, Any, Literal
from uuid import UUID

import httpx
from mcp import ClientSession
from mcp.client.streamable_http import streamablehttp_client
from mcp.types import CallToolResult, TextContent
from pydantic import BaseModel, Field, TypeAdapter

from klams_mind.config import KlamsConfig

ToolCaller = Callable[[str, dict[str, Any]], Awaitable[CallToolResult]]


class KlamsError(Exception):
    """A klams tool call failed; `error_code` is klams's machine code."""

    def __init__(self, message: str, error_code: str | None = None) -> None:
        super().__init__(message)
        self.error_code = error_code


# --- /healthz ----------------------------------------------------------------

HealthStatus = Literal["Ok", "Degraded", "Down"]


class SubsystemStatus(BaseModel):
    state: HealthStatus
    message: str | None = None


class QueueStatus(BaseModel):
    depth: int
    capacity: int
    workers: int


class HealthSnapshot(BaseModel):
    status: HealthStatus
    postgres: SubsystemStatus
    qdrant: SubsystemStatus
    embeddings: SubsystemStatus
    queue: QueueStatus
    version: str
    uptime_seconds: int


# --- memories ----------------------------------------------------------------


class AuthorRef(BaseModel):
    agent_name: str
    model: str | None = None
    repo: str | None = None


class _MemoryBase(BaseModel):
    id: UUID
    tags: list[str] = []
    author: AuthorRef
    created_at: datetime
    updated_at: datetime


class FactMemory(_MemoryBase):
    kind: Literal["fact"]
    type: str
    payload: Any


class KnowledgeMemory(_MemoryBase):
    kind: Literal["knowledge"]
    text: str
    source_path: str | None = None
    repo: str | None = None


class EventMemory(_MemoryBase):
    kind: Literal["event"]
    category: str
    payload: Any = None
    task_id: UUID | None = None


Memory = Annotated[FactMemory | KnowledgeMemory | EventMemory, Field(discriminator="kind")]


class ScoredMemory(BaseModel):
    """One `memory_search` hit (klams ≥ sprint 016).

    `score` is the raw per-source relevance score and is NOT normalized
    across kinds — knowledge is cosine similarity (~0..1), fact/event is
    Postgres ts_rank (typically ≪ 1) — so only compare scores within the
    same `memory.kind`. `source_rank` is the hit's 0-based rank within
    its own source before cross-source fusion; global rank is the list
    index.
    """

    score: float
    source_rank: int
    memory: Memory


_memory = TypeAdapter[Memory](Memory)
_scored_memories = TypeAdapter[list[ScoredMemory]](list[ScoredMemory])


class RegisteredAuthor(BaseModel):
    author_id: UUID
    agent_name: str
    created_at: datetime


# --- client -------------------------------------------------------------------


class KlamsClient:
    def __init__(
        self,
        cfg: KlamsConfig,
        tool_caller: ToolCaller | None = None,
        http: httpx.AsyncClient | None = None,
    ) -> None:
        self._cfg = cfg
        self._tool_caller = tool_caller
        self._http = http

    async def healthz(self) -> HealthSnapshot:
        """Fetch the health snapshot; 503 still carries a valid body."""
        url = f"{self._cfg.base_url}/healthz"
        if self._http is not None:
            resp = await self._http.get(url)
        else:
            async with httpx.AsyncClient(timeout=10) as http:
                resp = await http.get(url)
        if resp.status_code not in (200, 503):
            raise KlamsError(f"GET /healthz returned {resp.status_code}: {resp.text[:200]}")
        return HealthSnapshot.model_validate(resp.json())

    async def register_author(
        self,
        agent_name: str,
        *,
        model: str | None = None,
        session_title: str | None = None,
        repo: str | None = None,
        client_app: str | None = None,
        client_version: str | None = None,
    ) -> RegisteredAuthor:
        """Register an author identity; klams mints a fresh id per call."""
        args: dict[str, Any] = {"agent_name": agent_name}
        optionals = {
            "model": model,
            "session_title": session_title,
            "repo": repo,
            "client_app": client_app,
            "client_version": client_version,
        }
        args |= {k: v for k, v in optionals.items() if v is not None}
        return RegisteredAuthor.model_validate(await self._call("register_author", args))

    async def memory_search(
        self,
        query: str,
        *,
        kinds: Sequence[str] | None = None,
        tags: Sequence[str] | None = None,
        top_k: int = 10,
    ) -> list[ScoredMemory]:
        args: dict[str, Any] = {"query": query, "top_k": top_k}
        if kinds is not None:
            args["kinds"] = list(kinds)
        if tags is not None:
            args["tags"] = list(tags)
        return _scored_memories.validate_python(await self._call("memory_search", args))

    async def add_knowledge(
        self,
        author_id: str,
        text: str,
        *,
        tags: Sequence[str] = (),
        source_path: str | None = None,
        repo: str | None = None,
    ) -> Memory:
        args: dict[str, Any] = {
            "author_id": author_id,
            "kind": "knowledge",
            "text": text,
            "tags": list(tags),
        }
        if source_path is not None:
            args["source_path"] = source_path
        if repo is not None:
            args["repo"] = repo
        return _memory.validate_python(await self._call("memory_add", args))

    async def add_fact(
        self,
        author_id: str,
        fact_type: Literal["UserFact", "TaskFact", "EnvFact"],
        payload: Any,
    ) -> Memory:
        args = {
            "author_id": author_id,
            "kind": "fact",
            "fact_type": fact_type,
            "payload": payload,
        }
        return _memory.validate_python(await self._call("memory_add", args))

    async def _call(self, tool: str, args: dict[str, Any]) -> Any:
        if self._tool_caller is None:
            raise KlamsError("no MCP session — use `async with connect(cfg) as client`")
        result = await self._tool_caller(tool, args)
        text = next((c.text for c in result.content if isinstance(c, TextContent)), "")
        if result.isError:
            meta = result.meta or {}
            raise KlamsError(text or f"{tool} failed", error_code=meta.get("error_code"))
        if result.structuredContent is not None:
            return result.structuredContent
        return json.loads(text)


@asynccontextmanager
async def connect(cfg: KlamsConfig) -> AsyncIterator[KlamsClient]:
    """Open an authenticated MCP session against `{base_url}/mcp`."""
    headers = {"Authorization": f"Bearer {cfg.token}"} if cfg.token else None
    async with (
        streamablehttp_client(f"{cfg.base_url}/mcp", headers=headers) as (
            read,
            write,
            _,
        ),
        ClientSession(read, write) as session,
    ):
        await session.initialize()

        async def call(name: str, args: dict[str, Any]) -> CallToolResult:
            return await session.call_tool(name, args)

        yield KlamsClient(cfg, tool_caller=call)
