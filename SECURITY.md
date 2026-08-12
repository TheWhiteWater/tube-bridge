# Security Policy

## Reporting a vulnerability

Please use GitHub's private vulnerability reporting for this repository. Do not open a public issue containing credentials, exploit details, private endpoints, or personal data.

## Deployment responsibility

tube-bridge is self-hosted. Operators are responsible for network exposure, access control, API keys, proxy credentials, storage permissions, updates, and retention.

For remote HTTP deployments, set `TUBE_BRIDGE_AUTH_KEY`, use HTTPS at the ingress, and keep all credentials in environment variables or a secret manager.
