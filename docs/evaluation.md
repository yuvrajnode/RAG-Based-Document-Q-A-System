# Evaluating retrieval

Retrieval quality is the part of a RAG system that decides whether the answer
could have been right. If the passage containing the answer is not in the top
k, no amount of prompt work recovers it. So it gets measured.

## The question set

`eval/questions.jsonl`, one JSON object per line:

```json
{"question": "Which form do I use to claim expenses?", "expected": ["EX-114"]}
```

`expected` is a list of substrings. A retrieved passage counts as relevant if
it contains any of them, case-insensitively.

Substrings rather than chunk ids, deliberately: chunk ids change every time
`chunk_size` or the chunker changes, and comparing configurations is the entire
purpose. An id-based ground truth would have to be rebuilt after every change
it is meant to evaluate.

## Metrics

| Metric | Question it answers |
| --- | --- |
| `hit@k` | Did *any* relevant passage make the top k? The one that decides whether the model had a chance. |
| `precision@k` | What fraction of the k passages were relevant? Divided by k, never by the number returned. |
| `recall@k` | What fraction of the expected evidence was found? |
| `MRR` | How far down was the first relevant passage? |
| `nDCG@k` | Same, but discounted smoothly rather than only counting the first. |

`precision@k` divides by `k` rather than by the number of results actually
returned. Otherwise a configuration that returns two passages looks more
precise than one that returns five, and the comparison table stops meaning
anything.

## Running it

```bash
verbatim ingest ./samples
python -m verbatim.eval.run_eval eval/questions.jsonl --compare
python -m verbatim.eval.run_eval eval/questions.jsonl --json report.json
```

`--compare` re-runs the same questions under dense-only, lexical-only, hybrid
and hybrid+MMR. The runner also prints the questions that missed entirely,
alongside what was retrieved instead - which is where the actual diagnosis
happens.

## Using it as a gate

The runner exits `2` when `hit@k` for the configured setup drops below 0.66,
so CI fails on a change that quietly costs recall. Raise the threshold once you
have a question set that reflects your corpus; 0.66 is a floor, not a target.

## Building a question set for your own corpus

Twenty questions beats two hundred if the twenty are real. Take them from
whatever people actually ask, and make sure the set contains:

- **Literal lookups.** An identifier, a code, a surname. These are what dense
  retrieval alone gets wrong, and they will not show up if every question is a
  paraphrase.
- **Paraphrases.** Questions that share no content word with the passage.
  These are what BM25 alone gets wrong.
- **Multi-part questions.** Two facts from different sections. These are what
  MMR is for.
- **Questions the corpus does not answer.** Not scored by the metrics above,
  but run them by hand: the system should refuse, and a refusal that turns into
  a confident paragraph is the most expensive regression available.

## What this does not measure

These are retrieval metrics. They say nothing about whether the generated
answer is faithful to the passages it cites. Citation coverage - the share of
answers with at least one resolved marker - is reported per answer in the API
response as `grounded`, and is the cheap proxy; a real faithfulness eval needs
either human judgement or a judge model, and is not in scope here.
