"""Extraction chain: prompt wiring and strict JSON-array parsing."""

import pytest
from langchain_core.language_models.fake_chat_models import FakeListChatModel

from klams_mind.extract.chain import (
    CandidateFact,
    ExtractParseError,
    build_extraction_chain,
    parse_candidates,
)

REPLY = '[{"text": "klams runs on kubs0", "evidence": "klams runs on kubs0", "tags": ["klams"]}]'


def test_chain_threads_window_through_prompt() -> None:
    chain = build_extraction_chain(FakeListChatModel(responses=[REPLY]))
    assert chain.invoke({"window": "USER: klams runs on kubs0"}) == REPLY


def test_parse_plain_array() -> None:
    facts = parse_candidates(REPLY)
    assert facts == [
        CandidateFact(text="klams runs on kubs0", evidence="klams runs on kubs0", tags=["klams"])
    ]


def test_parse_tolerates_fences_and_prose() -> None:
    fenced = f"Here you go:\n```json\n{REPLY}\n```"
    assert len(parse_candidates(fenced)) == 1
    assert parse_candidates("[]") == []


@pytest.mark.parametrize(
    "raw",
    [
        "no array here",
        "[{broken json}]",
        '{"text": "an object, not an array"}',
        '[{"text": "missing evidence"}]',
    ],
)
def test_parse_rejects_bad_replies(raw: str) -> None:
    with pytest.raises(ExtractParseError):
        parse_candidates(raw)
