"""Smoke failure diagnosis (klams-mind #831).

`smoke` used to report every klams failure identically — "step 'connect
to klams MCP' failed: unhandled errors in a TaskGroup" — with a hint
that named the token first, so a pure reachability failure read as a
credential problem. Worse, the MCP client raises an `ExceptionGroup`, so
the useful leaf did not surface even *with* `--debug` (rich renders the
`SmokeError` chain and swallows the group).

The exception shapes below are recorded from live probes against
kubs0:7777 on 2026-09-10 — a bogus token, a refused port, and a
nonexistent host.
"""

import httpx
import pytest
from pydantic import ValidationError

from klams_mind.cli import diagnose, leaf_cause
from klams_mind.config import Config, KlamsConfig, ModelConfig

CFG = Config(
    klams=KlamsConfig(base_url="http://kubs0:7777", token="t"),
    model=ModelConfig(base_url="https://kai:8000/v1"),
)


def _group(leaf: Exception) -> Exception:
    """What the MCP client actually raises: a nested TaskGroup pair."""
    inner: Exception = ExceptionGroup("unhandled errors in a TaskGroup", [leaf])
    return ExceptionGroup("unhandled errors in a TaskGroup", [inner])


def _status(code: int) -> httpx.HTTPStatusError:
    request = httpx.Request("POST", "http://kubs0:7777/mcp")
    return httpx.HTTPStatusError(
        f"Client error '{code}' for url 'http://kubs0:7777/mcp'",
        request=request,
        response=httpx.Response(code, request=request),
    )


# --- leaf_cause -------------------------------------------------------------


def test_leaf_cause_unwraps_nested_exception_groups() -> None:
    leaf = httpx.ConnectError("All connection attempts failed")
    assert leaf_cause(_group(leaf)) is leaf


def test_leaf_cause_returns_a_plain_exception_unchanged() -> None:
    leaf = RuntimeError("boom")
    assert leaf_cause(leaf) is leaf


# --- diagnose ---------------------------------------------------------------


def test_connect_error_says_unreachable_and_names_the_url() -> None:
    """The acceptance criterion: klams stopped -> unreachable, with the URL."""
    hint = diagnose("connect to klams MCP", _group(httpx.ConnectError("refused")), CFG)

    assert "unreachable" in hint
    assert "http://kubs0:7777" in hint
    assert "KLAMS_TOKEN" not in hint  # the whole point of #831


def test_connect_timeout_is_also_unreachable() -> None:
    hint = diagnose("klams healthz", _group(httpx.ConnectTimeout("slow")), CFG)
    assert "unreachable" in hint


@pytest.mark.parametrize("code", [401, 403])
def test_rejected_token_says_so_and_not_unreachable(code: int) -> None:
    """The other acceptance criterion: bogus KLAMS_TOKEN -> token rejected."""
    hint = diagnose("connect to klams MCP", _group(_status(code)), CFG)

    assert "KLAMS_TOKEN" in hint
    assert str(code) in hint
    assert "unreachable" not in hint


def test_other_http_status_reports_the_code_without_blaming_the_token() -> None:
    hint = diagnose("klams healthz", _group(_status(503)), CFG)

    assert "503" in hint
    assert "KLAMS_TOKEN" not in hint


def test_a_hostname_equal_to_this_host_suggests_the_loopback_override() -> None:
    """The #831 note: `kubs0` resolves to 127.0.1.1, klams binds 127.0.0.1."""
    cfg = Config(klams=KlamsConfig(base_url="http://kubs0:7777"))
    hint = diagnose("connect to klams MCP", _group(httpx.ConnectError("x")), cfg, host="kubs0")

    assert "KLAMS_URL=http://localhost:7777" in hint


def test_a_remote_hostname_does_not_suggest_the_override() -> None:
    hint = diagnose("connect to klams MCP", _group(httpx.ConnectError("x")), CFG, host="kai")
    assert "localhost" not in hint


def test_a_parse_failure_is_named_as_contract_drift() -> None:
    """klams 0.1.46's compact contract presented exactly this way."""
    with pytest.raises(ValidationError) as caught:
        ModelConfig.model_validate({"base_url": []})
    hint = diagnose("memory search", _group(caught.value), CFG)

    assert "could not parse" in hint
    assert "version" in hint


def test_a_model_step_points_at_the_model_endpoint_not_klams() -> None:
    hint = diagnose("resolve model name", _group(httpx.ConnectError("x")), CFG)

    assert "https://kai:8000/v1" in hint
    assert "kubs0:7777" not in hint


def test_an_unclassified_failure_keeps_the_general_hint() -> None:
    hint = diagnose("register author", _group(RuntimeError("odd")), CFG)

    assert "http://kubs0:7777" in hint
    assert "KLAMS_TOKEN" in hint
