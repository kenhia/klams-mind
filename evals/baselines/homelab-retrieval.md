# Retrieval eval — homelab-retrieval

**OK — 15/21 queries passed (71%).**

0 regression(s), 6 known-open, 0 newly fixed.

## Checks by type

| Check | Passed |
| --- | --- |
| `memory_id` | 3/7 |
| `min_body_chars` | 1/2 |
| `no_duplicates` | 3/3 |
| `no_hallucination` | 2/2 |
| `source_cited` | 2/2 |
| `substring` | 10/11 |

## Known open (6)

Failing by design — tracked work, not a regression.

- **deferred MCP tools misdiagnosis** — klams#628 / #644 — provenance-weighted fusion, sprint 029
  - ✗ `memory_id` `019f95dc-df08` — 019f95dc-df08 absent from 10 result(s)
- **memory_add failed EMBEDDING_UNAVAILABLE should I retry** — klams#644 — curated content loses to bulk spec/test chunks
  - ✗ `memory_id` `019f9ae4-79c0` — 019f9ae4-79c0 surfaced at rank 5, above the max_rank 2 — it is being outranked
- **mcp tools missing from my tool list is the server down** — klams#644 — symptom phrasing loses to bulk chunks
  - ✗ `memory_id` `019f9a36-e558` — 019f9a36-e558 surfaced at rank 4, above the max_rank 2 — it is being outranked
- **rpidash3 tailscale ed25519 passwordless sudo cloud-init groups** — korg:635 / klams#632 — split record, last-paragraph terms unretrievable
  - ✗ `memory_id` `019f9a83` — 019f9a83 absent from 10 result(s)
- **kpidash dashboard build commands** — klams F-2.3 — fence-unaware chunker, not yet scheduled
  - ✗ `min_body_chars` — fragment in '/home/ken/src/tools/kpidash/.github/agents/copilot-instructions.md': 7 chars after stripping breadcrumb (min 40) — '```bash'
- **LOW_SCORE_THRESHOLD** — klams#333 — no lexical signal for knowledge; exact identifiers miss
  - ✗ `substring` `LOW_SCORE_THRESHOLD` — 'LOW_SCORE_THRESHOLD' absent from 10 retrieved item(s)

## Queries

- ✓ **what container image does the klams service use** — 5 hit(s)
  - `0.016` knowledge r0 — /home/ken/src/ai/klams-mind/evals/baselines/homelab-retrieval.md
  - `0.016` knowledge r1 — /home/ken/src/ai/klams/deploy/docker-compose.yml
  - `0.016` knowledge r2 — /home/ken/src/ai/klams/sprints/008-activity-observability/contracts/prometheus-scrape.md
  - `0.016` knowledge r3 — (no source)
  - `0.015` knowledge r4 — /home/ken/src/ai/klams/deploy/docker-compose.yml
- ✓ **what host runs the klams memory service** — 5 hit(s)
  - `0.016` knowledge r0 — /home/ken/src/ai/klams/sprints/planning/archive/plan.md
  - `0.016` knowledge r1 — /home/ken/src/ai/klams/README.md
  - `0.016` knowledge r2 — /home/ken/src/ai/klams/.claude/skills/deploy-kubs0/SKILL.md
  - `0.016` knowledge r3 — /home/ken/.claude/projects/-home-ken-src-ai-klams/24452a45-60b8-45f6-813c-b62aa79ea18e.jsonl
  - `0.015` knowledge r4 — /home/ken/src/ai/klams/sprints/planning/archive/plan.md
- ✓ **where does kvllm serve models** — 5 hit(s)
  - `0.016` knowledge r0 — /home/ken/src/ai/kvllm/justfile
  - `0.016` knowledge r1 — /home/ken/src/ai/kagent/kagent/llm.py
  - `0.016` knowledge r2 — /home/ken/src/ai/kvllm/models.toml
  - `0.016` knowledge r3 — /home/ken/src/ai/kyac/kyac/bundle.py
  - `0.015` knowledge r4 — /home/ken/src/ai/kvllm/kvllm/helper.py
- ✓ **klams sprint bootstrap first light** — 5 hit(s)
  - `0.016` knowledge r0 — /home/ken/src/ai/klams-mind/sprints/001-bootstrap-first-light/sprint.md
  - `0.016` knowledge r1 — /home/ken/src/ai/klams-mind/sprints/001-bootstrap-first-light/sprint.md
  - `0.016` knowledge r2 — /home/ken/src/ai/klams-mind/sprints/001-bootstrap-first-light/sprint.md
  - `0.016` knowledge r3 — /home/ken/src/ai/klams-mind/sprints/001-bootstrap-first-light/sprint.md
  - `0.015` knowledge r4 — /home/ken/src/ai/klams-mind/sprints/001-bootstrap-first-light/sprint.md
- ✓ **klams korg tools not available ToolSearch deferred lazily loaded** — 5 hit(s)
  - `0.016` knowledge r0 — (no source)
  - `0.016` knowledge r1 — (no source)
  - `0.016` knowledge r2 — /home/ken/src/ai/kyac/tests/test_server.py
  - `0.016` knowledge r3 — /home/ken/src/ai/multae-viae/crates/mv-cli/tests/cli_klams.rs
  - `0.015` knowledge r4 — /home/ken/src/tools/korg/crates/korg-api/tests/mcp_http.rs
- ○ **deferred MCP tools misdiagnosis** — 10 hit(s)
  - `0.016` knowledge r0 — (no source)
  - `0.016` knowledge r1 — /home/ken/src/ai/multae-viae/specs/004-mcp-integration/contracts/cli.md
  - `0.016` knowledge r2 — /home/ken/src/ai/multae-viae/specs/004-mcp-integration/spec.md
  - `0.016` knowledge r3 — /home/ken/src/ai/multae-viae/crates/mv-core/src/mcp/registry.rs
  - `0.015` knowledge r4 — /home/ken/src/ai/kyac/tests/test_errors.py
  - `0.015` knowledge r5 — /home/ken/src/tools/kwi/specs/supplemental-spec.md
  - `0.015` knowledge r6 — /home/ken/src/tools/kpidash/specs/001-mvp-dashboard/contracts/mcp-tools.md
  - `0.015` knowledge r7 — /home/ken/src/ai/multae-viae/docs/04-mcp-integration.md
  - `0.014` knowledge r8 — /home/ken/src/ai/multae-viae/specs/004-mcp-integration/research.md
  - `0.014` knowledge r9 — /home/ken/src/ai/multae-viae/crates/mv-cli/src/bin/fake_mcp_server.rs
- ○ **memory_add failed EMBEDDING_UNAVAILABLE should I retry** — 10 hit(s)
  - `0.016` knowledge r0 — /home/ken/src/ai/klams/crates/klams-store/src/embeddings.rs
  - `0.016` knowledge r1 — /home/ken/src/ai/klams/docs/reviews/2026-07-25-deep-review.md
  - `0.016` knowledge r2 — /home/ken/src/ai/krag/specs/001-text-rag-indexing/quickstart.md
  - `0.016` knowledge r3 — /home/ken/src/ai/klams/crates/klams-store/src/embeddings.rs
  - `0.015` knowledge r4 — /home/ken/src/ai/krag/specs/003-wsl-migration/quickstart.md
  - `0.015` knowledge r5 — (no source)
  - `0.015` knowledge r6 — /home/ken/src/ai/klams/docs/reviews/2026-07-25-deep-review.md
  - `0.015` knowledge r7 — /home/ken/src/tools/kdeskdash/lib/lvgl/src/draw/sw/arm2d/lv_draw_sw_arm2d.h
  - `0.014` knowledge r8 — /home/ken/src/ai/krag/docs/troubleshooting.md
  - `0.014` knowledge r9 — /home/ken/src/ai/kris/src/kris/processing/worker.py
- ✓ **klams memory_add size ceiling bge-small 512 tokens split the text** — 10 hit(s)
  - `0.016` knowledge r0 — (no source)
  - `0.016` knowledge r1 — /home/ken/src/ai/klams/sprints/008-activity-observability/quickstart.md
  - `0.016` knowledge r2 — /home/ken/src/ai/krag/tests/unit/test_prompt_builder.py
  - `0.016` knowledge r3 — /home/ken/src/ai/krag/examples/krag-plugin-code/README.md
  - `0.015` knowledge r4 — /home/ken/src/ai/klams/crates/klams-service/tests/backup_validate_config_cli.rs
  - `0.015` knowledge r5 — /home/ken/src/ai/klams/crates/klams-scanner/src/main.rs
  - `0.015` knowledge r6 — /home/ken/src/ai/klams-mind/src/klams_mind/cli.py
  - `0.015` knowledge r7 — /home/ken/src/ai/klams-mind/pyproject.toml
  - `0.014` knowledge r8 — /home/ken/src/ai/klams/tools/bench/README.md
  - `0.014` knowledge r9 — /home/ken/src/ai/klams/tools/bench/README.md
