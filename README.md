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
just smoke                       # prove the plumbing end to end
just smoke --json                # same, machine-readable
uv run klams-mind smoke          # the same thing, without just
```

`smoke` health-checks klams, registers the `klams-mind` author, runs
one memory search, and makes one LLM call through the configured
endpoint. Exit 0 means all four legs work.

When a leg fails, `smoke` names the leaf cause and what to do about it
rather than the `ExceptionGroup` the MCP client wrapped it in — klams
unreachable (with the URL it actually tried), `KLAMS_TOKEN` rejected
(with the HTTP status), or a response it could not parse (which is what
klams/klams-mind contract drift looks like). No `--debug` needed. If the
URL's host is this machine, it also points at the loopback override,
because the homelab default `http://kubs0:7777` does not work *on*
kubs0: the name resolves to 127.0.1.1 while klams binds 127.0.0.1 and
the tailnet address.

### Retrieval evals

```sh
uv run klams-mind eval run evals/suites/homelab-retrieval.toml
uv run klams-mind eval run <suite> --json               # machine-readable
uv run klams-mind eval run <suite> --out report.md      # also write markdown
uv run klams-mind eval run <suite> --baseline old.md    # compare provenance, don't overwrite
```

A suite is a TOML file of queries, each with retrieval checks run against
klams `memory_search` (deterministic — no LLM in the loop):

- `substring` — expected text appears in retrieved content (content recall)
- `source_cited` — expected source/tag appears among the hits (source recall)
- `no_hallucination` — a forbidden fragment is *absent* from all hits (precision)
- `no_duplicates` — no two hits share a `content_hash`
- `min_body_chars` — no hit's body (breadcrumb stripped) is below a floor
- `memory_id` — a specific memory id is retrieved, optionally within `max_rank`

Eval runs ask klams for **whole memory texts** (`full: true`), which
klams documents as the path for "callers that genuinely want bodies in
bulk (eval harnesses, exports)". That is deliberate: half these checks
assert on a body, and the default compact response carries a ≤320-char
match-window snippet instead. See "The klams search contract" below.

**Eval-run identity.** Set `KLAMS_EVAL_TOKEN` to a second, read-scoped
klams grant whose `[[auth.tokens]].agent_name` is the eval suite's own
(`klams-mind-eval` by default; override with `KLAMS_EVAL_AGENT_NAME`).
klams logs a search's `caller` from the *token's* grant, not from
`register_author`, so a distinct token is the only way to keep eval
traffic out of the pool that gets mined for new eval queries — otherwise
the suite is fed its own golden queries. The run works without one and
says so on stderr; every report stamps the `Caller` it ran as.

Exit code is **0** if every check passes, **1** if any check fails, **2**
for a bad suite file — so CI can gate on it. Reports list every hit with
its relevance score, kind, and pre-fusion source rank (klams ≥ 016 scored
envelopes; scores are only comparable within a kind). Suites live in
[evals/suites/](evals/suites/); a committed baseline report is in
[evals/baselines/](evals/baselines/) as the retrieval regression bar.

