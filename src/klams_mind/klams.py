"""Typed client for the klams memory service.

`/healthz` and the paged corpus read `GET /v1/memories` are plain
REST; `register_author`, `memory_search`, and `memory_add` exist only
as MCP tools on `{base_url}/mcp` (Streamable HTTP). Both surfaces
authenticate the declared `X-Homelab-Agent` name. Contract source: klams repo
`crates/klams-mcp/src/tools/` and `crates/klams-types/`.

Use `connect(cfg)` to get a session-backed client; tests inject a
`tool_caller` instead of opening a transport.
"""

import json
from collections.abc import AsyncIterator, Awaitable, Callable, Sequence
from contextlib import asynccontextmanager
from datetime import UTC, datetime, timedelta
from typing import Annotated, Any, Literal
from uuid import UUID

import httpx
from mcp import ClientSession
from mcp.client.streamable_http import streamablehttp_client
from mcp.types import CallToolResult, TextContent
from pydantic import BaseModel, ConfigDict, Field, TypeAdapter

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


# --- contract version range (#2249) ------------------------------------------

# The klams versions this client's contract has actually been exercised
# against. Every klams-facing unit test fakes the MCP transport, so the
# suite validates klams-mind against klams-mind's own idea of the
# contract; these two numbers are the part that refers to the world.
#
# The floor is not decoration. `memory_search`'s compact envelope
# (`{hits, more}`) landed in klams 0.1.46 (klams sprint 046, #1178), so
# an *older* klams breaks this client as surely as a newer one does.
#
# The ceiling is the newest klams `just gate-live` has round-tripped
# against. It is a NOTE, never a gate: the live test warns when klams
# has moved past it and does not fail (sprint 011 D-3, revised on the
# overseer's ruling). klams ships often — sixteen versions in the
# window this repo drifted — and a gate that goes red on every patch
# bump with no contract change is a gate people learn to ignore, which
# is the failure #2249 exists to stop. The contract assertions in the
# round-trip are the drift signal; this pair only records how far
# anyone has re-proved them.
TESTED_KLAMS_MIN = (0, 1, 46)
# Raised from 0.1.46 by `just gate-live` on kubs0, 2026-09-21: the
# round-trip (compact envelope, `full`, `memory_get`) passed against
# klams 0.1.52. Six versions of drift that nothing in this repo would
# otherwise have reported.
TESTED_KLAMS_MAX = (0, 1, 52)


def parse_version(version: str) -> tuple[int, ...] | None:
    """`"0.1.52"` → `(0, 1, 52)`, or None if it is not dotted integers."""
    try:
        return tuple(int(part) for part in version.split("."))
    except ValueError:
        return None


def _fmt_version(version: tuple[int, ...]) -> str:
    return ".".join(str(part) for part in version)


def version_warning(version: str) -> str | None:
    """One actionable line when klams is outside the tested range.

    None when it is inside — the caller prints nothing. This turns the
    failure klams-mind actually suffered (a bare `ValidationError` out
    of a search, sixteen versions after the envelope changed) into a
    sentence naming both versions before anything parses.
    """
    tested = f"{_fmt_version(TESTED_KLAMS_MIN)}-{_fmt_version(TESTED_KLAMS_MAX)}"
    parsed = parse_version(version)
    if parsed is None:
        return (
            f"klams reports version {version!r}, which this client cannot "
            f"compare against the range it was tested on ({tested})"
        )
    if parsed < TESTED_KLAMS_MIN:
        return (
            f"klams is {version}, older than the {tested} this client was "
            f"tested against — `memory_search`'s compact envelope landed in "
            f"{_fmt_version(TESTED_KLAMS_MIN)}, so searches will not parse"
        )
    if parsed > TESTED_KLAMS_MAX:
        return (
            f"klams is {version}, newer than the {tested} this client was "
            f"tested against — run `just gate-live` to check the contract, "
            f"then bump TESTED_KLAMS_MAX"
        )
    return None


class KlamsVersionWarning(UserWarning):
    """klams is outside the range this client has been exercised against.

    A warning and never a test failure. See the ceiling's note above:
    the drift signal is the round-trip's contract assertions, not the
    version number, and a tier that goes red on a no-op patch bump
    stops being read.
    """


