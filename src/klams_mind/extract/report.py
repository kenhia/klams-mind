"""Render an ExtractionResult as markdown or JSON (mirrors eval.report).

Markdown is the review surface for the propose-first loop: candidates
grouped by status, each with its evidence quote, so accepting or
rejecting a fact never requires rereading the transcript.
"""

import json

from klams_mind.extract.runner import ExtractionResult, Status

_ORDER: tuple[Status, ...] = ("written", "proposed", "duplicate", "uncited")
_MARK = {"written": "✓", "proposed": "•", "duplicate": "=", "uncited": "✗"}


def to_markdown(result: ExtractionResult) -> str:
    by = {s: [c for c in result.candidates if c.status == s] for s in _ORDER}
    counts = ", ".join(f"{len(by[s])} {s}" for s in _ORDER)
    failures = (
        f" — {len(result.parse_failures)} window parse failure(s)" if result.parse_failures else ""
    )
    lines = [
        f"# Extraction — {result.transcript}",
        "",
        f"**{len(result.candidates)} candidate(s) from {result.windows} window(s)**"
        f" ({counts}){failures}.",
    ]
    for status in _ORDER:
        group = by[status]
        if not group:
            continue
        lines += ["", f"## {status.capitalize()}", ""]
        for c in group:
            lines.append(f"- {_MARK[status]} {c.fact.text}")
            lines.append(f'  - evidence: "{c.fact.evidence}"')
            extras = f"window {c.window}"
            if c.fact.tags:
                extras += f" · tags: {', '.join(c.fact.tags)}"
            if c.detail != "dry-run":
                extras += f" · {c.detail}"
            lines.append(f"  - {extras}")
    if result.parse_failures:
        lines += ["", "## Window parse failures", ""]
        lines += [f"- {f}" for f in result.parse_failures]
    return "\n".join(lines) + "\n"


def to_json(result: ExtractionResult) -> str:
    return json.dumps(
        {
            "transcript": result.transcript,
            "windows": result.windows,
            "written": result.written,
            "parse_failures": result.parse_failures,
            "candidates": [
                {
                    "text": c.fact.text,
                    "evidence": c.fact.evidence,
                    "tags": c.fact.tags,
                    "status": c.status,
                    "detail": c.detail,
                    "window": c.window,
                }
                for c in result.candidates
            ],
        },
        indent=2,
    )
