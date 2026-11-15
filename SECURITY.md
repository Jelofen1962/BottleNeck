# Security Policy

## Supported release

Security fixes target the current stable release, `v1.0.x`. Upgrade to the latest stable patch before reporting an issue where possible.

## Reporting a vulnerability

Please don't publish exploit details, credentials, session cookies, invitation tokens or private workspace data in a public issue.

Until GitHub private vulnerability reporting is enabled for the repository, send a private report to the maintainer through [Telegram](https://t.me/jelofen1962) and include:

- The affected BottleNeck version and deployment method.
- A concise description of the impact.
- Reproduction steps using a test workspace and synthetic accounts.
- Relevant logs with secrets, emails and personal data removed.

The maintainer will acknowledge the report and coordinate a fix before public disclosure where practical. Do not test against installations or accounts you don't own.

## Deployment guidance

BottleNeck v1.0.0 targets self-hosted deployments on a trusted network. Before exposing it to the public Internet, configure HTTPS, secure cookies, an explicit allowed-origin list and a restrictive firewall; keep the database and uploaded files outside public web roots.

The application does not include malware scanning for uploaded files, and this release has not received an independent penetration test. Treat uploaded files and workspace exports as untrusted input. Keep off-device backups and test restore procedures.

## Security controls in v1.0.0

The application uses PBKDF2-HMAC-SHA256 password hashing, hashed session and join tokens, `HttpOnly`/`SameSite` session cookies, optional `Secure` cookies under HTTPS, persistent authentication throttles, origin checks on state-changing API requests, CSP/security response headers, permission checks in API handlers and rotating server logs.

These controls are not a substitute for a deployment review. For configuration details, read [Deployment](docs/DEPLOYMENT.md).
