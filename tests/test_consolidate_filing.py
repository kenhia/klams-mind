"""Filing consolidation proposals into klams' supersede queue (sprint 014,
WI 3331). klams-mind files; an identity with `manage` resolves. What this
pins: the per-run cap, no re-filing what is pending or was rejected, stale
proposals re-detected first, and a reason a reviewer can judge alone."""

import json
from typing import Any
from uuid import UUID

from mcp.types import CallToolResult

from klams_mind.config import KlamsConfig
from klams_mind.consolidate.filing import (
    MAX_REASON,
    Ledger,
    file_proposals,
    read_ledger,
    reason_for,
    stale_notes,
    triage,
)
from klams_mind.consolidate.pairing import CandidatePair
from klams_mind.consolidate.runner import Proposal
from klams_mind.klams import KlamsClient, SupersedeProposal
from tests.test_consolidate import A, B, C, agent_note
from tests.test_klams_client import tool_error, tool_ok
from tests.test_klams_supersede import PROPOSAL

D = agent_note("d0", "kmon writes one observation per host per hour.")


def row(keep: Any, *retire: Any, status: str = "pending", pid: str = "c0") -> SupersedeProposal:
    return SupersedeProposal.model_validate(
        {
            **PROPOSAL,
            "id": f"01980000-0000-7000-8000-0000000000{pid}",
            "keeper_id": str(keep.id),
            "retire_ids": [str(r.id) for r in retire],
            "status": status,
        }
    )


def dup(keep: Any, retire: Any, score: float = 0.9) -> Proposal:
    return Proposal(
        CandidatePair(keep, retire, score),
        "duplicate",
        "same claim",
        keep_id=str(keep.id),
        retire_id=str(retire.id),
    )


class Queue:
    """Fakes klams' proposal tools; fails on anything that could resolve."""

    def __init__(self, lists: dict[str, list[SupersedeProposal]] | None = None) -> None:
        self.lists = lists or {}
        self.filed: list[dict[str, Any]] = []
        self.fail_on: str | None = None

    async def __call__(self, name: str, args: dict[str, Any]) -> CallToolResult:
        if name == "supersede_proposals_list":
            rows = self.lists.get(args["status"], [])
            return tool_ok({"proposals": [json.loads(r.model_dump_json()) for r in rows]})
        assert name == "supersede_propose", f"filing must never call {name}"
        if args["keeper_id"] == self.fail_on:
            return tool_error("NOT_FOUND", "already superseded")
        self.filed.append(args)
        pid = f"01980000-0000-7000-8000-{len(self.filed):012d}"
        proposal = {**PROPOSAL, **args, "id": pid, "text": args.get("text")}
        return tool_ok({"proposal": proposal, "deduped": False})


def client(queue: Queue) -> KlamsClient:
    return KlamsClient(KlamsConfig(), tool_caller=queue)


# --- the ledger and triage ------------------------------------------------


async def test_read_ledger_reads_pending_rejected_and_stale_at_the_max_limit() -> None:
    queue = Queue({"pending": [row(A, B)], "stale": [row(A, C, status="stale")]})
    ledger = await read_ledger(client(queue))
    assert [len(ledger.pending), len(ledger.rejected), len(ledger.stale)] == [1, 0, 1]
    assert ledger.truncated == ()


def test_triage_skips_pairs_already_pending_or_rejected() -> None:
    ledger = Ledger(pending=[row(A, B)], rejected=[row(C, D, status="rejected")], stale=[])
    ab, cd, ac = CandidatePair(A, B, 0.95), CandidatePair(C, D, 0.9), CandidatePair(A, C, 0.86)
    to_judge, skipped = triage([ab, cd, ac], ledger)
    assert to_judge == [ac]
    assert [(s.pair, s.status) for s in skipped] == [(ab, "pending"), (cd, "rejected")]


