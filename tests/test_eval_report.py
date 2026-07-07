"""Reporter: aggregate stats, markdown, and JSON."""

import json

from klams_mind.eval.checks import CheckResult
from klams_mind.eval.report import build_report, to_json, to_markdown
from klams_mind.eval.runner import EvalQueryResult
from klams_mind.eval.suite import Check, CheckType


def qr(query: str, checks: list[CheckResult]) -> EvalQueryResult:
    return EvalQueryResult(
        query=query,
        hit_count=len(checks),
        sources=["src/a.py"],
        checks=checks,
        passed=all(c.passed for c in checks),
    )


def cr(type_: CheckType, passed: bool) -> CheckResult:
    return CheckResult(Check(type=type_, value="x"), passed, "detail here")


RESULTS = [
    qr("q1", [cr("substring", True), cr("source_cited", True)]),
    qr("q2", [cr("substring", False), cr("no_hallucination", True)]),
]


def test_build_report_aggregates() -> None:
    rep = build_report("homelab", RESULTS)

    assert rep.suite == "homelab"
    assert rep.total == 2
    assert rep.passed == 1
    assert rep.failed == 1
    assert rep.pass_rate == 0.5


def test_build_report_per_check_breakdown() -> None:
    rep = build_report("homelab", RESULTS)
    # substring: 1/2 passed; source_cited 1/1; no_hallucination 1/1
    assert rep.by_check_type["substring"] == (1, 2)
    assert rep.by_check_type["source_cited"] == (1, 1)
    assert rep.by_check_type["no_hallucination"] == (1, 1)


def test_build_report_empty() -> None:
    rep = build_report("empty", [])
    assert rep.total == 0
    assert rep.pass_rate == 0.0


def test_markdown_has_headline_and_failed_query() -> None:
    md = to_markdown(build_report("homelab", RESULTS))
    assert "# Retrieval eval — homelab" in md
    assert "1/2" in md  # headline pass count
    assert "q2" in md  # the failing query is called out
    assert "substring" in md  # per-check breakdown table
    # a passing-only report shouldn't invent failures
    clean = to_markdown(build_report("clean", [RESULTS[0]]))
    assert "q2" not in clean


def test_json_roundtrips_and_has_keys() -> None:
    payload = json.loads(to_json(build_report("homelab", RESULTS)))
    assert payload["suite"] == "homelab"
    assert payload["total"] == 2
    assert payload["pass_rate"] == 0.5
    assert payload["by_check_type"]["substring"] == [1, 2]
    assert payload["results"][1]["query"] == "q2"
    assert payload["results"][1]["passed"] is False
    assert payload["results"][1]["checks"][0]["type"] == "substring"
