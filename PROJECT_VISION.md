# Project Vision — tube-bridge

**Last updated:** 2026-08-10
**Status:** Published MIT self-hosted MCP. v1.1.0 is externally verified across GitHub, PyPI and GHCR; the Agent Plugin preview is a GitHub Release asset. There is no public hosted demo.

## North Star

Every AI agent can interact with YouTube as naturally as a human — search, discover, extract knowledge, and build local research corpora — without vendor lock-in. Users install and operate their own instance.

## Public Product

The complete public product is the self-hosted `tube-bridge` package:

- GitHub: source and releases.
- PyPI: `pip install tube-bridge`.
- GHCR: public container image.
- MIT license.
- No hosted access, accounts, tester program, managed corpus storage, billing, SLA, or OAuth service.

Each user controls their own YouTube API key, proxy, Bearer auth, storage, quota usage, and retention.

## Tool Baseline

The current source-tree MCP server registers exactly 17 tools from `TOOL_CATALOG`:

- 11 YouTube discovery/transcript/frame/metadata tools;
- 5 local corpus tools;
- 1 help tool.

Fourteen tools can operate without a YouTube Data API key. Three require `YOUTUBE_API_KEY`: comments, channel search, and channel information. Search, video information, and trending upgrade to Data API results when a key is present and fall back to yt-dlp where supported. `youtube_get_frame` returns one bounded ephemeral JPEG as MCP `ImageContent`; it does not persist the clip or image.

## Transports and Auth

- **stdio** — recommended for local clients; no inbound socket.
- **Streamable HTTP** (`/mcp`) — recommended remote transport.
- **SSE** (`/sse`) — legacy compatibility transport.
- **Health** (`/health`) — public process health and tool count.
- **Optional static Bearer** — `TUBE_BRIDGE_AUTH_KEY` protects `/mcp`, `/sse`, and `/messages` for header-capable clients.

There is no OAuth, invite-code, account, or tester-role layer.

## Storage

- `cache.db` stores transcript and video metadata cache entries.
- `corpus.db` stores user-created corpora, chunks, and sqlite-vec vectors.
- Embeddings run locally through fastembed after model assets are available.
- Corpus retention is controlled by the self-hosting user. The application imposes no demo TTL or hosted-retention policy.
- The nullable historical `expires_at` column remains schema-compatible for databases that passed through earlier development builds; new self-hosted corpora have `expires_at = NULL`.

## Private Operator Infrastructure

The Operator may run a private Railway instance for personal Pi/CLI usage. It is protected by the existing static Bearer key and is not a public product endpoint, demo, tester surface, or support promise. Its credentials and hostname are not distributed as an evaluation service.

Browser Claude Custom Connector is not a supported target for this private instance because it cannot attach the static Bearer header. Pi and Claude Code CLI remain suitable header-capable personal clients.

## Product Boundaries

- No public hosted demo or try-before-install service.
- No user accounts, signup, durable hosted profiles, billing, entitlements, or managed identity.
- No public upstream API key or proxy sharing.
- No browser extension.
- No full-video download, retained media library, upload, comment posting, playlist mutation, or account management. Timestamp frame extraction may use and immediately delete a bounded temporary clip.
- Grabbit remains a completely separate companion MCP with no connector, dependency, shared service, or code integration.

## Current Evidence

- Current public release: `v1.1.0`, 17 tools, including bounded ephemeral frame extraction. The source tree keeps the same tool surface and may contain separately gated, unreleased hardening after that immutable release.
- GitHub Release additionally distributes the Agent Plugin preview with one research skill, methodology, examples, templates, and the frozen but not-yet-runtime Corpus v2 contract.
- Original core freeze: 125 deterministic tests.
- Active tree: 211 deterministic tests, including frame extraction/tool, Agent Plugin, Corpus v2 storage, subtitle selection, Corpus v1 ranking/migration/rollback, distribution, retirement/privacy, and historical release contracts.
- Wheel/sdist, `twine check`, isolated install, installed CLI/MCP, Docker runtime, PyPI, GitHub Release, public GHCR, and hosted Python 3.12/3.13 CI are verification surfaces.
- `test_tools.py` remains an optional live YouTube smoke, not a deterministic gate.

## Decision Authority

ADR-003 is active: `docs/adr/003-self-hosted-only-private-operator-railway.md`.

ADR-001's hosted-demo clauses and ADR-002's OAuth/tester design are superseded. Their commits and audit receipts remain historical evidence; they are not active product requirements.
