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
unreachable (with the URL it actually tried), the declared identity
rejected (named, with the HTTP status), or a response it could not parse (which is what
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

**Eval-run identity.** An `eval run` declares `klams-mind-eval` instead
of `klams-mind` (override with `KLAMS_EVAL_AGENT_NAME`), matching a
second, **read-scoped** `[[auth.identities]]` row in klams. klams logs a
search's `caller` from the declared identity, not from
`register_author`, so a distinct name is the only way to keep eval
traffic out of the pool that gets mined for new eval queries — otherwise
the suite is fed its own golden queries. It is on by default because it
costs nothing: opting *out* is what takes a config line
(`eval_agent_name = ""`), and a run that has opted out says so on
stderr. Every report stamps the `Caller` it ran as.

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
file). Environment variables beat the file: `KLAMS_URL`,
`KLAMS_AGENT_NAME`, `KLAMS_EVAL_AGENT_NAME`, `KLAMS_MIND_MODEL_URL`,
`KLAMS_MIND_MODEL_NAME`, `KLAMS_MIND_MODEL_API_KEY`. A `./.env` is
auto-loaded (real environment variables still win), and is gitignored.

**klams-mind holds no klams credential.** It authenticates by declaring
who it is — `X-Homelab-Agent: klams-mind` — and klams matches that name
against an `[[auth.identities]]` row that carries the scopes. A name
klams does not know is a 401; there is no token to leak, rotate, or
register. (Homelab program korg:2440, sprint 010.)

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

#### The tested version range

klams-mind now says which klams versions it has actually been exercised
against, rather than waiting for a parse failure to imply it.
`TESTED_KLAMS_MIN`/`TESTED_KLAMS_MAX` in `klams_mind/klams.py` bound the
range, and `smoke` warns on stderr — in both human and `--json` mode —
when the klams it just health-checked falls outside it:

```
warning: klams is 0.1.53, newer than the 0.1.46-0.1.52 this client was
tested against — run `just gate-live` to check the contract, then bump
TESTED_KLAMS_MAX
```

The floor is not decoration: the compact envelope landed in klams
0.1.46, so an *older* klams breaks this client as surely as a newer one.

The ceiling is maintained by `just gate-live`, which asserts it after
its contract assertions have passed — so a newer klams fails that gate
saying "the round-trip passed at X; bump this", and the range can never
quietly become a claim nobody re-checked.

## Development

```sh
uv sync          # create/refresh the venv
just --list      # discover recipes
just gate        # fmt-check + lint + typecheck + tests — the single gate
just check       # alias for `gate`, the name the kproject harness uses
just gate-live   # the contract tier: the klams round-trip, against real klams
just smoke       # check the live klams + kvllm plumbing (not in the gate)
```

### Two test tiers

Every klams-facing test in `just gate` fakes the MCP transport by
injecting a tool-caller, so the suite validates klams-mind against
klams-mind's *own idea* of the klams contract. That is fast and it is
also a blind spot: when klams sprint 046 changed `memory_search`'s
envelope, this repo broke completely — smoke, evals, extraction's
duplicate check, contradiction pairing — and the gate stayed green
across sixteen klams versions. It was found by a human happening to run
`smoke`.

So the round-trip that talks to a real klams is its own tier:

| Recipe | Marker | Talks to klams | Run it |
|---|---|---|---|
| `just gate` | `-m "not live"` | no | every commit |
| `just gate-live` | `-m live` | yes | where klams is reachable, and after deploying either side |

`gate-live` **fails** when klams is unreachable — it is deliberately not
a `skipif`, because a skip cannot fail, and a contract gate that reports
`1 skipped, exit 0` is the same silent green this tier exists to remove.

It takes its URL from the ordinary config chain, so a checkout on kubs0
works with nothing exported; `KLAMS_URL=http://localhost:7777 just
gate-live` still wins.

**The live tier is local-only, by nature rather than by policy.** klams
runs on kubs0 and is reachable over the tailnet, so no GitHub-hosted
runner could ever reach it — `gate-live` belongs in the deploy/verify
path on a homelab host, not in a hosted CI workflow. (This repo has no
GitHub Actions workflow at all today; `just gate` is the single gate
definition, run before every commit.)

Workflow, principles, and the sprint convention are in
[AGENTS.md](AGENTS.md). The repo is on the
[kproject harness](https://github.com/kenhia/kprojects), which manages a
marked block in `CLAUDE.md` and `.github/copilot-instructions.md` —
AGENTS.md stays the authority on repo specifics.

## License

[MIT](LICENSE)
