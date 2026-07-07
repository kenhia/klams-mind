"""Retrieval checks over a query's results.

klams returns retrieved memories, not a synthesized answer, so these are
deterministic assertions about *what retrieval surfaced* — no LLM in the
loop. A `RetrievedItem` is the backend-neutral view a check sees:
`content` (the memory's text/payload), `source` (source_path or a
kind:type key), and `tags`. Dispatch is a plain `if/elif` on the check
type (as in krag); an unknown type returns a failing result rather than
raising.

- `substring`       — content recall: expected text is in some hit's content.
- `source_cited`    — source recall: expected fragment is in some hit's
                      source or equals a tag.
- `no_hallucination`— precision/absence: the forbidden fragment appears in
                      no hit's content or source (the dual of source_cited).
"""

from dataclasses import dataclass, field

from klams_mind.eval.suite import Check


@dataclass(frozen=True)
class RetrievedItem:
    content: str
    source: str
    tags: list[str] = field(default_factory=list)


@dataclass(frozen=True)
class CheckResult:
    check: Check
    passed: bool
    detail: str


def evaluate_check(check: Check, hits: list[RetrievedItem]) -> CheckResult:
    if check.type == "substring":
        return _substring(check, hits)
    if check.type == "source_cited":
        return _source_cited(check, hits)
    if check.type == "no_hallucination":
        return _no_hallucination(check, hits)
    return CheckResult(check, False, f"unknown check type {check.type!r}")


def _missing_value(check: Check) -> CheckResult:
    return CheckResult(check, False, f"{check.type} check requires a value")


def _substring(check: Check, hits: list[RetrievedItem]) -> CheckResult:
    if check.value is None:
        return _missing_value(check)
    haystack = "\n".join(h.content for h in hits).lower()
    found = check.value.lower() in haystack
    detail = (
        f"found {check.value!r} in retrieved content"
        if found
        else f"{check.value!r} absent from {len(hits)} retrieved item(s)"
    )
    return CheckResult(check, found, detail)


def _source_cited(check: Check, hits: list[RetrievedItem]) -> CheckResult:
    if check.value is None:
        return _missing_value(check)
    for h in hits:
        if check.value in h.source or check.value in h.tags:
            return CheckResult(check, True, f"cited by {h.source}")
    return CheckResult(check, False, f"{check.value!r} not among {len(hits)} source(s)")


def _no_hallucination(check: Check, hits: list[RetrievedItem]) -> CheckResult:
    if check.value is None:
        return _missing_value(check)
    needle = check.value.lower()
    for h in hits:
        if needle in h.content.lower() or needle in h.source.lower():
            return CheckResult(check, False, f"forbidden {check.value!r} surfaced in {h.source}")
    return CheckResult(check, True, f"{check.value!r} absent from results")
