# Retrieval eval — homelab-retrieval

- **Run:** 2026-07-26T18:39:22Z
- **klams version:** 0.1.29
- **Suite file:** `homelab-retrieval.toml` (`sha256:f24298a71e97`)

**OK — 19/21 queries passed (90%).**

0 regression(s), 2 known-open, 0 newly fixed.

## Checks by type

| Check | Passed |
| --- | --- |
| `memory_id` | 5/7 |
| `min_body_chars` | 2/2 |
| `no_duplicates` | 3/3 |
| `no_hallucination` | 2/2 |
| `source_cited` | 2/2 |
| `substring` | 11/11 |

## Known open (2)

Failing by design — tracked work, not a regression.

- **klams korg tools not available ToolSearch deferred lazily loaded** — sprint 030 reranker (korg:686) — post-029 the gotcha sits at rank 1 behind its SIBLING curated gotcha (019f9a36-e558, same topic); curated-beats-bulk now holds, intra-curated ordering is the reranker's job (or consolidate the two gotchas via memory_supersede and retarget)
  - ✗ `memory_id` `019f95dc-df08` — 019f95dc-df08 surfaced at rank 1, above the max_rank 0 — it is being outranked
- **rpidash3 raspberry pi machine specs** — sprint 030 reranker (korg:686) — post-029 the specs record sits at rank 1 behind the hand-authored 'rpidash3 joined the fleet' memory (019f9c03-8d25); same tier, ranking cannot separate them
  - ✗ `memory_id` `019f9a83-68bc` — 019f9a83-68bc surfaced at rank 1, above the max_rank 0 — it is being outranked

## Queries

- ✓ **what container image does the klams service use** — 5 hit(s)
  - `0.016` knowledge r0 — /home/ken/.claude/projects/-home-ken-src-ai-klams/24452a45-60b8-45f6-813c-b62aa79ea18e.jsonl
  - `0.016` knowledge r1 — /home/ken/src/ai/klams/deploy/docker-compose.yml
  - `0.016` knowledge r2 — /home/ken/src/ai/klams/deploy/install-systemd.sh
  - `0.016` knowledge r3 — /home/ken/.claude/projects/-home-ken-src-ai-klams/24452a45-60b8-45f6-813c-b62aa79ea18e.jsonl
  - `0.015` knowledge r4 — /home/ken/src/ai/klams/docs/architecture.md
- ✓ **what host runs the klams memory service** — 5 hit(s)
  - `0.016` knowledge r0 — /home/ken/src/ai/klams/README.md
  - `0.016` knowledge r1 — /home/ken/.claude/projects/-home-ken-src-ai-klams/24452a45-60b8-45f6-813c-b62aa79ea18e.jsonl
  - `0.016` knowledge r2 — /home/ken/src/ai/klams-mind/README.md
  - `0.016` knowledge r3 — /home/ken/src/ai/klams/sprints/planning/archive/plan.md
  - `0.015` knowledge r4 — /home/ken/src/ai/klams/sprints/planning/archive/tokenmaster-integration/analysis.md
- ✓ **where does kvllm serve models** — 5 hit(s)
  - `0.016` knowledge r0 — /home/ken/src/ai/kvllm/sprints/planning/00-kickoff.md
  - `0.016` knowledge r1 — /home/ken/src/ai/kvllm/justfile
  - `0.016` knowledge r2 — /home/ken/src/ai/kvllm/README.md
  - `0.016` knowledge r3 — /home/ken/src/ai/kvllm/kvllm/__init__.py
  - `0.015` knowledge r4 — /home/ken/src/ai/kvllm/models.toml
- ✓ **klams sprint bootstrap first light** — 5 hit(s)
  - `0.016` knowledge r0 — /home/ken/src/ai/klams-mind/sprints/001-bootstrap-first-light/sprint.md
  - `0.016` knowledge r1 — /home/ken/src/ai/klams-mind/sprints/001-bootstrap-first-light/sprint.md
  - `0.016` knowledge r2 — /home/ken/src/ai/klams-mind/sprints/001-bootstrap-first-light/sprint.md
  - `0.016` knowledge r3 — /home/ken/src/ai/klams-mind/sprints/001-bootstrap-first-light/sprint.md
  - `0.015` knowledge r4 — /home/ken/src/ai/klams-mind/sprints/001-bootstrap-first-light/sprint.md
