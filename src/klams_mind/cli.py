"""klams-mind CLI. Errors go to stderr, results to stdout, `--json`
for programmatic use; exit 0 on success, 1 on failure.
"""

import asyncio
import json
import logging
import socket
from collections.abc import Callable
from datetime import UTC, datetime
from pathlib import Path
from typing import Annotated, Any

import httpx
import typer
from pydantic import ValidationError

from klams_mind import __version__
from klams_mind.config import Config, load_config
from klams_mind.consolidate.chain import build_merge_chain
from klams_mind.consolidate.pairing import DEFAULT_THRESHOLD, curated, find_near_duplicates
from klams_mind.consolidate.report import to_json as consolidate_to_json
from klams_mind.consolidate.report import to_markdown as consolidate_to_markdown
from klams_mind.consolidate.runner import ConsolidationResult, judge_pairs
from klams_mind.contradict.chain import build_contradiction_chain
from klams_mind.contradict.pairing import find_candidate_pairs
from klams_mind.contradict.report import to_json as contradict_to_json
from klams_mind.contradict.report import to_markdown as contradict_to_markdown
from klams_mind.contradict.runner import DetectionResult, detect_contradictions
from klams_mind.eval.pins import PinResolution, drifted, resolve_pins
from klams_mind.eval.pins import to_json as pins_to_json
from klams_mind.eval.pins import to_markdown as pins_to_markdown
from klams_mind.eval.provenance import Provenance, now_stamp, parse_provenance, suite_digest
from klams_mind.eval.report import Report, build_report, to_json, to_markdown
from klams_mind.eval.runner import (
    KlamsRetriever,
    Retriever,
    eval_klams_config,
    run_suite,
)
from klams_mind.eval.suite import EvalLoadError, Suite, load_suite
from klams_mind.extract.chain import build_extraction_chain
from klams_mind.extract.report import to_json as extraction_to_json
from klams_mind.extract.report import to_markdown as extraction_to_markdown
from klams_mind.extract.runner import ExtractionResult, extract_windows
from klams_mind.klams import FactMemory, version_warning
from klams_mind.klams import connect as _connect
from klams_mind.llm import build_chat as _build_chat
from klams_mind.llm import ping
from klams_mind.llm import resolve_model_name as _resolve_model_name
from klams_mind.transcripts import TranscriptError, read_transcript, windows

app = typer.Typer(help="LLM-smart memory companion to klams.")
eval_app = typer.Typer(help="Retrieval-quality evals against klams.")
app.add_typer(eval_app, name="eval")
extract_app = typer.Typer(help="Distill durable facts from session transcripts into klams.")
app.add_typer(extract_app, name="extract")
contradict_app = typer.Typer(help="Find facts that contradict in meaning; propose dissents.")
app.add_typer(contradict_app, name="contradict")
consolidate_app = typer.Typer(help="Find agent notes that say the same thing; propose merges.")
app.add_typer(consolidate_app, name="consolidate")

# The oldest live memory on kubs0 was written 2026-05-25; a walk from here
# covers the whole corpus. Homelab-specific on purpose (AGENTS.md).
CORPUS_START = datetime(2026, 5, 1, tzinfo=UTC)


class SmokeError(Exception):
    def __init__(self, step: str, cause: Exception) -> None:
        super().__init__(f"step '{step}' failed: {cause}")
        self.step = step
        # #831: the diagnosis walks this, so keep it addressable rather
        # than relying on `__cause__` surviving a re-raise.
        self.exceptions = (cause,)


async def run_smoke(
    cfg: Config,
    *,
    connect: Any = _connect,
    resolve_model_name: Any = _resolve_model_name,
    build_chat: Any = _build_chat,
) -> dict[str, Any]:
    """Health-check klams, register author, one search, one LLM call."""
    report: dict[str, Any] = {"ok": False}
    step = "resolve model name"
    try:
        model_name = await resolve_model_name(cfg.model)
        report["model"] = {"endpoint": cfg.model.base_url, "name": model_name}

        step = "connect to klams MCP"
        async with connect(cfg.klams) as client:
            step = "klams healthz"
            snap = await client.healthz()
            report["klams"] = {
                "url": cfg.klams.base_url,
                "status": snap.status,
                "version": snap.version,
                # #2249: klams-mind's whole suite fakes the MCP
                # transport, so a klams that has moved out from under
                # this client is invisible until something fails to
                # parse. smoke already had the version in hand.
                "version_warning": version_warning(snap.version),
            }

            step = "register author"
            author = await client.register_author(
                agent_name=cfg.klams.agent_name,
                model=model_name,
                client_app="klams-mind",
                client_version=__version__,
            )
            report["author"] = {
                "author_id": str(author.author_id),
                "agent_name": author.agent_name,
            }

            step = "memory search"
            query = "homelab machines and services"
            # Deliberately the compact path (klams 046): the health check
            # should exercise the shape agents actually receive.
            found = await client.memory_search(query, top_k=3)
            report["search"] = {
                "query": query,
                "hits": len(found.hits),
                "truncated": found.more.truncated,
                "top": [{"kind": h.kind, "id": str(h.id), "score": h.score} for h in found.hits],
            }

        step = "LLM call"
        chat = build_chat(cfg.model.model_copy(update={"name": model_name}))
        report["model"]["reply"] = ping(chat)
    except Exception as exc:
        raise SmokeError(step, exc) from exc

    report["ok"] = True
    return report