- ○ **mcp tools missing from my tool list is the server down** — 10 hit(s)
  - `0.016` knowledge r0 — /home/ken/src/tools/kwi/tests/conftest.py
  - `0.016` knowledge r1 — /home/ken/src/ai/multae-viae/specs/004-mcp-integration/contracts/cli.md
  - `0.016` knowledge r2 — (no source)
  - `0.016` knowledge r3 — /home/ken/src/ai/kyac/kyac/mcp.py
  - `0.015` knowledge r4 — (no source)
  - `0.015` knowledge r5 — /home/ken/src/ai/klams/sprints/007-mcp-server/tasks.md
  - `0.015` knowledge r6 — /home/ken/src/ai/kyac/kyac/mcp.py
  - `0.015` knowledge r7 — /home/ken/src/ai/multae-viae/specs/004-mcp-integration/contracts/cli.md
  - `0.014` knowledge r8 — /home/ken/src/ai/multae-viae/docs/01-architecture-design.md
  - `0.014` knowledge r9 — /home/ken/src/ai/kyac/kyac/mcp.py
- ✓ **rpidash3 raspberry pi machine specs** — 5 hit(s)
  - `0.016` knowledge r0 — (no source)
  - `0.016` knowledge r1 — /home/ken/src/tools/kdeskdash/sprints/planning/roadmap.md
  - `0.016` knowledge r2 — (no source)
  - `0.016` knowledge r3 — /home/ken/src/tools/kdeskdash/sprints/018-multi-pi-deploy.md
  - `0.015` knowledge r4 — /home/ken/src/tools/kpidash/docs/ARCHITECTURE.md
- ○ **rpidash3 tailscale ed25519 passwordless sudo cloud-init groups** — 10 hit(s)
  - `0.016` knowledge r0 — /home/ken/src/tools/kwebi/README.md
  - `0.016` knowledge r1 — /home/ken/src/tools/kpidash/README.md
  - `0.016` knowledge r2 — /home/ken/src/ai/krag/specs/003-wsl-migration/research.md
  - `0.016` knowledge r3 — /home/ken/src/ai/krag/docs/migration-guide.md
  - `0.015` knowledge r4 — /home/ken/src/tools/kpidash/docs/HANDOFF-CROSSCOMPILE.md
  - `0.015` knowledge r5 — /home/ken/src/tools/kpidash/specs/002-exploration-sprint/quickstart.md
  - `0.015` knowledge r6 — /home/ken/src/ai/krag/specs/003-wsl-migration/quickstart.md
  - `0.015` knowledge r7 — /home/ken/src/ai/krag/docs/migration-guide.md
  - `0.014` knowledge r8 — /home/ken/src/tools/kpidash/README.md
  - `0.014` knowledge r9 — /home/ken/src/ai/kmon/vmlab/cloud-init.yaml
- ✓ **rpidash3 dashboard raspberry pi** — 10 hit(s)
  - `0.016` knowledge r0 — (no source)
  - `0.016` knowledge r1 — /home/ken/src/tools/kpidash/docs/HANDOFF-CROSSCOMPILE.md
  - `0.016` knowledge r2 — /home/ken/src/tools/kpidash/README.md
  - `0.016` knowledge r3 — /home/ken/src/tools/kpidash/specs/001-mvp-dashboard/plan.md
  - `0.015` knowledge r4 — (no source)
  - `0.015` knowledge r5 — /home/ken/src/tools/kpidash/.github/agents/copilot-instructions.md
  - `0.015` knowledge r6 — /home/ken/src/README-SRC.md
  - `0.015` knowledge r7 — /home/ken/src/GH_SUMMARY.md
  - `0.014` knowledge r8 — /home/ken/src/tools/kdeskdash/sprints/planning/roadmap.md
  - `0.014` knowledge r9 — /home/ken/src/tools/kpidash/docs/ARCHITECTURE.md
- ✓ **kpidash dashboard build commands** — 10 hit(s)
  - `0.016` knowledge r0 — /home/ken/src/tools/kpidash/.github/agents/copilot-instructions.md
  - `0.016` knowledge r1 — /home/ken/src/tools/kpidash/docs/IMPLEMENTATION-PLAN.md
  - `0.016` knowledge r2 — /home/ken/src/tools/kpidash/README.md
  - `0.016` knowledge r3 — /home/ken/src/tools/kpidash/specs/006-layout-refresh-status-cards/quickstart.md
  - `0.015` knowledge r4 — /home/ken/src/tools/kpidash/specs/001-mvp-dashboard/tasks.md
  - `0.015` knowledge r5 — /home/ken/src/tools/kpidash/.github/agents/copilot-instructions.md
  - `0.015` knowledge r6 — /home/ken/src/tools/kpidash/specs/001-mvp-dashboard/plan.md
  - `0.015` knowledge r7 — /home/ken/src/tools/kpidash/clients/kpidash-client/README.md
  - `0.014` knowledge r8 — /home/ken/src/tools/kpidash/specs/001-mvp-dashboard/quickstart.md
  - `0.014` knowledge r9 — /home/ken/src/tools/kpidash/README.md
