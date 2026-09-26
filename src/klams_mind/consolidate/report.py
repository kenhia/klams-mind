"""Render a ConsolidationResult as markdown or JSON (mirrors contradict.report).

Markdown is the review surface: the bounds the run worked within, then
each proposal with both notes, the verdict, and the call an apply step
would make — so accepting or rejecting one never requires re-querying
klams.
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
    if p.status == "merge":
        lines.append(
            f'  - apply: `memory_supersede(id="{p.keep_id}", text=…)`, retire `{p.retire_id}`'
        )
        lines.append("  - merged text:")
        lines += _quote(p.text or "")
    elif p.status == "duplicate":
        lines.append(f"  - apply: keep `{p.keep_id}`, retire `{p.retire_id}`")
    return lines


def to_markdown(result: ConsolidationResult) -> str:
    by = {s: [p for p in result.judged if p.status == s] for s in _ORDER}
    counts = ", ".join(f"{len(by[s])} {s}" for s in _ORDER)
    failures = f" — {len(result.judge_failures)} judge failure(s)" if result.judge_failures else ""
    lines = [
        "# Consolidation proposal",
        "",
        "**Propose-only** — nothing here has been applied to klams.",
        "",
        f"- {result.walked} memories walked, {result.curated} curated (agent-authored knowledge)",
        f"- {result.candidates} pair(s) at cosine ≥ {result.threshold}; "
        f"{len(result.judged) + len(result.judge_failures)} judged (cap {result.max_pairs}), "
        f"{result.unjudged} left unjudged",
        f"- verdicts: {counts}{failures}",
    ]
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
