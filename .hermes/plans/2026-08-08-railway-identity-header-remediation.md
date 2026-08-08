# WI-00029 Addendum — Railway Trusted Identity Header

**Trigger:** live deployment `23a2a4d9-8e6a-4da1-b89a-016632d143d6` showed six attacker-controlled `X-Forwarded-For` values created six allowance buckets. Railway did not append a trusted rightmost XFF hop, so the initial `XFF + hops=1` configuration is unsafe.

## Contract

Add explicit `TUBE_BRIDGE_CLIENT_IP_HEADER` selection when proxy trust is enabled:

- default remains `x-forwarded-for` for self-managed reverse proxies and retains right-hop semantics;
- Railway candidate single-value headers are allowlisted (`x-real-ip`, `cf-connecting-ip`, `true-client-ip`, `x-client-ip`);
- selected single-value headers must contain exactly one valid canonical IP; comma chains and invalid/unknown configuration fail closed;
- unselected client-supplied identity headers cannot affect the bucket;
- no raw identity is logged, persisted, or returned.

## TDD and live acceptance

One new deterministic test file is independently audited and frozen; all prior manifests remain byte-identical. After implementation and full verification, deploy once, then select/probe candidate headers via Railway environment and process restarts. A candidate is accepted only when:

1. the header is present (Data API operation is not rejected as identity unavailable);
2. six requests that spoof six distinct values in that same client header produce exactly one bucket, five allows, and a structured sixth rejection;
3. restart resets aggregate counters;
4. XFF remains untrusted/unselected in that configuration.

If no candidate passes, Railway demo remains blocked rather than falling back to spoofable XFF or a shared proxy socket identity.
