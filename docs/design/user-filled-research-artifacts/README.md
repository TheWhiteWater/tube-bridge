# User-filled research artifacts v1

Active concept draft for separating Tube Bridge from the methodology and agent that use it.

## Documents

- `CONCEPT.md` — ownership and product boundary.
- `TOOL_CONTRACT.md` — proposed MCP interaction for creating, filling, saving, listing, and exporting artifacts.
- `templates/structured-source-v1.template.yaml` — machine-prefilled video/transcript scaffold with empty agent fields.
- `templates/corpus-study-v1.template.yaml` — machine-prefilled corpus scaffold with empty agent fields.

## Core rule

Tube Bridge fills `machine_fields`. The user or user-selected agent fills `agent_fields`. Tube Bridge validates references and stores revisions but does not perform the research.

## Runtime status

None of the proposed research artifact tools exist in the immutable v1.1.6 17-tool runtime. This pack is a design gate, not a runtime claim or implementation authorization.
