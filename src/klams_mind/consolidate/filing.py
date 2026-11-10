"""File judged consolidations into klams' supersede-proposal queue.

klams 058 gave consolidation a review queue (WI 3331, Ken's 2026-10-23
"propose-merge path"): klams-mind files a proposal with
`supersede_propose`, and an identity holding `manage` accepts or rejects
it with `supersede_proposal_resolve`. This module files and reads; it
never resolves, and the client has no method that could.

Four rules shape a run, all recorded in sprints/014-supersede-propose:

- **A cap per run** (`FILE_CAP`), so a first run cannot flood the queue.
- **Nothing twice.** A pair already inside a pending proposal is not
  judged again (the model's merged text varies run to run, so klams'
  exact-match dedupe would not catch it), and a pair inside a rejected
  one is not proposed again — a rejection is an answer.
- **No overlap within a run.** klams re-validates at acceptance (058 D3):
  of two proposals sharing a record, the second goes `stale` once the
  first is accepted. Filing both spends the cap on a proposal that is
  likely to die; the second is deferred to a later run instead.
- **Stale first.** A stale proposal's cluster is re-detected from the
  live corpus — against the survivor, since the retired records no
  longer appear — and its pairs are judged ahead of the rest.
"""

from collections.abc import Iterable
from dataclasses import dataclass
from typing import Literal
from uuid import UUID

from klams_mind.consolidate.pairing import CandidatePair
from klams_mind.consolidate.runner import Proposal
from klams_mind.klams import KlamsClient, KlamsError, KnowledgeMemory, SupersedeProposal

# Most proposals one run files. Small on purpose: the queue is read by a
# human (or an agent Ken directs), and a run that files 60 is a run nobody
# reviews. The first live run found 8 actionable pairs in 312 notes.
FILE_CAP = 5

# klams' `reason` bound (supersede_propose.rs, MAX_REASON_CHARS).
MAX_REASON = 2000
# klams' list cap; a list that comes back this long may be missing rows.
LIST_LIMIT = 200

_EXCERPT_MAX = 600


@dataclass(frozen=True)
class Ledger:
    """What the queue already holds, read once at the start of a run."""

    pending: list[SupersedeProposal]
    rejected: list[SupersedeProposal]
    stale: list[SupersedeProposal]
    truncated: tuple[str, ...] = ()

    def covering(self, pair: CandidatePair) -> "Skipped | None":
        """The pending or rejected proposal that already holds both records."""
        ids = {pair.a.id, pair.b.id}
        for row in self.pending:
            if ids <= row.ids:
                return Skipped(pair, "pending", str(row.id))
        for row in self.rejected:
            if ids <= row.ids:
                return Skipped(pair, "rejected", str(row.id))
        return None


async def read_ledger(client: KlamsClient) -> Ledger:
    lists = {
        status: await client.supersede_proposals_list(status=status, limit=LIST_LIMIT)
        for status in ("pending", "rejected", "stale")
    }
    return Ledger(
        pending=lists["pending"],
        rejected=lists["rejected"],
        stale=lists["stale"],
        truncated=tuple(s for s, rows in lists.items() if len(rows) >= LIST_LIMIT),
    )


@dataclass(frozen=True)
class Skipped:
    pair: CandidatePair
    status: Literal["pending", "rejected"]
    proposal_id: str


def triage(
    pairs: list[CandidatePair], ledger: Ledger
) -> tuple[list[CandidatePair], list[Skipped]]:
    """Drop pairs the queue already answers; put stale clusters first.

    The sort is stable, so within each group the best-cosine-first order
    `find_near_duplicates` produced still holds.
    """
    to_judge: list[CandidatePair] = []
    skipped: list[Skipped] = []
    for pair in pairs:
        hit = ledger.covering(pair)
        if hit is None:
            to_judge.append(pair)
        else:
            skipped.append(hit)
    stale_ids = set().union(*(row.ids for row in ledger.stale))
    to_judge.sort(key=lambda p: not ({p.a.id, p.b.id} & stale_ids))
    return to_judge, skipped


def _excerpt(text: str, limit: int) -> str:
    flat = " ".join(text.split())
    return flat if len(flat) <= limit else flat[: limit - 1].rstrip() + "…"


