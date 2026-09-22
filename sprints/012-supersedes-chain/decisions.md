# Sprint 012 — decisions

## D-1 — `memory_id` itself follows the chain; no second check type

The ruling said "option (1) as the check type … applied to all 13
`memory_id` checks". That can be read two ways: a *new* type the 13
checks are converted to, or the existing type taught to follow the
chain. Both produce identical behaviour for all 13.

**Taken: change `memory_id`.** Keeping a strict variant alongside would
leave the fuse sitting next to the fix — the next suite author reaches
for the familiar name and re-creates #2247. The repo's YAGNI principle
says the same thing from the other side: a strict pin has no caller and
no use case anyone has named.

A direct hit still wins over a descendant, so no currently-passing check
changes meaning, and the detail string reports which way a pin matched.

**Flagged for the overseer** — this is a reading of the ruling rather
than the ruling itself, and it is one line to reverse.

## D-2 — the pin keeps naming the lineage ROOT, not the live head

`019fa04a-ceac` is now a deliberately historical id. It is the stable
name for the body of knowledge; the head is whatever klams has
re-measured it into this week. Repointing would restart the clock, which
is precisely what the original ruling forbade — and now it would not
even be a fix, since the check passes either way.

The refresh recipe's report was reworded to match: it reports a
superseded pin as a **legibility** call with the lineage printed, not as
an instruction to repoint.

## D-3 — `max_rank` lowered from 0 to 1 on the "score field behavior" query

This is the one judgement call in the sprint, and it was made on a
measurement rather than on taste.

`max_rank = 0` demanded that the lineage head outrank **everything**.
What actually holds rank 0 is `019fbc9c-5c74` — a live note that has
never been superseded and is not part of this lineage — and reading both
texts settles it: the query names the **score field**, and that record is
specifically about the `score` / `raw_score` split ("an agent
thresholding on `score` rejects everything"). The lineage head is about
the ranking *pipeline*. Retrieval is putting the better answer first.

Meanwhile the invariant this query exists to prove is holding perfectly:
all four superseded ancestors were verified **hidden** from the whole
page, and the `no_hallucination` check on the 0.1.29 phrasing still
passes.

So `max_rank = 0` was asserting something the query never claimed. It
now asserts that the lineage reaches the top two, which is what the
suite's own comment describes.

**Flagged for the overseer.** Changing an eval's threshold changes what
the suite measures, and WI 2247 explicitly said that is not done
unilaterally. The evidence above is why it was done here rather than
filed — but it is the overseer's to reverse, and reversing it costs one
character and returns the query to `known_open`.

## D-4 — the ancestry walk lives in the retriever, not the check

`evaluate_check` is a pure function of the page and is worth keeping
that way — it is what lets every check type be tested against canned
hits with no transport. The walk is per-record and cached for the
retriever's lifetime (a `supersedes` link is immutable once written), so
an ordinary hit costs nothing: `supersedes` already rides on the search
result, and only a hit that carries one pays for a `memory_get`.

Bounded deliberately: a cycle breaks the walk, a depth of 32 caps it,
and an ancestor klams will not serve truncates the lineage instead of
failing the run. An eval that dies at a boundary measures nothing, which
is worse than one that measures a shorter chain.

## D-5 — `refresh-pins` is outside `just gate`, and exits 1 on drift

Pin rot is a fact about klams' corpus, which moves with no commit in this
repo and lives on kubs0 behind the tailnet — no hosted runner can see it,
and a red gate would misattribute it to whatever landed last. It is a
recipe you run, not a gate you pass.

Ranking is reported but **not** counted as drift. A live pin that has
lost its slot is a retrieval regression; folding the two together is how
a suite ends up re-pinning to hide one.
