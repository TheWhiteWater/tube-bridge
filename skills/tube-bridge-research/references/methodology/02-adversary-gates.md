# Adversary gates

The adversary does not write a more dramatic competing story. Its job is to find where the current reasoning can break before the user acts on it.

Use the full gate for comparative, causal, predictive, or high-consequence work. A quick lookup needs only source, scope, and arithmetic checks.

## Role separation

- **Orchestrator:** owns the question, definitions, boundaries, and stopping rule.
- **Analyst:** maps sources, classifies claims, builds hypotheses, and gathers distinguishing evidence.
- **Adversary:** attacks frame, evidence, mechanisms, and confidence. It does not silently replace the question or promote its own narrative.
- **Human:** owns consequential judgment and can accept an explicitly stated residual risk.

A separate model can help, but independence of model identity is not proof of independent evidence.

Every applicable gate check receives exactly one status:

- **PASS** — sufficient method evidence shows the check is satisfied;
- **FAIL** — a repairable methodological defect can materially distort the answer;
- **INCONCLUSIVE** — the method is sound but required evidence is unavailable or cannot distinguish outcomes;
- **NOT APPLICABLE** — the check does not fit the locked question, with a written reason. Silence is not NOT APPLICABLE.

## Canonical check registry

Declare applicability and materiality (`material` or `non-material`) during FRAME-LOCK, before evidence retrieval. The profile records the canonical registry version/hash and is immutable within its `frame_id`. A change creates a new frame and research run, applies prospectively, and preserves the prior frame and verdict.

A check is **material** when a different status could change the direct answer, claim class, confidence, recommended action, or stop decision. F1, F2, E1, E2, S1, and S2 are always **mandatory-material**. A conditional check becomes mandatory-material whenever its subject is used decisively: E3 for corpus/absence claims, H1–H2 for causal or predictive conclusions, A1 for quantitative conclusions, A3 for actor reasoning, A4 for feasibility claims, and A5 for incentive or attribution claims. The adversary validates this classification under F2; laundering a decisive check as non-material makes F2 FAIL.

| ID | Canonical check | PASS criterion |
|---|---|---|
| **F1** | Object integrity | Object and key definitions remain unchanged within the immutable frame |
| **F2** | Question/register/boundary/evidence standard | Output stays within the locked question, mode, tools, admissibility rules, and valid materiality profile |
| **E1** | Claim and speech-level classification | OBSERVATION, FACT, SOURCE-CLAIM, INFERENCE, UNKNOWN, and subtitle speech levels are explicit |
| **E2** | Provenance, tool boundary, lineage, independence | Every decisive edge is traceable and its verification status is honest |
| **E3** | Corpus and negative-evidence admissibility | Hits return to source text; every absence condition records achieved results against preregistered thresholds |
| **H1** | Plausible alternatives | Required explanatory alternatives are domain-plausible or rejected with evidence |
| **H2** | Distinguishing prediction and falsifiability | Live hypotheses make at least one meaningfully different prediction |
| **A1** | Arithmetic | Decisive values, units, dates, denominators, and transformations reproduce |
| **A2** | Alternatives/parsimony | A plausible simpler or different mechanism was tested |
| **A3** | Actor model | Incentives, constraints, information, internal conflict, and possible error were considered where actors matter |
| **A4** | Physical/temporal feasibility | The proposed mechanism fits time, distance, sequence, capacity, and technology |
| **A5** | Incentives/cui bono | Benefits generate search leads but do not substitute for mechanism or evidence |
| **S1** | Confidence, freshness, and residual uncertainty | Confidence is claim-specific; material UNKNOWNs are disclosed; gate time is before `review_due` or stale behavior was applied |
| **S2** | Stopping, update, and resolution | Stop rule is met; immutable frames, state changes, review actions, and resolution criteria are traceable |

Default applicability by mode:

- **Quick lookup:** F1, F2, E1, E2, S1, S2. E3 applies if corpus retrieval or absence is used; A1 applies to quantitative claims. H1–H2 and remaining A checks are normally NOT APPLICABLE unless the lookup becomes explanatory.
- **Focused study:** quick checks plus E3 when relevant; H and A checks apply when causal interpretation is offered.
- **Comparative investigation or living corpus:** all checks are presumed applicable unless FRAME-LOCK records a reason otherwise.

## Gate 1 — Frame integrity (F1–F2)

Check:

- Is the object still the one defined in FRAME-LOCK?
- Is the report answering the current question rather than a neighboring one?
- Did `process` quietly become `verdict`?
- Did the time window, language, population, or meaning of a key term drift?

**Failure mode:** The investigation begins with “what did the speaker claim?” and ends by asserting “what actually happened.”

**Verdict:** FAIL and return to framing if the answer's scope exceeds the evidence contract.

## Gate 2 — Claim and source integrity (E1–E3)

Check:

- Did any SOURCE-CLAIM silently become FACT?
- Do decisive excerpts retain video, track, and timestamp provenance?
- Are apparent independent sources actually linked to one upstream origin?
- Were corpus results verified against the source transcript?
- Did missing search results get misused as negative evidence?

**Verdict:** FAIL when a decisive claim lacks a traceable chain. INCONCLUSIVE when the required upstream source cannot be obtained.

## Gate 3 — Competing hypotheses (H1–H2)

For explanatory work:

1. list at least two distinct, domain-plausible mechanisms when available;
2. if alternatives fail basic plausibility or base-rate checks, record their rejection instead of manufacturing false balance;
3. state what each live branch predicts FOR and AGAINST;
4. identify a distinguishing prediction;
5. record evidence inconsistent with the leading branch;
6. keep alternatives alive until an explicit downgrade reason exists.

A hypothesis that absorbs every outcome is an umbrella, not an explanation.

**Operational check:** If tomorrow's opposite outcome could also be described as supporting the same hypothesis, it is not falsifiable enough to lead.

## Gate 4 — Five attacks (A1–A5)

Attack the leading hypothesis before acceptance.

### 1. Arithmetic

Do quantities, units, dates, denominators, and ranges agree? Recalculate rather than trusting a quoted result.

- **Failure:** a percentage is correct but uses the wrong baseline year.
- **Check:** show the calculation and sensitivity range.

### 2. Alternatives and parsimony

What simpler mechanism explains the same observations? What mundane process, selection effect, or reporting artifact could produce the pattern?

- **Failure:** coordination is inferred where copying or common incentives suffice.
- **Check:** write at least one plausible alternative grounded in domain knowledge or base rates. Add an intentional alternative only when intentionality is material; otherwise mark it NOT APPLICABLE with a reason.

### 3. Actor model — rationality and error

Do not explain an action merely with “they are idiots.” First model information, incentives, constraints, time horizon, internal conflict, and local rationality. Then retain error, incompetence, and randomness as real hypotheses rather than banning them.

- **Failure:** assuming either perfect strategic genius or impossible stupidity.
- **Check:** can the action be rational under a different objective, and can it also arise from error? What evidence separates those paths?

### 4. Physical, temporal, and operational feasibility

Can the mechanism occur with the available time, distance, logistics, capacity, sequence, and technology?

- **Failure:** a supply response is claimed before production and shipping lead times allow it.
- **Check:** draw the chain and calculate the slowest or weakest link.

### 5. Incentives and cui bono

Who benefits from the event, from the interpretation, and from making the audience believe that interpretation?

- **Failure:** treating benefit as proof of authorship or control.
- **Check:** use incentives to generate search targets, then demand mechanism and evidence. Benefit alone does not pass the gate.

## Gate 5 — Missingness and negative evidence (E3 detail)

Before using absence, inspect the timestamped observation contract/test ID and record per-condition results:

- Was the expected observation specified before searching?
- Was there opportunity for the event to occur?
- Would this source universe and retrieval method expose it?
- Did achieved coverage meet the preregistered threshold?
- Did achieved recall evidence or its declared proxy meet the preregistered threshold?
- Was the full time window covered and stop rule met?
- Were all preregistered language and vocabulary variants executed?

E3 PASS requires every required condition to pass. An unmet threshold yields UNKNOWN or INCONCLUSIVE. Using absence as AGAINST despite an unmet or missing criterion makes E3 FAIL. See the worked corpus example `../examples/03-absence-is-not-negative-evidence.md`.

## Gate verdicts and roll-up

Apply this deterministic roll-up after a **preflight** over every canonical check ID F1–F2, E1–E3, H1–H2, A1–A5, and S1–S2:

0. If any ID is missing; applicability, materiality, or status is undeclared; a mandatory-material check is downgraded; or a NOT APPLICABLE reason is invalid, the overall verdict is **FAIL**.
1. If any check is FAIL, the overall verdict is **FAIL**. Return to the named stage, repair the defect, and rerun affected checks under the same immutable frame when the frame itself remains valid.
2. Otherwise, if any material check is INCONCLUSIVE, the overall verdict is **INCONCLUSIVE**. State the unavailable or non-discriminating evidence.
3. Otherwise, if all material applicable checks are PASS, every NOT APPLICABLE has a valid reason, and at least one applicable predeclared non-material check is INCONCLUSIVE, the overall verdict is **PASS with limitations**. The machine-readable verdict remains PASS and each limitation is listed.
4. Otherwise, if every applicable check is PASS and every NOT APPLICABLE has a valid reason, the overall verdict is **PASS**.
5. **Fallback:** any gate record matching none of the rules above is invalid and therefore FAIL.

PASS means the method and evidence chain are fit for synthesis and residual uncertainty is named. It is not a truth certificate. FAIL identifies a repairable process defect; INCONCLUSIVE identifies an evidentiary limit that more careful prose cannot fix.

Record each check status, the roll-up, reviewer, failed checks, and remediation in the adversary-gate template. Never convert INCONCLUSIVE into PASS because a deadline arrived.

## Stopping criteria (S1–S2)

A research cycle may stop when:

- predeclared evidence requirements are met;
- every decisive time-sensitive claim is still before `review_due` or its stale behavior has been applied;
- the adversary gate passes;
- remaining alternatives are lower confidence for stated, discriminating reasons;
- remaining UNKNOWNs are immaterial to the decision or explicitly accepted;
- marginal retrieval is producing shared-origin repetition;
- the bounded result is honestly INCONCLUSIVE.

Continue when a cheap distinguishing test could reverse the conclusion. Stop when continued searching merely decorates the preferred story.

## Updates, resolution, and calibration

When new evidence arrives without changing the frame:

1. preserve the previous state;
2. identify the affected claim or hypothesis;
3. classify and trace the new evidence;
4. show old confidence → new confidence and why;
5. record alternatives strengthened or weakened;
6. run the relevant adversary checks again;
7. append an update record.

Resolve predictions only against criteria and time windows declared before the outcome. If numeric probabilities are used repeatedly, score resolved predictions with a proper calibration measure such as Brier score. Do not manufacture percentages for one-off explanatory judgments merely to look scientific.

Apply decay according to claim type:

- rapidly changing operational claims need short review intervals;
- strategic trends need longer intervals;
- an established historical observation does not become false because no new article repeats it;
- a stale interpretation may lose relevance even when its underlying facts remain true.

Before roll-up, S1 checks every decisive claim against gate time and `review_due`; overdue claims must execute their declared retain/downgrade/stale/reopen behavior. S2 checks that the action and resulting update are recorded.

## Final audit record

The canonical check registry is the only roll-up input. Do not replace it with an unscoped prose checklist. The adversary-gate template records `gate_at`, frame ID, methodology and registry version/hash, every check ID, applicability, materiality, status, evidence or defect, and any NOT APPLICABLE reason.