def untested_version_note(version: str) -> str | None:
    """The `gate-live` message, or None when `version` is in range.

    Distinct from `version_warning` because the context is the
    opposite: this is spoken *after* the live round-trip has passed, so
    an out-of-range answer means a stale constant rather than drift —
    and the one thing worth saying is which constant to move.
    """
    parsed = parse_version(version)
    if parsed is None:
        return (
            f"the live round-trip passed, but klams reports version "
            f"{version!r}, which cannot be compared against this client's "
            f"tested range — check TESTED_KLAMS_MIN/MAX in "
            f"src/klams_mind/klams.py by hand"
        )
    if parsed < TESTED_KLAMS_MIN:
        return (
            f"the live round-trip passed against klams {version}, which is "
            f"BELOW this client's tested floor {_fmt_version(TESTED_KLAMS_MIN)} "
            f"— lower TESTED_KLAMS_MIN to {parsed} in "
            f"src/klams_mind/klams.py, or find out why an older klams still "
            f"speaks the compact contract"
        )
    if parsed > TESTED_KLAMS_MAX:
        return (
            f"the live round-trip passed against klams {version}: the "
            f"contract holds, only the constant is stale. Bump "
            f"TESTED_KLAMS_MAX to {parsed} in src/klams_mind/klams.py so "
            f"`smoke` stops warning about a combination this gate has now "
            f"proven"
        )
    return None


# --- memories ----------------------------------------------------------------


class AuthorRef(BaseModel):
    # klams sprint 026 (#641): the author's own id, so ownership can be
    # reasoned about without a register_author round-trip.
    id: UUID | None = None
    agent_name: str
    model: str | None = None
    repo: str | None = None


class KnowledgeCopy(BaseModel):
    """A duplicate that klams collapsed into a surviving hit.

    klams sprint 026 (#641): the same chunk is stored once per host, so
    ~44% of the corpus is duplicate content. klams now collapses them at
    query time and lists what it absorbed here, keyed on content only.
    """

    id: UUID
    host: str | None = None
    file: str | None = None


class _MemoryBase(BaseModel):
    id: UUID
    tags: list[str] = []
    author: AuthorRef
    created_at: datetime
    updated_at: datetime
    # The `memory_supersede` links, both directions (klams-mind #2247).
    # klams hides a superseded record from search rather than deleting
    # it, so `memory_get` still serves it and these two are how a caller
    # walks a lineage: `supersedes` points at the record this one
    # replaced, `superseded_by` at the one that replaced it. klams omits
    # each where it does not apply, and sends `supersedes` on search hits
    # in both envelopes — this client simply never declared them, so
    # pydantic dropped data that had been arriving since sprint 001.
    supersedes: UUID | None = None
    superseded_by: UUID | None = None


class FactMemory(_MemoryBase):
    kind: Literal["fact"]
    type: str
    payload: Any


class KnowledgeMemory(_MemoryBase):
    kind: Literal["knowledge"]
    text: str
    source_path: str | None = None
    repo: str | None = None
    # klams sprint 023 (#409): host the source file lives on, so a hit is
    # a fully-qualified (host, source_path) pair.
    host: str | None = None
    # klams sprint 026 (#641): the projection additions. `content_hash`
    # is what the no-duplicates invariant asserts on; `heading_path` is
    # the breadcrumb the chunker prepended, which the junk-ceiling check
    # strips before measuring body length.
    content_hash: str | None = None
    heading_path: str | None = None
    language: str | None = None
    chunk_index: int | None = None
    copies: list[KnowledgeCopy] = []


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
    # klams sprint 024 (#332): post-RRF `score` is pure rank
    # (1/(60+rank+1)) and carries no magnitude, so match quality lives
    # here — the pre-fusion cosine / ts_rank.
    raw_score: float | None = None
    memory: Memory


_memory = TypeAdapter[Memory](Memory)
_scored_memories = TypeAdapter[list[ScoredMemory]](list[ScoredMemory])


class More(BaseModel):
    """klams' explicit "here is how you get the rest" pointer.

    Present on every compact response, not only truncated ones — klams'
    reasoning is that a field appearing only sometimes is a field nobody
    learns to read.
    """

    fetch: str
    truncated: bool


