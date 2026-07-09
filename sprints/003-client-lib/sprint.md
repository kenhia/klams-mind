# 003 — consume kvllm-client

Final slice of the WS5 shared-client extraction (homelab-ai WI 274, proposal
korg:298): klams-mind was the third copy of the ChatOpenAI + `/v1/models`
auto-discovery pattern; kvllm sprint 13 extracted it into `kvllm-client`
(the `client/` distribution in the kvllm repo), kmon and kagent converted,
and this sprint retires the last private copy.

## What changed

- `src/klams_mind/llm.py`: `build_chat` and `resolve_model_name` keep their
  exact signatures (the config-shaped seam stays klams-mind's) but delegate
  to `kvllm_client.local_model` / `aresolve_model`. `ping` stays local — it's
  a klams-mind smoke helper, not client mechanics. The async discovery +
  injectable `httpx.AsyncClient` pattern in the lib came FROM this repo, so
  the delegation is nearly 1:1.
- `pyproject.toml`: `langchain-openai` replaced by
  `kvllm-client @ git+ssh://git@github.com/kenhia/kvllm.git#subdirectory=client`.
  `httpx`/`langchain-core` stay (imported directly). No `[anthropic]` extra —
  klams-mind has no escalation tier.
- Lock pins the lib to a kvllm commit; bump with
  `uv lock --upgrade-package kvllm-client`.

Behavior nit worth recording: `build_chat` on a cfg still carrying
`name="auto"` now sync-discovers instead of constructing a chat bound to the
literal string "auto" — the old behavior was a latent bug; the CLI always
resolves first, so no caller sees a difference.

## Untouched on purpose

- `tests/test_llm.py` — byte-for-byte, 4/4 pass (20 passed, 1 skipped total).
- The pending `sprints/planning/001-cross-project-note.md` (klams
  `memory_search` scored-hit envelope) — that's eval-runner work coupled to a
  klams deploy, deliberately not folded into a client-lib swap.