- ○ **klams korg tools not available ToolSearch deferred lazily loaded** — 5 hit(s)
  - `0.065` knowledge r1 — (no source)
  - `0.064` knowledge r2 — (no source)
  - `0.016` knowledge r0 — /home/ken/src/ai-agents/harness-eval/_eval/run_01/runs/transcripts/04-runlog-transcript.txt
  - `0.016` knowledge r3 — /home/ken/src/ai/kyac/sprints/010-chat-exploration.md
  - `0.015` knowledge r4 — /home/ken/src/tools/korg/sprints/review/2026-07-21-review-prompt.md
- ✓ **deferred MCP tools misdiagnosis** — 10 hit(s)
  - `0.065` knowledge r1 — (no source)
  - `0.064` knowledge r2 — (no source)
  - `0.016` knowledge r0 — /home/ken/src/ai/multae-viae/specs/004-mcp-integration/spec.md
  - `0.016` knowledge r3 — /home/ken/src/ai/multae-viae/specs/004-mcp-integration/spec.md
  - `0.015` knowledge r4 — /home/ken/src/ai/multae-viae/specs/004-mcp-integration/tasks.md
  - `0.015` knowledge r5 — /home/ken/src/atv/ATV-Phoenix/BUILDLOG.md
  - `0.015` knowledge r6 — /home/ken/src/ai/kyac/sprints/post-mvp-review/architecture.md
  - `0.015` knowledge r7 — /home/ken/src/ai/multae-viae/specs/004-mcp-integration/spec.md
  - `0.014` knowledge r8 — /home/ken/src/atv/ATV-Phoenix/evals/m2-mcp/RESULT.md
  - `0.014` knowledge r9 — /home/ken/src/ai/multae-viae/specs/004-mcp-integration/spec.md
- ✓ **memory_add failed EMBEDDING_UNAVAILABLE should I retry** — 10 hit(s)
  - `0.066` knowledge r0 — (no source)
  - `0.016` knowledge r1 — /home/ken/src/ai/klams/sprints/007-mcp-server/contracts/error-codes.md
  - `0.016` knowledge r2 — /home/ken/src/ai/klams/crates/klams-mcp/tests/mcp_memory_add_knowledge.rs
  - `0.016` knowledge r3 — /home/ken/src/ai/klams/sprints/027-ingest-correctness/sprint.md
  - `0.015` knowledge r4 — /home/ken/src/ai/klams/crates/klams-mcp/src/errors.rs
  - `0.015` knowledge r5 — /home/ken/src/ai/klams/docs/reviews/2026-07-25-deep-review.md
  - `0.015` knowledge r6 — /home/ken/src/ai/klams/sprints/007-mcp-server/contracts/error-codes.md
  - `0.015` knowledge r7 — /home/ken/src/ai/krag/docs/troubleshooting.md
  - `0.014` knowledge r8 — /home/ken/src/ai/klams/crates/klams-mcp/src/errors.rs
  - `0.014` knowledge r9 — /home/ken/src/ai/klams/crates/klams-store/src/embeddings.rs
- ✓ **klams memory_add size ceiling how much text PAYLOAD_TOO_LARGE split** — 10 hit(s)
  - `0.066` knowledge r0 — (no source)
  - `0.016` knowledge r1 — /home/ken/src/ai/klams/docs/usage.md
  - `0.016` knowledge r2 — /home/ken/src/ai/multae-viae/specs/010-klams-rag/plan.md
  - `0.016` knowledge r3 — /home/ken/src/ai/klams/sprints/027-ingest-correctness/sprint.md
  - `0.015` knowledge r4 — /home/ken/src/ai/klams/migrations/0012_oversize_write.sql
  - `0.015` knowledge r5 — /home/ken/src/ai/klams/crates/klams-api/tests/contract_knowledge.rs
  - `0.015` knowledge r6 — /home/ken/src/ai/multae-viae/specs/010-klams-rag/plan.md
  - `0.015` knowledge r7 — /home/ken/src/ai/klams/sprints/027-ingest-correctness/sprint.md
  - `0.014` knowledge r8 — /home/ken/src/ai/klams/sprints/007-mcp-server/contracts/error-codes.md
  - `0.014` knowledge r9 — /home/ken/src/ai/klams/sprints/027-ingest-correctness/sprint.md
