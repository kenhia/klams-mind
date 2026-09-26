"""Merge-judgment chain: two notes in, one verdict out.

*Refute-by-default*, like contradiction detection: notes on related
subjects, or complementary notes, are `distinct`. A missed merge costs
nothing; a wrong one retires a record somebody wrote on purpose.

`duplicate` covers both "adds nothing the other lacks" and "its claims
are wholly replaced by the other's" (a supersession nobody recorded) —
the proposed action is the same: keep one, retire the other. `merge`
returns the single note that would replace both.
"""

import json
from typing import Literal

from langchain_core.language_models import BaseChatModel
from langchain_core.output_parsers import StrOutputParser
from langchain_core.prompts import ChatPromptTemplate
from langchain_core.runnables import Runnable
from pydantic import BaseModel, ValidationError


class MergeVerdict(BaseModel):
    verdict: Literal["duplicate", "merge", "distinct"]
    reason: str = ""
    keep: Literal["a", "b"] | None = None
    merged_text: str | None = None


class JudgeParseError(Exception):
    """The model's reply was not a well-formed verdict object."""


_SYSTEM = """\
You review two notes from a homelab memory store and decide whether they \
should be consolidated. Each note is headed with its date and author.

- "duplicate": both say the same thing, or one note's claims are wholly \
replaced by the other's (e.g. a newer note that updates every claim). \
Name the note to keep in "keep" — the more complete, or the current one.
- "merge": the same subject, mostly overlapping, each has a detail the \
other lacks, and one note could hold both without losing anything. Name \
the note to keep and give "merged_text": the single replacement note, in \
the notes' own style, dropping nothing true from either.
- "distinct": anything else — different subjects, related but \
complementary notes, or notes that disagree. When in doubt, distinct: a \
missed merge is cheap, a wrong one destroys a record.

Reply with a single JSON object only — no prose, no code fences:
{{"verdict": "<duplicate|merge|distinct>", "reason": "<one sentence>", \
"keep": "<a|b, omit for distinct>", "merged_text": "<merge only>"}}"""

_PROMPT = ChatPromptTemplate.from_messages(
    [("system", _SYSTEM), ("human", "Note A:\n{a}\n\nNote B:\n{b}")]
)


def build_merge_chain(chat: BaseChatModel) -> Runnable[dict, str]:
    return _PROMPT | chat | StrOutputParser()


def parse_verdict(raw: str) -> MergeVerdict:
    """Parse the model reply; tolerant of fences/prose around the object."""
    start, end = raw.find("{"), raw.rfind("}")
    if start == -1 or end < start:
        raise JudgeParseError(f"no JSON object in reply: {raw[:120]!r}")
    try:
        data = json.loads(raw[start : end + 1])
    except json.JSONDecodeError as exc:
        raise JudgeParseError(f"bad JSON in reply: {exc}") from exc
    if not isinstance(data, dict):
        raise JudgeParseError("reply JSON is not an object")
    try:
        return MergeVerdict.model_validate(data)
    except ValidationError as exc:
        raise JudgeParseError(f"bad verdict shape: {exc}") from exc