# --- smoke failure diagnosis (#831) -----------------------------------------

# Steps whose failure is the model endpoint's fault, not klams'.
_MODEL_STEPS = frozenset({"resolve model name", "LLM call"})


def leaf_cause(exc: BaseException) -> BaseException:
    """The innermost informative exception inside an `ExceptionGroup`.

    The MCP streamable-http client nests two task groups, so a refused
    connection arrives as `ExceptionGroup[ExceptionGroup[ConnectError]]`
    and reads as "unhandled errors in a TaskGroup" — true, and useless.
    """
    while True:
        subs = getattr(exc, "exceptions", None)
        if not subs:
            return exc
        exc = subs[0]


def _endpoint(step: str, cfg: Config) -> str:
    return cfg.model.base_url if step in _MODEL_STEPS else cfg.klams.base_url


def diagnose(step: str, exc: BaseException, cfg: Config, *, host: str | None = None) -> str:
    """One actionable line for a smoke failure, chosen by the leaf cause.

    `host` is this machine's short hostname (injected in tests); it only
    affects the loopback tip below.
    """
    leaf = leaf_cause(exc)
    url = _endpoint(step, cfg)

    if isinstance(leaf, httpx.ConnectError | httpx.ConnectTimeout):
        hint = f"unreachable at {url} ({leaf})"
        # #831's own diagnosis cost: on kubs0 the default `kubs0`
        # hostname resolves to 127.0.1.1, while klams binds 127.0.0.1
        # and the tailnet address — so the service is up and the name
        # is what is wrong.
        parsed = httpx.URL(url)
        if host is None:
            host = socket.gethostname().split(".")[0]
        if parsed.host == host and step not in _MODEL_STEPS:
            hint += f"\nthis host is {host}: try KLAMS_URL=http://localhost:{parsed.port or 7777}"
        return hint

    if isinstance(leaf, httpx.HTTPStatusError):
        code = leaf.response.status_code
        if code in (401, 403):
            return (
                f"klams at {url} rejected the identity "
                f"'{cfg.klams.agent_name}' (HTTP {code}) — it needs an "
                "[[auth.identities]] row in klams.toml"
            )
        return f"klams at {url} returned HTTP {code}"

    if isinstance(leaf, ValidationError):
        return (
            f"{url} answered, but klams-mind could not parse the response "
            f"— client/server contract drift; check this client against "
            f"klams' version ({leaf.error_count()} validation error(s))"
        )

    return (
        f"check klams ({cfg.klams.base_url}), kvllm ({cfg.model.base_url}), "
        f"and the X-Homelab-Agent identity ({cfg.klams.agent_name})"
    )


def _warn_version(report: dict[str, Any]) -> None:
    """Echo the version-range warning to stderr, if there is one.

    Always stderr, in both output modes: a `--json` consumer reads the
    field off the report, and a human piping to `jq` still sees the
    line because it never touches stdout.
    """
    warning = report.get("klams", {}).get("version_warning")
    if warning:
        typer.echo(f"warning: {warning}", err=True)


def _print_human(report: dict[str, Any]) -> None:
    klams, author = report["klams"], report["author"]
    search, model = report["search"], report["model"]
    typer.echo(f"klams   {klams['status']} (v{klams['version']}) at {klams['url']}")
    typer.echo(f"author  {author['agent_name']} {author['author_id']}")
    typer.echo(f'search  "{search["query"]}" -> {search["hits"]} hit(s)')
    typer.echo(f"model   {model['name']} at {model['endpoint']} -> {model['reply']!r}")
    typer.echo("smoke: all steps passed")
    _warn_version(report)