- ✓ **mcp tools missing from my tool list is the server down** — 10 hit(s)
  - `0.066` knowledge r0 — (no source)
  - `0.065` knowledge r1 — (no source)
  - `0.016` knowledge r2 — /home/ken/src/ai/multae-viae/CLAUDE.md
  - `0.016` knowledge r3 — /home/ken/src/ai/multae-viae/specs/004-mcp-integration/spec.md
  - `0.015` knowledge r4 — /home/ken/src/ai/multae-viae/specs/004-mcp-integration/spec.md
  - `0.015` knowledge r5 — /home/ken/src/ai/multae-viae/specs/004-mcp-integration/spec.md
  - `0.015` knowledge r6 — /home/ken/src/ai/multae-viae/specs/004-mcp-integration/spec.md
  - `0.015` knowledge r7 — /home/ken/src/ai/multae-viae/specs/004-mcp-integration/spec.md
  - `0.014` knowledge r8 — /home/ken/src/ai/multae-viae/specs/004-mcp-integration/tasks.md
  - `0.014` knowledge r9 — /home/ken/src/tools/kwi/docs/usage.md
- ○ **rpidash3 raspberry pi machine specs** — 5 hit(s)
  - `0.066` knowledge r0 — (no source)
  - `0.065` knowledge r1 — (no source)
  - `0.016` knowledge r2 — /home/ken/src/tools/kdeskdash/deploy/hosts/rpidash3.env
  - `0.016` knowledge r3 — /home/ken/src/tools/kdeskdash/sprints/018-multi-pi-deploy.md
  - `0.015` knowledge r4 — /home/ken/src/tools/kpidash/.github/agents/copilot-instructions.md
- ✓ **rpidash3 tailscale ed25519 passwordless sudo cloud-init groups** — 10 hit(s)
  - `0.057` knowledge r20 — (no source)
  - `0.057` knowledge r21 — (no source)
  - `0.056` knowledge r22 — (no source)
  - `0.055` knowledge r23 — (no source)
  - `0.016` knowledge r0 — /home/ken/src/tools/kwebi/README.md
  - `0.016` knowledge r1 — /home/ken/src/tools/kdeskdash/deploy/hosts/rpidash3.env
  - `0.016` knowledge r2 — /home/ken/src/tools/kpidash/clients/kpidash-client/systemd/README.md
  - `0.016` knowledge r3 — /home/ken/src/tools/kpidash/clients/kpidash-client/systemd/README.md
  - `0.015` knowledge r4 — /home/ken/src/tools/kdeskdash/CLAUDE.md
  - `0.015` knowledge r5 — /home/ken/src/tools/kdeskdash/deploy/hosts/README.md
- ✓ **rpidash3 dashboard raspberry pi** — 10 hit(s)
  - `0.066` knowledge r0 — (no source)
  - `0.063` knowledge r5 — (no source)
  - `0.016` knowledge r1 — /home/ken/src/tools/kpidash/docs/HANDOFF-CROSSCOMPILE.md
  - `0.016` knowledge r2 — /home/ken/src/tools/kdeskdash/CLAUDE.md
  - `0.016` knowledge r3 — /home/ken/src/tools/kpidash/.github/agents/copilot-instructions.md
  - `0.015` knowledge r4 — /home/ken/src/tools/kpidash/README.md
  - `0.015` knowledge r6 — /home/ken/src/tools/kpidash/specs/001-mvp-dashboard/plan.md
  - `0.015` knowledge r7 — /home/ken/src/tools/kdeskdash/.github/copilot-instructions.md
  - `0.014` knowledge r8 — /home/ken/src/tools/kdeskdash/deploy/hosts/rpidash3.env
  - `0.014` knowledge r9 — /home/ken/src/README-SRC.md
- ✓ **kpidash dashboard build commands** — 10 hit(s)
  - `0.057` knowledge r20 — (no source)
  - `0.057` knowledge r21 — (no source)
  - `0.056` knowledge r22 — (no source)
  - `0.016` knowledge r0 — /home/ken/src/tools/kpidash/docs/HANDOFF-CROSSCOMPILE.md
  - `0.016` knowledge r1 — /home/ken/src/tools/kpidash/docs/IMPLEMENTATION-PLAN.md
  - `0.016` knowledge r2 — /home/ken/src/tools/kpidash/.github/agents/copilot-instructions.md
  - `0.016` knowledge r3 — /home/ken/src/tools/kpidash/docs/ARCHITECTURE.md
  - `0.015` knowledge r4 — /home/ken/src/tools/kpidash/clients/kpidash-client/README.md
  - `0.015` knowledge r5 — /home/ken/src/tools/kpidash/docs/HANDOFF-CROSSCOMPILE.md
  - `0.015` knowledge r6 — /home/ken/src/tools/kpidash/specs/006-layout-refresh-status-cards/quickstart.md
