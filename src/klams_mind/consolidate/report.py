"""Render a ConsolidationResult as markdown or JSON (mirrors contradict.report).

Markdown is the review surface: the bounds the run worked within, what
was filed to klams' supersede queue (or would be, on a dry run), then
each proposal with both notes, the verdict, and the `supersede_propose`
arguments — so judging one never requires re-querying klams.
"""

import json

from klams_mind.consolidate.runner import ConsolidationResult, Proposal, Status

_ORDER: tuple[Status, ...] = ("merge", "duplicate", "unactionable", "distinct")
_MARK = {"merge": "+", "duplicate": "=", "unactionable": "?", "distinct": "·"}


def _quote(text: str) -> list[str]:
    return [f"    > {line}".rstrip() for line in text.splitlines() or [""]]


def _render(p: Proposal) -> list[str]:
    a, b = p.pair.a, p.pair.b
    lines = [f"- {_MARK[p.status]} cosine {p.pair.score:.3f} — {p.reason or '(no reason given)'}"]
    for label, note in (("A", a), ("B", b)):
        lines.append(
            f"  - {label} [{note.id}] {note.created_at:%Y-%m-%d} by {note.author.agent_name}"
        )
        lines += _quote(note.text)
    if p.status in ("merge", "duplicate"):
        text = ", text=…" if p.status == "merge" else ""
        lines.append(
            f'  - propose: `supersede_propose(keeper_id="{p.keep_id}", '
            f'retire_ids=["{p.retire_id}"]{text})`'
        )
    if p.status == "merge":
        lines.append("  - merged text:")
        lines += _quote(p.text or "")
    return lines


def _queue_lines(result: ConsolidationResult) -> list[str]:
    lines: list[str] = []
    if result.filings is not None:
        lines += ["", "## Filed", ""]
        if not result.filings:
            lines.append("- nothing actionable to file")
        for f in result.filings:
            p = f.proposal
            ref = f" → proposal `{f.proposal_id}`" if f.proposal_id else ""
            detail = f" ({f.detail})" if f.detail else ""
            lines.append(
                f"- {f.outcome}: {p.status} keep `{p.keep_id}` retire `{p.retire_id}`{ref}{detail}"
            )
    if result.skipped:
        lines += ["", "## Already in the queue", ""]
        lines += [
            f"- {s.status} `{s.proposal_id}`: `{s.pair.a.id}` + `{s.pair.b.id}`"
            for s in result.skipped
        ]
    if result.stale or result.stale_settled:
        lines += ["", "## Stale proposals", ""]
        lines += [f"- `{n.proposal_id}` {n.outcome} — {n.detail}" for n in result.stale]
        if result.stale_settled:
            lines.append(f"- {result.stale_settled} settled (no retiree left live)")
    return lines


def _mode_line(result: ConsolidationResult) -> str:
    if result.filings is None:
        return (
            "**Dry run** — nothing filed. `--file` files up to "
            f"{result.file_cap} to klams' supersede queue."
        )
    filed = sum(f.outcome == "filed" for f in result.filings)
    return (
        f"**Filed {filed} proposal(s)** (cap {result.file_cap}) to klams' supersede queue, "
        "pending review. klams-mind never resolves them: an identity with `manage` "
        "accepts or rejects with `supersede_proposal_resolve`."
    )


def to_markdown(result: ConsolidationResult) -> str:
    by = {s: [p for p in result.judged if p.status == s] for s in _ORDER}
    counts = ", ".join(f"{len(by[s])} {s}" for s in _ORDER)
    failures = f" — {len(result.judge_failures)} judge failure(s)" if result.judge_failures else ""
    lines = [
        "# Consolidation proposal",
        "",
        _mode_line(result),
        "",
        f"- {result.walked} memories walked, {result.curated} curated (agent-authored knowledge)",
        f"- {result.candidates} pair(s) at cosine ≥ {result.threshold}; "
        f"{len(result.judged) + len(result.judge_failures)} judged (cap {result.max_pairs}), "
        f"{result.unjudged} left unjudged",
        f"- verdicts: {counts}{failures}",
    ]
    if result.skipped:
        lines.append(f"- {len(result.skipped)} pair(s) skipped: already pending or rejected")
    if result.ledger_truncated:
        lines.append(
            f"- warning: the {', '.join(result.ledger_truncated)} proposal list hit klams' "
            "limit, so some already-answered pairs may have been judged again"
        )
    lines += _queue_lines(result)
    for status in _ORDER:
        if by[status]:
            lines += ["", f"## {status.capitalize()}", ""]
            for p in by[status]:
                lines += _render(p)
    if result.judge_failures:
        lines += ["", "## Judge failures", ""]
        lines += [f"- {f}" for f in result.judge_failures]
    return "\n".join(lines) + "\n"


def to_json(result: ConsolidationResult) -> str:
    return json.dumps(
        {
            "walked": result.walked,
            "curated": result.curated,
            "threshold": result.threshold,
            "max_pairs": result.max_pairs,
            "candidates": result.candidates,
            "unjudged": result.unjudged,
            "judge_failures": result.judge_failures,
            "file_cap": result.file_cap,
            "filings": None
            if result.filings is None
            else [
                {
                    "outcome": f.outcome,
                    "proposal_id": f.proposal_id,
                    "detail": f.detail,
                    "keep_id": f.proposal.keep_id,
                    "retire_id": f.proposal.retire_id,
                }
                for f in result.filings
            ],
            "skipped": [
                {
                    "status": s.status,
                    "proposal_id": s.proposal_id,
                    "a": str(s.pair.a.id),
                    "b": str(s.pair.b.id),
                }
                for s in result.skipped
            ],
            "stale": [
                {"proposal_id": n.proposal_id, "outcome": n.outcome, "detail": n.detail}
                for n in result.stale
            ],
            "stale_settled": result.stale_settled,
            "ledger_truncated": list(result.ledger_truncated),
            "proposals": [
                {
                    "status": p.status,
                    "reason": p.reason,
                    "score": p.pair.score,
                    "a": str(p.pair.a.id),
                    "b": str(p.pair.b.id),
                    "keep_id": p.keep_id,
                    "retire_id": p.retire_id,
                    "text": p.text,
                }
                for p in result.judged
            ],
        },
        indent=2,
    )