def _line(label: str, note: KnowledgeMemory, budget: int) -> str:
    head = f"{label} {note.id} ({note.created_at:%Y-%m-%d}, by {note.author.agent_name}): "
    return head + _excerpt(note.text, max(budget - len(head), 40))


def reason_for(p: Proposal) -> str:
    """The reviewer's whole case, within klams' 2,000 characters.

    Names both records with an excerpt of each, the judge's reason, and
    what acceptance would do — so a proposal can be judged without
    opening either record.
    """
    pair = p.pair
    keep, retire = (pair.a, pair.b) if str(pair.a.id) == p.keep_id else (pair.b, pair.a)
    head = (
        f"klams-mind consolidation: {p.status}, cosine {pair.score:.3f}. "
        f"Judge: {_excerpt(p.reason, 400)}"
    )
    if p.status == "merge":
        action = "Accepting writes this proposal's merged text as a new memory replacing both."
    else:
        action = "Accepting retires the second note into the first, which stays as written."
    budget = min((MAX_REASON - len(head) - len(action) - 3) // 2, _EXCERPT_MAX)
    reason = "\n".join(
        [head, _line("Keep", keep, budget), _line("Retire", retire, budget), action]
    )
    return reason[:MAX_REASON]


Outcome = Literal["filed", "deduped", "deferred", "over_cap", "failed"]


@dataclass
class Filing:
    proposal: Proposal
    outcome: Outcome
    proposal_id: str | None = None
    detail: str = ""


async def file_proposals(
    client: KlamsClient, judged: Iterable[Proposal], *, cap: int = FILE_CAP
) -> list[Filing]:
    """File each actionable proposal, best first, up to `cap` new ones."""
    filings: list[Filing] = []
    claimed: dict[UUID, str] = {}
    filed = 0
    for p in judged:
        if p.status not in ("merge", "duplicate") or p.keep_id is None or p.retire_id is None:
            continue
        ids = {UUID(p.keep_id), UUID(p.retire_id)}
        overlap = sorted(str(claimed[i]) for i in ids & claimed.keys())
        if overlap:
            filings.append(
                Filing(p, "deferred", detail=f"shares a record with {overlap[0]} filed this run")
            )
            continue
        if filed >= cap:
            filings.append(Filing(p, "over_cap"))
            continue
        try:
            out = await client.supersede_propose(
                keeper_id=p.keep_id, retire_ids=[p.retire_id], reason=reason_for(p), text=p.text
            )
        except KlamsError as exc:
            filings.append(Filing(p, "failed", detail=f"{exc.error_code or 'error'}: {exc}"))
            continue
        pid = str(out.proposal.id)
        claimed |= dict.fromkeys(ids, pid)
        if out.deduped:
            filings.append(Filing(p, "deduped", pid))
        else:
            filed += 1
            filings.append(Filing(p, "filed", pid))
    return filings


@dataclass(frozen=True)
class StaleNote:
    proposal_id: str
    outcome: Literal["re-filed", "not re-filed"]
    detail: str


def stale_notes(
    ledger: Ledger, *, live: set[UUID], filings: list[Filing]
) -> tuple[list[StaleNote], int]:
    """What became of each stale proposal whose cluster still stands.

    A stale proposal with no retiree left live is *settled* — the
    acceptance that staled it already consumed every record it would
    have retired — and is only counted.
    """
    filed = [
        (f, {UUID(f.proposal.keep_id or ""), UUID(f.proposal.retire_id or "")})
        for f in filings
        if f.outcome in ("filed", "deduped")
    ]
    notes: list[StaleNote] = []
    settled = 0
    for row in ledger.stale:
        if not set(row.retire_ids) & live:
            settled += 1
            continue
        by = [f.proposal_id for f, ids in filed if ids & row.ids]
        if by:
            notes.append(StaleNote(str(row.id), "re-filed", f"as {', '.join(map(str, by))}"))
        else:
            standing = ", ".join(str(i) for i in sorted(row.ids & live, key=str))
            notes.append(StaleNote(str(row.id), "not re-filed", f"live: {standing}"))
    return notes, settled