- ✓ **kpidash cross compilation aarch64 toolchain** — 10 hit(s)
  - `0.016` knowledge r0 — /home/ken/src/tools/kpidash/specs/001-mvp-dashboard/quickstart.md
  - `0.016` knowledge r1 — /home/ken/src/tools/kpidash/docs/HANDOFF-CROSSCOMPILE.md
  - `0.016` knowledge r2 — /home/ken/src/tools/kpidash/specs/001-mvp-dashboard/quickstart.md
  - `0.016` knowledge r3 — /home/ken/src/tools/kpidash/docs/HANDOFF-CROSSCOMPILE.md
  - `0.015` knowledge r4 — /home/ken/src/tools/kpidash/docs/HANDOFF-CROSSCOMPILE.md
  - `0.015` knowledge r5 — /home/ken/src/tools/kpidash/README.md
  - `0.015` knowledge r6 — /home/ken/src/tools/kpidash/scripts/deploy.sh
  - `0.015` knowledge r7 — /home/ken/src/tools/kdeskdash/README.md
  - `0.014` knowledge r8 — /home/ken/src/tools/kpidash/docs/HANDOFF-CROSSCOMPILE.md
  - `0.014` knowledge r9 — /home/ken/src/tools/kpidash/specs/002-exploration-sprint/quickstart.md
- ✓ **kpidash dashboard build commands** — 5 hit(s)
  - `0.061` knowledge r10 — (no source)
  - `0.060` knowledge r11 — (no source)
  - `0.059` knowledge r12 — (no source)
  - `0.016` knowledge r0 — /home/ken/src/tools/kpidash/docs/HANDOFF-CROSSCOMPILE.md
  - `0.016` knowledge r1 — /home/ken/src/tools/kpidash/docs/IMPLEMENTATION-PLAN.md
- ✓ **klams gate fmt clippy test** — 5 hit(s)
  - `0.016` knowledge r0 — /home/ken/.claude/projects/-home-ken-src-ai-klams/24452a45-60b8-45f6-813c-b62aa79ea18e.jsonl
  - `0.016` knowledge r1 — /home/ken/src/ai/klams/AGENTS.md
  - `0.016` knowledge r2 — /home/ken/src/ai/multae-viae/docs/08-rag-integration.md
  - `0.016` knowledge r3 — /home/ken/src/ai/klams/sprints/planning/archive/tokenmaster-integration/findings.md
  - `0.015` knowledge r4 — /home/ken/src/ai/klams/sprints/planning/archive/tokenmaster-integration/analysis.md
- ✓ **EMBEDDING_UNAVAILABLE** — 10 hit(s)
  - `0.061` knowledge r10 — (no source)
  - `0.016` knowledge r0 — /home/ken/src/ai/krag/apps/krager/src/lib/components/domain/SystemStatus.svelte
  - `0.016` knowledge r1 — /home/ken/src/blizzard/wowadd/AcePlay/Libs/AceBucket-3.0/AceBucket-3.0.lua
  - `0.016` knowledge r2 — /home/ken/src/ai/klams/sprints/planning/archive/wi259-recommendation.md
  - `0.016` knowledge r3 — /home/ken/src/ai/klams/crates/klams-mcp/src/errors.rs
  - `0.015` knowledge r4 — /home/ken/src/ai/klams/crates/klams-mcp/src/errors.rs
  - `0.015` knowledge r5 — /home/ken/src/ai/kris/specs/supplemental-spec.md
  - `0.015` knowledge r6 — /home/ken/src/ai/klams/deploy/config/klams.example.toml
  - `0.015` knowledge r7 — /home/ken/src/ai/krag/apps/krager/src/lib/components/domain/SystemStatus.test.ts
  - `0.014` knowledge r8 — /home/ken/src/ai/klams/crates/klams-store/src/embeddings.rs
