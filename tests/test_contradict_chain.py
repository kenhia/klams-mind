"""Contradiction judge: refute-by-default verdict parsing."""

import json

import pytest

from klams_mind.contradict.chain import (
    ContradictionVerdict,
    JudgeParseError,
    parse_verdict,
)


def verdict(**kw: object) -> str:
    return json.dumps(kw)


def test_parses_clear_verdict() -> None:
    v = parse_verdict(verdict(contradicts=False, reason="different hosts, both plausible"))
    assert v == ContradictionVerdict(contradicts=False, reason="different hosts, both plausible")
    assert v.target is None
    assert v.proposed_payload is None


def test_parses_contradiction_with_target_and_payload() -> None:
    v = parse_verdict(
        verdict(
            contradicts=True,
            reason="same service cannot live on two hosts",
            target="a",
            proposed_payload={"host": "kai", "service": "klams"},
        )
    )
    assert v.contradicts
    assert v.target == "a"
    assert v.proposed_payload == {"host": "kai", "service": "klams"}


def test_tolerates_fences_and_prose_around_object() -> None:
    raw = 'Here is my call:\n```json\n{"contradicts": false, "reason": "ok"}\n```\nDone.'
    v = parse_verdict(raw)
    assert not v.contradicts


def test_non_object_reply_raises() -> None:
    with pytest.raises(JudgeParseError):
        parse_verdict("no json here at all")


def test_bad_json_raises() -> None:
    with pytest.raises(JudgeParseError):
        parse_verdict('{"contradicts": true, ')


def test_missing_required_field_raises() -> None:
    with pytest.raises(JudgeParseError):
        parse_verdict(verdict(reason="forgot the verdict flag"))


def test_target_must_be_a_or_b() -> None:
    with pytest.raises(JudgeParseError):
        parse_verdict(verdict(contradicts=True, reason="x", target="c", proposed_payload={"k": 1}))
