# Adversary gate

**Research-state version:**<br>
**`frame_id`:**<br>
**Methodology version/hash:**<br>
**Canonical registry version/hash:**<br>
**Reviewer:**<br>
**`gate_at`:**<br>
**Machine verdict:** PASS / FAIL / INCONCLUSIVE<br>
**Presentation:** PASS / PASS with limitations / FAIL / INCONCLUSIVE<br>
**Roll-up:** any FAIL → FAIL; otherwise material INCONCLUSIVE → INCONCLUSIVE; otherwise predeclared non-material INCONCLUSIVE → PASS with limitations; otherwise all applicable PASS with justified NOT APPLICABLE → PASS

PASS means fit for synthesis, not guaranteed truth. FAIL is a repairable method defect; INCONCLUSIVE is an evidence limit.

## Canonical check register

Applicability and materiality must come from the immutable FRAME-LOCK before evidence retrieval. Core checks are mandatory-material; any conditional check used decisively is material.

| Check ID | Applicable? | Materiality | Status | Evidence, defect, limit, or NA reason |
|---|---|---|---|---|
| F1 | yes | mandatory-material | PASS / FAIL / INCONCLUSIVE |  |
| F2 | yes | mandatory-material |  |  |
| E1 | yes | mandatory-material |  |  |
| E2 | yes | mandatory-material |  |  |
| E3 |  |  |  |  |
| H1 |  |  |  |  |
| H2 |  |  |  |  |
| A1 |  |  |  |  |
| A2 |  |  |  |  |
| A3 |  |  |  |  |
| A4 |  |  |  |  |
| A5 |  |  |  |  |
| S1 | yes | mandatory-material |  | include gate time versus `review_due` |
| S2 | yes | mandatory-material |  |  |

### Preflight

- [ ] Every canonical ID is present
- [ ] Applicability, materiality, and status are declared
- [ ] No decisive conditional check is labeled non-material
- [ ] Every NOT APPLICABLE has a valid locked reason
- [ ] Missing or invalid metadata has triggered overall FAIL

## 1. Frame integrity

| Check | PASS / FAIL / INCONCLUSIVE / NOT APPLICABLE | Evidence, defect, or NA reason |
|---|---|---|
| Object retained its defined meaning |  |  |
| Current question was not replaced |  |  |
| Process/verdict register respected |  |  |
| Time, language, and source boundaries retained |  |  |

## 2. Evidence integrity

| Check | PASS / FAIL / INCONCLUSIVE / NOT APPLICABLE | Evidence, defect, or NA reason |
|---|---|---|
| FACT and SOURCE-CLAIM remain separate |  |  |
| Decisive spans have track/timestamp provenance |  |  |
| Source lineage and independence checked |  |  |
| Corpus hits verified against transcript |  |  |
| Negative evidence has an observation contract |  |  |

## 3. Competing hypotheses

- Leading hypothesis:
- Strongest surviving alternative:
- Distinguishing prediction:
- Evidence AGAINST the leader:
- Umbrella/falsifiability check:

## 4. Five attacks

| Attack | Question | PASS / FAIL / INCONCLUSIVE / NOT APPLICABLE | Defect, evidence limit, or surviving rationale |
|---|---|---|---|
| Arithmetic | Do values, units, dates, and denominators reproduce? |  |  |
| Alternatives | What simpler or different mechanism fits? |  |  |
| Actor model | Local rationality, constraints, internal conflict, or error? |  |  |
| Physical/temporal | Can the chain occur in available time and capacity? |  |  |
| Incentives/cui bono | Lead with mechanism, or unsupported attribution? |  |  |

## 5. Confidence and stopping

- Confidence justified at claim level:
- Material UNKNOWNs visible:
- Cheap distinguishing test still available:
- Stop rule met:

## Remediation

| Defect ID | Return to stage | Required action | Owner | Recheck condition |
|---|---|---|---|---|
| G-001 | frame / evidence / hypotheses / retrieval / synthesis |  |  |  |

## Dissent

- Residual concern not captured by the verdict:
- Human-accepted risk, if any:
