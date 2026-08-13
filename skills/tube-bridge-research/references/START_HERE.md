# Start here

Use this onboarding on first use, after a plugin upgrade, or when the runtime environment has changed.

## 1. Understand the package boundary

The package contains:

- `plugin.json`: portable plugin identity and version
- `mcp.json`: local stdio MCP launch contract
- `tube_bridge/`: the released 17-tool v1.1.2 runtime
- `SKILL.md`: the canonical research workflow and routing map
- `references/`: doctrine and operating detail loaded on demand
- `assets/templates/`: reusable research records
- `pyproject.toml` and `requirements-release.txt`: adjacent dependency contracts

Agent Plugins v1 does not install Python dependencies or secrets. The MCP command assumes Python 3.12+ and the tube-bridge runtime dependencies are available. Operators can install the released package or prepare the plugin source environment separately.

## 2. Verify capability before research

1. Call `tube_bridge_help` and confirm the server identifies itself as tube-bridge.
2. Confirm the expected 17 source-tree tools are available, including `youtube_get_frame`.
3. Use `youtube_search` for a harmless discovery query.
4. On one candidate, call `youtube_get_available_languages`.
5. Select an intended language code explicitly and call `youtube_get_transcript` with `with_timestamps=true`.
6. Check the returned `language`, `is_generated`, warnings, and timestamped text before treating the result as evidence.

Creating a corpus is not part of the minimum smoke test. It can download an embedding model and persist local data.

## 3. Choose a research mode

- **Quick lookup:** one bounded fact about a source; keep provenance without creating unnecessary hypotheses.
- **Focused study:** one source or question; use FRAME-LOCK and claim classification.
- **Comparative investigation:** disputed or causal question; add source lineage, competing hypotheses, and an adversary gate.
- **Living corpus:** repeated monitoring; preserve state snapshots and update traces.

Read [methodology/00-research-method.md](methodology/00-research-method.md) for the mode-specific workflow. Create a corpus only when repeated or large-scale retrieval justifies indexing.

## 4. Record the research contract

Start with the research brief template. At minimum define the question, source inclusion criteria, language policy, evidence standard, time boundary, and desired output.

## Ready state

The plugin is ready when the MCP launches, the source catalog contains 17 tools, a language can be selected explicitly, a timestamped transcript can be retrieved, and `youtube_get_frame` is available for bounded visual inspection. Live source unavailability must be reported without fabrication.
