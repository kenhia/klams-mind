"""The three retrieval checks as pure functions over retrieved items."""

from klams_mind.eval.checks import RetrievedItem, evaluate_check
from klams_mind.eval.suite import Check, CheckType

HITS = [
    RetrievedItem(
        content="services:\n  image: klams:dev",
        source="/home/ken/src/ai/klams/deploy/docker-compose.yml",
        tags=["homelab"],
    ),
    RetrievedItem(
        content="kvllm serves OpenAI-compatible models on kai:8000",
        source="/home/ken/src/ai/kvllm/README.md",
        tags=[],
    ),
]


def check(type_: CheckType, value: str | None = None) -> Check:
    return Check(type=type_, value=value)


# --- substring: content recall ---------------------------------------------


def test_substring_passes_when_present() -> None:
    r = evaluate_check(check("substring", "image: klams"), HITS)
    assert r.passed


def test_substring_is_case_insensitive() -> None:
    assert evaluate_check(check("substring", "IMAGE: KLAMS"), HITS).passed


def test_substring_fails_when_absent() -> None:
    r = evaluate_check(check("substring", "postgresql cluster"), HITS)
    assert not r.passed
    assert "postgresql cluster" in r.detail


def test_substring_without_value_fails() -> None:
    assert not evaluate_check(check("substring", None), HITS).passed


# --- source_cited: source recall -------------------------------------------


def test_source_cited_matches_source_path_fragment() -> None:
    r = evaluate_check(check("source_cited", "deploy/docker-compose.yml"), HITS)
    assert r.passed


def test_source_cited_matches_tag() -> None:
    assert evaluate_check(check("source_cited", "homelab"), HITS).passed


def test_source_cited_fails_when_not_retrieved() -> None:
    r = evaluate_check(check("source_cited", "nginx.conf"), HITS)
    assert not r.passed


def test_source_cited_without_value_fails() -> None:
    assert not evaluate_check(check("source_cited", None), HITS).passed


# --- no_hallucination: precision / absence ---------------------------------


def test_no_hallucination_passes_when_forbidden_absent() -> None:
    r = evaluate_check(check("no_hallucination", "sourdough"), HITS)
    assert r.passed


def test_no_hallucination_fails_when_forbidden_in_content() -> None:
    r = evaluate_check(check("no_hallucination", "kvllm"), HITS)
    assert not r.passed
    assert "kvllm" in r.detail


def test_no_hallucination_fails_when_forbidden_in_source() -> None:
    assert not evaluate_check(check("no_hallucination", "docker-compose"), HITS).passed


def test_no_hallucination_without_value_fails() -> None:
    assert not evaluate_check(check("no_hallucination", None), HITS).passed


# --- empty results ----------------------------------------------------------


def test_positive_checks_fail_on_no_hits() -> None:
    assert not evaluate_check(check("substring", "anything"), []).passed
    assert not evaluate_check(check("source_cited", "anything"), []).passed


def test_no_hallucination_passes_on_no_hits() -> None:
    # nothing retrieved -> nothing spurious surfaced.
    assert evaluate_check(check("no_hallucination", "anything"), []).passed


# --- klams sprint 026 (#643): the checks that measure what was broken ------
#
# The three checks above all pass on scanner chunks, which is why the
# suite scored 4/4 while every klams#628 failure was happening live.


def k(
    content: str,
    source: str = "/src/x.md",
    content_hash: str | None = None,
    heading_path: str | None = None,
    memory_id: str = "",
    ancestry: tuple[str, ...] = (),
) -> RetrievedItem:
    return RetrievedItem(
        content=content,
        source=source,
        kind="knowledge",
        content_hash=content_hash,
        heading_path=heading_path,
        memory_id=memory_id,
        ancestry=ancestry,
    )


# --- no_duplicates: klams #641's invariant ---------------------------------


def test_no_duplicates_fails_on_a_cross_host_pair() -> None:
    # The live failure shape: same chunk, both hosts, both in the page.
    hits = [
        k("body", "/kai/x.md", content_hash="aaa"),
        k("body", "/kubs0/x.md", content_hash="aaa"),
    ]
    r = evaluate_check(Check(type="no_duplicates"), hits)
    assert not r.passed
    assert "/kai/x.md" in r.detail and "/kubs0/x.md" in r.detail


def test_no_duplicates_passes_on_distinct_content() -> None:
    hits = [k("a", content_hash="aaa"), k("b", content_hash="bbb")]
    assert evaluate_check(Check(type="no_duplicates"), hits).passed


def test_no_duplicates_ignores_hits_without_a_hash() -> None:
    # Facts, events and pre-022 points carry no hash. Two of them must
    # not read as duplicates of each other.
    hits = [
        RetrievedItem(content="a", source="fact:EnvFact", kind="fact"),
        RetrievedItem(content="b", source="fact:EnvFact", kind="fact"),
    ]
    r = evaluate_check(Check(type="no_duplicates"), hits)
    assert r.passed
    assert "no hashed results" in r.detail


def test_no_duplicates_honours_top_n() -> None:
    hits = [
        k("a", content_hash="aaa"),
        k("b", content_hash="bbb"),
        k("a again", content_hash="aaa"),
    ]
    assert evaluate_check(Check(type="no_duplicates", top_n=2), hits).passed
    assert not evaluate_check(Check(type="no_duplicates"), hits).passed


# --- min_body_chars: the junk ceiling (klams F-2.3) ------------------------


