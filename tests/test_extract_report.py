"""Extraction reporter: markdown review surface and JSON."""

import json

from klams_mind.extract.chain import CandidateFact
from klams_mind.extract.report import to_json, to_markdown
from klams_mind.extract.runner import ExtractionResult, Status, VettedCandidate


def vc(status: Status, text: str = "klams listens on kubs0:7777") -> VettedCandidate:
    fact = CandidateFact(text=text, evidence=text, tags=["klams"])
    detail = {"written": "memory abc", "proposed": "dry-run", "duplicate": "matches memory xyz"}
    return VettedCandidate(fact, status, detail.get(status, "nope"), 1)


RESULT = ExtractionResult(
    transcript="session.jsonl",
    windows=3,
    parse_failures=["window 2: no JSON array in reply"],
    candidates=[vc("written"), vc("proposed"), vc("duplicate"), vc("uncited")],
)


def test_markdown_groups_by_status_with_evidence() -> None:
    md = to_markdown(RESULT)
    assert "**4 candidate(s) from 3 window(s)**" in md
    assert "1 written, 1 proposed, 1 duplicate, 1 uncited" in md
    for heading in ("## Written", "## Proposed", "## Duplicate", "## Uncited"):
        assert heading in md
    assert 'evidence: "klams listens on kubs0:7777"' in md
    assert "matches memory xyz" in md
    assert "window 2: no JSON array in reply" in md


def test_json_carries_statuses_and_counts() -> None:
    payload = json.loads(to_json(RESULT))
    assert payload["windows"] == 3
    assert payload["written"] == 1
    assert [c["status"] for c in payload["candidates"]] == [
        "written",
        "proposed",
        "duplicate",
        "uncited",
    ]
    assert payload["parse_failures"] == ["window 2: no JSON array in reply"]
