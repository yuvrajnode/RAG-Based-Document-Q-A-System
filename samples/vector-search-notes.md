# Notes on vector search for the document Q&A project

Working notes, not a spec. Written while choosing the retrieval stack.

## Why hybrid rather than dense alone

Dense retrieval handles paraphrase well - "how much holiday do I get" finds a
passage about annual leave entitlement without sharing a single content word.
It handles rare literal tokens badly. Ask about form EX-114 or reference
SD-2200 and a small encoder has no useful representation for the string; the
nearest neighbours come back semantically plausible and factually wrong.

BM25 has the mirror-image failure. It nails the identifier and misses every
paraphrase.

Running both and fusing the rankings costs one extra index in memory and a few
milliseconds per query. On the internal question set it moved hit@5 from 0.71
(dense only) to 0.89.

## Fusion: scores or ranks

Two options were tried.

Relative score fusion normalises each ranking to [0,1] and takes a weighted
sum. It preserves the magnitude of a confident dense hit, which is useful when
one retriever is clearly right and the other is guessing.

Reciprocal rank fusion ignores scores entirely, scoring 1/(60+rank). It is more
robust when the two score distributions are not comparable - and BM25 scores
are unbounded while cosine similarity is not, so they never really are.

The default is relative score fusion at alpha 0.6, with RRF available. Alpha
0.6 rather than 0.5 because the corpus is prose; on a corpus of part numbers
the right value is lower.

## Chunk size

At 400 characters, chunks were too small to contain a whole policy statement,
and answers cited three chunks to make one point. At 1500, retrieval started
returning passages where the relevant sentence was buried and the model
sometimes answered from the wrong half.

900 characters with 150 of overlap was the best compromise on the internal set.
The overlap matters more than the size: without it, any fact that straddles a
boundary is unretrievable at any k.

## MMR

Overlapping chunks mean the top 5 by pure similarity frequently contain the
same paragraph three times. MMR at lambda 0.65 trades a little relevance for
coverage. On multi-part questions - "what are the notice periods and the
probation length" - it is the difference between answering half the question
and all of it.

## What was left out

No cross-encoder reranker. It would add maybe 3 points of precision@5 and about
200ms per query, which is the wrong trade for an interactive UI. Worth
revisiting if the corpus grows past a few hundred thousand chunks.

No query rewriting. Multi-turn follow-ups ("and for part-time staff?") would
benefit, but the honest version needs an extra model call before retrieval and
the latency budget is already spent on generation.
