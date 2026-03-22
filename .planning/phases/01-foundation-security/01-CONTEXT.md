# Phase 1: Foundation & Security - Context

**Gathered:** 2026-03-22
**Status:** Ready for planning

<domain>
## Phase Boundary

Secure, tenant-isolated data layer with authentication, encryption, audit logging, and consent management. Includes JWT auth, role-based access control, field-level PII encryption, immutable audit logging, granular consent flows, right-to-delete with cascade, multi-tenant data isolation, LLM training opt-out enforcement, and Docker infrastructure scaffolding. This is the trusted foundation every subsequent phase builds on.

</domain>

<decisions>
## Implementation Decisions

### Authentication & Session Design
- Three auth modes, org-configurable: email+password, OAuth/SSO, and kiosk/anonymous (no auth)
- Kiosk mode is fully org-configurable: the deploying org decides audit logging behavior, consent requirements, and data lifecycle for anonymous sessions
- Flat three-role model: admin, professional, consumer — fixed roles with predefined permission sets. Custom roles deferred.
- One org per user — if someone works across orgs, they have separate accounts
- JWT refresh strategy: Claude's discretion (rotating refresh tokens recommended)

### Tenant Isolation
- Schema-per-tenant on PostgreSQL for multi-tenant deployments
- SQLite mode is single-tenant only (self-hosted deployments) — no multi-tenancy on SQLite
- Kiosk/anonymous sessions live in the deploying org's schema with null/anonymous user reference — org controls retention
- LLM API keys configurable per org: orgs can bring their own keys OR use platform-provided keys

### Encryption & Key Management
- Cloud KMS (AWS KMS / GCP KMS) for cloud deployments with envelope encryption; local key file fallback for self-hosted
- Per-tenant encryption keys — each org gets its own data encryption key wrapped by the master key
- Targeted field-level encryption for PII only: names, contact info, narrative text, document contents, voice transcripts
- Non-PII fields (timestamps, status, FOLIO IRIs, config) remain plaintext for queryability
- LLM training opt-out enforcement is org-configurable: cloud with provider opt-out flags, cloud with BAA, or local-only — platform enforces whatever the org configures

### Consent & Right-to-Delete
- Consent granularity is org-configurable — orgs define what consent options their consumers see (from all-or-nothing to per-feature granular)
- Right-to-delete audit trail handling is org-configurable: full deletion, anonymized retention, or time-based retention
- Cascade deletion: full cascade with admin confirmation preview showing what will be deleted (case records, narratives, documents, analysis results, fact mappings, research results)
- Audit log stored in a separate append-only table within the tenant schema, INSERT-only permissions — immutable by application code (except by the deletion cascade when org policy requires it)

### Claude's Discretion
- JWT token structure and refresh strategy specifics
- Exact PII field classification beyond the explicit list above
- Database migration tooling choice
- Docker compose structure and service layout
- API framework middleware ordering
- Test infrastructure setup

</decisions>

<canonical_refs>
## Canonical References

**Downstream agents MUST read these before planning or implementing.**

### Project context
- `.planning/PROJECT.md` — Project vision, FOLIO ecosystem context, integration patterns, tech stack constraints
- `.planning/REQUIREMENTS.md` — Full v1 requirements with traceability; Phase 1 requirements: SECURITY-01 through SECURITY-10, DEPLOY-01, DEPLOY-04, INTEGRATE-04
- `.planning/ROADMAP.md` — Phase dependencies and success criteria

### FOLIO ecosystem (integration reference)
- `../folio-mapper/` — Reference implementation for FastAPI + React pattern in the FOLIO ecosystem

</canonical_refs>

<code_context>
## Existing Code Insights

### Reusable Assets
- No existing code — this is a greenfield project
- `folio-mapper` (sibling project) provides a reference for FastAPI + React + pnpm monorepo structure

### Established Patterns
- FOLIO ecosystem uses FastAPI for backends and React/Vite/TypeScript/Tailwind for frontends
- `alea-llm-client` library provides multi-provider LLM abstraction — import as a dependency

### Integration Points
- `folio-python` — direct library import for ontology queries (Phase 2+)
- `alea-llm-client` — LLM provider abstraction, needed in Phase 1 for INTEGRATE-04
- Docker containerization for both backend and frontend services

</code_context>

<specifics>
## Specific Ideas

- Kiosk mode inspired by legal aid deployment reality: shared devices in walk-in clinics where consumers can't create accounts
- Per-org configurability is a recurring theme — the platform provides capabilities, orgs choose what to enable
- "Maximum security posture" means defaults should be the most secure option, with orgs able to relax for their context

</specifics>

<deferred>
## Deferred Ideas

None — discussion stayed within phase scope

</deferred>

---

*Phase: 01-foundation-security*
*Context gathered: 2026-03-22*