@app.callback()
def main() -> None:
    """klams-mind — extraction, contradiction detection, and evals for klams."""
    # klams (rmcp) answers the session-close DELETE with 202; the mcp SDK
    # logs a spurious "Session termination failed: 202" warning on it.
    logging.getLogger("mcp.client.streamable_http").setLevel(logging.ERROR)


@app.command()
def smoke(
    json_output: Annotated[
        bool, typer.Option("--json", help="Emit the report as JSON on stdout.")
    ] = False,
    config: Annotated[
        Path | None, typer.Option(help="Config file (default: KLAMS_MIND_CONFIG).")
    ] = None,
    debug: Annotated[bool, typer.Option(help="Re-raise failures with full tracebacks.")] = False,
) -> None:
    """Prove the plumbing: klams health, author, search, one LLM call."""
    cfg = load_config(path=config)
    try:
        report = asyncio.run(run_smoke(cfg))
    except SmokeError as failure:
        if debug:
            raise
        # #831: report the leaf, not the TaskGroup wrapper it arrived in.
        leaf = leaf_cause(failure.__cause__ or failure)
        typer.echo(
            f"smoke failed at step '{failure.step}': {type(leaf).__name__}: {leaf}",
            err=True,
        )
        typer.echo(diagnose(failure.step, failure, cfg), err=True)
        raise typer.Exit(1) from failure
    if json_output:
        typer.echo(json.dumps(report, indent=2))
        _warn_version(report)
    else:
        _print_human(report)


async def _klams_version(client: Any) -> str | None:
    """Read the version off `/healthz`, or None if it can't be reached.

    klams#676: provenance is advisory. Retrieval already proves klams is
    up; failing an otherwise-good eval because the health probe hiccuped
    would trade a real signal for a label.
    """
    try:
        return (await client.healthz()).version
    except Exception:
        return None


async def run_eval(
    suite: Suite,
    cfg: Config,
    *,
    suite_path: Path,
    connect: Any = _connect,
    retriever_factory: Any = KlamsRetriever,
    now: Any = now_stamp,
) -> Report:
    """Run a suite against live klams retrieval and aggregate a report.

    #735: the run declares the eval-scoped identity when one is
    configured, so its searches land in `search_sample` under their own
    `caller` and mining can exclude them. The report stamps whatever
    identity actually went on the wire — `eval run` is where the "you
    have no distinct one" warning lives.
    """
    scoped, _ = eval_klams_config(cfg.klams)
    async with connect(scoped) as client:
        version = await _klams_version(client)
        retriever: Retriever = retriever_factory(client)
        results = await run_suite(suite, retriever)
    provenance = Provenance(
        run_at=now(),
        suite_file=suite_path.name,
        suite_hash=suite_digest(suite_path),
        klams_version=version,
        caller=scoped.agent_name,
    )
    return build_report(suite.name, results, provenance=provenance)


@eval_app.command("run")
def eval_run(
    suite_path: Annotated[Path, typer.Argument(metavar="SUITE", help="TOML query suite.")],
    json_output: Annotated[
        bool, typer.Option("--json", help="Emit the report as JSON on stdout.")
    ] = False,
    out: Annotated[
        Path | None, typer.Option(help="Also write the markdown report to this file.")
    ] = None,
    baseline: Annotated[
        Path | None,
        typer.Option(help="Report to compare provenance against (default: --out, if it exists)."),
    ] = None,
    config: Annotated[
        Path | None, typer.Option(help="Config file (default: KLAMS_MIND_CONFIG).")
    ] = None,
    debug: Annotated[bool, typer.Option(help="Re-raise failures with full tracebacks.")] = False,
) -> None:
    """Run a retrieval suite; exit 0 if there are no regressions, 1 otherwise.

    klams sprint 026 (#643): the gate keys on *regressions*, not raw
    failures. Queries marked `expect = "known_open"` are failing by
    design against tracked work (klams#628's curated-beats-bulk pair, the
    fence-chunker junk ceiling), so counting them would leave the suite
    permanently red and useless as a gate. A `known_open` query that
    starts passing is reported prominently but does not fail the run.
    """
    cfg = load_config(path=config)
    _, distinct = eval_klams_config(cfg.klams)
    if not distinct:
        # #735: not fatal, but it must not be silent — this is the state
        # that made 75% of `search_sample` the suite's own queries.
        typer.echo(
            "eval: no distinct eval identity (set KLAMS_EVAL_AGENT_NAME) — this "
            f"run's searches will be logged as caller '{cfg.klams.agent_name}', "
            "indistinguishable from real agent queries in klams' search_sample "
            "(#735)",
            err=True,
        )
    try:
        suite = load_suite(suite_path)
    except EvalLoadError as exc:
        typer.echo(f"eval: {exc}", err=True)
        raise typer.Exit(2) from exc

    # klams#676: read the artifact we are about to compare against *before*
    # `--out` overwrites it. Refreshing the baseline is the documented way
    # to regenerate, and that is exactly when "you are replacing something
    # five sprints old" is worth hearing.
    baseline_path = baseline if baseline is not None else out
    prior = _read_provenance(baseline_path)

    try:
        report = asyncio.run(run_eval(suite, cfg, suite_path=suite_path))
    except Exception as exc:
        if debug:
            raise
        typer.echo(f"eval: retrieval failed: {exc}", err=True)
        typer.echo("check klams (kubs0:7777) and the X-Homelab-Agent identity", err=True)
        raise typer.Exit(1) from exc

    if out is not None:
        # Written before `baseline` is attached: the drift note describes
        # this run, not the artifact. A refreshed baseline must not carry a
        # note about the baseline it replaced.
        out.write_text(to_markdown(report))
        typer.echo(f"wrote {out}", err=True)
    report.baseline = prior
    typer.echo(to_json(report) if json_output else to_markdown(report))
    raise typer.Exit(0 if report.regressions == 0 else 1)


