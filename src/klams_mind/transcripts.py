"""Claude Code session-transcript reader.

A transcript is JSONL, one object per line; only `type: "user"` and
`type: "assistant"` lines are conversation, and even those carry
harness noise this reader strips: meta and sidechain entries,
tool_use/tool_result blocks, `<command-name>` skill wrappers (the
injected skill body dwarfs any fact inside it), and `<system-reminder>`
spans. What's left is what a person reading the session would call the
conversation.
"""

import json
import re
from dataclasses import dataclass
from pathlib import Path

_SYSTEM_REMINDER = re.compile(r"<system-reminder>.*?</system-reminder>", re.DOTALL)
_COMMAND_MARKERS = ("<command-message>", "<command-name>", "<local-command-stdout>")


class TranscriptError(Exception):
    """The transcript file is missing, unreadable, or not JSONL."""


@dataclass(frozen=True)
class Turn:
    role: str  # "user" | "assistant"
    text: str


def read_transcript(path: Path) -> list[Turn]:
    try:
        lines = path.read_text().splitlines()
    except OSError as exc:
        raise TranscriptError(f"cannot read {path}: {exc}") from exc
    turns: list[Turn] = []
    for n, line in enumerate(lines, start=1):
        if not line.strip():
            continue
        try:
            entry = json.loads(line)
        except json.JSONDecodeError as exc:
            raise TranscriptError(f"{path}:{n}: not JSON: {exc}") from exc
        turn = _to_turn(entry)
        if turn is not None:
            turns.append(turn)
    return turns


def _to_turn(entry: object) -> Turn | None:
    if not isinstance(entry, dict):
        return None
    role = entry.get("type")
    if not isinstance(role, str) or role not in ("user", "assistant"):
        return None
    if entry.get("isMeta") or entry.get("isSidechain"):
        return None
    message = entry.get("message")
    content = message.get("content") if isinstance(message, dict) else None
    if isinstance(content, str):
        text = content
    elif isinstance(content, list):
        parts: list[str] = []
        for block in content:
            if not isinstance(block, dict) or block.get("type") != "text":
                continue
            block_text = block.get("text")
            if isinstance(block_text, str):
                parts.append(block_text)
        text = "\n".join(parts)
    else:
        return None
    if any(marker in text for marker in _COMMAND_MARKERS):
        return None
    text = _SYSTEM_REMINDER.sub("", text).strip()
    if not text:
        return None
    return Turn(role=role, text=text)


def windows(turns: list[Turn], max_chars: int = 12_000) -> list[str]:
    """Pack turns into `ROLE: text` windows of at most `max_chars` each.

    A single turn longer than the budget is truncated rather than
    dropped — the head of a long message is usually where the substance
    is.
    """
    out: list[str] = []
    buf: list[str] = []
    size = 0
    for t in turns:
        piece = f"{t.role.upper()}: {t.text}"[:max_chars]
        added = len(piece) + (2 if buf else 0)  # "\n\n" separator between pieces
        if buf and size + added > max_chars:
            out.append("\n\n".join(buf))
            buf, size = [], 0
            added = len(piece)
        buf.append(piece)
        size += added
    if buf:
        out.append("\n\n".join(buf))
    return out
