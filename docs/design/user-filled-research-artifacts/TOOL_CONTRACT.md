# Proposed MCP tool contract

**Status:** experimental opt-in preview behind `TUBE_BRIDGE_EXPERIMENTAL_RESEARCH_ARTIFACTS=1`; not present in the immutable released v1.1.6 17-tool runtime.

## Why the creation tool creates a scaffold, not a template

Template definitions are reusable schemas. Agents normally need an instance of an existing template for a specific video (with its selected transcript bundled) or corpus. Therefore the primary call is `research_scaffold_create`, not `research_template_create`.

## 1. `research_templates_list`

Read-only. Lists available template definitions and their intended target scopes.

```json
{}
```

Example result:

```json
{
  "templates": [
    {
      "template_id": "structured-source-v1",
      "target_types": ["video"],
      "description": "Metadata scaffold and agent-filled internal content hierarchy"
    },
    {
      "template_id": "corpus-study-v1",
      "target_types": ["corpus"],
      "description": "Agent-filled study record bound to a Tube Bridge corpus"
    }
  ]
}
```

## 2. `research_scaffold_create`

Creates one artifact instance and auto-fills machine-owned fields.

Input for a video target (its selected transcript is bundled into the scaffold):

```json
{
  "template_id": "structured-source-v1",
  "target": {
    "type": "video",
    "video_id": "9SHjQgNrpys",
    "language": "en"
  }
}
```

Input for a corpus:

```json
{
  "template_id": "corpus-study-v1",
  "target": {
    "type": "corpus",
    "corpus_id": "nz_media"
  }
}
```

Behavior:

1. Validate the template and target.
2. Read or fetch observable video metadata and channel context. The machine-owned result includes exact video title, channel ID/name/URL, channel description when observable, and honest provider/retrieval provenance; absence is explicit and never replaced with an inferred description.
3. Resolve an existing transcript version when the template requires one. Caption retrieval is allowed; ASR is never triggered implicitly.
4. Fill `machine_fields`.
5. Initialize every `agent_fields` entry as `null`, `[]`, or `unfilled`.
6. Persist revision 1 and return it.

The call does not invoke an LLM or produce semantic classifications.

## 3. `research_artifact_get`

Read-only. Retrieves a stored scaffold and its revision history.

```json
{
  "artifact_id": "rart_..."
}
```

Omit `revision` to read the latest revision; provide a positive integer to read an immutable historical revision.

## 4. `research_artifact_save`

Stores user/agent-authored fields. Machine fields are not accepted as input.

```json
{
  "artifact_id": "rart_...",
  "expected_revision": 1,
  "agent_fields": {
    "metadata_annotation": {
      "summary": "...",
      "tags": []
    },
    "content_structure": {
      "sections": []
    }
  },
  "author": {
    "type": "agent",
    "name": "user-selected-research-agent"
  }
}
```

Validation checks:

- optimistic revision match;
- template schema;
- template-defined field types, required keys, and string tag arrays;
- valid transcript version and segment ranges when an artifact cites them;
- complete section coverage only when the agent marks the content map `complete`;
- no modification of machine-owned fields.

A successful save creates a new immutable revision.

## 5. `research_artifacts_list`

Read-only. Lists artifacts attached to a video or corpus target.

```json
{
  "target_type": "corpus",
  "target_id": "nz_media",
  "template_id": null
}
```

## 6. `research_artifact_export`

Read-only. Exports one artifact or an attached artifact set without changing its meaning.

```json
{
  "artifact_id": "rart_...",
  "format": "json"
}
```

Initial formats: `json`, plus `csv` when the selected template defines a tabular coding-row projection.

## Typical source workflow

```text
research_templates_list
→ research_scaffold_create(structured-source-v1, video)
→ agent reads machine_fields.source_segments (or reopens the source transcript)
→ agent constructs sections and tags
→ research_artifact_save
→ research_artifact_get
```

## Typical corpus workflow

```text
corpus_create / corpus_add
→ research_scaffold_create(corpus-study-v1, corpus)
→ corpus_search and source inspection
→ agent fills groupings, coding rows, evidence, and lineage
→ research_artifact_save
→ research_artifact_export(csv)
```

## Security and ownership

- Artifact payloads are local user data.
- Agent identity is provenance, not authentication authority.
- Write calls require normal local/remote MCP authorization.
- Destructive replacement is not supported; revisions are append-only.
- The runtime never sends an artifact to another service unless the user-selected client explicitly does so.