async def run_pin_refresh(
    suite: Suite,
    cfg: Config,
    *,
    connect: Any = _connect,
    retriever_factory: Any = KlamsRetriever,
) -> list[PinResolution]:
    """Re-resolve the suite's `memory_id` pins against live klams."""
    scoped, _ = eval_klams_config(cfg.klams)
    async with connect(scoped) as client:
        retriever: Retriever = retriever_factory(client)
        return await resolve_pins(suite, retriever)


@eval_app.command("pins")
def eval_pins(
    suite_path: Annotated[Path, typer.Argument(metavar="SUITE", help="TOML query suite.")],
    json_output: Annotated[
        bool, typer.Option("--json", help="Emit the drift report as JSON on stdout.")
    ] = False,
    out: Annotated[
        Path | None, typer.Option(help="Also write the markdown report to this file.")
    ] = None,
    config: Annotated[
        Path | None, typer.Option(help="Config file (default: KLAMS_MIND_CONFIG).")
    ] = None,
    debug: Annotated[bool, typer.Option(help="Re-raise failures with full tracebacks.")] = False,
) -> None:
    """Re-resolve every `memory_id` pin; exit 1 if any has drifted.

    klams-mind #2247. `eval run` now follows a supersession chain, so a
    pin naming a long-dead record still passes — which is the right
    behaviour for a gate and the wrong thing to leave unsaid. This is
    the recipe that says it: which pins still name a live record, which
    have been superseded and by what, and which have no witness at all.

    Drift is not a gate failure in the CI sense — it is a fact about a
    corpus that changes with no commit in this repo — so this lives
    outside `just gate` by design. Run it when the suite feels stale,
    and after klams' corpus moves.
    """
    cfg = load_config(path=config)
    try:
        suite = load_suite(suite_path)
    except EvalLoadError as exc:
        typer.echo(f"eval pins: {exc}", err=True)
        raise typer.Exit(2) from exc

    try:
        rows = asyncio.run(run_pin_refresh(suite, cfg))
    except Exception as exc:
        if debug:
            raise
        typer.echo(f"eval pins: retrieval failed: {exc}", err=True)
        typer.echo("check klams (kubs0:7777) and the X-Homelab-Agent identity", err=True)
        raise typer.Exit(1) from exc

    if not rows:
        typer.echo(f"eval pins: {suite_path.name} has no memory_id checks", err=True)
        raise typer.Exit(0)

    if out is not None:
        out.write_text(pins_to_markdown(rows))
        typer.echo(f"wrote {out}", err=True)
    typer.echo(pins_to_json(rows) if json_output else pins_to_markdown(rows))
    raise typer.Exit(1 if drifted(rows) else 0)


def _read_provenance(path: Path | None) -> Provenance | None:
    if path is None or not path.exists():
        return None
    return parse_provenance(path.read_text())


