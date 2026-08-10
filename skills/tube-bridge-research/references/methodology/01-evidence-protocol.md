# Evidence protocol

A transcript response is tool-observed evidence of what the selected subtitle track renders. It is not automatic proof of the speaker's exact words, endorsement, identity, or world claim. This distinction is the center of the protocol.

## The evidence chain

Keep the chain inspectable:

```text
video → selected subtitle track → timestamped rendering → probable utterance
      → identified speaker or dub/translation status → classified source statement
      → corroboration or contradiction → inference → conclusion
```

A broken link lowers confidence. A summary that cannot return to a source span is context, not admissible evidence.

## Claim classes

| Class | Meaning | May support a conclusion? |
|---|---|---|
| **OBSERVATION** | Direct tool output or visible source property | Yes, within its exact scope |
| **FACT** | Bounded proposition meeting the investigation's evidence standard | Yes |
| **SOURCE-CLAIM** | A source's assertion about the world | Yes, but only as attributed testimony until verified |
| **INFERENCE** | Reasoning from observations, facts, or claims | Yes, labeled and attackable |
| **UNKNOWN** | Missing or unresolved information | It constrains the conclusion |

Promotion is explicit. A SOURCE-CLAIM becomes a FACT only when the stated evidence rule is satisfied and the update is recorded. Authority, confidence of delivery, or repetition does not perform this promotion.

Keep five speech levels distinct:

1. **Subtitle rendering observed:** the tool returned text at a timestamp.
2. **Probable semantic content:** the rendering plausibly conveys the meaning of spoken content, qualified by track language, manual/generated status, and ASR or translation risk.
3. **Probable wording:** a same-language rendering plausibly reflects the words uttered, with uncertainty proportional to track quality.
4. **Attributed statement:** the identified speaker appears to make or endorse the claim rather than quote, dub, translate, or report someone else.
5. **Exact quotation verified:** wording has been checked through audio inspection or an authenticated verbatim record whose derivation is independent of the subtitle rendering being tested. Derivative captions, copied transcripts, summaries, translations, and video frames cannot verify exact source-language speech. The current tools do not inspect audio.

A translated or dubbed track may support probable semantic content but not probable wording in the source's spoken language. If spoken language, dub status, translation path, or speaker identity cannot be established, record UNKNOWN. Do not call rendered wording an exact speaker FACT without the verification required by the research brief.

## Minimum provenance for transcript evidence

Record:

- `video_id` and URL;
- title, channel, and speaker identity when established;
- requested subtitle language and returned language;
- manual or generated track status;
- source spoken language and dub/translation status, or UNKNOWN;
- retrieval date;
- start and end timestamp;
- short excerpt or faithful observation;
- retrieval warnings;
- claim class;
- upstream source named by the speaker, if any;
- provenance-edge status: tool-observed, source-described, externally verified, or inaccessible.

Until the known selector defect is fixed, inspect available tracks, pass `lang` explicitly, and verify the returned language. A manual foreign dub is not better evidence merely because it is manual.

## Available-tool boundary

The bundled source-tree tools can directly observe YouTube discovery results, selected metadata, subtitle-track listings, subtitle renderings, timestamped frames, comments, and local corpus operations. They cannot by themselves authenticate external documents, inspect audio, prove speaker identity, recover off-screen context, or verify a world claim merely referenced in a video.

Label every important provenance edge:

- **tool-observed** — returned directly by a tube-bridge tool;
- **source-described** — named, linked, or characterized by the video but not independently opened with the available tools;
- **externally verified** — checked through an explicitly available external capability, recording capability identity, artifact title and publisher, canonical source URI, publication/effective date, retrieval date, version or snapshot/hash for mutable content, inspected page/section/span, derivation lineage, and authenticity basis;
- **inaccessible** — required verification was unavailable in this research run.

A URL in a description is source-described until its content and authenticity are actually checked. If an inaccessible edge is required for external-world FACT promotion, keep the item as SOURCE-CLAIM or return INCONCLUSIVE according to the locked evidence standard.

## Evaluate evidence at claim level

Do not assign one permanent tier to an entire channel. Score the relationship between a source and a specific claim.

| Dimension | Ask | Common failure |
|---|---|---|
| **Access / authenticity** | Could this source directly know or observe this? Is the record authentic? | Treating confident commentary as firsthand evidence |
| **Relevance** | Does it answer this claim in this place, version, and population? | Using an adjacent case as direct proof |
| **Independence** | Does it have a distinct observation path or merely repeat another source? | Counting ten retellings as ten confirmations |
| **Timeliness** | Was it current for the event or version being analyzed? | Applying an old snapshot to a changed system |
| **Completeness** | Is material context, methodology, or denominator missing? | Quoting a percentage without its baseline |

Use qualitative ratings with reasons unless calibrated numeric weights exist. Fake precision is not rigor.

## Source lineage before source count

Build a source lineage graph whenever multiple videos support the same claim:

```text
primary dataset D
├── article A interprets D
│   ├── video 1 cites A
│   └── video 2 cites video 1
└── video 3 independently analyzes D
```