- ✓ **LOW_SCORE_THRESHOLD** — 10 hit(s)
  - `0.016` knowledge r0 — /home/ken/src/ai/krag/tests/contract/test_retriever_contract.py
  - `0.016` knowledge r1 — /home/ken/src/ai/krag/tests/unit/test_relevance_critic.py
  - `0.016` knowledge r2 — /home/ken/src/ai/krag/tests/unit/test_relevance_critic.py
  - `0.016` knowledge r3 — /home/ken/src/ai/krag/tests/contract/test_retriever_contract.py
  - `0.015` knowledge r4 — /home/ken/src/ai/krag/apps/krager/src/lib/components/domain/QueryAnswer.test.ts
  - `0.015` knowledge r5 — /home/ken/src/ai/krag/tests/contract/test_retriever_contract.py
  - `0.015` knowledge r6 — /home/ken/src/ai/klams/docs/architecture.md
  - `0.015` knowledge r7 — /home/ken/src/ai/klams/crates/klams-mcp/src/tools/memory_search.rs
  - `0.014` knowledge r8 — /home/ken/src/ai/klams/crates/klams-mcp/src/tools/memory_search.rs
  - `0.014` knowledge r9 — /home/ken/src/ai/krag/specs/006-code-quality-sprint/data-model.md
- ✓ **encke-wahoo.ts.net tailnet hostname** — 10 hit(s)
  - `0.066` knowledge r0 — (no source)
  - `0.064` knowledge r3 — (no source)
  - `0.016` knowledge r1 — /home/ken/src/ai/homelab-ai-plan/385_386_response.md
  - `0.016` knowledge r2 — /home/ken/src/ai/homelab-ai-plan/plan.md
  - `0.015` knowledge r4 — /home/ken/src/ai/homelab-ai-plan/385_386_response.md
  - `0.015` knowledge r5 — /home/ken/src/ai/homelab-ai-plan/decisions/2026-07-11-tls-and-auth-direction.md
  - `0.015` knowledge r6 — /home/ken/src/ai/homelab-ai-plan/385_386_response.md
  - `0.015` knowledge r7 — /home/ken/src/ai/homelab-ai-plan/decisions/2026-07-11-tls-and-auth-direction.md
  - `0.014` knowledge r8 — (no source)
  - `0.014` knowledge r9 — /home/ken/src/ai/homelab-ai-plan/decisions/2026-07-11-tls-and-auth-direction.md
- ✓ **find_knowledge_by_content_hash** — 10 hit(s)
  - `0.016` knowledge r0 — /home/ken/src/ai/klams/crates/klams-store/src/lib.rs
  - `0.016` knowledge r1 — /home/ken/src/ai/klams/crates/klams-store/src/qdrant.rs
  - `0.016` knowledge r2 — /home/ken/src/ai/klams/crates/klams-store/src/qdrant.rs
  - `0.016` knowledge r3 — /home/ken/src/ai/klams/crates/klams-api/tests/contract_search.rs
  - `0.015` knowledge r4 — /home/ken/src/ai/klams/sprints/026-retrieval-measurement/sprint.md
  - `0.015` knowledge r5 — /home/ken/src/ai/kris/docs/specification.md
  - `0.015` knowledge r6 — /home/ken/src/ai/klams-mind/tests/test_eval_checks.py
  - `0.015` knowledge r7 — /home/ken/src/ai/klams/crates/klams-api/tests/contract_knowledge.rs
  - `0.014` knowledge r8 — /home/ken/src/ai/klams/crates/klams-api/tests/contract_context.rs
  - `0.014` knowledge r9 — /home/ken/src/ai/klams/crates/klams-api/tests/contract_events.rs
- ✓ **klams listen_addr config key** — 10 hit(s)
  - `0.065` knowledge r1 — (no source)
  - `0.063` knowledge r4 — (no source)
  - `0.016` knowledge r0 — /home/ken/.claude/projects/-home-ken-src-ai-klams/24452a45-60b8-45f6-813c-b62aa79ea18e.jsonl
  - `0.016` knowledge r2 — /home/ken/src/ai/klams/deploy/config/klams.example.toml
  - `0.016` knowledge r3 — /home/ken/src/ai/klams-mind/README.md
  - `0.015` knowledge r5 — /home/ken/src/ai/klams-mind/README.md
  - `0.015` knowledge r6 — /home/ken/.claude/projects/-home-ken-src-ai-klams/24452a45-60b8-45f6-813c-b62aa79ea18e.jsonl
  - `0.015` knowledge r7 — /home/ken/src/ai/klams/docs/setup.md
  - `0.014` knowledge r8 — /home/ken/src/ai/klams-mind/sprints/007-eval-provenance/sprint.md
  - `0.014` knowledge r9 — /home/ken/src/ai/klams/tools/bench/README.md
