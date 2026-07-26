"""Reporter: aggregate stats, markdown, and JSON."""

import json
from dataclasses import replace

from klams_mind.eval.checks import CheckResult, RetrievedItem
from klams_mind.eval.provenance import Provenance, parse_provenance
from klams_mind.eval.report import build_report, to_json, to_markdown
from klams_mind.eval.runner import EvalQueryResult
from klams_mind.eval.suite import Check, CheckType

HIT = RetrievedItem(content="c", source="src/a.py", kind="knowledge", score=0.712, source_rank=0)


def qr(query: str, checks: list[CheckResult]) -> EvalQueryResult:
    return EvalQueryResult(
        query=query,
        hit_count=len(checks),
        sources=["src/a.py"],
        checks=checks,
        passed=all(c.passed for c in checks),
        hits=[HIT],
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


def test_markdown_lists_per_hit_score_kind_rank() -> None:
    md = to_markdown(build_report("homelab", [RESULTS[0]]))
    assert "`0.712` knowledge r0 — src/a.py" in md
    # hits without score metadata (e.g. hand-built items) still render
    md_bare = to_markdown(
        build_report("h", [EvalQueryResult("q3", 1, ["s"], [], True, [RetrievedItem("c", "s")])])
    )
    assert "`—` ? r? — s" in md_bare


def test_json_roundtrips_and_has_keys() -> None:
    payload = json.loads(to_json(build_report("homelab", RESULTS)))
    assert payload["suite"] == "homelab"
    assert payload["total"] == 2
    assert payload["pass_rate"] == 0.5
    assert payload["by_check_type"]["substring"] == [1, 2]
    assert payload["results"][1]["query"] == "q2"
    assert payload["results"][1]["passed"] is False
    assert payload["results"][1]["checks"][0]["type"] == "substring"
    hit = payload["results"][0]["hits"][0]
    assert hit == {"source": "src/a.py", "kind": "knowledge", "score": 0.712, "source_rank": 0}


# --- klams sprint 026 (#643): the gate counts regressions, not failures ----


def _result(query: str, passed: bool, expect: str = "pass") -> EvalQueryResult:
    check = Check(type="substring", value="x")
    return EvalQueryResult(
        query=query,
        hit_count=1,
        sources=["s"],
        checks=[CheckResult(check, passed, "d")],
        passed=passed,
        expect=expect,
    )


def test_report_separates_regressions_from_known_open_failures() -> None:
    report = build_report(
        "t",
        [
            _result("ok", True),
            _result("broke", False),
            _result("tracked", False, expect="known_open"),
        ],
    )
    assert report.failed == 2, "both failures are counted as failures"
    assert report.regressions == 1, "only the unexpected one is a regression"
    assert report.known_open == 1


def test_report_counts_a_newly_fixed_known_open_query() -> None:
    report = build_report("t", [_result("fixed", True, expect="known_open")])
    assert report.newly_fixed == 1
    assert report.regressions == 0


def test_markdown_says_ok_when_only_known_open_queries_fail() -> None:
    md = to_markdown(build_report("t", [_result("tracked", False, expect="known_open")]))
    assert "OK" in md
    assert "REGRESSION" not in md
    assert "Known open" in md


def test_markdown_says_regression_when_a_pass_query_fails() -> None:
    md = to_markdown(build_report("t", [_result("broke", False)]))
    assert "REGRESSION" in md
    assert "Regressions (1)" in md


# --- klams#676: reports and baselines state what they ran against ----------

PROV = Provenance(
    run_at="2026-07-26T04:10:27Z",
    suite_file="homelab-retrieval.toml",
    suite_hash="sha256:ab12cd34ef56",
    klams_version="0.1.26",
)
CLEAN = [RESULTS[0]]


def test_markdown_stamps_provenance_and_round_trips_it() -> None:
    md = to_markdown(build_report("homelab", CLEAN, provenance=PROV))
    assert "2026-07-26T04:10:27Z" in md
    assert "0.1.26" in md
    assert "sha256:ab12cd34ef56" in md
    # It must parse back, or the next run cannot compare against this file.
    assert parse_provenance(md) == PROV


def test_markdown_omits_the_block_when_no_provenance_is_supplied() -> None:
    assert parse_provenance(to_markdown(build_report("homelab", CLEAN))) is None


def test_markdown_flags_a_klams_version_mismatch_against_the_baseline() -> None:
    """The one line that would have short-circuited sprint 026's detour."""
    baseline = replace(PROV, klams_version="0.1.19", run_at="2026-07-08T00:00:00Z")
    md = to_markdown(build_report("homelab", CLEAN, provenance=PROV, baseline=baseline))
    assert "Baseline captured against klams 0.1.19; running against 0.1.26" in md
    assert "REGRESSION" not in md, "provenance drift is informational, never a failure"


def test_markdown_notes_a_suite_change_since_the_baseline() -> None:
    baseline = replace(PROV, suite_hash="sha256:000000000000")
    md = to_markdown(build_report("homelab", CLEAN, provenance=PROV, baseline=baseline))
    assert "suite has changed since the baseline" in md


def test_markdown_is_silent_when_the_baseline_matches() -> None:
    md = to_markdown(build_report("homelab", CLEAN, provenance=PROV, baseline=PROV))
    assert "Baseline captured against" not in md
    assert "suite has changed" not in md


def test_json_carries_provenance_and_baseline() -> None:
    baseline = replace(PROV, klams_version="0.1.19")
    payload = json.loads(to_json(build_report("h", CLEAN, provenance=PROV, baseline=baseline)))
    assert payload["provenance"] == {
        "run_at": "2026-07-26T04:10:27Z",
        "suite_file": "homelab-retrieval.toml",
        "suite_hash": "sha256:ab12cd34ef56",
        "klams_version": "0.1.26",
    }
    assert payload["baseline"]["klams_version"] == "0.1.19"


def test_json_baseline_is_null_when_there_is_nothing_to_compare() -> None:
    payload = json.loads(to_json(build_report("h", CLEAN, provenance=PROV)))
    assert payload["baseline"] is None
