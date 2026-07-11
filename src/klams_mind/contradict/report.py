"""Render a DetectionResult as markdown or JSON (mirrors extract.report).

Markdown is the review surface for the propose-first loop: pairs
grouped by status, each contradiction showing the two facts, which is
the target, the cited conflict, and the proposed correction — so
accepting or rejecting a dissent never requires re-querying klams.
"""

import json

from klams_mind.contradict.pairing import fact_text
from klams_mind.contradict.runner import DetectionResult, JudgedPair, Status

_ORDER: tuple[Status, ...] = ("filed", "contradiction", "unactionable", "clear")
_MARK = {"filed": "✓", "contradiction": "!", "unactionable": "?", "clear": "·"}


def _render_pair(jp: JudgedPair) -> list[str]:
    a, b = jp.pair.a, jp.pair.b
    lines = [f"- {_MARK[jp.status]} {jp.reason or '(no reason given)'}"]
    lines.append(f"  - A [{a.id}]: {fact_text(a)}")
    lines.append(f"  - B [{b.id}]: {fact_text(b)}")
    if jp.target_id is not None:
        which = "A" if jp.target_id == str(a.id) else "B"
        lines.append(f"  - target: {which} [{jp.target_id}] · cites [{jp.contradicting_id}]")
    if jp.proposed_payload is not None:
        lines.append(f"  - proposed: {json.dumps(jp.proposed_payload, ensure_ascii=False)}")
    if jp.detail not in ("dry-run", "no contradiction"):
        lines.append(f"  - {jp.detail}")
    return lines


def to_markdown(result: DetectionResult) -> str:
    by = {s: [j for j in result.judged if j.status == s] for s in _ORDER}
    counts = ", ".join(f"{len(by[s])} {s}" for s in _ORDER)
    failures = f" — {len(result.judge_failures)} judge failure(s)" if result.judge_failures else ""
    lines = [
        f"# Contradiction detection — {result.query}",
        "",
        f"**{result.pairs} pair(s) judged** ({counts}){failures}.",
    ]
    for status in _ORDER:
        group = by[status]
        if not group:
            continue
        lines += ["", f"## {status.capitalize()}", ""]
        for jp in group:
            lines += _render_pair(jp)
    if result.judge_failures:
        lines += ["", "## Judge failures", ""]
        lines += [f"- {f}" for f in result.judge_failures]
    return "\n".join(lines) + "\n"


def to_json(result: DetectionResult) -> str:
    return json.dumps(
        {
            "query": result.query,
            "pairs": result.pairs,
            "contradictions": result.contradictions,
            "filed": result.filed,
            "judge_failures": result.judge_failures,
            "judged": [
                {
                    "status": j.status,
                    "reason": j.reason,
                    "detail": j.detail,
                    "fact_a": str(j.pair.a.id),
                    "fact_b": str(j.pair.b.id),
                    "target_id": j.target_id,
                    "contradicting_id": j.contradicting_id,
                    "proposed_payload": j.proposed_payload,
                    "dissent_id": j.dissent_id,
                }
                for j in result.judged
            ],
        },
        indent=2,
    )
