"""klams-mind CLI. Errors go to stderr, results to stdout, `--json`
for programmatic use; exit 0 on success, 1 on failure.
"""

import asyncio
import json
import logging
from pathlib import Path
from typing import Annotated, Any

import typer

from klams_mind import __version__
from klams_mind.config import Config, load_config
from klams_mind.eval.report import Report, build_report, to_json, to_markdown
from klams_mind.eval.runner import KlamsRetriever, Retriever, run_suite
from klams_mind.eval.suite import EvalLoadError, Suite, load_suite
from klams_mind.klams import connect as _connect
from klams_mind.llm import build_chat as _build_chat
from klams_mind.llm import ping
from klams_mind.llm import resolve_model_name as _resolve_model_name

app = typer.Typer(help="LLM-smart memory companion to klams.")
eval_app = typer.Typer(help="Retrieval-quality evals against klams.")
app.add_typer(eval_app, name="eval")


class SmokeError(Exception):
    def __init__(self, step: str, cause: Exception) -> None:
        super().__init__(f"step '{step}' failed: {cause}")
        self.step = step


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
            }

            step = "register author"
            author = await client.register_author(
                agent_name="klams-mind",
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
            hits = await client.memory_search(query, top_k=3)
            report["search"] = {
                "query": query,
                "hits": len(hits),
                "top": [{"kind": h.kind, "id": str(h.id)} for h in hits],
            }

        step = "LLM call"
        chat = build_chat(cfg.model.model_copy(update={"name": model_name}))
        report["model"]["reply"] = ping(chat)
    except Exception as exc:
        raise SmokeError(step, exc) from exc

    report["ok"] = True
    return report


def _print_human(report: dict[str, Any]) -> None:
    klams, author = report["klams"], report["author"]
    search, model = report["search"], report["model"]
    typer.echo(f"klams   {klams['status']} (v{klams['version']}) at {klams['url']}")
    typer.echo(f"author  {author['agent_name']} {author['author_id']}")
    typer.echo(f'search  "{search["query"]}" -> {search["hits"]} hit(s)')
    typer.echo(f"model   {model['name']} at {model['endpoint']} -> {model['reply']!r}")
    typer.echo("smoke: all steps passed")


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
        typer.echo(f"smoke failed at {failure}", err=True)
        typer.echo(
            "check klams (kubs0:7777), kvllm (kai:8000), and KLAMS_TOKEN",
            err=True,
        )
        raise typer.Exit(1) from failure
    if json_output:
        typer.echo(json.dumps(report, indent=2))
    else:
        _print_human(report)


async def run_eval(
    suite: Suite,
    cfg: Config,
    *,
    connect: Any = _connect,
    retriever_factory: Any = KlamsRetriever,
) -> Report:
    """Run a suite against live klams retrieval and aggregate a report."""
    async with connect(cfg.klams) as client:
        retriever: Retriever = retriever_factory(client)
        results = await run_suite(suite, retriever)
    return build_report(suite.name, results)


@eval_app.command("run")
def eval_run(
    suite_path: Annotated[Path, typer.Argument(metavar="SUITE", help="TOML query suite.")],
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
    """Run a retrieval suite; exit 0 if every check passes, 1 if any fails."""
    cfg = load_config(path=config)
    try:
        suite = load_suite(suite_path)
    except EvalLoadError as exc:
        typer.echo(f"eval: {exc}", err=True)
        raise typer.Exit(2) from exc
    try:
        report = asyncio.run(run_eval(suite, cfg))
    except Exception as exc:
        if debug:
            raise
        typer.echo(f"eval: retrieval failed: {exc}", err=True)
        typer.echo("check klams (kubs0:7777) and KLAMS_TOKEN", err=True)
        raise typer.Exit(1) from exc

    markdown = to_markdown(report)
    if out is not None:
        out.write_text(markdown)
        typer.echo(f"wrote {out}", err=True)
    typer.echo(to_json(report) if json_output else markdown)
    raise typer.Exit(0 if report.failed == 0 else 1)