class CompactHit(BaseModel):
    """One compact `memory_search` hit (klams sprint 046, WI #1178).

    The default agent-facing shape: enough to rank, cite and decide on,
    plus `id` as the locator for the one `memory_get` that yields the
    rest. `snippet` is a match-window excerpt of at most 320 characters
    with elisions marked `…` — so it is *not* the memory's text, and
    anything measuring a body needs `memory_search_full` or `memory_get`.

    Typed metadata is omitted where it does not apply rather than faked,
    which is why every field below the score block is optional: an
    agent-added knowledge memory has no `source_path`, and a fact has
    neither that nor `heading_path`.
    """

    id: UUID
    kind: str
    snippet: str
    score: float
    raw_score: float | None = None
    source_rank: int
    age_seconds: int
    tags: list[str] = Field(default_factory=list)
    author: str

    # Knowledge locators.
    source_path: str | None = None
    repo: str | None = None
    host: str | None = None
    heading_path: str | None = None
    supersedes: UUID | None = None
    # Fact / event discriminators (`type` is reserved, hence the alias).
    fact_type: str | None = Field(default=None, alias="type")
    category: str | None = None
    # Duplicate copies this hit absorbed at query time; omitted when it
    # collapsed nothing.
    copies: int | None = None

    model_config = ConfigDict(populate_by_name=True)


class SearchResponse(BaseModel):
    """The compact `memory_search` envelope: `{hits, more}`."""

    hits: list[CompactHit]
    more: More


class MemoryPage(BaseModel):
    """One page of `GET /v1/memories`; the walk ends when `next_cursor`
    is absent. klams adds a `state` to each item, which the memory
    models ignore — a walk reads `live` unless asked otherwise."""

    memories: list[Memory]
    next_cursor: str | None = None


# `GET /v1/memories` caps a request's span (`memories_max_window_days`,
# klams default 30) and a page at 200 — so a corpus walk is windows of
# pages, not one cursor.
MEMORIES_WINDOW = timedelta(days=30)
MEMORIES_PAGE_MAX = 200


def _rfc3339(when: datetime) -> str:
    return when.astimezone(UTC).isoformat().replace("+00:00", "Z")


class RegisteredAuthor(BaseModel):
    author_id: UUID
    agent_name: str
    created_at: datetime


