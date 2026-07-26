"""Provenance stamping — klams#676: a report must say what it ran against."""

import re
from pathlib import Path

from klams_mind.eval.provenance import Provenance, now_stamp, parse_provenance, suite_digest

PROV = Provenance(
    run_at="2026-07-26T04:10:27Z",
    suite_file="homelab-retrieval.toml",
    suite_hash="sha256:ab12cd34ef56",
    klams_version="0.1.26",
)


def test_suite_digest_is_content_addressed(tmp_path: Path) -> None:
    a, b = tmp_path / "a.toml", tmp_path / "b.toml"
    a.write_text('name = "s"\n')
    b.write_text('name = "s"\n')
    assert suite_digest(a) == suite_digest(b), "same bytes, same digest"
    assert suite_digest(a).startswith("sha256:")

    b.write_text('name = "s"\n# one more query later\n')
    assert suite_digest(a) != suite_digest(b), "an edited suite is a different suite"


def test_now_stamp_is_utc_iso_to_the_second() -> None:
    assert re.fullmatch(r"\d{4}-\d{2}-\d{2}T\d{2}:\d{2}:\d{2}Z", now_stamp())


def test_rendered_provenance_round_trips() -> None:
    text = "# Retrieval eval — homelab\n\n" + "\n".join(PROV.markdown_lines()) + "\n"
    assert parse_provenance(text) == PROV


def test_unknown_klams_version_round_trips_as_none() -> None:
    prov = Provenance("2026-07-26T04:10:27Z", "s.toml", "sha256:abc123abc123", None)
    text = "\n".join(prov.markdown_lines())
    assert "unknown" in text
    assert parse_provenance(text) == prov


def test_parse_returns_none_for_an_unstamped_report() -> None:
    """The pre-#676 baselines carry no block at all; that is not an error."""
    assert parse_provenance("# Retrieval eval — old\n\n**OK — 4/4 passed.**\n") is None
