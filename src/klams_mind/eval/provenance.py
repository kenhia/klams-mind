"""What a report was run against: date, klams version, suite identity.

klams#676. The harness emitted reports and a checked-in baseline that
recorded nothing about their origin. A baseline five klams sprints stale
therefore presented as two regressions on sprint 026's first live run,
and the only thing that eventually gave it away was that its `score`
values were raw cosine (~0.84) — impossible after klams 024 replaced
score sort with RRF. That was an accidental fingerprint; this module is
the deliberate one.

The block is rendered into the markdown report *and* parsed back out of
it, so a run can compare itself against the checked-in baseline without
a second sidecar file to keep in sync.

Deliberately absent: corpus point count (not cheaply available — klams
exposes no total over MCP, and reaching Qdrant directly is out of
bounds for a client), and any notion of baseline expiry. Refreshing a
baseline stays a deliberate act; an eval that silently rebaselines
measures nothing.
"""

import hashlib
import re
from dataclasses import dataclass
from datetime import UTC, datetime
from pathlib import Path

# Enough to distinguish suite revisions in a diff without a 64-char wall.
_DIGEST_CHARS = 12

_UNKNOWN = "unknown"

_RUN_AT = re.compile(r"^- \*\*Run:\*\* (\S+)$", re.MULTILINE)
_VERSION = re.compile(r"^- \*\*klams version:\*\* (\S+)$", re.MULTILINE)
_SUITE = re.compile(r"^- \*\*Suite file:\*\* `([^`]+)` \(`(sha256:[0-9a-f]+)`\)$", re.MULTILINE)


@dataclass(frozen=True)
class Provenance:
    run_at: str
    suite_file: str
    suite_hash: str
    klams_version: str | None = None

    def markdown_lines(self) -> list[str]:
        return [
            f"- **Run:** {self.run_at}",
            f"- **klams version:** {self.klams_version or _UNKNOWN}",
            f"- **Suite file:** `{self.suite_file}` (`{self.suite_hash}`)",
        ]


def now_stamp() -> str:
    """UTC, to the second. Seconds are plenty and keep diffs readable."""
    return datetime.now(UTC).strftime("%Y-%m-%dT%H:%M:%SZ")


def suite_digest(path: Path) -> str:
    """Hash the suite file's bytes — comments and whitespace included.

    A whitespace-only edit changing the digest is the intended behaviour:
    the claim is "this exact file", not "an equivalent set of queries".
    """
    return "sha256:" + hashlib.sha256(Path(path).read_bytes()).hexdigest()[:_DIGEST_CHARS]


def parse_provenance(text: str) -> Provenance | None:
    """Recover the block from a rendered report, or None if it has none.

    Pre-#676 artifacts carry no block at all; that is a fact about them,
    not a parse error.
    """
    run_at, suite = _RUN_AT.search(text), _SUITE.search(text)
    if run_at is None or suite is None:
        return None
    version_match = _VERSION.search(text)
    version = version_match.group(1) if version_match else _UNKNOWN
    return Provenance(
        run_at=run_at.group(1),
        suite_file=suite.group(1),
        suite_hash=suite.group(2),
        klams_version=None if version == _UNKNOWN else version,
    )
