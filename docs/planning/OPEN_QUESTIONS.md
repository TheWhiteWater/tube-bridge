# Open Questions

## Current Blocking Questions

None. ADR-003 resolves the active product boundary: self-hosted distribution only, with private Operator Railway infrastructure outside the public product.

## Resolved Product Questions

### Q1: Tool and data-source model

**Resolved.** Exactly 16 tools. Thirteen are keyless-capable; three require the user's Data API key. Search/video information/trending use Data API when configured and yt-dlp fallback where supported.

### Q2: Transcript behavior

**Resolved.** One transcript tool, manual captions preferred over ASR. Confirmed caption absence remains distinct from upstream/network/proxy failures.

### Q3: Transports and auth

**Resolved.** stdio, Streamable HTTP and legacy SSE are supported. Optional static Bearer protects remote MCP routes. No OAuth/account layer.

### Q4: Storage and retention

**Resolved.** Cache and corpus databases are user-managed and persistent according to the user's deployment. No forced TTL. The nullable historical `expires_at` column remains for compatibility and is written as `NULL`.

### Q5: Hosted demo

**Resolved by ADR-003: retired.** The project does not operate or advertise a public hosted demo. Historical WI-00029 controls remain evidence only.

### Q6: Browser Claude OAuth and tester distinction

**Resolved by ADR-003: retired.** No OAuth, DCR, invite, Operator/Tester role, or browser-Claude Custom Connector requirement. ADR-003 supersedes the authority of WI-00047 and WI-00057; their Station statuses remain to be marked cancelled during WI-00060 finalization.

### Q7: Private Operator Railway

**Resolved.** Keep the service for personal Pi/CLI use behind the existing static Bearer key. Remove demo/OAuth/trusted-proxy variables. Do not publish the hostname/key as product access.

### Q8: Public distribution

**Resolved.** GitHub, PyPI and GHCR are the complete public surfaces. Users install and operate their own server.

## Historical Decisions

- ADR-001 remains historical authority for the self-hosted/open-core boundary; its hosted-demo clauses are superseded.
- ADR-002 is superseded in full.
- ADR-003 is active.
- `v1.0.0` remains functional and unyanked; `v1.0.2` is current and metadata-corrected.
- Grabbit remains a separate MCP with no integration roadmap.

## Conditional Operational Questions

YouTube quota and proxy reliability belong to each self-hosting user. The project documents configuration but does not promise additional quota, proxy availability, or hosted support.
