"""Aggregate run results into a report; render markdown or JSON.

The roadmap asks for a markdown report per run (krag emits JSON+stderr
only); we produce both, and add a per-check-type breakdown krag lacks so
a regression shows *which* check class slipped.
"""

import json
from dataclasses import dataclass

from klams_mind.eval.checks import RetrievedItem
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
    # klams sprint 026 (#643): `failed` counts every failing query,
    # including the ones we already know about. `regressions` is the one
    # that matters for a gate — it excludes `known_open`.
    regressions: int = 0
    known_open: int = 0
    newly_fixed: int = 0


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
        regressions=sum(1 for r in results if r.is_regression),
        known_open=sum(1 for r in results if r.expect == "known_open" and not r.passed),
        newly_fixed=sum(1 for r in results if r.is_newly_fixed),
    )


def to_json(report: Report) -> str:
    return json.dumps(
        {
            "suite": report.suite,
            "total": report.total,
            "passed": report.passed,
            "failed": report.failed,
            "regressions": report.regressions,
            "known_open": report.known_open,
            "newly_fixed": report.newly_fixed,
            "pass_rate": report.pass_rate,
            "by_check_type": report.by_check_type,
            "results": [
                {
                    "query": r.query,
                    "hit_count": r.hit_count,
                    "sources": r.sources,
                    "hits": [
                        {
                            "source": h.source,
                            "kind": h.kind,
                            "score": h.score,
                            "source_rank": h.source_rank,
                        }
                        for h in r.hits
                    ],
                    "passed": r.passed,
                    "expect": r.expect,
                    "tracking": r.tracking,
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
    verdict = "REGRESSION" if report.regressions else "OK"
    lines = [
        f"# Retrieval eval — {report.suite}",
        "",
        f"**{verdict} — {report.passed}/{report.total} queries passed ({pct}).**",
        "",
        f"{report.regressions} regression(s), {report.known_open} known-open, "
        f"{report.newly_fixed} newly fixed.",
        "",
        "## Checks by type",
        "",
        "| Check | Passed |",
        "| --- | --- |",
    ]
    for ctype, (p, t) in sorted(report.by_check_type.items()):
        lines.append(f"| `{ctype}` | {p}/{t} |")

    def _detail_lines(r: EvalQueryResult) -> list[str]:
        out = []
        for c in r.checks:
            if not c.passed:
                val = f" `{c.check.value}`" if c.check.value is not None else ""
                out.append(f"  - ✗ `{c.check.type}`{val} — {c.detail}")
        return out

    # Regressions first — they are the only thing that fails a run.
    regressions = [r for r in report.results if r.is_regression]
    if regressions:
        lines += ["", f"## Regressions ({len(regressions)})", ""]
        for r in regressions:
            lines.append(f"- **{r.query}** ({r.hit_count} hit(s))")
            lines += _detail_lines(r)

    newly_fixed = [r for r in report.results if r.is_newly_fixed]
    if newly_fixed:
        lines += ["", f"## Newly fixed ({len(newly_fixed)})", ""]
        lines.append("These are marked `known_open` but now pass — promote them to")
        lines.append('`expect = "pass"` so the next regression in them is caught.')
        lines.append("")
        for r in newly_fixed:
            track = f" ({r.tracking})" if r.tracking else ""
            lines.append(f"- **{r.query}**{track}")

    still_open = [r for r in report.results if r.expect == "known_open" and not r.passed]
    if still_open:
        lines += ["", f"## Known open ({len(still_open)})", ""]
        lines.append("Failing by design — tracked work, not a regression.")
        lines.append("")
        for r in still_open:
            track = f" — {r.tracking}" if r.tracking else ""
            lines.append(f"- **{r.query}**{track}")
            lines += _detail_lines(r)

    lines += ["", "## Queries", ""]
    for r in report.results:
        if r.passed:
            mark = "✓"
        elif r.expect == "known_open":
            mark = "○"
        else:
            mark = "✗"
        lines.append(f"- {mark} **{r.query}** — {r.hit_count} hit(s)")
        lines += [_hit_line(h) for h in r.hits]
    return "\n".join(lines) + "\n"


def _hit_line(h: RetrievedItem) -> str:
    """One per-hit detail line: score, kind, pre-fusion source rank, source.

    Raw scores are only comparable within the same kind (cosine for
    knowledge vs ts_rank for fact/event), so the kind sits next to the
    score rather than being aggregated across hits.
    """
    score = f"{h.score:.3f}" if h.score is not None else "—"
    rank = f"r{h.source_rank}" if h.source_rank is not None else "r?"
    kind = h.kind or "?"
    return f"  - `{score}` {kind} {rank} — {h.source or '(no source)'}"
