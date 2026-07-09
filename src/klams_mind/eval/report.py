"""Aggregate run results into a report; render markdown or JSON.

The roadmap asks for a markdown report per run (krag emits JSON+stderr
only); we produce both, and add a per-check-type breakdown krag lacks so
a regression shows *which* check class slipped.
"""

import json
from dataclasses import dataclass

from klams_mind.eval.runner import EvalQueryResult


@dataclass
class Report:
    suite: str
    total: int
    passed: int
    failed: int
    pass_rate: float
    by_check_type: dict[str, tuple[int, int]]  # type -> (passed, total)
    results: list[EvalQueryResult]


def build_report(suite: str, results: list[EvalQueryResult]) -> Report:
    total = len(results)
    passed = sum(1 for r in results if r.passed)
    by_type: dict[str, tuple[int, int]] = {}
    for r in results:
        for c in r.checks:
            p, t = by_type.get(c.check.type, (0, 0))
            by_type[c.check.type] = (p + int(c.passed), t + 1)
    return Report(
        suite=suite,
        total=total,
        passed=passed,
        failed=total - passed,
        pass_rate=(passed / total) if total else 0.0,
        by_check_type=by_type,
        results=results,
    )


def to_json(report: Report) -> str:
    return json.dumps(
        {
            "suite": report.suite,
            "total": report.total,
            "passed": report.passed,
            "failed": report.failed,
            "pass_rate": report.pass_rate,
            "by_check_type": report.by_check_type,
            "results": [
                {
                    "query": r.query,
                    "hit_count": r.hit_count,
                    "sources": r.sources,
                    "passed": r.passed,
                    "checks": [
                        {
                            "type": c.check.type,
                            "value": c.check.value,
                            "passed": c.passed,
                            "detail": c.detail,
                        }
                        for c in r.checks
                    ],
                }
                for r in report.results
            ],
        },
        indent=2,
    )


def to_markdown(report: Report) -> str:
    pct = f"{report.pass_rate:.0%}"
    lines = [
        f"# Retrieval eval — {report.suite}",
        "",
        f"**{report.passed}/{report.total} queries passed ({pct}).**",
        "",
        "## Checks by type",
        "",
        "| Check | Passed |",
        "| --- | --- |",
    ]
    for ctype, (p, t) in sorted(report.by_check_type.items()):
        lines.append(f"| `{ctype}` | {p}/{t} |")

    failures = [r for r in report.results if not r.passed]
    if failures:
        lines += ["", "## Failures", ""]
        for r in failures:
            lines.append(f"- **{r.query}** ({r.hit_count} hit(s))")
            for c in r.checks:
                if not c.passed:
                    val = f" `{c.check.value}`" if c.check.value is not None else ""
                    lines.append(f"  - ✗ `{c.check.type}`{val} — {c.detail}")

    lines += ["", "## Queries", ""]
    for r in report.results:
        mark = "✓" if r.passed else "✗"
        lines.append(f"- {mark} **{r.query}** — {r.hit_count} hit(s)")
    return "\n".join(lines) + "\n"