Videos 1 and 2 are not independent confirmations. Video 3 may be analytically independent but still shares the same underlying dataset. State what is independent: observation, interpretation, or publication channel.

**Operational check:** For each apparent corroboration, ask “What is the earliest traceable origin?” and “Would this source still exist if the upstream item disappeared?”

See the worked example `../examples/02-shared-origin-is-not-independence.md`.

## Official statements, experts, comments, and models

- An official statement is strong evidence that the institution made the statement. Its substantive content remains a SOURCE-CLAIM unless independently established.
- Expertise improves interpretation only within demonstrated scope. It does not erase incentives or missing access.
- Comments can show audience reaction or supply leads. They are not a sample of public opinion and do not verify the video's claims.
- An LLM or agent is not an oracle. Multiple models can share training data, search results, and failure modes. Model convergence is a robustness clue, not factual evidence without source lineage.
- Market prices and popularity are observations about beliefs and incentives, not ground truth before a clearly defined resolution.

## Negative evidence requires a pre-registered observation contract

Before searching for absence, create a timestamped **observation contract** with `registered_at`, expected signal, source universe, query and vocabulary variants, languages, time window, coverage basis, predefined coverage/recall acceptance criteria, stopping rule, and known recall limitation. Amendments create a new contract/test ID; they do not retroactively rescue the original test. A post-hoc absence noticed after retrieval is exploratory and may generate a new test, but it is not evidence AGAINST in the current test.

“What did not happen” can be informative, but absence becomes **negative evidence** only if all of these are defensible:

1. the hypothesis predicted the event or mention;
2. the actor or system had a real opportunity to produce it;
3. the event would have been observable through the available sources;
4. source and time coverage were sufficient;
5. the expected window has elapsed;
6. retrieval recall is adequate for the vocabulary and languages involved.

The result record must cite its contract/test ID and record each condition's outcome, achieved coverage, achieved recall evidence or declared proxy, and comparison with the predeclared threshold. Absence is admissible AGAINST only when every required criterion passes. If thresholds are not met, record UNKNOWN or INCONCLUSIVE. If the analysis uses absence anyway, the adversary marks E3 FAIL.

A missing `corpus_search` hit usually fails conditions 3, 4, and 6. Dense retrieval can miss exact terms, synonyms, unsupported languages, or material outside top-k. See `../examples/03-absence-is-not-negative-evidence.md`.

## Corpus retrieval is candidate generation

For each hit:

1. preserve corpus ID, query, rank, score, video ID, and returned time span;
2. detect near-duplicate overlapping windows;
3. return to the timestamped source transcript;
4. inspect surrounding context and track provenance;
5. classify the resulting statement;
6. only then enter it in the evidence ledger.

A similarity score is not a probability, credibility rating, or entailment score. Top-k is a cutoff imposed by retrieval, not the boundary of reality.

## Confidence without theatre

Use confidence labels tied to evidence conditions:

- **High:** direct or strongly authenticated evidence, relevant to the exact claim, with independent corroboration where the claim requires it; no unresolved contradiction capable of reversing the result.
- **Medium:** meaningful evidence exists, but access, independence, timeliness, or alternative explanations remain limited.
- **Low:** mostly indirect, single-origin, incomplete, or weakly discriminating evidence.
- **Unresolved:** available evidence does not distinguish the live alternatives.

Confidence applies to a specific claim at a specific time. Do not transfer it to the entire report.

For every time-sensitive claim, record:

- `as_of` — when the assessment was valid;
- claim type — historical observation, current state, trend, forecast, or interpretation;
- review interval and `review_due`;
- stale-state behavior — retain, downgrade, mark stale, or reopen;
- resolution status and criterion where the claim can resolve.

Maintain a **resolved-claim ledger** containing claim ID, label assigned prospectively, `as_of`, resolution criterion, outcome, resolution date, and domain/cohort. For ordinal labels, evaluate discrimination over a declared window: resolved-support rates should be monotonic from low to medium to high, with cohort sizes and unresolved cases reported. This checks ordering, not probability calibration. Reserve calibration curves and Brier score for numeric forecasts recorded prospectively with explicit resolution criteria.

## Arithmetic and transformations

Whenever a conclusion depends on numbers:

- preserve raw values, units, currency, date, and denominator;
- show the transformation or calculation;
- distinguish source-provided values from analyst-calculated values;
- test sensitivity to plausible ranges;
- reject comparisons that mix versions, currencies, or time windows without adjustment.

If the calculation cannot be reproduced, it is an INFERENCE with missing support, not a FACT.

## Evidence completion check

Before synthesis:

- every decisive statement has a class;
- every FACT has a reproducible provenance path;
- every SOURCE-CLAIM is attributed;
- source lineage has been checked for duplicated origins;
- timestamp and subtitle provenance are present;
- corpus hits were verified against source transcript text;
- missing retrieval was not promoted to negative evidence without an observation contract;
- UNKNOWN remains visible where verification failed.
