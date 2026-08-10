# Research method

This method governs the live reasoning between a question and a finished research output. It is deliberately stricter than “search, summarize, answer.” Search returns material. Method turns material into a traceable conclusion.

## Choose the mode before the method chooses for you

| Mode | Use when | Required discipline | Do not add |
|---|---|---|---|
| **Quick lookup** | One bounded factual question | Source identity, explicit subtitle language, timestamp, honest uncertainty | A fake hypothesis tournament |
| **Focused study** | Understanding one video or one source position | FRAME-LOCK, claim inventory, source-claim separation, source verification | A corpus unless the transcript is too large or repeatedly reused |
| **Comparative investigation** | Several videos, disputed claims, causal or “why” questions | Source lineage, competing hypotheses, distinguishing tests, adversary gate | Majority voting by video count |
| **Living corpus** | Repeated monitoring or a changing question | All comparative controls plus immutable state, update trace, resolution and decay policy | Treating retrieval output as a final report |

Escalate modes when the question becomes causal, consequential, multi-source, or long-lived. Do not force a full investigation onto a two-minute lookup.

## Stage 0 — FRAME-LOCK

A long investigation drifts unless its frame is written down.

| Lock | Write explicitly | Failure it prevents | Operational check |
|---|---|---|---|
| **Object** | The exact thing being studied and definitions of ambiguous terms | Quietly changing what a word means halfway through | Could another analyst identify the same object without reading the conversation? |
| **Question** | The current answerable question | Researching an interesting neighboring topic instead | Does the next tool call reduce uncertainty about this question? |
| **Register** | `process` or `verdict` | Producing a polished answer while the evidence is still moving | If `process`, preserve branches and do not force closure |
| **Boundary** | Time window, languages, admissible sources, non-goals | Infinite search and stale evidence | Can the agent say what it will not investigate? |
| **Evidence standard** | Admissible evidence, authenticity and independence needs, contradiction handling, tolerable gaps, and unavailable-evidence outcome | Moving the goalposts after seeing results | Could another analyst decide FACT versus SOURCE-CLAIM and PASS versus INCONCLUSIVE the same way? |

The evidence standard must also state what the available toolset cannot verify. If required external authentication is unavailable, the predeclared outcome is bounded SOURCE-CLAIM or INCONCLUSIVE—not silent promotion to FACT.

### Frame immutability

Assign every frame a `frame_id`, `created_at`, methodology version/hash, and canonical check-registry version/hash. Once evidence retrieval begins, that frame is immutable. A changed object, question, evidence standard, check applicability, materiality, or stop rule creates a new `frame_id` and research run with `supersedes_frame_id` and supersession reason; it never overwrites the previous run. Preserve the previous frame, evidence, and verdict. Amendments apply prospectively; carried-forward evidence must be re-evaluated under the new frame and identified as reused. Transparent goalpost movement is still goalpost movement.

**Example:** “Does the presenter claim Model X was trained only on public data?” is not the same object as “Was Model X actually trained only on public data?” The first can be answered from the video. The second requires independent evidence outside the speaker's statement.

For short lookups, a one-line frame is enough. For longer work, use the research-state template.

## Stage 1 — Map before conclusion

Build a map before writing an explanation:

- candidate videos and channels;
- speakers, quoted people, institutions, and upstream documents;
- relevant dates and version changes;
- claims and counterclaims;
- source lineage: who observed something and who merely repeated it;
- known gaps in language, coverage, or access.

The map is not the conclusion. Its job is to expose missing actors, missing periods, duplicate sources, and claims that have no observable support.

**Failure mode:** A highly detailed analysis of one transcript segment can become “googling the pixel”: the detail is correct but the larger source and time context are wrong.

**Operational check:** Before synthesis, ask whether a timeline, actor, upstream source, or omitted period could reverse the apparent meaning.

## Stage 2 — Inventory without narrative glue

Classify every material statement before using it:

- **OBSERVATION** — what tube-bridge directly returned: metadata, a track listing, or transcript text at a timestamp.
- **FACT** — a bounded proposition established by admissible evidence. “The selected English generated subtitle track renders X at 12:40” can be a fact about the retrieval record; exact speech, speaker endorsement, and X itself remain separate verification questions.
- **SOURCE-CLAIM** — what a speaker, channel, report, or institution asserts about the world.
- **INFERENCE** — an analyst's interpretation connecting observations or claims.
- **UNKNOWN** — a gap that remains open.

For a non-trivial investigation, list material UNKNOWNs or explicitly explain why none remain inside the locked scope. Do not manufacture ceremonial uncertainty, but do not hide a verification gap inside confident prose.

**Failure mode:** “Three videos say shipments collapsed” silently becomes FACT even though all three repeat the same newsletter.

**Operational check:** For each sentence planned for the conclusion, point to its class and provenance. If the class cannot be named, the sentence is not ready.

## Stage 3 — Build competing hypotheses only when the question needs them

For causal, explanatory, or predictive questions, keep at least two genuinely different and domain-plausible hypotheses alive when the evidence permits. If only one remains after basic admissibility checks, document why alternatives were rejected instead of inventing false balance. Each live hypothesis must include:

- a precise claim;
- mechanism, not just a label;
- prior or qualitative starting confidence;
- evidence expected FOR and AGAINST;
- a **distinguishing prediction** not shared by its competitors;
- falsification or downgrade conditions;
- a time window if it predicts an event.

A fact that every hypothesis predicts does not distinguish them. It may establish background, but it should not move one branch ahead of another.

**Umbrella warning:** “It is all strategic” explains everything and therefore predicts nothing. Split it into mechanisms that could fail separately.

**Operational check:** Ask, “What observation would be likely under H1 and unlikely under H2?” If no answer exists, the hypotheses have not been separated.

## Stage 4 — Retrieve for discrimination, not accumulation

The next query should target the cheapest high-value uncertainty:

1. Which UNKNOWN blocks the decision?
2. Which evidence would most change the ranking of hypotheses?
3. Which upstream source can replace several repeated summaries?
4. Which timestamp or date range contains the decisive claim?
5. What would disconfirm the leading explanation?

Do not search for “more about the topic” when a specific distinguishing question is available.

**Example:** Instead of retrieving ten more reviews saying a product is faster, find whether they used the same benchmark version and whether the raw benchmark report changed its scoring method.

## Stage 5 — Adversary before synthesis

The analyst builds the case. The adversary tries to break it. This can be a separate agent, a separate pass, or a deliberately isolated role, but it must not merely polish the analyst's answer.

The adversary checks frame drift, evidence classes, source lineage, alternative mechanisms, arithmetic, physical and temporal feasibility, actor assumptions, and incentives. The full protocol is in `02-adversary-gates.md`.

A gate PASS means the reasoning process is fit to present. It does not mean the conclusion is certainly true.

## Stage 6 — Synthesis comes last

A final synthesis contains:

1. direct answer to the locked question;
2. strongest established observations and FACTS;
3. material SOURCE-CLAIMS with attribution;
4. best current explanation and surviving alternatives;
5. confidence with reasons, not tone;
6. timestamped evidence spans;
7. UNKNOWNs and missing verification;
8. what new evidence would change the conclusion.

Narrative written before hypothesis separation is a trap: later evidence gets recruited to support the story already on the page.

## Stage 7 — Update state, not memory

For a living investigation:

- preserve the previous state snapshot;
- append an update record with old view, new evidence, and new view;
- never silently rewrite a claim class or confidence;
- resolve predictions only against predeclared criteria;
- apply decay to time-sensitive claims and forecasts, not immutable historical observations;
- reopen a conclusion when a material assumption or source is invalidated.

Continue from the research state and evidence ledger, not from a model's recollection of its previous prose.

## Stop rules

Stop and synthesize when:

- the question is answered to the predeclared evidence standard;
- remaining UNKNOWNs would not change the decision or are explicitly accepted;
- new retrieval is producing duplicates rather than independent information;
- a time or resource boundary has been reached;
- the honest result is INCONCLUSIVE and the missing evidence is named.

Do not stop because the leading hypothesis feels elegant. Do not continue because admitting UNKNOWN feels unsatisfying.