async def run_extract(
    wins: list[str],
    cfg: Config,
    *,
    transcript: str,
    apply: bool,
    connect: Any = _connect,
    resolve_model_name: Any = _resolve_model_name,
    build_chat: Any = _build_chat,
    chain_factory: Any = build_extraction_chain,
) -> ExtractionResult:
    """Extract facts from transcript windows; write to klams when `apply`."""
    model_name = await resolve_model_name(cfg.model)
    chain = chain_factory(build_chat(cfg.model.model_copy(update={"name": model_name})))
    async with connect(cfg.klams) as client:
        author_id: str | None = None
        if apply:
            author = await client.register_author(
                agent_name=cfg.klams.agent_name,
                model=model_name,
                client_app="klams-mind",
                client_version=__version__,
            )
            author_id = str(author.author_id)
        return await extract_windows(
            wins, chain, client, transcript=transcript, apply=apply, author_id=author_id
        )


@extract_app.command("run")
def extract_run(
    transcript_path: Annotated[
        Path, typer.Argument(metavar="TRANSCRIPT", help="Claude Code JSONL session transcript.")
    ],
    apply: Annotated[
        bool, typer.Option("--apply", help="Write accepted facts to klams (default: dry-run).")
    ] = False,
    json_output: Annotated[
        bool, typer.Option("--json", help="Emit the report as JSON on stdout.")
    ] = False,
    out: Annotated[
        Path | None, typer.Option(help="Also write the markdown report to this file.")
    ] = None,
    max_windows: Annotated[
        int | None, typer.Option(help="Only process the first N windows.")
    ] = None,
    window_chars: Annotated[int, typer.Option(help="Window size budget in characters.")] = 12_000,
    config: Annotated[
        Path | None, typer.Option(help="Config file (default: KLAMS_MIND_CONFIG).")
    ] = None,
    debug: Annotated[bool, typer.Option(help="Re-raise failures with full tracebacks.")] = False,
) -> None:
    """Propose (or with --apply, write) durable facts from a session transcript."""
    cfg = load_config(path=config)
    try:
        turns = read_transcript(transcript_path)
    except TranscriptError as exc:
        typer.echo(f"extract: {exc}", err=True)
        raise typer.Exit(2) from exc
    wins = windows(turns, max_chars=window_chars)
    if max_windows is not None:
        wins = wins[:max_windows]
    if not wins:
        typer.echo("extract: transcript has no conversation content", err=True)
        raise typer.Exit(2)
    try:
        result = asyncio.run(run_extract(wins, cfg, transcript=str(transcript_path), apply=apply))
    except Exception as exc:
        if debug:
            raise
        typer.echo(f"extract: failed: {exc}", err=True)
        typer.echo(
            "check klams (kubs0:7777), kvllm (kai:8000), and the X-Homelab-Agent identity",
            err=True,
        )
        raise typer.Exit(1) from exc

    markdown = extraction_to_markdown(result)
    if out is not None:
        out.write_text(markdown)
        typer.echo(f"wrote {out}", err=True)
    typer.echo(extraction_to_json(result) if json_output else markdown)


async def run_contradict(
    query: str,
    cfg: Config,
    *,
    apply: bool,
    neighbours: int,
    top: int,
    connect: Any = _connect,
    resolve_model_name: Any = _resolve_model_name,
    build_chat: Any = _build_chat,
    chain_factory: Any = build_contradiction_chain,
) -> DetectionResult:
    """Pull a fact working set for `query`, pair by similarity, judge, file."""
    model_name = await resolve_model_name(cfg.model)
    chain = chain_factory(build_chat(cfg.model.model_copy(update={"name": model_name})))
    async with connect(cfg.klams) as client:
        hits = await client.memory_search_full(query, kinds=["fact"], top_k=top)
        seeds = [h.memory for h in hits if isinstance(h.memory, FactMemory)]
        pairs = await find_candidate_pairs(client, seeds, neighbours=neighbours)
        author_id: str | None = None
        if apply:
            author = await client.register_author(
                agent_name=cfg.klams.agent_name,
                model=model_name,
                client_app="klams-mind",
                client_version=__version__,
            )
            author_id = str(author.author_id)
        return await detect_contradictions(
            pairs, chain, client, query=query, apply=apply, author_id=author_id
        )