- ✓ **kpidash cross compilation aarch64 toolchain** — 10 hit(s)
  - `0.016` knowledge r0 — /home/ken/src/tools/kpidash/specs/001-mvp-dashboard/quickstart.md
  - `0.016` knowledge r1 — /home/ken/src/tools/kpidash/docs/HANDOFF-CROSSCOMPILE.md
  - `0.016` knowledge r2 — /home/ken/src/tools/kpidash/docs/HANDOFF-CROSSCOMPILE.md
  - `0.016` knowledge r3 — /home/ken/src/tools/kdeskdash/sprints/001-premvp-display-touch/plan.md
  - `0.015` knowledge r4 — /home/ken/src/tools/kpidash/docs/HANDOFF-CROSSCOMPILE.md
  - `0.015` knowledge r5 — /home/ken/src/tools/kpidash/scripts/deploy.sh
  - `0.015` knowledge r6 — /home/ken/src/tools/kpidash/docs/HANDOFF-CROSSCOMPILE.md
  - `0.015` knowledge r7 — /home/ken/src/tools/kpidash/README.md
  - `0.014` knowledge r8 — /home/ken/src/tools/kpidash/docs/HANDOFF-CROSSCOMPILE.md
  - `0.014` knowledge r9 — /home/ken/src/tools/kpidash/specs/001-mvp-dashboard/quickstart.md
- ○ **kpidash dashboard build commands** — 5 hit(s)
  - `0.016` knowledge r0 — /home/ken/src/tools/kpidash/.github/agents/copilot-instructions.md
  - `0.016` knowledge r1 — /home/ken/src/tools/kpidash/docs/IMPLEMENTATION-PLAN.md
  - `0.016` knowledge r2 — /home/ken/src/tools/kpidash/README.md
  - `0.016` knowledge r3 — /home/ken/src/tools/kpidash/specs/006-layout-refresh-status-cards/quickstart.md
  - `0.015` knowledge r4 — /home/ken/src/tools/kpidash/specs/001-mvp-dashboard/tasks.md
- ✓ **klams gate fmt clippy test** — 5 hit(s)
  - `0.016` knowledge r0 — /home/ken/src/misc/tools/kapollo/specs/002-mvp-hardening/quickstart.md
  - `0.016` knowledge r1 — /home/ken/src/ai/klams/sprints/005-advanced-retrieval/plan.md
  - `0.016` knowledge r2 — /home/ken/src/ai/klams/sprints/001-initial-mvp/tasks.md
  - `0.016` knowledge r3 — /home/ken/src/misc/tools/kapollo/specs/002-mvp-hardening/quickstart.md
  - `0.015` knowledge r4 — /home/ken/src/blizzard/battlenet-rs/.specify/memory/constitution.md
- ✓ **EMBEDDING_UNAVAILABLE** — 10 hit(s)
  - `0.016` knowledge r0 — /home/ken/src/ai/krag/specs/001-text-rag-indexing/quickstart.md
  - `0.016` knowledge r1 — /home/ken/src/ai/krag/specs/001-text-rag-indexing/quickstart.md
  - `0.016` knowledge r2 — /home/ken/src/ai/krag/specs/002-plugin-architecture/contracts/plugin-chunking.md
  - `0.016` knowledge r3 — /home/ken/src/ai/klams/crates/klams-core/src/context.rs
  - `0.015` knowledge r4 — /home/ken/src/ai/krag/specs/003-wsl-migration/quickstart.md
  - `0.015` knowledge r5 — /home/ken/src/ai/klams/docs/reviews/2026-07-25-deep-review.md
  - `0.015` knowledge r6 — /home/ken/src/ai/krag/specs/010-infrastructure-polish/quickstart.md
  - `0.015` knowledge r7 — /home/ken/src/ai/krag/specs/010-infrastructure-polish/quickstart.md
  - `0.014` knowledge r8 — /home/ken/src/ai/krag/specs/003-wsl-migration/quickstart.md
  - `0.014` knowledge r9 — /home/ken/src/ai/klams/crates/klams-mcp/src/tools/memory_add.rs