def test_triage_puts_pairs_from_stale_proposals_first() -> None:
    ledger = Ledger(pending=[], rejected=[], stale=[row(A, D, status="stale")])
    bc, cd = CandidatePair(B, C, 0.95), CandidatePair(C, D, 0.88)
    to_judge, _ = triage([bc, cd], ledger)
    assert to_judge == [cd, bc]


# --- filing ---------------------------------------------------------------


async def test_files_merges_and_duplicates_and_skips_the_rest() -> None:
    merge = Proposal(
        CandidatePair(A, B, 0.93), "merge", "overlap", str(A.id), str(B.id), text="both"
    )
    distinct = Proposal(CandidatePair(A, C, 0.9), "distinct", "different")
    queue = Queue()
    filings = await file_proposals(client(queue), [merge, distinct, dup(C, D)], cap=5)
    assert [f.outcome for f in filings] == ["filed", "filed"]
    assert queue.filed[0]["keeper_id"] == str(A.id)
    assert queue.filed[0]["retire_ids"] == [str(B.id)]
    assert queue.filed[0]["text"] == "both"
    assert "text" not in queue.filed[1]


async def test_the_cap_bounds_what_one_run_files() -> None:
    queue = Queue()
    filings = await file_proposals(client(queue), [dup(A, B), dup(C, D)], cap=1)
    assert [f.outcome for f in filings] == ["filed", "over_cap"]
    assert len(queue.filed) == 1


async def test_overlapping_proposals_in_one_run_are_deferred_not_filed() -> None:
    # klams 058 D3: an overlapping sibling would only go stale on acceptance.
    queue = Queue()
    filings = await file_proposals(client(queue), [dup(A, B), dup(A, C)], cap=5)
    assert [f.outcome for f in filings] == ["filed", "deferred"]
    assert filings[0].proposal_id is not None
    assert filings[0].proposal_id in filings[1].detail


async def test_a_refused_proposal_is_recorded_and_the_run_continues() -> None:
    queue = Queue()
    queue.fail_on = str(A.id)
    filings = await file_proposals(client(queue), [dup(A, B), dup(C, D)], cap=5)
    assert [f.outcome for f in filings] == ["failed", "filed"]
    assert "NOT_FOUND" in filings[0].detail


# --- the reason -----------------------------------------------------------


def test_reason_names_both_records_and_what_acceptance_does() -> None:
    reason = reason_for(dup(A, B, 0.931))
    assert "duplicate" in reason and "0.931" in reason and "same claim" in reason
    assert f"Keep {A.id}" in reason and f"Retire {B.id}" in reason
    assert A.text in reason and B.text in reason
    assert "by claude" in reason


def test_reason_fits_klams_limit_whatever_the_note_sizes() -> None:
    big_a = agent_note("e0", "a " * 3000)
    big_b = agent_note("f0", "b " * 3000)
    p = Proposal(
        CandidatePair(big_a, big_b, 0.9), "duplicate", "r" * 3000, str(big_a.id), str(big_b.id)
    )
    reason = reason_for(p)
    assert len(reason) <= MAX_REASON
    assert f"Retire {big_b.id}" in reason


# --- stale ----------------------------------------------------------------


async def test_stale_notes_say_what_became_of_each_cluster() -> None:
    refiled = row(A, B, status="stale", pid="d1")
    standing = row(C, D, status="stale", pid="d2")
    settled = row(A, agent_note("99", "gone"), status="stale", pid="d3")
    queue = Queue()
    filings = await file_proposals(client(queue), [dup(B, A)], cap=5)
    ledger = Ledger(pending=[], rejected=[], stale=[refiled, standing, settled])
    notes, settled_count = stale_notes(ledger, live={A.id, B.id, C.id, D.id}, filings=filings)
    assert settled_count == 1
    by = {n.proposal_id: n for n in notes}
    assert by[str(refiled.id)].outcome == "re-filed"
    assert str(filings[0].proposal_id) in by[str(refiled.id)].detail
    assert by[str(standing.id)].outcome == "not re-filed"
    assert UUID(by[str(standing.id)].proposal_id) == standing.id
