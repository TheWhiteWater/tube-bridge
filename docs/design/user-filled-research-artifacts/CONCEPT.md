# User-filled research artifacts

**Status:** draft concept and templates only. No runtime implementation is authorized by this document.

## Product boundary

> Tube Bridge provides source access, stable addressing, corpus storage, templates, validation, and persistence. The user or the user's agent performs the research and fills the templates.

Three responsibilities are separate:

| Layer | Responsibility |
|---|---|
| Tube Bridge | Fetch facts, preserve source text/provenance, create prefilled scaffolds, validate references, store and retrieve user artifacts. |
| Optional method package | Supply reusable templates, field descriptions, examples, and skills. |
| User/agent | Choose a method, interpret sources, create semantic structure, assign tags, classify, code, compare, and write conclusions. |

Tube Bridge does not run an internal research agent and does not fill semantic fields.

## Template definition versus scaffold instance

A **template definition** is a reusable schema shipped with Tube Bridge or registered by a user. It describes editable fields and allowed source references.

A **scaffold instance** is created for one target:

```text
research_scaffold_create
├── template_id: structured-source-v1
└── target: video (the selected transcript is bundled into its machine fields)
```

or:

```text
research_scaffold_create
├── template_id: corpus-study-v1
└── target: corpus
```

Tube Bridge creates an artifact instance and automatically fills only machine-owned fields. Agent-owned fields remain `null`, `[]`, or explicitly `unfilled`.

## Ownership inside every artifact

```text
artifact
├── machine_fields      read-only; filled by Tube Bridge
└── agent_fields        editable; filled by user/agent
```

### Machine fields

May include only observed or deterministic values:

- video/channel IDs and URLs;
- exact video title, the bounded video description exposed by the existing metadata path, exact observed channel name and description (with explicit truncation status), publication date, duration, and language hints;
- per-field metadata provider/retrieval provenance, including an explicit unavailable state when a channel description cannot be observed;
- transcript version, selected track, manual/generated provenance, source hash;
- source segment IDs and timestamp range;
- corpus membership;
- exact duplicate IDs;
- technical retrieval attempts and typed errors.

### Agent fields

May include any methodology-defined interpretation:

- metadata summary and broad navigation tags;
- semantic content hierarchy and section tags;
- media environment or organization classification;
- source roles and lineage;
- coding categories;
- quote selection;
- inclusion decisions;
- confidence and notes.

Tube Bridge stores these values as user/agent-authored artifacts. It does not endorse them as source truth.

## Binding model

An agent-filled field may reference:

```text
channel
video
transcript_version
source_segment_range
semantic_node
corpus
research_artifact
```

Tube Bridge validates only structural facts:

- the referenced target exists;
- transcript/source hashes match;
- segment and timestamp ranges are valid;
- referenced sections belong to the correct artifact;
- payload conforms to the selected template;
- machine fields were not modified.

It does not validate whether a research classification or conclusion is correct.

## End-to-end interaction

```text
1. Agent selects a template.
2. Agent calls research_scaffold_create.
3. Tube Bridge fetches/reads source facts and returns a prefilled scaffold.
4. Agent reads the transcript or corpus using existing Tube Bridge tools.
5. Agent fills agent_fields locally.
6. Agent calls research_artifact_save with expected_revision.
7. Tube Bridge validates schema and source references, then stores a new revision.
8. Agent can retrieve, continue, search, or export the artifact later.
```

No semantic model runs inside steps 2, 3, 6, or 7.

## Initial template set

- `structured-source-v1` — one video target with its selected transcript: metadata annotation plus internal semantic hierarchy.
- `corpus-study-v1` — one corpus: research frame, grouping, coding, lineage, evidence, and unresolved items.

Templates are optional. A user may ignore them, extend them through `custom_fields`, or later register a different template.

## Search and corpus relationship

Raw source search and user-artifact search remain distinct:

- source search returns transcript evidence;
- artifact search returns user/agent-authored structure, tags, coding, or notes;
- every artifact hit links back to its source target;
- generated content is never presented as original transcript evidence.

## Non-goals

Tube Bridge does not automatically:

- classify news organizations;
- decide whether reporting is independent;
- trace rumors;
- create semantic sections or tags;
- choose evidence;
- fill a coding table;
- produce a research verdict.

Those are uses of the tool, not responsibilities of the tool.