@contradict_app.command("run")
def contradict_run(
    query: Annotated[
        str,
        typer.Argument(help="Seed query — the fact neighbourhood to check for contradictions."),
    ],
    apply: Annotated[
        bool, typer.Option("--apply", help="File dissents for contradictions (default: dry-run).")
    ] = False,
    top: Annotated[
        int, typer.Option(help="Size of the fact working set from the seed query.")
    ] = 30,
    neighbours: Annotated[
        int, typer.Option(help="Similarity neighbours paired per seed fact.")
    ] = 5,
    json_output: Annotated[
        bool, typer.Option("--json", help="Emit the report as JSON on stdout.")
    ] = False,
    out: Annotated[
        Path | None, typer.Option(help="Also write the markdown report to this file.")
    ] = None,
    config: Annotated[
        Path | None, typer.Option(help="Config file (default: KLAMS_MIND_CONFIG).")
    ] = None,
    debug: Annotated[bool, typer.Option(help="Re-raise failures with full tracebacks.")] = False,
) -> None:
    """Detect semantic contradictions in a fact neighbourhood; propose (or --apply) dissents."""
    cfg = load_config(path=config)
    try:
        result = asyncio.run(
            run_contradict(query, cfg, apply=apply, neighbours=neighbours, top=top)
        )
    except Exception as exc:
        if debug:
            raise
        typer.echo(f"contradict: failed: {exc}", err=True)
        typer.echo(
            "check klams (kubs0:7777), kvllm (kai:8000), and the X-Homelab-Agent identity",
            err=True,
        )
        raise typer.Exit(1) from exc

    markdown = contradict_to_markdown(result)
    if out is not None:
        out.write_text(markdown)
        typer.echo(f"wrote {out}", err=True)
    typer.echo(contradict_to_json(result) if json_output else markdown)


async def run_consolidate(
    cfg: Config,
    *,
    threshold: float,
    max_pairs: int,
    top_k: int,
    since: datetime = CORPUS_START,
    now: Callable[[], datetime] = lambda: datetime.now(UTC),
    connect: Any = _connect,
    resolve_model_name: Any = _resolve_model_name,
    build_chat: Any = _build_chat,
    chain_factory: Any = build_merge_chain,
) -> ConsolidationResult:
    """Walk the knowledge corpus, pair curated near-duplicates, judge a
    capped number of them. Reads klams, never writes it."""
    model_name = await resolve_model_name(cfg.model)
    chain = chain_factory(build_chat(cfg.model.model_copy(update={"name": model_name})))
    async with connect(cfg.klams) as client:
        walked = 0
        notes = []
        async for memory in client.walk_memories(since=since, until=now(), kinds=["knowledge"]):
            walked += 1
            notes += curated([memory])
        pairs = await find_near_duplicates(client, notes, threshold=threshold, top_k=top_k)
    judged, failures = await judge_pairs(pairs, chain, max_pairs=max_pairs)
    return ConsolidationResult(
        walked=walked,
        curated=len(notes),
        threshold=threshold,
        max_pairs=max_pairs,
        candidates=len(pairs),
        judged=judged,
        judge_failures=failures,
    )


@consolidate_app.command("run")
def consolidate_run(
    threshold: Annotated[
        float, typer.Option(help="Minimum raw cosine for a candidate pair (klams' own 0.85).")
    ] = DEFAULT_THRESHOLD,
    max_pairs: Annotated[
        int, typer.Option(help="Cap on pairs sent to the model, best cosine first.")
    ] = 60,
    top_k: Annotated[
        int, typer.Option(help="Search depth per note; scanner chunks crowd the top slots.")
    ] = 30,
    json_output: Annotated[
        bool, typer.Option("--json", help="Emit the proposal as JSON on stdout.")
    ] = False,
    out: Annotated[
        Path | None, typer.Option(help="Also write the markdown proposal to this file.")
    ] = None,
    config: Annotated[
        Path | None, typer.Option(help="Config file (default: KLAMS_MIND_CONFIG).")
    ] = None,
    debug: Annotated[bool, typer.Option(help="Re-raise failures with full tracebacks.")] = False,
) -> None:
    """Propose consolidations of near-duplicate agent notes. Propose-only: no --apply."""
    cfg = load_config(path=config)
    try:
        result = asyncio.run(
            run_consolidate(cfg, threshold=threshold, max_pairs=max_pairs, top_k=top_k)
        )
    except Exception as exc:
        if debug:
            raise
        typer.echo(f"consolidate: failed: {exc}", err=True)
        typer.echo(
            "check klams (KLAMS_URL), kvllm (kai:8000), and the X-Homelab-Agent identity",
            err=True,
        )
        raise typer.Exit(1) from exc

    markdown = consolidate_to_markdown(result)
    if out is not None:
        out.write_text(markdown)
        typer.echo(f"wrote {out}", err=True)
    typer.echo(consolidate_to_json(result) if json_output else markdown)
