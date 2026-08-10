# AGENTS.md — tube-bridge

**Project:** Self-hosted YouTube MCP server — v1.1.0, 17 tools, plus Agent Plugin preview
**Stack:** Python 3.12+, MCP 1.28.1, yt-dlp, youtube-transcript-api, SQLite, sqlite-vec, fastembed
**License:** MIT

## Product Authority

Read these before changing product behavior:

1. `PROJECT_VISION.md`
2. `docs/adr/003-self-hosted-only-private-operator-railway.md`
3. `docs/planning/PUBLICATION_READINESS.md`

The only public product is the self-hosted MCP. There is no public hosted demo, OAuth service, tester program, account system, managed storage, or SLA. The Operator's Railway instance is private personal infrastructure and is not distributed as an endpoint.

ADR-001 hosted-demo clauses and ADR-002 are historical/superseded. Do not revive demo quotas, trusted-IP buckets, forced corpus TTL, OAuth, invite roles, or browser-Claude connector work without a new Operator-approved ADR.

## Quick Start

```bash
pip install tube-bridge

tube-bridge                  # stdio
tube-bridge --http           # HTTP on :8080
python3 -m pytest tests -q    # deterministic suite
python3 test_tools.py         # optional live YouTube smoke
```

## Architecture

```text
tube_bridge/
├── server.py          # 17-tool catalog, MCP registration, help and dispatch
├── tools.py           # YouTube and corpus tool implementations
├── cli.py             # synchronous installed entrypoint; stdio/HTTP selection
├── transport.py       # Streamable HTTP/SSE, optional static Bearer, health
├── cache.py           # cache.db — transcripts and video metadata
├── corpus.py          # corpus.db — user-managed corpora and local vectors
└── youtube/
    ├── client.py      # yt-dlp subprocess, retry, proxy
    ├── api.py         # Data API v3 via stdlib urllib
    ├── transcript.py  # transcript extraction; real upstream errors preserved
    ├── frame.py       # bounded timestamp→JPEG extraction
    └── models.py      # VideoInfo
```

Retired modules `oauth.py`, `demo_policy.py`, and `demo_ttl.py` must remain absent.

## Core Contract

- Exactly 17 source-tree tools from `TOOL_CATALOG`.
- 14 keyless-capable tools; 3 require `YOUTUBE_API_KEY`.
- `youtube_search`, video information and trending use Data API first when configured and yt-dlp fallback where supported.
- The Data API client uses Python stdlib `urllib`; do not add the Google SDK without an ADR.
- Transcripts use `youtube-transcript-api`; select the original/default language cohort first, then prefer matching manual captions over ASR.
- `youtube_get_frame` exposes one ephemeral 64–1280px JPEG as MCP `ImageContent`; raw JPEG ≤1.5 MB, base64 image data ≤2 MB, no batch, no frame/clip persistence.
- Network/proxy failures must not be collapsed into a false “no captions” result.
- Embeddings are local through fastembed after assets are available.

## Transports and Auth

- stdio for local child-process clients.
- Streamable HTTP `/mcp` for remote clients.
- Legacy SSE `/sse` plus `/messages`.
- `/health` is public.
- Optional `TUBE_BRIDGE_AUTH_KEY` protects `/mcp`, `/sse`, and `/messages`.
- No OAuth, invite, tester-role, IP-bucket, or demo-mode behavior.

Pi and Claude Code CLI may use the Operator's private Railway service because they support a Bearer header. Browser Claude Custom Connector is not an active requirement.

## Storage

- `cache.db` and `corpus.db` are separate SQLite databases under `TUBE_BRIDGE_CACHE` (default `~/.tube_bridge`).
- Self-hosting users own retention. No forced corpus TTL.
- Keep the nullable `corpora.expires_at` compatibility column; new corpora write `NULL`.
- Do not break databases created by earlier development builds.

## Security

- Read API keys, proxy URLs and Bearer keys from environment variables only.
- Never commit, print, bundle, rotate, or expose credentials without explicit Operator authorization.
- Do not distribute the private Railway URL/key as a public evaluation service.
- Grabbit is a separate MCP; no connector/shared service/code integration exists.

## Testing and Methodology

- `test_tools.py` is optional live smoke only.
- Original core freeze: 125 tests.
- Active source-tree suite: 188 deterministic tests, including frame, plugin, subtitle, Corpus v2, distribution, retirement/privacy, and historical release contracts.
- Source/test changes require RED, independent contract audit, frozen SHA-256, GREEN, independent source audit, and hosted CI.
- Do not modify a frozen test after source work begins; use an audited addendum or superseding product ADR.
- Build/release verification uses a disposable tools environment when system Python lacks `build`/`twine`.

## Publication

Current public release `v1.1.0` is verified across GitHub, PyPI and GHCR as the self-hosted-only 17-tool runtime. GitHub additionally carries the Agent Plugin preview bundle; dependency bootstrap remains operator-managed. Historical `v1.0.0`–`v1.0.3` artifacts remain immutable, unyanked release history.

Public documentation must describe self-hosting only. Do not advertise Railway demo access, hosted retention, tester invites, OAuth, accounts, billing, managed quota, or uptime guarantees.
