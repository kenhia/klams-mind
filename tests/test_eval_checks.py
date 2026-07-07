"""The three retrieval checks as pure functions over retrieved items."""

from klams_mind.eval.checks import RetrievedItem, evaluate_check
from klams_mind.eval.suite import Check, CheckType

HITS = [
    RetrievedItem(
        content="services:\n  image: klams:dev",
        source="/home/ken/src/ai/klams/deploy/docker-compose.yml",
        tags=["homelab"],
    ),
    RetrievedItem(
        content="kvllm serves OpenAI-compatible models on kai:8000",
        source="/home/ken/src/ai/kvllm/README.md",
        tags=[],
    ),
]


def check(type_: CheckType, value: str | None = None) -> Check:
    return Check(type=type_, value=value)


# --- substring: content recall ---------------------------------------------


def test_substring_passes_when_present() -> None:
    r = evaluate_check(check("substring", "image: klams"), HITS)
    assert r.passed


def test_substring_is_case_insensitive() -> None:
    assert evaluate_check(check("substring", "IMAGE: KLAMS"), HITS).passed


def test_substring_fails_when_absent() -> None:
    r = evaluate_check(check("substring", "postgresql cluster"), HITS)
    assert not r.passed
    assert "postgresql cluster" in r.detail


def test_substring_without_value_fails() -> None:
    assert not evaluate_check(check("substring", None), HITS).passed


# --- source_cited: source recall -------------------------------------------


def test_source_cited_matches_source_path_fragment() -> None:
    r = evaluate_check(check("source_cited", "deploy/docker-compose.yml"), HITS)
    assert r.passed


def test_source_cited_matches_tag() -> None:
    assert evaluate_check(check("source_cited", "homelab"), HITS).passed


def test_source_cited_fails_when_not_retrieved() -> None:
    r = evaluate_check(check("source_cited", "nginx.conf"), HITS)
    assert not r.passed


def test_source_cited_without_value_fails() -> None:
    assert not evaluate_check(check("source_cited", None), HITS).passed


# --- no_hallucination: precision / absence ---------------------------------


def test_no_hallucination_passes_when_forbidden_absent() -> None:
    r = evaluate_check(check("no_hallucination", "sourdough"), HITS)
    assert r.passed


def test_no_hallucination_fails_when_forbidden_in_content() -> None:
    r = evaluate_check(check("no_hallucination", "kvllm"), HITS)
    assert not r.passed
    assert "kvllm" in r.detail


def test_no_hallucination_fails_when_forbidden_in_source() -> None:
    assert not evaluate_check(check("no_hallucination", "docker-compose"), HITS).passed


def test_no_hallucination_without_value_fails() -> None:
    assert not evaluate_check(check("no_hallucination", None), HITS).passed


# --- empty results ----------------------------------------------------------


def test_positive_checks_fail_on_no_hits() -> None:
    assert not evaluate_check(check("substring", "anything"), []).passed
    assert not evaluate_check(check("source_cited", "anything"), []).passed


def test_no_hallucination_passes_on_no_hits() -> None:
    # nothing retrieved -> nothing spurious surfaced.
    assert evaluate_check(check("no_hallucination", "anything"), []).passed