def test_min_body_chars_strips_the_breadcrumb_before_measuring() -> None:
    # The exact observed junk chunk: a breadcrumb plus an opening fence.
    # It LOOKS like 40+ chars and scores 0.956, but its body is empty.
    junk = k(
        "kpidash > Dashboard build\n\n```bash",
        heading_path="kpidash > Dashboard build",
    )
    r = evaluate_check(Check(type="min_body_chars", min_chars=40), [junk])
    assert not r.passed
    assert "after stripping breadcrumb" in r.detail


def test_min_body_chars_passes_real_content() -> None:
    good = k(
        "klams > Setup\n\nThe service binds 0.0.0.0:7777 so the viewport "
        "on the LAN can reach it; UFW restricts the port to the subnet.",
        heading_path="klams > Setup",
    )
    assert evaluate_check(Check(type="min_body_chars", min_chars=40), [good]).passed


def test_min_body_chars_ignores_facts_and_events() -> None:
    # A fact payload is legitimately short; the junk ceiling is a claim
    # about chunked prose, not about structured records.
    fact = RetrievedItem(content='EnvFact {"k": 1}', source="fact:EnvFact", kind="fact")
    assert evaluate_check(Check(type="min_body_chars", min_chars=40), [fact]).passed


def test_min_body_chars_requires_min_chars() -> None:
    r = evaluate_check(Check(type="min_body_chars"), [k("x")])
    assert not r.passed
    assert "requires min_chars" in r.detail


# --- memory_id: curated-beats-bulk (klams #628) ----------------------------


def test_memory_id_matches_on_prefix() -> None:
    hits = [k("gotcha", memory_id="019f95dc-df08-70e3-bce0-f209cb7402c4")]
    assert evaluate_check(Check(type="memory_id", value="019f95dc-df08"), hits).passed


def test_memory_id_fails_when_the_memory_is_absent() -> None:
    # klams#628's Query A: the purpose-written gotcha did not appear at all.
    hits = [k("some multae-viae spec chunk", memory_id="deadbeef-0000")]
    r = evaluate_check(Check(type="memory_id", value="019f95dc-df08"), hits)
    assert not r.passed
    assert "absent" in r.detail


def test_memory_id_fails_when_outranked_even_though_present() -> None:
    # The teeth. Presence alone would have passed while the bug was live
    # — #628's complaint was that the right memory LOST its slot.
    hits = [
        k("bulk chunk", memory_id="aaaa"),
        k("bulk chunk", memory_id="bbbb"),
        k("the gotcha", memory_id="019f95dc-df08-70e3"),
    ]
    r = evaluate_check(Check(type="memory_id", value="019f95dc-df08", max_rank=1), hits)
    assert not r.passed
    assert "rank 2" in r.detail and "outranked" in r.detail


def test_memory_id_passes_within_max_rank() -> None:
    hits = [
        k("bulk chunk", memory_id="aaaa"),
        k("the gotcha", memory_id="019f95dc-df08-70e3"),
    ]
    assert evaluate_check(Check(type="memory_id", value="019f95dc-df08", max_rank=1), hits).passed


# --- memory_id follows the supersedes chain (WI 2247, sprint 012) ----------
#
# A pinned id is a ticking assertion in a corpus designed for
# supersession: klams hides the superseded record, so the pin stops
# matching the moment the knowledge it named is re-measured. The pin
# therefore names a LINEAGE — the memory, or whatever it has since
# become — and matching walks the hit's ancestry as well as its own id.


def test_memory_id_matches_a_hit_that_descends_from_the_pin() -> None:
    # WI 2247's live shape: 019fa04a-ceac → 019fb1c9-7c16 → 019fb6b1-1c9a.
    # The pin names the root; only the head is still in the corpus.
    hits = [
        k(
            "the re-measured note",
            memory_id="019fb6b1-1c9a-7850-9822-79ef941025f2",
            ancestry=(
                "019fb1c9-7c16-7513-9ad4-f067611afbf1",
                "019fa04a-ceac-7253-9420-ea3a39cd0ef2",
            ),
        )
    ]
    r = evaluate_check(Check(type="memory_id", value="019fa04a-ceac", max_rank=0), hits)
    assert r.passed
    # The detail has to say the pin is dated, or the suite never learns.
    assert "superseded" in r.detail and "019fb6b1" in r.detail


def test_memory_id_via_chain_still_respects_max_rank() -> None:
    # Following the chain must not cost the check its teeth: a lineage
    # that surfaces but loses its slot is still a failure.
    hits = [
        k("bulk chunk", memory_id="aaaa"),
        k("bulk chunk", memory_id="bbbb"),
        k("the head", memory_id="019fb6b1-1c9a", ancestry=("019fa04a-ceac",)),
    ]
    r = evaluate_check(Check(type="memory_id", value="019fa04a-ceac", max_rank=1), hits)
    assert not r.passed
    assert "rank 2" in r.detail and "outranked" in r.detail


def test_memory_id_prefers_a_direct_hit_over_a_descendant() -> None:
    # Both are in the page; the record itself is the better witness and
    # the detail should not claim a supersession that did not happen.
    hits = [
        k("the original, still live", memory_id="019fa04a-ceac-7253"),
        k("a descendant", memory_id="019fb6b1-1c9a", ancestry=("019fa04a-ceac",)),
    ]
    r = evaluate_check(Check(type="memory_id", value="019fa04a-ceac"), hits)
    assert r.passed
    assert "superseded" not in r.detail


def test_memory_id_ignores_an_unrelated_ancestry() -> None:
    hits = [k("something else", memory_id="cccc", ancestry=("dddd", "eeee"))]
    r = evaluate_check(Check(type="memory_id", value="019fa04a-ceac"), hits)
    assert not r.passed
    assert "absent" in r.detail