class DissentProposed(BaseModel):
    """Result of `dissent_propose`; the dissent lands pending, resolved
    by a human in the viewport. `deduped` is True when this proposal
    matched an existing pending `(fact_id, payload)` and bumped its
    submission count instead of creating a new row."""

    dissent_id: UUID
    fact_id: UUID
    status: str
    deduped: bool


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

    async def list_memories(
        self,
        *,
        since: datetime,
        until: datetime,
        kinds: Sequence[str] | None = None,
        limit: int = MEMORIES_PAGE_MAX,
        cursor: str | None = None,
    ) -> MemoryPage:
        """One page of the live corpus in `[since, until]`, newest first.

        The span must fit in klams' window cap (`MEMORIES_WINDOW`); use
        `walk_memories` for anything longer. The response strips vectors,
        trust and decay by design, so this gives the *set* — similarity
        still comes from search.
        """
        query: dict[str, str] = {"since": _rfc3339(since), "until": _rfc3339(until)}
        if kinds is not None:
            query["kinds"] = ",".join(kinds)
        query["limit"] = str(limit)
        if cursor is not None:
            query["cursor"] = cursor
        headers = {"X-Homelab-Agent": self._cfg.agent_name} if self._cfg.agent_name else {}
        url = f"{self._cfg.base_url}/v1/memories"
        if self._http is not None:
            resp = await self._http.get(url, params=query, headers=headers)
        else:
            async with httpx.AsyncClient(timeout=30) as http:
                resp = await http.get(url, params=query, headers=headers)
        if resp.status_code != 200:
            raise KlamsError(f"GET /v1/memories returned {resp.status_code}: {resp.text[:200]}")
        return MemoryPage.model_validate(resp.json())

    async def walk_memories(
        self,
        *,
        since: datetime,
        until: datetime,
        kinds: Sequence[str] | None = None,
    ) -> AsyncIterator[Memory]:
        """Every live memory in `[since, until]`: newest window first,
        each window paged to the end of its cursor."""
        if since >= until:
            raise ValueError(f"since ({since}) must be before until ({until})")
        hi = until
        while hi > since:
            lo = max(since, hi - MEMORIES_WINDOW)
            cursor: str | None = None
            while True:
                page = await self.list_memories(since=lo, until=hi, kinds=kinds, cursor=cursor)
                for memory in page.memories:
                    yield memory
                cursor = page.next_cursor
                if cursor is None:
                    break
            hi = lo

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

    @staticmethod
    def _search_args(
        query: str,
        kinds: Sequence[str] | None,
        tags: Sequence[str] | None,
        top_k: int,
    ) -> dict[str, Any]:
        args: dict[str, Any] = {"query": query, "top_k": top_k}
        if kinds is not None:
            args["kinds"] = list(kinds)
        if tags is not None:
            args["tags"] = list(tags)
        return args

    async def memory_search(
        self,
        query: str,
        *,
        kinds: Sequence[str] | None = None,
        tags: Sequence[str] | None = None,
        top_k: int = 10,
    ) -> SearchResponse:
        """Search, compact — the shape agents actually receive.

        klams sprint 046 (#1178) made compact the default for a measured
        reason: 9,599 → 4,193 tokens per answered query, counting the
        follow-up read when a snippet fell short. Hits carry a ≤320-char
        `snippet`, not a body; reach for `memory_search_full` when you
        need texts in bulk, or `memory_get` for one record.
        """
        args = self._search_args(query, kinds, tags, top_k)
        return SearchResponse.model_validate(await self._call("memory_search", args))

    async def memory_search_full(
        self,
        query: str,
        *,
        kinds: Sequence[str] | None = None,
        tags: Sequence[str] | None = None,
        top_k: int = 10,
    ) -> list[ScoredMemory]:
        """Search with whole memory texts inline (`full: true`).

        klams documents this as the path for "callers that genuinely want
        bodies in bulk (eval harnesses, exports)" — which is exactly the
        eval suite, extraction's duplicate check, and fact pairing, all
        of which assert on full text or a fact payload. It returns the
        pre-046 `{score, source_rank, raw_score, memory}` envelope, so
        the eval baseline stays comparable across the contract change.
        """
        args = self._search_args(query, kinds, tags, top_k) | {"full": True}
        return _scored_memories.validate_python(await self._call("memory_search", args))

    async def memory_get(self, memory_id: str) -> Memory:
        """Fetch one memory whole — the tool `more.fetch` names."""
        return _memory.validate_python(await self._call("memory_get", {"id": memory_id}))

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

    async def memory_delete(self, *, author_id: str, memory_id: str) -> None:
        """Soft-delete a fact or knowledge memory by id (idempotent)."""
        await self._call("memory_delete", {"author_id": author_id, "id": memory_id})

    async def dissent_propose(
        self,
        *,
        fact_id: str,
        proposed_payload: dict[str, Any],
        reason: str,
        author_id: str | None = None,
        contradicting_memory_id: str | None = None,
    ) -> DissentProposed:
        """File a dissent against a live canonical fact.

        `proposed_payload` must be a JSON object (klams rejects scalars).
        `author_id` defaults to the caller's bearer identity; pass it to
        attribute the write to a specific registered author.
        """
        args: dict[str, Any] = {
            "fact_id": fact_id,
            "proposed_payload": proposed_payload,
            "reason": reason,
        }
        if author_id is not None:
            args["author_id"] = author_id
        if contradicting_memory_id is not None:
            args["contradicting_memory_id"] = contradicting_memory_id
        return DissentProposed.model_validate(await self._call("dissent_propose", args))

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
    """Open an authenticated MCP session against `{base_url}/mcp`.

    Sprint 010 (korg:2423): klams authenticates a declared identity, so
    what goes on the wire is a name rather than a bearer token. An empty
    `agent_name` sends no header at all — klams answers 401 either way,
    and declaring "" would be a claim rather than an omission.
    """
    headers = {"X-Homelab-Agent": cfg.agent_name} if cfg.agent_name else None
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
