# 05 — Non-Goals

These are explicit things tube-bridge will not build into the active product without a new Operator-approved ADR.

## Hosted Product

- No public hosted demo or try-before-install endpoint.
- No SaaS, managed transcript/corpus hosting, account continuity, backups, uptime commitment, or SLA.
- No public tester program, invite provisioning, OAuth authorization server, or managed identity.
- Private Operator infrastructure is not a public product surface.

Users evaluate tube-bridge by installing and operating their own instance.

## YouTube Mutation and Media

- No video download, file streaming, or media storage tool.
- No upload, comment posting, playlist editing, channel management, or account mutation.
- No public shared YouTube credentials, proxy access, or managed quota.
- No bulk scraping, scheduled harvesting, or high-volume export pipeline.

## Accounts and Commercial Features

- No public signup, user accounts, durable profiles, email login, billing, subscriptions, entitlements, trials, or paid extension.
- Optional self-hosted `TUBE_BRIDGE_AUTH_KEY` is deployment-level static Bearer protection, not an account system.
- No browser-Claude OAuth compatibility layer. Browser Claude Custom Connector is not an active target for the Operator's private Bearer-protected instance.

## Product UI

- No dashboard, admin panel, account portal, or browser extension.
- MCP clients provide the interaction surface.

## Language Processing

- No translation, summarization, sentiment analysis, or keyword extraction inside tools. The calling agent's LLM performs interpretation.

## Grabbit

Grabbit is a separate MCP. There is no connector, dependency, shared service, bundled workflow, code integration, or implementation roadmap between it and tube-bridge. An agent may independently call both MCPs.

## No Unsupported Promises

The project does not promise:

- YouTube availability or immunity from bot detection;
- quota above a user's own allocation;
- reliability of any proxy service;
- legal/copyright/terms-of-service clearance;
- hosted retention, deletion timing, backups, or disaster recovery;
- pricing, launch channels, coverage percentages, or SLAs not backed by explicit evidence and authority.

## In-Scope User-Managed Storage

- `cache.db` is a deletable local performance cache.
- `corpus.db` is explicit user-managed semantic corpus storage.
- The self-hosting user controls storage location, persistence, retention, deletion and backups.
- The nullable historical `expires_at` column is retained only for schema compatibility; active code imposes no TTL.

## What tube-bridge Is

- A self-hosted MIT MCP with 17 read-only tools: 11 YouTube interactions, 5 local corpus operations, and help.
- A dual-source system using yt-dlp and an optional user-owned Data API key.
- A local semantic transcript-search engine using fastembed and sqlite-vec.
- A package/container distributed through GitHub, PyPI and GHCR.
