# Operating model

Tube-bridge is a bounded research system with one tool surface and one doctrine. The package structure is an interface for the agent, not a document archive.

## Authority layers

1. **External source observation** — video metadata, subtitle-track inventory, transcript segments, comments, and retrieval warnings.
2. **Preserved source record** — ordered subtitle text, timing, language, track type, video identity, and fetch provenance.
3. **Derived working data** — normalized text, chunks, embeddings, summaries, outlines, topic boundaries, and relations.
4. **Interpretation** — claims formed by comparing source evidence and derived retrieval results.
5. **Research output** — the answer or report, with evidence spans, uncertainty, and limitations.

Higher-numbered layers must remain traceable to lower-numbered layers. A generated summary or vector match never outranks the subtitle evidence from which it was derived.

## Package responsibilities

- MCP tools perform retrieval and corpus operations.
- `SKILL.md` defines the canonical order of work and non-negotiable evidence rules.
- Numbered references provide detail for one stage without competing for skill discovery.
- Templates make research state explicit and repeatable.
- Tests ensure the runtime catalog and doctrine package remain structurally aligned.

## Progressive disclosure

Load the entry skill first. Read a numbered reference only when its stage is active. Do not inject every reference into every task: excess context can hide the operative rule and create contradictions.

## Change discipline

Runtime and doctrine are versioned together. When runtime behavior changes, update the corresponding reference and contract tests in the same change. Proposed architecture must be labeled as proposed until implementation and verification exist.

Avoid duplicate sources of truth. A rule belongs in the entry skill if it is always mandatory; detailed rationale and procedures belong in one canonical reference linked from that skill.

For the reasoning lifecycle between a raw question and a research output, follow [methodology/00-research-method.md](methodology/00-research-method.md). Its evidence and adversary protocols extend this operating model without changing corpus runtime behavior.
