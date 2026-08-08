# 05 — Non-Goals

These are explicit things tube-bridge will NOT build into the open-core.

### SaaS / Managed Hosting
tube-bridge is an MIT self-hosted MCP, never a SaaS or managed transcript-hosting product. The Railway demo is solely a disposable try-before-install convenience. No accounts, billing, durable hosted transcripts/corpora, or commercial extension architecture.

### Full Publication Distribution
Full open-source distribution (GitHub release, PyPI package, Docker image, documented demo) remains in scope. Readiness is tracked in `docs/planning/PUBLICATION_READINESS.md` and is not yet accepted.

### Browser Extension
A browser extension is outside this project's scope and release gate. It must not be architected, planned, or documented here.

---

## Core Non-Goals (MIT Open-Core)

### Video downloading
yt-dlp can download videos, but tube-bridge is a **read-only metadata and transcript server**. No `youtube_download` tool. No video file access, streaming, or storage.

### Video upload / comment posting / account management
tube-bridge is **read-only**. No upload, no comment posting, no playlist editing, no channel management, no account creation or modification. It observes YouTube content but does not mutate it.

### UI / Dashboard
No web UI, admin panel, or dashboard. tube-bridge is an MCP server for AI agents. CLI tooling, if ever built, would be a separate project.

### Bulk scraping
Designed for agent use (dozens of calls per session). Not optimized for thousands of parallel requests. No scraping pipelines, no scheduled harvests, no bulk export.

### Translation / NLP
Transcripts are returned as-is in the requested language. No translation, sentiment analysis, keyword extraction, summarization, or any NLP processing. The agent's LLM handles all interpretation.

### Authentication / user accounts (core)
No built-in user accounts, registration, login, or identity management in the open-core. The only auth mechanism is an optional `TUBE_BRIDGE_AUTH_KEY` Bearer token protecting remote transport endpoints — a deployment-level access control, not a user-account system.

### Billing / subscriptions / entitlements
No payment processing, subscription management, trial enforcement, or usage metering. tube-bridge is an MIT self-hosted MCP with no commercial extension, SaaS, accounts, billing, or managed hosting.

### Grabbit integration
Grabbit is a completely separate MCP. There is no connector, dependency, shared service, bundled workflow, code integration, or implementation roadmap between tube-bridge and Grabbit. An agent may independently invoke both MCPs in sequence — that is the full extent of any relationship.



---

## No Promises Without Gates

The following are **not promised** until their respective readiness gates are passed (tracked in `docs/planning/PUBLICATION_READINESS.md`):

- **Unlimited public demo access** — the hosted demo endpoint exists for development and testing. Controlled public access (budgets, abuse controls, observability) is proposed but not yet implemented.
- **YouTube Data API quota beyond default allocation** — no additional allocation beyond the default has been documented as requested or granted. YouTube's official docs identify the audit/extension process; no purchasable quota tier was identified.
- **Legal clearance** — no legal review, copyright compliance assessment, or terms-of-service analysis has been completed. Users are responsible for their own compliance.
- **Proxy reliability** — the `TUBE_BRIDGE_PROXY` feature is operational, but no uptime SLA, throughput guarantee, or reliability promise is made for any specific proxy service.
- **Durable hosted corpus storage** — the disposable demo automatically deletes every corpus 10 minutes after creation. No persistent volume, backups, or durable transcript/corpus hosting is provided on the demo. Self-hosted instances have full persistent corpus storage.

---

## In-Scope Read-Only Storage

The following **is in scope** for the open-core:

- **Metadata caching** — `cache.db` stores transcripts and video metadata persistently. This is a performance optimization, not a long-term archive. Safe to delete and regenerate.
- **Corpus storage** — `corpus.db` stores user-created semantic search corpora with chunks and vectors. This is user-managed, persistent, and explicitly created/deleted by the user.

**Policy/retention decisions** (how long to keep cached data, whether to auto-expire, data deletion procedures) are **still readiness decisions** for the Operator. The storage mechanism exists; the governance around it does not yet.

---

## What tube-bridge IS

To contrast with non-goals, tube-bridge is:

- An **MCP server** providing 16 read-only YouTube tools for AI agents.
- An **MIT-licensed open-core Python package** installable from a source checkout via pip tooling (`pip install .`).
- A **dual-source** system: yt-dlp for anonymous access, Data API v3 for higher-quality results when a key is present.
- A **local semantic search engine** over YouTube transcripts (fastembed + sqlite-vec); embedding inference local after assets available, initial model acquisition may require network.
- **Zero-registration**: 13 tools work without any API key or account.
