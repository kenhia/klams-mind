"""Judge candidate pairs into consolidation proposals.

Propose-only by construction: this module takes no klams client and so
cannot write. A proposal names what an apply step would do —
`memory_supersede(id=keep, text=merged)` for a merge, and the record to
retire in both cases — and stops there. How apply retires the second
record is not decided here (sprint 013's follow-ups).
"""

from dataclasses import dataclass, field
from typing import Literal

from langchain_core.runnables import Runnable

from klams_mind.consolidate.chain import JudgeParseError, MergeVerdict, parse_verdict
from klams_mind.consolidate.pairing import CandidatePair
from klams_mind.klams import KnowledgeMemory

Status = Literal["merge", "duplicate", "unactionable", "distinct"]


def note_text(note: KnowledgeMemory) -> str:
    return f"[{note.created_at:%Y-%m-%d}, by {note.author.agent_name}]\n{note.text}"


@dataclass
class Proposal:
    pair: CandidatePair
    status: Status
    reason: str
    keep_id: str | None = None
    retire_id: str | None = None
    text: str | None = None  # the merged replacement; merges only


@dataclass
class ConsolidationResult:
    walked: int
    curated: int
    threshold: float
    max_pairs: int
    candidates: int
    judged: list[Proposal] = field(default_factory=list)
    judge_failures: list[str] = field(default_factory=list)

    @property
    def unjudged(self) -> int:
        return self.candidates - len(self.judged) - len(self.judge_failures)


async def judge_pairs(
    pairs: list[CandidatePair], chain: Runnable[dict, str], *, max_pairs: int
) -> tuple[list[Proposal], list[str]]:
    """Judge the first `max_pairs` pairs (callers pass them best-first)."""
    judged: list[Proposal] = []
    failures: list[str] = []
    for i, pair in enumerate(pairs[:max_pairs], start=1):
        raw = await chain.ainvoke({"a": note_text(pair.a), "b": note_text(pair.b)})
        try:
            verdict = parse_verdict(raw)
        except JudgeParseError as exc:
            failures.append(f"pair {i}: {exc}")
            continue
        judged.append(_propose(pair, verdict))
    return judged, failures


def _propose(pair: CandidatePair, verdict: MergeVerdict) -> Proposal:
    reason = verdict.reason.strip()
    if verdict.verdict == "distinct":
        return Proposal(pair, "distinct", reason)
    merged = (verdict.merged_text or "").strip()
    if verdict.keep is None or not reason or (verdict.verdict == "merge" and not merged):
        return Proposal(pair, "unactionable", reason or "(no reason given)")
    keep, retire = (pair.a, pair.b) if verdict.keep == "a" else (pair.b, pair.a)
    return Proposal(
        pair,
        verdict.verdict,
        reason,
        keep_id=str(keep.id),
        retire_id=str(retire.id),
        text=merged if verdict.verdict == "merge" else None,
    )
