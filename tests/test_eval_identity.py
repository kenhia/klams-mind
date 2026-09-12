"""Eval-run identity (klams-mind #735).

Sprint 033's retrospective measured `search_sample` at ~400 of 532 rows
being the eval suite's own 21 golden queries, all logged as caller
`klams-mind` and so indistinguishable from klams-mind's genuine
session-extraction searches. The log exists to mine *real* agent queries
for eval growth, so mining it naively closes a feedback loop: the suite
harvests its own queries back into itself.

`search_sample`'s `caller` is the caller's klams identity, not anything
`register_author` says — verified in klams
`crates/klams-types/src/auth.rs`. Sprint 010 (korg:2423) moved that
identity from a bearer grant to a declared `X-Homelab-Agent` name, so
the eval run now presents `klams-mind-eval` as a *name*: the row it
matches in `[[auth.identities]]` is read-scoped, and nothing is minted.

The mechanism changed; the contract did not. `eval_klams_config` still
returns `(config, distinct)`, and `distinct=False` still means this
run's rows will be indistinguishable from real agent queries.
"""

from pathlib import Path

from klams_mind.config import Config, KlamsConfig, load_config
from klams_mind.eval.provenance import Provenance, parse_provenance
from klams_mind.eval.runner import eval_klams_config

MAIN = "klams-mind"
EVAL = "klams-mind-eval"


# --- config -----------------------------------------------------------------


def test_eval_agent_name_comes_from_the_environment() -> None:
    cfg = load_config(path=Path("/nonexistent.toml"), env={"KLAMS_EVAL_AGENT_NAME": "other-eval"})
    assert cfg.klams.eval_agent_name == "other-eval"


def test_eval_agent_name_defaults_distinct_from_the_main_name() -> None:
    """Silently reusing the main identity is the bug #735 is about."""
    cfg = load_config(path=Path("/nonexistent.toml"), env={})
    assert cfg.klams.agent_name == MAIN
    assert cfg.klams.eval_agent_name == EVAL


# --- the swap ---------------------------------------------------------------


def test_eval_config_swaps_in_the_eval_agent_name() -> None:
    cfg = Config(klams=KlamsConfig(base_url="http://k:7777"))

    scoped, distinct = eval_klams_config(cfg.klams)

    assert scoped.agent_name == EVAL
    assert scoped.base_url == "http://k:7777"  # same service, different identity
    assert distinct is True


def test_an_empty_eval_name_falls_back_and_says_it_is_not_distinct() -> None:
    """Falling back must still work — an eval you cannot run measures nothing."""
    cfg = Config(klams=KlamsConfig(eval_agent_name=""))

    scoped, distinct = eval_klams_config(cfg.klams)

    assert scoped.agent_name == MAIN
    assert distinct is False


def test_an_eval_name_equal_to_the_main_name_is_not_distinct() -> None:
    """The indistinguishable case #735 exists to catch, spelled as a name."""
    cfg = Config(klams=KlamsConfig(eval_agent_name=MAIN))

    scoped, distinct = eval_klams_config(cfg.klams)

    assert scoped.agent_name == MAIN
    assert distinct is False


def test_the_swap_does_not_mutate_the_original_config() -> None:
    klams = KlamsConfig()
    eval_klams_config(klams)
    assert klams.agent_name == MAIN


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
