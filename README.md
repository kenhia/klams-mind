# klams-mind

> **Disclaimer:** Like its sibling [klams](../klams), this project is
> purpose-built for Ken's homelab (`kubs0`, `kai`, the klams memory
> service, the kvllm serving stack). It is not intended as a
> general-purpose system.

## What it is

`klams-mind` is the LLM-smart companion to **klams**, Ken's homelab
memory service. klams owns storage, retrieval, attribution, trust, and
the MCP surface; klams-mind supplies the intelligence that klams
deliberately keeps out of its core:

- **Memory extraction** — distill durable facts from agent session
  logs and conversations, written back via `memory_add` with proper
  attribution.
- **Semantic contradiction detection** — find memories that contradict
  each other in meaning (not just trust-rank conflicts on the same
  fact) and propose dissents for human resolution in the klams
  viewport.
- **Consolidation** — periodic merge/summarize/prune passes over aging
  memories, guided by klams's decay signals.
- **Retrieval-quality evals** — TOML-defined query suites run against
  `memory_search`, so retrieval changes are measured, not vibes.

Built on Python 3.12+, [uv](https://docs.astral.sh/uv/) + ruff (Astral
tooling), LangChain for orchestration, and vLLM (OpenAI-compatible
serving) for model access. klams-mind is a **client** of klams — it
talks MCP/REST to `kubs0:7777` and never touches klams's
Postgres/Qdrant directly.

## Status

First light: the vertical slice works end to end. See
[sprints/planning/roadmap.md](sprints/planning/roadmap.md) for the
sprint queue; the keep-klams / build-klams-mind decision record lives
in the klams repo at `sprints/planning/wi259-recommendation.md`.

## Usage

```sh
uv run klams-mind smoke          # prove the plumbing end to end
uv run klams-mind smoke --json   # same, machine-readable
```

`smoke` health-checks klams, registers the `klams-mind` author, runs
one memory search, and makes one LLM call through the configured
endpoint. Exit 0 means all four legs work.

### Configuration

Defaults target the homelab (klams at `kubs0:7777`, kvllm at
`kai:8000/v1`, model name auto-discovered from `/models`). To override,
copy [config.example.toml](config.example.toml) to
`~/.config/klams-mind/config.toml` (or point `KLAMS_MIND_CONFIG` at a
file). Environment variables beat the file: `KLAMS_URL`, `KLAMS_TOKEN`,
`KLAMS_MIND_MODEL_URL`, `KLAMS_MIND_MODEL_NAME`,
`KLAMS_MIND_MODEL_API_KEY`. A `./.env` is auto-loaded (real environment
variables still win), so dropping `KLAMS_TOKEN=...` in `.env` is enough
for live runs — `.env` is gitignored; keep the token out of the repo.
The klams token is required for anything beyond `/healthz`.

Note: klams exposes `register_author` / `memory_search` / `memory_add`
only as MCP tools (Streamable HTTP at `{KLAMS_URL}/mcp`), not REST —
the client wraps them via the official `mcp` SDK.

## Development

```sh
uv sync          # create/refresh the venv
just --list      # discover recipes
just gate        # fmt-check + lint + typecheck + tests (what CI runs)

# live tests (skipped otherwise) need the real service:
KLAMS_URL=http://kubs0:7777 KLAMS_TOKEN=... uv run pytest -m live
```

Workflow, principles, and the sprint convention are in
[AGENTS.md](AGENTS.md).

## License

[MIT](LICENSE)
