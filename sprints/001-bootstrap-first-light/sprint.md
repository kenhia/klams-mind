# Sprint 001 — Bootstrap & first light

**Branch:** `001-bootstrap-first-light`  
**Started:** 2026-07-06  
**Status:** Done — smoke passes live against kubs0 + kai; gate green

## Goal

Prove the full plumbing with the thinnest possible vertical slice:
config → klams client → LLM endpoint → CLI, all exercised by one
`klams-mind smoke` command against live kubs0 (klams) and kai (kvllm).

## Scope

1. **Config** (`klams_mind.config`): klams base URL + token, model
   endpoint(s) + names. TOML file with env-var overrides; secrets never
   committed.
2. **klams client** wrapping only the REST surface needed now:
   `register_author`, `memory_search`, `memory_add`, `/healthz`. Typed
   responses (pydantic), tested against recorded fixtures; live
   round-trip test marked and skipped without `KLAMS_URL`.
3. **LangChain + OpenAI-compatible chat** (`langchain-openai` pointed
   at kvllm): one trivial chain proving model access.
4. **CLI entry** (`klams-mind smoke`): health-check klams, register
   author, run one search, one LLM call; human-readable output plus
   `--json`.

Out of scope: extraction, evals, contradiction detection, any MCP
transport (REST only for now), scheduled operation.

## Acceptance criteria

- `klams-mind smoke` passes against live kubs0 + kvllm.
- `just gate` green (format, lint, ty, pytest).
- Deps added this sprint are each justified below.

## Dependencies added

| Dependency | Why |
|------------|-----|
| `httpx` | HTTP client for the klams REST surface; sync API, timeouts, testable via transport injection. |
| `pydantic` | Typed request/response models for the klams client and config validation. |
| `langchain-core` | Chain/prompt primitives; also provides fake chat models for offline tests. |
| `langchain-openai` | `ChatOpenAI` against OpenAI-compatible endpoints (kvllm) — the chosen orchestration layer per charter. |
| `typer` | CLI entry point with minimal boilerplate; stderr/stdout separation and exit codes come cheap. |
| `mcp` | **Unplanned.** klams exposes `register_author`/`memory_search`/`memory_add` only as MCP tools, not REST (see chronicle). Official SDK beats hand-rolling Streamable HTTP JSON-RPC + SSE parsing. |
| `pytest-asyncio` (dev) | The `mcp` SDK is async-only, so the client and its tests are async. |

## Chronicle

- **2026-07-06** — Sprint opened from roadmap queue entry. Scouted the
  klams repo for the exact contract before writing the client.
- **Contract surprise: the needed surface is MCP, not REST.** Of the
  four operations, only `/healthz` is a REST route. `register_author`,
  `memory_search`, and `memory_add` exist solely as MCP tools mounted
  at `{base_url}/mcp` (rmcp Streamable HTTP, same bearer auth). klams's
  REST routes (`POST /memory/search`, `POST /memory/facts`, …) have
  *different* request/response shapes than the MCP tools. Decision:
  wrap the MCP tools via the official `mcp` Python SDK — they match the
  roadmap contract names and the shapes klams documents as canonical.
  Consequence: the client is async, `pytest-asyncio` added.
- **`register_author` is not idempotent** — every call mints a new
  author row (no uniqueness on `agent_name` in klams). The documented
  pattern is register-once-per-session and reuse the `author_id`;
  `smoke` registers per run, which is a session by that definition.
  A persistent klams-mind identity is a klams sprint 015 concern
  (scoped token + `agent_name = "klams-mind"` grant); until then live
  runs use the legacy full-scope token via `KLAMS_TOKEN`.
- **Model name auto-discovery.** kvllm serves one model at a time and
  Ken switches it by registry key (`just service-switch`), so a
  hardcoded default model name would go stale. `model.name = "auto"`
  (the default) resolves the served model via `GET /v1/models` at run
  time — at first light the live answer was `gemma-4-31b-it-awq`, not
  the qwen key kvllm's example env suggests.
- **Cosmetic wart silenced:** klams (rmcp) answers the MCP session-close
  DELETE with `202`; the `mcp` SDK logs a spurious "Session termination
  failed: 202" warning. The CLI drops that logger to ERROR.
- **First light (live, 2026-07-06):** `klams-mind smoke` → klams `Ok`
  (v0.1.0), author registered under `klams-mind`, 3 hits for "homelab
  machines and services", and `gemma-4-31b-it-awq` replied `pong`.
  The live round-trip test (`pytest -m live`) also passed: added a
  knowledge memory tagged `["klams-mind", "smoke-test"]` and found it
  again via `memory_search`. Test-data memories carry the `smoke-test`
  tag so they're easy to review/prune.

## Outcome

Acceptance criteria met: smoke passes live against kubs0 + kvllm
(human and `--json` output, exit 0); `just gate` green (20 tests
passing offline, 1 live test env-gated); all deps justified above.
Modules: `config` (TOML + env), `klams` (typed MCP/REST client),
`llm` (LangChain chat + model discovery), `cli` (typer entry).
