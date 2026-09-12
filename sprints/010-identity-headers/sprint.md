# Sprint 010 — identity headers for `klams-mind` and `klams-mind-eval`

Proposal: korg:2423 (slice 4 of program korg:2440, "Simplify homelab
secrets"). Covers WI 2398; dissolves WI 2257.

## Goal

klams-mind stops presenting bearer tokens to klams and declares who it
is instead: `X-Homelab-Agent: klams-mind` on the ordinary path, and
`X-Homelab-Agent: klams-mind-eval` for an `eval run`. No klams token
remains in klams-mind's config, its env file, or its code.

## Why the shape changed under us

WI 2257 asked for a second read-scoped grant to be *minted* and
*registered in krot*. Under program korg:2440 (Ken, 2026-09-11) neither
half survives: klams grants became `[[auth.identities]]` rows keyed on a
declared name, and krot stopped registering MCP-service identities at
all. So 2257 is not work — it is a row that now exists — and it closes
against this sprint.

## Premise check (start-sprint Step 5)

Verified on kubs0, which is also the host that runs klams-mind — the
probe and the work are on the same machine.

- **klams accepts the header.** `crates/klams-api/src/auth.rs` declares
  `AGENT_HEADER = "x-homelab-agent"` and resolves it against
  `[[auth.identities]]` ahead of the bearer path; klams 0.1.49 is
  deployed and live. Upstream slice korg:2419 is `done`.
- **Both identity rows exist** in `/etc/klams/klams.toml`: `klams-mind`
  with `read`/`write`, `klams-mind-eval` with `read` alone.
- **Live probe**, `GET /v1/memories?limit=1` against `localhost:7777`:
  `klams-mind` → 200, `klams-mind-eval` → 200, an unknown name → 401,
  no header → 401. The header is genuinely what authenticates, and a
  wrong name fails closed.
- **The transition window is still open**, so bearer callers are not
  broken by this sprint and this sprint is not broken by ordering —
  klams closes the window in slice korg:2450, after all four clients.

Verdict for WI 2398: **premise holds**, and 2257's remaining half is
already satisfied by the row being present.

## Decisions

- **`token` and `eval_token` are deleted, not deprecated.** Keeping a
  bearer path alive would be dead code the moment korg:2450 deletes the
  `[[auth.tokens]]` table, and the program's whole point is that the
  name is the credential. `KLAMS_TOKEN` and `KLAMS_EVAL_TOKEN` stop
  being read.
- **`eval_klams_config`'s `(config, distinct)` contract survives**, and
  so does its deliberate non-fatal fallback — an eval that refuses to
  run measures nothing (#735). What changes is the swap: it substitutes
  `agent_name`, not `token`, and `distinct` now means "the eval declares
  a name of its own".
- **`_MAIN_AGENT_NAME` goes away in favour of `cfg.klams.agent_name`.**
  The constant and the wire identity were two sources for one fact kept
  in step by a comment; now that the declared name *is* the credential,
  `register_author` reads the same field the header carries.

## What shipped

- **`KlamsConfig` holds no secret.** `token` and `eval_token` are gone;
  `agent_name` (default `klams-mind`) and `eval_agent_name` (default
  `klams-mind-eval`) replace them. `KLAMS_TOKEN` and `KLAMS_EVAL_TOKEN`
  are no longer read; `KLAMS_AGENT_NAME` joins `KLAMS_EVAL_AGENT_NAME`
  as the env override. A config file still carrying a stale `token`
  loads fine and ignores it — pinned by a test, since every existing
  install has one.
- **`connect()` sends `X-Homelab-Agent`**, never `Authorization`. An
  empty `agent_name` sends no header rather than declaring `""`: klams
  answers 401 either way, and an omission is honest where a blank claim
  is not.
- **`eval_klams_config` swaps the name**, keeping its `(config,
  distinct)` contract and its non-fatal fallback. `distinct` now means
  the eval declares a name of its own.
- **`_MAIN_AGENT_NAME` deleted** — `register_author` and the wire
  identity now read one field instead of a constant and a comment
  asking someone to keep them equal.
- **Diagnosis follows.** A 401/403 now names the identity it declared
  and points at `[[auth.identities]]`, instead of blaming a token that
  no longer exists.
- Docs: `README.md`, `config.example.toml`, the `live` pytest marker
  (which gated on `KLAMS_TOKEN` being set and would have skipped
  forever), and the live round-trip test.

### The one behaviour change worth naming

The distinct eval identity used to be **opt-in** — it needed a token
minted, so the default was to fall back and warn, and sprint 009 shipped
that warning firing. It is now **on by default**, because a name costs
nothing; opting out takes `eval_agent_name = ""`. The warning still
exists for that case. `test_run_eval_stamps_the_klams_version_and_suite_digest`
changed its expected `caller` accordingly, and a companion test pins the
opted-out side.

## Verification

All on kubs0, the host that runs klams-mind and klams both.

- `just gate` green: 179 passed, 1 skipped.
- `just smoke` passes with **no klams token anywhere** — not in the
  environment, not in `.env`, not in the code.
- `uv run klams-mind eval run evals/suites/homelab-retrieval.toml`:
  26/27, 0 regressions, `- **Caller:** klams-mind-eval`. Unchanged from
  the 0.1.49 baseline, so the identity swap cost no retrieval quality.
- **The acceptance criterion at the source of truth, not the report
  stamp.** `search_sample` over the last 20 minutes:
  `klams-mind-eval` 27, `kyac` 8, `klams-mind` 2 — the eval run's 27
  queries and smoke's 2 searches, separated. #735's mining recipe
  (`caller NOT IN (eval identities)`) now works on live rows.
- `.env` on kubs0: `KLAMS_TOKEN` deleted through kaed (txn 78). What
  remains is `KLAMS_MIND_MODEL_URL` and `KLAMS_URL`, neither secret.

WI 2257 is satisfied without work: the `klams-mind-eval` row exists in
`/etc/klams/klams.toml` with `scopes = ["read"]`, nothing was minted,
and krot registers no MCP-service identity.

## Repaired in passing

- **The roadmap's queue number.** It penciled `010 — Consolidation`,
  and this sprint took 010 — the third time an unplanned sprint has
  consumed the number consolidation was waiting on. Consolidation is
  now 011, the header note says why, and the charter line calling
  klams-mind a client with "own scoped token" is corrected to the
  declared identity.

## Noted, not repaired

- Reading `/etc/klams/klams.toml` to verify the identity rows put the
  **klams Postgres URL, password included, into this session's
  transcript** — a `grep` whose redaction pattern did not match the
  URL form. The value did not leave kubs0 and the database is bound to
  127.0.0.1, so this is not an exposure, but it is exactly what the
  program's "nothing prints a value, ever" rule exists to prevent, and
  the file is outside every kaed root so the classified-read path that
  would have sealed it was unavailable. Flagged to the overseer rather
  than repaired: whether that warrants rotating the klams DB password,
  or bringing `/etc/klams/` into a kaed root, is a program decision.
