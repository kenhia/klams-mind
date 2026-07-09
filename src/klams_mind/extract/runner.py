"""Extraction workflow: windows → candidates → vetting → optional write.

Vetting is the codified krag lesson: a candidate whose `evidence` quote
does not appear verbatim (whitespace/case-normalized) in the window it
came from is `uncited` and can never be written, no matter how
plausible it reads. Dedupe asks klams what it already knows (normalized
containment against existing knowledge text — the scored envelope is
available, but a similarity threshold is deferred until the corpus
teaches us one). Propose-first: writes happen only when `apply=True`.
"""

from collections.abc import Sequence
from dataclasses import dataclass, field
from typing import Literal

from langchain_core.runnables import Runnable

from klams_mind.extract.chain import CandidateFact, ExtractParseError, parse_candidates
from klams_mind.klams import KlamsClient

Status = Literal["proposed", "uncited", "duplicate", "written"]


@dataclass
class VettedCandidate:
    fact: CandidateFact
    status: Status
    detail: str
    window: int  # 1-based index of the window the fact came from


@dataclass
class ExtractionResult:
    transcript: str
    windows: int
    parse_failures: list[str] = field(default_factory=list)
    candidates: list[VettedCandidate] = field(default_factory=list)

    @property
    def written(self) -> int:
        return sum(1 for c in self.candidates if c.status == "written")


def _normalize(s: str) -> str:
    return " ".join(s.lower().split())


def is_cited(evidence: str, window: str) -> bool:
    return bool(evidence.strip()) and _normalize(evidence) in _normalize(window)


async def find_duplicate(client: KlamsClient, text: str) -> str | None:
    """Return the id of an existing memory that already says this, if any."""
    hits = await client.memory_search(text, kinds=["knowledge"], top_k=5)
    norm = _normalize(text)
    for h in hits:
        m = h.memory
        if m.kind != "knowledge":
            continue
        existing = _normalize(m.text)
        if norm in existing or existing in norm:
            return str(m.id)
    return None


async def extract_windows(
    windows: list[str],
    chain: Runnable[dict, str],
    client: KlamsClient,
    *,
    transcript: str,
    apply: bool = False,
    author_id: str | None = None,
    tags: Sequence[str] = ("session-extract",),
) -> ExtractionResult:
    if apply and author_id is None:
        raise ValueError("apply=True requires a registered author_id")
    result = ExtractionResult(transcript=transcript, windows=len(windows))
    for i, window in enumerate(windows, start=1):
        raw = await chain.ainvoke({"window": window})
        try:
            candidates = parse_candidates(raw)
        except ExtractParseError as exc:
            result.parse_failures.append(f"window {i}: {exc}")
            continue
        for fact in candidates:
            result.candidates.append(
                await _vet(fact, window, i, client, transcript, apply, author_id, tags)
            )
    return result


async def _vet(
    fact: CandidateFact,
    window: str,
    index: int,
    client: KlamsClient,
    transcript: str,
    apply: bool,
    author_id: str | None,
    tags: Sequence[str],
) -> VettedCandidate:
    if not is_cited(fact.evidence, window):
        return VettedCandidate(fact, "uncited", "evidence not found verbatim in window", index)
    dup = await find_duplicate(client, fact.text)
    if dup is not None:
        return VettedCandidate(fact, "duplicate", f"matches memory {dup}", index)
    if not apply or author_id is None:  # author guaranteed by extract_windows when applying
        return VettedCandidate(fact, "proposed", "dry-run", index)
    written = await client.add_knowledge(
        author_id, fact.text, tags=[*tags, *fact.tags], source_path=transcript
    )
    return VettedCandidate(fact, "written", f"memory {written.id}", index)
