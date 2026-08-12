# Worked example: absence is not negative evidence

**Status:** Synthetic example. The corpus and query are invented to demonstrate retrieval limits.

## Question

> Does this twelve-video corpus contain discussion of sulfur supply risk?

## Search result

The agent runs:

```text
corpus_search(corpus_id="supply-chain-demo", query="sulfur supply risk", top_k=10)
```

No returned window mentions sulfur.

## Tempting but invalid conclusion

> The speakers do not discuss sulfur supply risk, so the issue was not considered.

The search result only establishes that this dense top-k query returned no matching window. It does not establish absence from the transcripts or absence from the speakers' reasoning.

## Why the observation contract fails

- The corpus contains only twelve selected videos, not the full relevant source universe.
- Dense retrieval may rank paraphrases below top-k.
- A speaker may use “refinery by-product,” “fertilizer feedstock,” or another term.
- Some indexed transcript tracks may be generated ASR with recognition errors.
- Current flat windows and embeddings do not provide a lexical exhaustiveness guarantee.
- The query did not scan every timestamped transcript directly.

## Follow-up

1. Search several paraphrases and exact related terms.
2. Inspect corpus video and language coverage.
3. Review full transcripts or run a reproducible lexical scan if exhaustive absence matters.
4. Define the time and source universe in which the mention was expected.

## Correct synthesis before exhaustive review

> No sulfur-related passage appeared in the top ten semantic results for this query. Because corpus coverage and retrieval recall are not exhaustive, the result is UNKNOWN with respect to whether the videos discuss the issue.

## When absence could become negative evidence

Absence could weigh against a hypothesis only after the expected vocabulary or concepts, complete relevant transcripts, languages, time window, and sufficiently sensitive retrieval method are defined and checked. Even then, the conclusion is bounded: “not found in the reviewed source universe,” not “does not exist.”
