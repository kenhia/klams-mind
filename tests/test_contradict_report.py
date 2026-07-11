"""Contradiction report: markdown review surface + JSON envelope."""

import json

from klams_mind.contradict.pairing import CandidatePair
from klams_mind.contradict.report import to_json, to_markdown
from klams_mind.contradict.runner import DetectionResult, JudgedPair
from tests.test_contradict_pairing import as_fact, make_fact

A = as_fact(make_fact("a0", {"host": "kubs0", "service": "klams"}))
B = as_fact(make_fact("b0", {"host": "kai", "service": "klams"}))
PAIR = CandidatePair(a=A, b=B)


def sample_result() -> DetectionResult:
    return DetectionResult(
        query="homelab services",
        judge_failures=["pair 3: no JSON object in reply"],
        judged=[
            JudgedPair(
                PAIR,
                "filed",
                "one service cannot run on two hosts",
                "dissent d-1",
                target_id=str(B.id),
                contradicting_id=str(A.id),
                proposed_payload={"host": "kubs0", "service": "klams"},
                dissent_id="d-1",
            ),
            JudgedPair(PAIR, "clear", "different subjects", "no contradiction"),
        ],
    )


def test_markdown_headlines_counts_and_shows_correction() -> None:
    md = to_markdown(sample_result())
    assert "# Contradiction detection" in md
    assert "homelab services" in md
    assert "1 filed" in md and "1 clear" in md
    assert "1 judge failure" in md
    # the correction and the cited conflict are visible without rereading klams
    assert str(B.id) in md
    assert '"host": "kubs0"' in md or "host" in md
    assert "one service cannot run on two hosts" in md


def test_json_is_machine_readable_and_counts_match() -> None:
    payload = json.loads(to_json(sample_result()))
    assert payload["query"] == "homelab services"
    assert payload["pairs"] == 2
    assert payload["filed"] == 1
    assert payload["contradictions"] == 1
    assert payload["judge_failures"] == ["pair 3: no JSON object in reply"]
    (filed,) = [j for j in payload["judged"] if j["status"] == "filed"]
    assert filed["target_id"] == str(B.id)
    assert filed["contradicting_id"] == str(A.id)
    assert filed["proposed_payload"] == {"host": "kubs0", "service": "klams"}
    assert filed["dissent_id"] == "d-1"
