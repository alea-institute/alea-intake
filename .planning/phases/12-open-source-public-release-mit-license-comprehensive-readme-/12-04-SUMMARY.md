---
phase: 12-open-source-public-release
plan: 04
subsystem: readme-documentation
tags: [readme, security, configuration, scenarios, deployment, roadmap, mermaid]
dependency_graph:
  requires: [12-03-SUMMARY.md]
  provides: [complete-readme]
  affects: [12-05-PLAN.md]
tech_stack:
  added: []
  patterns: [mermaid-diagrams, env-var-reference-tables, scenario-walkthroughs]
key_files:
  created: []
  modified:
    - README.md
decisions:
  - "Cloud KMS described as planned/roadmap per D-19 and 12-01 KMS verification -- NOT as supported or available"
  - "Configuration reference organized into 12 categorical tables matching config.py field groupings"
  - "Organization-level settings documented separately from platform env vars per D-21g/D-21n/D-21o"
  - "5 scenario walkthroughs use concrete .env snippets with placeholder secrets (no real credentials)"
  - "Roadmap section signals active development without over-promising specific timelines"
  - "TOC expanded with sub-section anchors for Security, Deployment, Config Reference, and Scenarios"
metrics:
  duration: 5min
  completed: "2026-04-13T00:50:42Z"
  tasks_completed: 2
  tasks_total: 2
  files_created: 0
  files_modified: 1
---

# Phase 12 Plan 04: README Part 2 Summary

Security documentation, configuration reference (every ALEA_* env var and org-level field), 5 scenario walkthroughs with .env snippets, 4 deployment topology Mermaid diagrams, 1 data-flow/security Mermaid diagram, and roadmap section appended to README.md -- completing the comprehensive 1186-line self-contained README.

## Task Results

### Task 1: Security Documentation and Deployment Topology Diagrams

Appended the following sections to README.md after Plan 03 content:

**Security section (D-17, D-18):**
- Opening paragraph with "privacy by design" and "security by design" framing
- Explicit D-17 disclaimer: "not certified or compliant with any specific regulatory framework"
- Encryption: AES-256-GCM envelope encryption, 12-byte nonces, field-level PII encryption, 0o600 key permissions
- Key Management: Local file backend documented; Cloud KMS explicitly described as **planned/not yet implemented** per D-19 and 12-01-SUMMARY KMS verification
- Authentication: JWT access/refresh tokens with jti, OAuth 2.0 SSO (Google, Microsoft), RBAC (admin/professional/consumer) with DB-authoritative role checks
- Audit Logging: Immutable append-only log, INSERT-only permissions, separate DB session for transaction isolation
- Consent Management: Middleware interception, per-org templates, versioned consent records
- Right-to-Delete: Three policies (full_delete, anonymize, time_based), SHA-256 preview hash confirmation, cascade deletion
- LLM Data Privacy: Three-level training opt-out (API-tier, provider headers, local_only policy), per-org data policy table
- Tenant Isolation: Schema-level isolation (tenant_{slug}), TenantMiddleware, public route exemptions
- Network Security: Rate limiting (memory/Redis), CSP/HSTS/security headers, CORS, max request size

**Deployment Topologies section (D-23c) -- 4 Mermaid diagrams:**
1. Single-Tenant Docker Compose (SQLite) -- simplest deployment
2. Multi-Tenant PostgreSQL -- production with pgvector, optional Redis + OTEL
3. Kiosk Deployment -- air-gapped/restricted network, ephemeral, local vLLM
4. Kubernetes with Helm -- production cloud with autoscaling, Secrets, Ingress

**Data Flow and Security Model section (D-23d) -- 1 Mermaid diagram:**
- PII lifecycle: input -> middleware stack -> field-level encryption -> DB storage
- Read path: DEK unwrap -> field decryption -> response
- Audit events at each stage via separate session
- Right-to-delete flow: preview -> hash confirm -> policy-based deletion/anonymization

### Task 2: Configuration Reference, Scenario Walkthroughs, and Roadmap

**Configuration Reference (D-09, D-21a-o):**
- Platform Settings: 12 categorical tables covering all 49 ALEA_* environment variables from config.py Settings class
  - Deployment, Database, Encryption, Authentication, Intake, ASR, FOLIO Ontology, Research, Observability, Rate Limiting, Security Headers, CMS Integration, CORS
- Organization-Level Settings: 1 table covering all 10 OrganizationConfig fields (excluding id, created_at, updated_at)
- KMS fields (`ALEA_KMS_PROVIDER`, `ALEA_KMS_KEY_ID`) include bold "Not yet implemented" note

**Scenario Walkthroughs (D-22a-e) -- 5 scenarios with .env snippets:**
1. Legal Aid Kiosk (D-22a): ephemeral, SQLite, local vLLM, consent required, DV protocol
2. Court SRL Portal (D-22b): persistent, PostgreSQL, local vLLM, all 7 languages, accessibility
3. Multi-Tenant Cloud (D-22c): multi-tenant, PostgreSQL, Redis rate limiting, OTEL, CMS enabled
4. Small Legal Aid Office (D-22d): single-tenant, SQLite, Clio CMS sync, Google OAuth SSO
5. Domestic Violence Shelter (D-22e): ephemeral, no cloud, no audio retention, 2-hour TTL, local vLLM

**Roadmap (D-10):**
- Cloud KMS integration (highest priority)
- Additional CMS connectors
- Additional language support
- Protocol library governance
- Strength-of-claim scoring
- Multi-language README

**Table of Contents:** Updated with sub-section anchors for Security (8 sub-sections), Deployment (4 sub-sections), Configuration Reference (2 sub-sections), and Scenario Walkthroughs (5 sub-sections).

## Commits

| Task | Commit | Description |
|------|--------|-------------|
| Task 1 | 8c3d4f6 | Security docs, deployment topology diagrams, data flow diagram |
| Task 2 | 0f0085a | Config reference, scenario walkthroughs, roadmap, TOC update |

## Verification Results

| Check | Result |
|-------|--------|
| `grep "## Configuration Reference" README.md` | PASS |
| `grep -c "ALEA_" README.md` >= 40 | PASS (142) |
| `grep "Not yet implemented" README.md` | PASS (KMS fields) |
| `grep "## Scenario Walkthroughs" README.md` | PASS |
| `grep "## Roadmap" README.md` | PASS |
| `wc -l README.md` between 1000-3000 | PASS (1186) |
| `grep -c '```mermaid' README.md` >= 6 | PASS (6) |
| Cloud KMS says "planned" not "supported" | PASS |
| License and Contributing are final sections | PASS |

## Deviations from Plan

None -- plan executed exactly as written.

## Known Stubs

None. All sections contain substantive content sourced from the actual codebase.

## Self-Check: PASSED

- FOUND: README.md (1186 lines)
- FOUND: commit 8c3d4f6
- FOUND: commit 0f0085a
- FOUND: 12-04-SUMMARY.md
