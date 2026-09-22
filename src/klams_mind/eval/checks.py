"""Retrieval checks over a query's results.

klams returns retrieved memories, not a synthesized answer, so these are
deterministic assertions about *what retrieval surfaced* — no LLM in the
loop. A `RetrievedItem` is the backend-neutral view a check sees:
`content` (the memory's text/payload), `source` (source_path or a
kind:type key), and `tags`. Dispatch is a plain `if/elif` on the check
type (as in krag); an unknown type returns a failing result rather than
raising.

- `substring`       — content recall: expected text is in some hit's content.
- `source_cited`    — source recall: expected fragment is in some hit's
                      source or equals a tag.
- `no_hallucination`— precision/absence: the forbidden fragment appears in
                      no hit's content or source (the dual of source_cited).
"""

from dataclasses import dataclass, field

from klams_mind.eval.suite import Check


@dataclass(frozen=True)
class RetrievedItem:
    content: str
    source: str
    tags: list[str] = field(default_factory=list)
    # klams-016 scored-envelope metadata; checks ignore it, the report
    # shows it. `score` is only comparable within the same `kind`.
    kind: str = ""
    score: float | None = None
    source_rank: int | None = None
    # klams-026 (#641/#643) projection additions.
    memory_id: str = ""
    # Content hash — the no-duplicates invariant asserts on this.
    content_hash: str | None = None
    # Heading breadcrumb the chunker prepended. The junk ceiling strips
    # it before measuring, because a breadcrumb makes an empty chunk look
    # long *and* makes it a strong embedding match for the query.
    heading_path: str | None = None
    # Pre-fusion match quality. Post-RRF `score` is pure rank.
    raw_score: float | None = None
    # The ids this hit has superseded, transitively, nearest ancestor
    # first (klams-mind #2247). Resolved once by the retriever so checks
    # stay pure; empty for the overwhelming majority of hits.
    ancestry: tuple[str, ...] = ()

    def body(self) -> str:
        """Content with the heading breadcrumb stripped.

        klams' chunker prepends `heading_path` to the chunk text, so a
        chunk whose real content is an empty code fence still presents as
        a few dozen characters of heading. Measuring fragment-ness means
        measuring what is left after that.
        """
        text = self.content
        if not self.heading_path:
            return text.strip()
        head = self.heading_path.strip()
        stripped = text.strip()
        if stripped.startswith(head):
            stripped = stripped[len(head) :]
        return stripped.strip()


@dataclass(frozen=True)
class CheckResult:
    check: Check
    passed: bool
    detail: str


def evaluate_check(check: Check, hits: list[RetrievedItem]) -> CheckResult:
    if check.type == "substring":
        return _substring(check, hits)
    if check.type == "source_cited":
        return _source_cited(check, hits)
    if check.type == "no_hallucination":
        return _no_hallucination(check, hits)
    if check.type == "no_duplicates":
        return _no_duplicates(check, hits)
    if check.type == "min_body_chars":
        return _min_body_chars(check, hits)
    if check.type == "memory_id":
        return _memory_id(check, hits)
    return CheckResult(check, False, f"unknown check type {check.type!r}")


def _missing_value(check: Check) -> CheckResult:
    return CheckResult(check, False, f"{check.type} check requires a value")


def _substring(check: Check, hits: list[RetrievedItem]) -> CheckResult:
    if check.value is None:
        return _missing_value(check)
    haystack = "\n".join(h.content for h in hits).lower()
    found = check.value.lower() in haystack
    detail = (
        f"found {check.value!r} in retrieved content"
        if found
        else f"{check.value!r} absent from {len(hits)} retrieved item(s)"
    )
    return CheckResult(check, found, detail)


def _source_cited(check: Check, hits: list[RetrievedItem]) -> CheckResult:
    if check.value is None:
        return _missing_value(check)
    for h in hits:
        if check.value in h.source or check.value in h.tags:
            return CheckResult(check, True, f"cited by {h.source}")
    return CheckResult(check, False, f"{check.value!r} not among {len(hits)} source(s)")


def _no_hallucination(check: Check, hits: list[RetrievedItem]) -> CheckResult:
    if check.value is None:
        return _missing_value(check)
    needle = check.value.lower()
    for h in hits:
        if needle in h.content.lower() or needle in h.source.lower():
            return CheckResult(check, False, f"forbidden {check.value!r} surfaced in {h.source}")
    return CheckResult(check, True, f"{check.value!r} absent from results")


def _window(check: Check, hits: list[RetrievedItem]) -> list[RetrievedItem]:
    """The slice of the page a check applies to (default: all of it)."""
    return hits[: check.top_n] if check.top_n else hits


