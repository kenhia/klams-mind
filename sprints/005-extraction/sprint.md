# 005 — extraction (propose-first, cite-or-refuse)

Memory extraction (homelab-ai WI 270, proposal korg:301): distill durable
facts from agent session logs into klams. Completes the WS1 "real
education" gate (with 004's eval work and the gen-ai-langchain track),
unblocking WS1 v0 (WI 275).

## Goal

`klams-mind extract run <transcript.jsonl>` reads a Claude Code session
transcript, proposes candidate facts with verbatim evidence, dedupes
against what klams already knows, and — only with `--apply` — writes the
survivors via `memory_add` under the klams-mind author.

## Scope

1. **Transcript reader** (`transcripts.py`): Claude Code JSONL → ordered
   user/assistant turns. Skips everything that isn't conversation: other
   line types (`mode`, `file-history-snapshot`, …), meta and sidechain
   entries, tool_use/tool_result blocks, `<command-name>` skill wrappers;
   strips `<system-reminder>` spans. Turns pack into character-bounded
   windows for the LLM.
2. **Extraction chain** (`extract/chain.py`): LangChain prompt → chat →
   JSON-array parse into `CandidateFact {text, evidence, tags}`. The
   krag lesson is enforced, not just prompted: **cite-or-refuse** means
   every candidate's `evidence` must appear verbatim (whitespace/case
   normalized) in the window it came from, checked in code — uncited
   candidates are kept in the report but can never be written.
3. **Runner** (`extract/runner.py`): per window — extract, citation-check,
   dedupe via `memory_search` (normalized containment against existing
   knowledge text; the scored envelope is available but a similarity
   threshold is deliberately deferred until the corpus teaches us one),
   then optionally `add_knowledge` with `source_path` = the transcript
   path. Propose-first: dry-run is the default, `--apply` is explicit.
4. **CLI** (`extract run`): `--apply`, `--json`, `--out report.md`,
   `--max-windows` / `--window-chars` for practical control over long
   transcripts. Errors to stderr; exit 0 on a completed run, 1 on
   operational failure, 2 on bad input.

Out of scope (roadmap "later"): scheduled runs, GHCP session logs, other
log sources.

## Acceptance

A real session log yields reviewed facts landed in klams, visible under
the klams-mind author. Target transcript:
`~/.claude/projects/-home-ken-src-ai-klams/24452a45-*.jsonl` — the klams
016/017 ship + deploy session (2026-07-08), chosen because it is recent,
single-session coherent, and dense with durable homelab facts (deploy
layout, service contracts, verification results).

## Decisions & surprises

- **Markup-insensitive citation matching.** The first live run refused
  9 of 13 candidates as uncited — but 8 of the 9 evidence quotes were
  verbatim in their windows. The model copies the *words* faithfully
  and drops markdown markup (backticks, `**`, smart quotes) while
  quoting. `_normalize` now strips markup from both sides before the
  containment check; the words themselves still have to match. The 9th
  refusal was the gate working as designed.
- **Tool noise dominates transcripts.** The 867 KB acceptance
  transcript reduced to 69 conversation turns / 3 windows (~24 KB)
  once tool_use/tool_result blocks, skill bodies, sidechains, and
  system reminders were stripped.
- **Acceptance run** (klams 016/017 ship + deploy session,
  2026-07-08): dry-run proposed 13/13 cited candidates; all reviewed
  accurate; `--apply` wrote 13 under the klams-mind author (tagged
  `session-extract`, `source_path` = the transcript); the written fact
  ranks first on `memory_search` for its own text (score 0.928); an
  immediate dry-run re-run flagged 13/13 as duplicates — the
  propose → apply → dedupe loop closes.
