"""Eval-run identity (klams-mind #735).

Sprint 033's retrospective measured `search_sample` at ~400 of 532 rows
being the eval suite's own 21 golden queries, all logged as caller
`klams-mind` and so indistinguishable from klams-mind's genuine
session-extraction searches. The log exists to mine *real* agent queries
for eval growth, so mining it naively closes a feedback loop: the suite
harvests its own queries back into itself.

`search_sample`'s `caller` comes from the klams **token's** grant
(`[[auth.tokens]].agent_name`), not from `register_author` — verified in
klams `crates/klams-types/src/auth.rs`. So the client cannot relabel
itself; it can only present a *different token*. This is the klams-mind
half: configure and use an eval-scoped token, record which identity ran,
and say so loudly when there isn't one.

The grant itself is klams-side and is handed up — see the sprint doc.
"""

from pathlib import Path

from klams_mind.config import Config, KlamsConfig, load_config
from klams_mind.eval.provenance import Provenance, parse_provenance
from klams_mind.eval.runner import eval_klams_config

MAIN = "main-token-value"
EVAL = "eval-token-value"


# --- config -----------------------------------------------------------------


def test_eval_token_comes_from_the_environment() -> None:
    cfg = load_config(path=Path("/nonexistent.toml"), env={"KLAMS_EVAL_TOKEN": EVAL})
    assert cfg.klams.eval_token == EVAL


def test_eval_token_defaults_to_empty_not_to_the_main_token() -> None:
    """Silently reusing the main token is the bug #735 is about."""
    cfg = load_config(path=Path("/nonexistent.toml"), env={"KLAMS_TOKEN": MAIN})
    assert cfg.klams.token == MAIN
    assert cfg.klams.eval_token == ""


# --- the swap ---------------------------------------------------------------


def test_eval_config_swaps_in_the_eval_token() -> None:
    cfg = Config(klams=KlamsConfig(base_url="http://k:7777", token=MAIN, eval_token=EVAL))

    scoped, distinct = eval_klams_config(cfg.klams)

    assert scoped.token == EVAL
    assert scoped.base_url == "http://k:7777"  # same service, different grant
    assert distinct is True


def test_eval_config_falls_back_to_the_main_token_and_says_it_is_not_distinct() -> None:
    """Falling back must still work — an eval you cannot run measures nothing."""
    cfg = Config(klams=KlamsConfig(token=MAIN))

    scoped, distinct = eval_klams_config(cfg.klams)

    assert scoped.token == MAIN
    assert distinct is False


def test_the_swap_does_not_mutate_the_original_config() -> None:
    klams = KlamsConfig(token=MAIN, eval_token=EVAL)
    eval_klams_config(klams)
    assert klams.token == MAIN


# --- provenance -------------------------------------------------------------


def test_provenance_records_the_caller_identity() -> None:
    """So a miner can tell from the report which rows this run produced."""
    prov = Provenance(
        run_at="2026-09-10T12:00:00Z",
        suite_file="s.toml",
        suite_hash="sha256:abc",
        klams_version="0.1.46",
        caller="klams-mind-eval",
    )
    assert "- **Caller:** klams-mind-eval" in "\n".join(prov.markdown_lines())


def test_provenance_round_trips_the_caller() -> None:
    prov = Provenance(
        run_at="2026-09-10T12:00:00Z",
        suite_file="s.toml",
        suite_hash="sha256:abc",
        klams_version="0.1.46",
        caller="klams-mind-eval",
    )
    recovered = parse_provenance("\n".join(prov.markdown_lines()))
    assert recovered is not None
    assert recovered.caller == "klams-mind-eval"


def test_a_report_without_a_caller_line_parses_with_caller_none() -> None:
    """Pre-#735 baselines carry no Caller line; that is a fact about them."""
    prov = Provenance(run_at="r", suite_file="s.toml", suite_hash="sha256:abc")
    text = "\n".join(prov.markdown_lines())
    assert "Caller" not in text
    recovered = parse_provenance(text)
    assert recovered is not None
    assert recovered.caller is None