Every report — markdown and JSON — is stamped with **when** it ran, the
**klams version** it ran against, and the **suite file + content hash**,
so a baseline can never again be five sprints stale without saying so.
If the baseline it's compared against records a different klams version,
the report says so in one line; that is informational and never fails a
run. `--baseline` names the artifact to compare against explicitly;
otherwise an existing `--out` file is used (read before it's overwritten,
so refreshing a baseline still tells you what you're replacing). The
refreshed artifact never carries the drift note — it describes the run,
not the file.

Refreshing the baseline stays a deliberate act. Regenerate with:

```sh
uv run klams-mind eval run evals/suites/homelab-retrieval.toml \
  --out evals/baselines/homelab-retrieval.md
```

> The repo-root [.klamsignore](.klamsignore) keeps `evals/` out of the
> klams corpus. Without it the suite is indexed into the very corpus it
> queries, wins its own queries on lexical overlap, and each refreshed
> baseline contaminates the next run. See
> [sprints/007-eval-provenance/](sprints/007-eval-provenance/).

### Memory extraction

```sh
uv run klams-mind extract run <session.jsonl>          # dry-run: propose only
uv run klams-mind extract run <session.jsonl> --apply  # write accepted facts
uv run klams-mind extract run <session.jsonl> --json --out report.md
```

Reads a Claude Code JSONL session transcript, strips harness noise
(tool calls, skill bodies, system reminders), and asks the model for
durable facts, each carrying a verbatim evidence quote. **Cite or
refuse is enforced in code**: evidence not found in the source window
(markup-insensitive match) marks the candidate `uncited` and it is
never written. Candidates klams already knows (normalized containment
via `memory_search`) are flagged `duplicate`. Dry-run is the default;
`--apply` writes the survivors via `memory_add` under the klams-mind
author, tagged `session-extract` with `source_path` = the transcript.

### Contradiction detection

```sh
uv run klams-mind contradict run "<seed query>"          # dry-run: propose only
uv run klams-mind contradict run "<seed query>" --apply   # file dissents
uv run klams-mind contradict run "<seed query>" --json --out report.md
uv run klams-mind contradict run "<seed query>" --top 30 --neighbours 5
```

Finds facts that contradict **in meaning** — the same service on two
hosts, one setting given two incompatible values — which klams's
write-time trust check (same-fact only) can't catch. The seed query
pulls a working set of facts; each is paired with its embedding-
similarity neighbours (via `memory_search`, kind `fact`) so the corpus
is never compared O(n²). A **refute-by-default** judge rules on each
pair: only genuine mutual exclusivity counts, and a claimed
contradiction with no concrete, object-shaped correction is
`unactionable` — refused, never filed. Dry-run is the default;
`--apply` files a dissent via the klams MCP `dissent_propose` tool
against the fact judged wrong (citing the conflicting one), under the
klams-mind author. Dissents land as lowest-trust proposals and are
resolved by a human in the viewport `/dissents` page.

### Configuration

Defaults target the homelab (klams at `kubs0:7777`, kvllm at
`kai:8000/v1`, model name auto-discovered from `/models`). To override,
copy [config.example.toml](config.example.toml) to
`~/.config/klams-mind/config.toml` (or point `KLAMS_MIND_CONFIG` at a
file). Environment variables beat the file: `KLAMS_URL`, `KLAMS_TOKEN`,
`KLAMS_EVAL_TOKEN`, `KLAMS_EVAL_AGENT_NAME`, `KLAMS_MIND_MODEL_URL`,
`KLAMS_MIND_MODEL_NAME`, `KLAMS_MIND_MODEL_API_KEY`. A `./.env` is auto-loaded (real environment
variables still win), so dropping `KLAMS_TOKEN=...` in `.env` is enough
for live runs — `.env` is gitignored; keep the token out of the repo.
The klams token is required for anything beyond `/healthz`.

Note: klams exposes `register_author` / `memory_search` / `memory_add`
only as MCP tools (Streamable HTTP at `{KLAMS_URL}/mcp`), not REST —
the client wraps them via the official `mcp` SDK.

### The klams search contract

klams sprint 046 (WI #1178) made `memory_search` **compact by default**:
each hit carries a match-window `snippet` of at most 320 characters plus
a locator, and the response ends with
`more: {"fetch": "memory_get", "truncated": …}`. The motive is measured
— 9,599 → 4,193 tokens per answered query, counting the follow-up read
when a snippet fell short. Typed metadata (`source_path`, `heading_path`,
`repo`, fact `type`, event `category`, `copies`) is omitted where it does
not apply rather than faked, so those fields are all optional.

klams-mind mirrors the distinction in two methods rather than a flag
with a union return type:

| Method | Returns | For |
|---|---|---|
| `memory_search` | `SearchResponse` — `hits: list[CompactHit]`, `more` | The ordinary agent path. `smoke` uses it deliberately, so the health check exercises the shape agents receive. |
| `memory_search_full` | `list[ScoredMemory]` — bodies inline | Callers that assert on a body or a fact payload: the eval suite, extraction's duplicate check, contradiction pairing. |
| `memory_get(id)` | `Memory` | The single-record follow-up `more.fetch` names. |

If klams-mind ever raises `ValidationError` out of a search, suspect
this contract first: it is what a version skew between the two projects
looks like. `smoke` says so in as many words.

## Development

```sh
uv sync          # create/refresh the venv
just --list      # discover recipes
just gate        # fmt-check + lint + typecheck + tests (what CI runs)
just check       # alias for `gate`, the name the kproject harness uses
just smoke       # check the live klams + kvllm plumbing (not in the gate)

# live tests (skipped otherwise) need the real service:
KLAMS_URL=http://localhost:7777 KLAMS_TOKEN=... uv run pytest -m live
```

Workflow, principles, and the sprint convention are in
[AGENTS.md](AGENTS.md). The repo is on the
[kproject harness](https://github.com/kenhia/kprojects), which manages a
marked block in `CLAUDE.md` and `.github/copilot-instructions.md` —
AGENTS.md stays the authority on repo specifics.

## License

[MIT](LICENSE)
