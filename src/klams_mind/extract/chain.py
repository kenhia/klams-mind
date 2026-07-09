"""Candidate-fact extraction chain: prompt → chat → JSON-array parse.

The prompt asks for durable facts, each carrying a verbatim `evidence`
quote (cite-or-refuse). Parsing is deliberately strict — a reply that
is not the requested JSON array raises `ExtractParseError`, which the
runner counts per window instead of silently yielding nothing.
"""

import json

from langchain_core.language_models import BaseChatModel
from langchain_core.output_parsers import StrOutputParser
from langchain_core.prompts import ChatPromptTemplate
from langchain_core.runnables import Runnable
from pydantic import BaseModel, ValidationError


class CandidateFact(BaseModel):
    text: str
    evidence: str
    tags: list[str] = []


class ExtractParseError(Exception):
    """The model's reply was not the requested JSON array."""


_SYSTEM = """\
You distill durable facts from an excerpt of a coding-session transcript \
between a user and an AI agent working in the user's homelab.

Extract only facts worth remembering weeks from now: how systems are \
configured, where services run and deploy, API and wire contracts, \
decisions and their reasons, project conventions. Skip transient task \
state, speculation, pleasantries, and anything about the mechanics of \
this conversation itself.

Cite or refuse: every fact must include "evidence" — an exact quote \
copied verbatim from the excerpt that supports it. If you cannot quote \
support for a fact, do not output that fact. If the excerpt holds no \
durable facts, output [].

Reply with a JSON array only — no prose, no code fences:
[{{"text": "<one standalone sentence>", "evidence": "<verbatim quote>", \
"tags": ["lowercase-keyword"]}}]"""

_PROMPT = ChatPromptTemplate.from_messages(
    [("system", _SYSTEM), ("human", "Transcript excerpt:\n\n{window}")]
)


def build_extraction_chain(chat: BaseChatModel) -> Runnable[dict, str]:
    return _PROMPT | chat | StrOutputParser()


def parse_candidates(raw: str) -> list[CandidateFact]:
    """Parse the model reply; tolerant of fences/prose around the array."""
    start, end = raw.find("["), raw.rfind("]")
    if start == -1 or end < start:
        raise ExtractParseError(f"no JSON array in reply: {raw[:120]!r}")
    try:
        data = json.loads(raw[start : end + 1])
    except json.JSONDecodeError as exc:
        raise ExtractParseError(f"bad JSON in reply: {exc}") from exc
    if not isinstance(data, list):
        raise ExtractParseError("reply JSON is not an array")
    facts: list[CandidateFact] = []
    for item in data:
        try:
            facts.append(CandidateFact.model_validate(item))
        except ValidationError as exc:
            raise ExtractParseError(f"bad candidate shape: {exc}") from exc
    return facts
