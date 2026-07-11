"""Contradiction-judgment chain: prompt → chat → JSON-object verdict.

Two facts go in; a single verdict comes out. The prompt is
*refute-by-default*: facts that are merely different, or that could
both be true, are NOT contradictions — only genuine mutual exclusivity
counts. This is the precision-favouring dual of extraction's
cite-or-refuse: we would rather miss a contradiction than file a false
dissent for a human to reject.

When a contradiction is found the verdict names the fact believed
wrong (`target`, "a" or "b") and a corrected `proposed_payload` (a JSON
object — the `dissent_propose` contract rejects scalars). Parsing is
strict: a reply that is not the requested object, or a claimed
contradiction missing its verdict flag, raises `JudgeParseError`, which
the runner counts per pair instead of silently dropping it.
"""

import json
from typing import Any, Literal

from langchain_core.language_models import BaseChatModel
from langchain_core.output_parsers import StrOutputParser
from langchain_core.prompts import ChatPromptTemplate
from langchain_core.runnables import Runnable
from pydantic import BaseModel, ValidationError


class ContradictionVerdict(BaseModel):
    contradicts: bool
    reason: str = ""
    target: Literal["a", "b"] | None = None
    proposed_payload: dict[str, Any] | None = None


class JudgeParseError(Exception):
    """The model's reply was not a well-formed verdict object."""


_SYSTEM = """\
You compare two durable facts from a homelab memory store and decide \
whether they contradict in meaning.

A contradiction means the two facts cannot both be true at the same \
time about the same subject — e.g. the same service placed on two \
different hosts, or a setting given two incompatible values. Facts that \
are merely different, describe different subjects, or could both hold \
at once are NOT contradictions. When in doubt, they do not contradict: \
a missed contradiction is cheap, a false one wastes a human's review.

Reply with a single JSON object only — no prose, no code fences:
{{"contradicts": <true|false>, "reason": "<one sentence>"}}

If and only if they contradict, also include which fact is wrong and \
the corrected payload for it:
{{"contradicts": true, "reason": "<why they cannot both be true>", \
"target": "<a|b>", "proposed_payload": {{<corrected object for the \
target fact, same shape as its payload>}}}}

The target is the fact you believe is outdated or mistaken; \
proposed_payload must be a JSON object."""

_PROMPT = ChatPromptTemplate.from_messages(
    [("system", _SYSTEM), ("human", "Fact A:\n{a}\n\nFact B:\n{b}")]
)


def build_contradiction_chain(chat: BaseChatModel) -> Runnable[dict, str]:
    return _PROMPT | chat | StrOutputParser()


def parse_verdict(raw: str) -> ContradictionVerdict:
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
        return ContradictionVerdict.model_validate(data)
    except ValidationError as exc:
        raise JudgeParseError(f"bad verdict shape: {exc}") from exc
