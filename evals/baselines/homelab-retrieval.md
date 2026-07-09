# Retrieval eval — homelab-retrieval

**4/4 queries passed (100%).**

## Checks by type

| Check | Passed |
| --- | --- |
| `no_hallucination` | 1/1 |
| `source_cited` | 4/4 |
| `substring` | 4/4 |

## Queries

- ✓ **what container image does the klams service use** — 5 hit(s)
  - `0.895` knowledge r0 — /home/ken/src/ai/klams/deploy/docker-compose.yml
  - `0.830` knowledge r1 — /home/ken/src/ai/klams/deploy/docker-compose.yml
  - `0.821` knowledge r2 — /home/ken/src/ai/klams/deploy/compose.env.example
  - `0.811` knowledge r3 — /home/ken/src/ai/klams/deploy/prometheus/prometheus.yml
  - `0.807` knowledge r4 — /home/ken/src/ai/klams/deploy/config/klams.example.toml
- ✓ **what host runs the klams memory service** — 5 hit(s)
  - `0.843` knowledge r0 — /home/ken/src/ai/klams/deploy/config/klams.example.toml
  - `0.841` knowledge r1 — /home/ken/src/ai/klams/README.md
  - `0.820` knowledge r2 — /home/ken/src/ai/klams-mind/src/klams_mind/__init__.py
  - `0.817` knowledge r3 — /home/ken/src/ai/klams/deploy/systemd/klams.service
  - `0.814` knowledge r4 — /home/ken/src/ai/klams/docs/usage.md
- ✓ **where does kvllm serve models** — 5 hit(s)
  - `0.802` knowledge r0 — /home/ken/src/ai/klams-mind/tests/test_klams_client.py
  - `0.787` knowledge r1 — /home/ken/src/ai/klams-mind/sprints/001-bootstrap-first-light/sprint.md
  - `0.776` knowledge r2 — /home/ken/src/ai/klams/sprints/planning/wi259-three-project-review.md
  - `0.775` knowledge r3 — /home/ken/src/ai/klams/sprints/planning/wi259-recommendation.md
  - `0.771` knowledge r4 — /home/ken/src/ai/klams/deploy/config/klams.example.toml
- ✓ **klams sprint bootstrap first light** — 5 hit(s)
  - `0.764` knowledge r0 — /home/ken/src/ai/klams/deploy/config/monitor.example.toml
  - `0.761` knowledge r1 — /home/ken/src/ai/klams-mind/sprints/001-bootstrap-first-light/sprint.md
  - `0.739` knowledge r2 — /home/ken/src/ai/klams/deploy/config/scanner.example.toml
  - `0.723` knowledge r3 — (no source)
  - `0.718` knowledge r4 — /home/ken/src/ai/klams/deploy/install-systemd.sh
