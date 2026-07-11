"""Detection workflow: candidate pairs → judgment → optional dissent.

Propose-first, mirroring extraction: dry-run (the default) judges every
pair and prints the review surface; `apply=True` files a dissent for
each confirmed contradiction via klams' `dissent_propose`, targeting the
fact the judge believes is wrong and citing the other as the conflict.

A judge reply that claims a contradiction but gives no concrete,
object-shaped correction (missing target, empty payload, empty reason)
is `unactionable` — refused, never filed. That is the cite-or-refuse
discipline of extraction applied to corrections: klams would reject a
scalar payload, and a human should not be asked to review a dissent
with no proposed fix.
"""

from dataclasses import dataclass, field
from typing import Literal

from langchain_core.runnables import Runnable

from klams_mind.contradict.chain import ContradictionVerdict, JudgeParseError, parse_verdict
from klams_mind.contradict.pairing import CandidatePair, fact_text
from klams_mind.klams import KlamsClient

Status = Literal["clear", "contradiction", "filed", "unactionable"]


@dataclass
class JudgedPair:
    pair: CandidatePair
    status: Status
    reason: str
    detail: str
    target_id: str | None = None
    contradicting_id: str | None = None
    proposed_payload: dict | None = None
    dissent_id: str | None = None


@dataclass
class DetectionResult:
    query: str
    judge_failures: list[str] = field(default_factory=list)
    judged: list[JudgedPair] = field(default_factory=list)

    @property
    def pairs(self) -> int:
        return len(self.judged)

    @property
    def contradictions(self) -> int:
        return sum(1 for j in self.judged if j.status in ("contradiction", "filed"))

    @property
    def filed(self) -> int:
        return sum(1 for j in self.judged if j.status == "filed")


async def detect_contradictions(
    pairs: list[CandidatePair],
    chain: Runnable[dict, str],
    client: KlamsClient,
    *,
    query: str,
    apply: bool = False,
    author_id: str | None = None,
) -> DetectionResult:
    if apply and author_id is None:
        raise ValueError("apply=True requires a registered author_id")
    result = DetectionResult(query=query)
    for i, pair in enumerate(pairs, start=1):
        raw = await chain.ainvoke({"a": fact_text(pair.a), "b": fact_text(pair.b)})
        try:
            verdict = parse_verdict(raw)
        except JudgeParseError as exc:
            result.judge_failures.append(f"pair {i}: {exc}")
            continue
        result.judged.append(await _act(pair, verdict, client, apply, author_id))
    return result


async def _act(
    pair: CandidatePair,
    verdict: ContradictionVerdict,
    client: KlamsClient,
    apply: bool,
    author_id: str | None,
) -> JudgedPair:
    if not verdict.contradicts:
        return JudgedPair(pair, "clear", verdict.reason, "no contradiction")
    reason = verdict.reason.strip()
    payload = verdict.proposed_payload
    if verdict.target not in ("a", "b") or not payload or not reason:
        return JudgedPair(
            pair, "unactionable", reason, "contradiction claimed without a concrete correction"
        )
    target = pair.a if verdict.target == "a" else pair.b
    other = pair.b if verdict.target == "a" else pair.a
    tid, cid = str(target.id), str(other.id)
    if not apply or author_id is None:  # author guaranteed when applying (checked upstream)
        return JudgedPair(pair, "contradiction", reason, "dry-run", tid, cid, payload)
    filed = await client.dissent_propose(
        fact_id=tid,
        proposed_payload=payload,
        reason=reason,
        author_id=author_id,
        contradicting_memory_id=cid,
    )
    detail = f"dissent {filed.dissent_id}" + (" (deduped)" if filed.deduped else "")
    return JudgedPair(pair, "filed", reason, detail, tid, cid, payload, str(filed.dissent_id))