- ○ **LOW_SCORE_THRESHOLD** — 10 hit(s)
  - `0.016` knowledge r0 — /home/ken/src/ai/krag/src/krag/critic/relevance_critic.py
  - `0.016` knowledge r1 — /home/ken/src/ai/krag/tests/contract/test_retriever_contract.py
  - `0.016` knowledge r2 — /home/ken/src/ai/krag/tests/unit/test_relevance_critic.py
  - `0.016` knowledge r3 — /home/ken/src/ai/krag/tests/unit/test_relevance_critic.py
  - `0.015` knowledge r4 — /home/ken/src/ai/krag/specs/007-service-architecture/contracts/openapi.yaml
  - `0.015` knowledge r5 — /home/ken/src/ai/krag/src/krag/critic/relevance_critic.py
  - `0.015` knowledge r6 — /home/ken/src/ai/krag/src/krag/critic/relevance_critic.py
  - `0.015` knowledge r7 — /home/ken/src/ai/krag/tests/unit/kragd/test_schemas.py
  - `0.014` knowledge r8 — /home/ken/src/ai/krag/src/krag/critic/relevance_critic.py
  - `0.014` knowledge r9 — /home/ken/src/ai/krag/src/kragd/service.py
- ✓ **encke-wahoo.ts.net tailnet hostname** — 10 hit(s)
  - `0.016` knowledge r0 — (no source)
  - `0.016` knowledge r1 — /home/ken/src/ai/homelab-ai-plan/plan.md
  - `0.016` knowledge r2 — /home/ken/src/ai/homelab-ai-plan/385_386_response.md
  - `0.016` knowledge r3 — /home/ken/src/blizzard/ToonTool/src/WowApi/Get-WowDataUrl.ps1
  - `0.015` knowledge r4 — /home/ken/src/ai/homelab-ai-plan/385_386_response.md
  - `0.015` knowledge r5 — /home/ken/src/ai/homelab-ai-plan/decisions/2026-07-11-tls-and-auth-direction.md
  - `0.015` knowledge r6 — /home/ken/src/ai/homelab-ai-plan/385_386_response.md
  - `0.015` knowledge r7 — /home/ken/src/ai/kvllm/kvllm/registry.py
  - `0.014` knowledge r8 — /home/ken/src/ai/kyac/kyac/auth.py
  - `0.014` knowledge r9 — (no source)
- ✓ **find_knowledge_by_content_hash** — 10 hit(s)
  - `0.016` knowledge r0 — /home/ken/src/ai/klams/crates/klams-api/tests/contract_events.rs
  - `0.016` knowledge r1 — /home/ken/src/ai/klams/crates/klams-mcp/src/tools/memory_search.rs
  - `0.016` knowledge r2 — /home/ken/src/ai/klams/crates/klams-mcp/src/tools/memory_search.rs
  - `0.016` knowledge r3 — /home/ken/src/ai/klams/crates/klams-api/tests/contract_facts.rs
  - `0.015` knowledge r4 — /home/ken/src/ai/klams/crates/klams-core/tests/queue.rs
  - `0.015` knowledge r5 — /home/ken/src/ai/klams/crates/klams-mcp/src/tools/memory_add.rs
  - `0.015` knowledge r6 — /home/ken/src/ai/klams/crates/klams-types/src/memory.rs
  - `0.015` knowledge r7 — /home/ken/src/ai/klams-mind/src/klams_mind/eval/checks.py
  - `0.014` knowledge r8 — /home/ken/src/ai/klams/docs/reviews/2026-07-25-deep-review.md
  - `0.014` knowledge r9 — /home/ken/src/ai/klams/crates/klams-api/tests/contract_knowledge.rs
- ✓ **klams listen_addr config key** — 10 hit(s)
  - `0.016` knowledge r0 — /home/ken/src/ai/klams/crates/klams-monitor/src/main.rs
  - `0.016` knowledge r1 — /home/ken/src/ai/klams/sprints/007-mcp-server/quickstart.md
  - `0.016` knowledge r2 — /home/ken/src/ai/kyac/docs/usage.md
  - `0.016` knowledge r3 — /home/ken/src/ai/klams/crates/klams-service/tests/backup_validate_config_cli.rs
  - `0.015` knowledge r4 — /home/ken/src/ai/klams/crates/klams-service/src/main.rs
  - `0.015` knowledge r5 — /home/ken/src/ai/klams/sprints/007-mcp-server/quickstart.md
  - `0.015` knowledge r6 — /home/ken/src/ai/klams/crates/klams-monitor/Cargo.toml
  - `0.015` knowledge r7 — /home/ken/src/ai/klams/sprints/010-operationalize-ingestion/tasks.md
  - `0.014` knowledge r8 — /home/ken/src/ai/klams/deploy/install-systemd.sh
  - `0.014` knowledge r9 — /home/ken/src/ai/klams-mind/src/klams_mind/config.py
