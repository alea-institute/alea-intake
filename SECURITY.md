# Security Policy

## Reporting a Vulnerability

**Please report security vulnerabilities through GitHub's private vulnerability reporting feature:**

1. Go to the [Security tab](https://github.com/alea-institute/alea-intake/security/advisories/new) of this repository.
2. Click "Report a vulnerability."
3. Fill in the details of the vulnerability.

**Do not open a public issue for security vulnerabilities.**

## Scope

The following are in scope for security reports:

- Authentication and authorization bypass
- Encryption implementation flaws (AES-256-GCM envelope encryption, field-level PII encryption)
- Tenant isolation failures (cross-tenant data access)
- Injection vulnerabilities (SQL injection, XSS, command injection)
- Sensitive data exposure (PII leaks, audit log tampering, consent bypass)
- Cryptographic weaknesses (nonce reuse, key management flaws)
- Session management issues (JWT handling, token rotation)

The following are out of scope:

- Vulnerabilities in third-party dependencies (report those to the dependency maintainers directly)
- Denial-of-service attacks that require significant resources
- Social engineering attacks
- Issues in development/test configurations (e.g., SQLite in-memory test databases)

## Response Timeline

- **Acknowledgment:** Within 3 business days of report submission.
- **Initial assessment:** Within 7 business days.
- **Resolution target:** Severity-dependent. Critical: 14 days. High: 30 days. Medium: 60 days. Low: next release cycle.

## Disclosure Policy

We follow a coordinated disclosure model:

- We request an embargo on public disclosure until a fix is available.
- We will coordinate with the reporter on disclosure timing.
- We will credit reporters in the security advisory (unless they prefer anonymity).
- If we are unable to resolve the issue within 90 days, we support the reporter's right to disclose.

## Acknowledgments

We appreciate the security research community's efforts to improve the security of open-source legal technology. Reporters who follow this policy will be acknowledged in the relevant security advisory.

## Supported Versions

| Version | Supported |
|---------|-----------|
| 1.x     | Yes       |
| < 1.0   | No        |