def _no_duplicates(check: Check, hits: list[RetrievedItem]) -> CheckResult:
    """No two results share a `content_hash` (klams #641's invariant).

    klams stores the same chunk once per host, so before sprint 026 a
    10-result page was reliably 5 duplicate pairs. Hits with no hash
    (pre-022 points, facts, events) are skipped rather than treated as
    mutually duplicate.
    """
    window = _window(check, hits)
    seen: dict[str, RetrievedItem] = {}
    for h in window:
        if not h.content_hash:
            continue
        prior = seen.get(h.content_hash)
        if prior is not None:
            return CheckResult(
                check,
                False,
                f"duplicate content_hash {h.content_hash[:12]}… shared by "
                f"{prior.source!r} and {h.source!r}",
            )
        seen[h.content_hash] = h
    if not seen:
        # An all-facts page trivially satisfies this; say so rather than
        # reporting a pass that proves nothing.
        return CheckResult(check, True, f"no hashed results among {len(window)} hit(s)")
    return CheckResult(check, True, f"{len(seen)} distinct content hashes in {len(window)} hit(s)")


def _min_body_chars(check: Check, hits: list[RetrievedItem]) -> CheckResult:
    """No result is a content-free fragment (klams F-2.3's junk ceiling).

    The chunker is fence-unaware, so a shell comment inside a ```bash
    block parses as a heading and closes the section right after the
    opening fence. The resulting chunk is a breadcrumb plus ```bash — and
    it scores *strongly*, because it is almost exactly the query's words
    and nothing else (0.956 measured). Breadcrumb stripped, it is empty.
    """
    if check.min_chars is None:
        return CheckResult(check, False, "min_body_chars check requires min_chars")
    window = _window(check, hits)
    for h in window:
        if h.kind and h.kind != "knowledge":
            continue
        body = h.body()
        if len(body) < check.min_chars:
            return CheckResult(
                check,
                False,
                f"fragment in {h.source!r}: {len(body)} chars after stripping "
                f"breadcrumb (min {check.min_chars}) — {body[:40]!r}",
            )
    return CheckResult(check, True, f"all {len(window)} bodies ≥ {check.min_chars} chars")


def _memory_id(check: Check, hits: list[RetrievedItem]) -> CheckResult:
    """A pinned memory — or whatever it has become — must surface.

    This is the curated-beats-bulk assertion. klams#628's failure was
    *not* that the hand-written gotcha was missing from the store — it
    was that the gotcha lost its slot to bulk-scanned chunks. Asserting
    on presence alone would have passed while the bug was live, so
    `max_rank` is what gives the check teeth. Matching is by prefix, so a
    suite can name `019f95dc-df08` without the full UUID.

    **The pin names a lineage, not a leaf** (klams-mind #2247). klams
    treats supersession as a first-class operation and hides the
    superseded record, so a pinned id is a ticking assertion by
    construction: sprint 009 found one that had gone off, with twelve
    more carrying the same fuse. A hit therefore satisfies the pin when
    it *is* the pinned memory, or when it descends from it through
    `memory_supersede` — the retriever resolves that ancestry, so this
    stays a pure function of the page.

    A direct hit wins over a descendant: the record itself is the better
    witness, and the detail must not report a supersession that has not
    happened.
    """
    if check.value is None:
        return _missing_value(check)
    wanted = check.value.lower()
    match = _find_pin(wanted, hits)
    if match is None:
        return CheckResult(check, False, f"{check.value} absent from {len(hits)} result(s)")
    rank, hit, via_chain = match
    # The lineage is worth naming either way: on a pass it is how the
    # suite learns its pin is dated, and on a failure it says which
    # record was being outranked.
    trail = f" (superseded — now {hit.memory_id[:13]})" if via_chain else ""
    if check.max_rank is not None and rank > check.max_rank:
        return CheckResult(
            check,
            False,
            f"{check.value}{trail} surfaced at rank {rank}, above the "
            f"max_rank {check.max_rank} — it is being outranked",
        )
    return CheckResult(check, True, f"{check.value}{trail} at rank {rank}")


def _find_pin(wanted: str, hits: list[RetrievedItem]) -> tuple[int, RetrievedItem, bool] | None:
    """`(rank, hit, via_chain)` for the best witness of `wanted`, or None.

    Two passes rather than one, because a direct hit anywhere on the page
    beats a descendant at rank 0 — otherwise a check would report a
    supersession purely because the successor happened to rank higher.
    """
    for rank, h in enumerate(hits):
        if h.memory_id.lower().startswith(wanted):
            return rank, h, False
    for rank, h in enumerate(hits):
        if any(anc.lower().startswith(wanted) for anc in h.ancestry):
            return rank, h, True
    return None
