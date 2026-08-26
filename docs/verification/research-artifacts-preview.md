# Research artifact preview verification

**Candidate commit:** `759e324`  
**Acceptance status:** verification complete; independent audit blocked/pending; not accepted for release.

## RED evidence

Before production implementation, the four new contract suites failed during collection because `tube_bridge.research_artifacts` did not exist:

```text
3 collection errors
ImportError: cannot import name 'research_artifacts' from 'tube_bridge'
```

The test bytes were then frozen in:

```text
tests/frozen/research-artifacts-preview.sha256
```

## Frozen hash verification

```text
tests/test_research_artifact_contract.py: OK
tests/test_research_artifact_store.py: OK
tests/test_research_scaffold_tools.py: OK
tests/test_research_preview_mcp.py: OK
```

## GREEN evidence

Targeted contract plus channel-context addendum:

```text
22 passed in 2.44s
```

The addendum first failed because corpus scaffolds did not reuse an attached source artifact's channel context, then passed after the bounded local-only linkage was implemented. Its frozen hash is `tests/frozen/research-artifacts-channel-context-addendum.sha256`.

Full deterministic suite:

```text
291 passed in 56.98s
```

Additional checks:

```text
public-tree hygiene check passed
verified 1 self-hosted-only release artifacts
secret-pattern scan passed: 20 changed/untracked files
```

The built wheel contained:

```text
tube_bridge/research_artifacts.py
tube_bridge/research_templates/corpus-study-v1.json
tube_bridge/research_templates/structured-source-v1.json
```

Preview-enabled real stdio handshake:

```text
preview_stdio_tools 23
research_artifact_export
research_artifact_get
research_artifact_save
research_artifacts_list
research_scaffold_create
research_templates_list
```

The default, preview-disabled catalog remains 17 tools.

## Bounded live channel-context smoke

A keyless scaffold was created for `9SHjQgNrpys` in an isolated disposable cache. No secret or description content was printed.

```text
video_title_present: true
channel_id_present: true
channel_title_present: true
channel_description_present: true
channel_description_chars: 412
channel_provider: yt-dlp
transcript_status: unavailable
agent_metadata_completion: unfilled
agent_section_count: 0
```

The temporary research database/cache was deleted after the smoke. The result proves that a no-caption source still receives honest video/channel context while all agent-owned semantic fields remain empty.

## Audit boundary

- Station executor/auditor delegation returned `delegation_policy_blocked` twice.
- Claude Code executor was unavailable because the subscription limit was reached.
- Codex CLI audit was unavailable because its OAuth refresh token was invalidated.

Therefore no independent PASS exists. The implementation is a local source-preview candidate only. It must not be merged, released, published, or represented as accepted until a fresh independent audit completes and the orchestrator explicitly confirms that provisional verdict.
