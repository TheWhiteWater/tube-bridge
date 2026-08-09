# WI-00064 Private Endpoint Help Remediation

## Trigger

Final WI-00060 conformance audit found that active `tube_bridge.server.HELP_TEXT` still contains a hard-coded `deploy_url` pointing to the Operator's private Railway hostname. ADR-003 forbids distributing that endpoint. The same object reports stale version `1.0.0` while package metadata is `1.0.2`.

## Change

- Remove `deploy_url` entirely from `HELP_TEXT`.
- Require serialized help to contain no private Railway hostname.
- Set help `version` to the exact `project.version` in `pyproject.toml`.
- Do not change tool names, schemas, dispatch, transports, auth, or release tags.

## Gates

Separate RED test, independent safe-to-freeze audit, SHA-256 freeze, minimal source edit, cumulative GREEN, independent source audit, hosted CI, private Railway redeploy and live help scan.
