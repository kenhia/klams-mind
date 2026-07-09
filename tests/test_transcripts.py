"""Claude Code JSONL reader: what counts as conversation."""

import json
from pathlib import Path

import pytest

from klams_mind.transcripts import TranscriptError, Turn, read_transcript, windows


def line(**kw: object) -> str:
    return json.dumps(kw)


def write(tmp_path: Path, lines: list[str]) -> Path:
    p = tmp_path / "t.jsonl"
    p.write_text("\n".join(lines) + "\n")
    return p


def test_reads_user_and_assistant_text_skips_other_types(tmp_path: Path) -> None:
    p = write(
        tmp_path,
        [
            line(type="mode", mode="normal"),
            line(type="user", message={"role": "user", "content": "klams runs on kubs0"}),
            line(
                type="assistant",
                message={
                    "role": "assistant",
                    "content": [
                        {"type": "text", "text": "Confirmed."},
                        {"type": "tool_use", "id": "x", "name": "Bash", "input": {}},
                    ],
                },
            ),
            line(type="file-history-snapshot", messageId="m"),
        ],
    )
    assert read_transcript(p) == [
        Turn("user", "klams runs on kubs0"),
        Turn("assistant", "Confirmed."),
    ]


def test_skips_meta_sidechain_commands_and_tool_results(tmp_path: Path) -> None:
    p = write(
        tmp_path,
        [
            line(type="user", isMeta=True, message={"role": "user", "content": "meta"}),
            line(type="user", isSidechain=True, message={"role": "user", "content": "side"}),
            line(
                type="user",
                message={"role": "user", "content": "<command-name>/ship</command-name>"},
            ),
            # tool_result blocks carry no "text" type blocks
            line(
                type="user",
                message={
                    "role": "user",
                    "content": [{"type": "tool_result", "tool_use_id": "x", "content": "out"}],
                },
            ),
            line(type="user", message={"role": "user", "content": "keep me"}),
        ],
    )
    assert read_transcript(p) == [Turn("user", "keep me")]


def test_strips_system_reminder_spans(tmp_path: Path) -> None:
    body = "before <system-reminder>noise\nmore noise</system-reminder> after"
    p = write(tmp_path, [line(type="user", message={"role": "user", "content": body})])
    assert read_transcript(p) == [Turn("user", "before  after")]


def test_bad_jsonl_raises_transcript_error(tmp_path: Path) -> None:
    p = tmp_path / "t.jsonl"
    p.write_text("not json\n")
    with pytest.raises(TranscriptError):
        read_transcript(p)
    with pytest.raises(TranscriptError):
        read_transcript(tmp_path / "missing.jsonl")


def test_windows_pack_by_budget_and_truncate_long_turns() -> None:
    turns = [Turn("user", "a" * 50), Turn("assistant", "b" * 50), Turn("user", "c" * 500)]
    wins = windows(turns, max_chars=120)
    # first two fit one window; the long third starts a new one, truncated
    assert len(wins) == 2
    assert "USER: " + "a" * 50 in wins[0] and "ASSISTANT: " + "b" * 50 in wins[0]
    assert len(wins[1]) == 120
    assert wins[1].startswith("USER: ccc")
