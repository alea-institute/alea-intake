---
phase: 12-open-source-public-release
plan: 01
subsystem: release-audits
tags: [audit, security, licensing, pii, secrets, kms]
dependency_graph:
  requires: []
  provides: [THIRD_PARTY_LICENSES.md, audit-findings]
  affects: [12-03-PLAN.md, 12-04-PLAN.md]
tech_stack:
  added: []
  patterns: [SPDX-license-attribution]
key_files:
  created:
    - THIRD_PARTY_LICENSES.md
  modified: []
decisions:
  - "KMS status: Cloud KMS raises NotImplementedError at key_management.py:46-49 -- README must describe as planned/roadmap, NOT supported"
  - "PyMuPDF AGPL-3.0: acceptable as pip-installed library; documented in THIRD_PARTY_LICENSES.md"
  - "psycopg LGPL-3.0: acceptable as dynamically-linked library via pip; documented in THIRD_PARTY_LICENSES.md"
  - "Dockerfile findings (unpinned pip, no USER directive) documented for README security posture; no code changes in Phase 12"
metrics:
  duration: 3min
  completed: "2026-04-13T00:12:00Z"
  tasks_completed: 2
  tasks_total: 2
  files_created: 1
  files_modified: 0
---

# Phase 12 Plan 01: Pre-Flight Release Audits Summary

Four pre-flight release audits completed with THIRD_PARTY_LICENSES.md attribution file created; zero blocking secrets or PII found; Cloud KMS confirmed not yet implemented for accurate downstream README claims.

## Audit Results

### Secret Scan (D-28a)

**Commands run:**
```bash
grep -rn "AKIA|sk-ant-|ghp_|ghs_|glpat-|xoxb-|xoxp-|-----BEGIN.*PRIVATE KEY" --include="*.py" --include="*.ts" ... | grep -v node_modules | grep -v .git/
git log --all -p -- '*.env' '*.env.*' | head -200
git log --all --diff-filter=D -- '*.env' '*.key' '*.pem'
```

**Findings: 0 real secrets**

- No AWS access keys (AKIA*), API tokens (sk-*, ghp_*, ghs_*, glpat_*), Slack tokens, or private keys found in tracked files
- Git history contains only `.env.example` with placeholder values (`change-me-to-random-64-char-string`, `change-me`)
- No deleted `.env`, `.key`, or `.pem` files in git history
- `backend/app/deployment/provisioning.py:169` uses `secrets.choice()` for dynamic password generation (not hardcoded)
- `.gitignore` correctly excludes `.env`, `.env.local`, `.env.*.local`, and `data/`

**Status: PASS**

### PII / Internal Reference Scrub (D-28c)

**Commands run:**
```bash
grep -rn "@" --include="*.py" --include="*.ts" ... | grep -v [decorators/imports/packages]
grep -rn "slack.com|notion.so|atlassian.net|jira.|confluence." ...
grep -rn "staging.|dev.|internal." ...
grep -rn "SSN|social security|555-|123-45-6789" ...
grep -rn "AKIA|sk-ant-|ghp_|-----BEGIN" .planning/ ...
```

**Findings: 0 real PII or internal references**

- Email addresses: Only fictional/test emails found (admin@acme.com in test fixtures)
- Internal URLs: No Slack, Notion, Jira, or Confluence URLs (only a grep command in 12-05-PLAN.md)
- Staging/dev URLs: Only code references (`structlog.dev.ConsoleRenderer()`, `doc.internal.pageSize`)
- PII in fixtures: "social security" appears as a legal term in term_expansions.py; `555-1234` is the standard fictional phone number
- .planning/ directory: No secrets or PII (only plan files containing grep command examples)
- docker-compose.dev.yml: Contains `POSTGRES_PASSWORD: devpassword` -- acceptable for local dev compose file, not a production secret

**Status: PASS**

### KMS Verification (D-19)

**File:** `backend/app/core/key_management.py`

**Exact status (lines 44-49):**
```python
elif kms_provider and kms_key_id:
    # Cloud KMS -- deferred to Phase 11
    raise NotImplementedError(
        f"Cloud KMS provider '{kms_provider}' is not yet implemented. "
        "Use master_key_path for local key file backend."
    )
```

**Conclusion:** Cloud KMS (AWS KMS / GCP KMS) is **NOT implemented**. The code path explicitly raises `NotImplementedError`. The README (Plan 04) MUST describe Cloud KMS as "planned / roadmap" and NOT as "supported" or "available."

Current encryption: AES-256-GCM envelope encryption with local file-based master KEK only.

**Status: PASS -- factual status confirmed for downstream plans**

### Dependency License Audit (D-28b)

**Python dependencies (34 packages):**
- Allowed licenses found: MIT (18), BSD-3-Clause (7), Apache-2.0 (8), BSD-2-Clause (1), ISC (1)
- Flagged for review: LGPL-3.0-or-later (psycopg), AGPL-3.0-only (pymupdf)
- Blocked: None
- Unknown: None

**Frontend dependencies (46 packages):**
- Allowed licenses found: MIT (37), ISC (6), BSD-3-Clause (2), Apache-2.0 (1)
- Font licenses: OFL-1.1 (4 @fontsource packages) -- compatible with MIT
- Flagged: None
- Blocked: None

**AGPL/LGPL compatibility assessment:**
- **pymupdf (AGPL-3.0):** Acceptable. Used as a pip-installed library. ALEA Intake does not modify, fork, or redistribute PyMuPDF source. AGPL copyleft applies to PyMuPDF itself, not to calling code. Documented in THIRD_PARTY_LICENSES.md with note that organizations may substitute alternatives.
- **psycopg (LGPL-3.0):** Acceptable. Used as a dynamically-linked library via pip. LGPL explicitly permits this use pattern without copyleft propagation. Documented in THIRD_PARTY_LICENSES.md.

**Artifact created:** `THIRD_PARTY_LICENSES.md` at repo root with all 80 dependencies listed with SPDX identifiers.

**Status: PASS**

### Infrastructure Security Linting (D-28d)

**Dockerfile findings:**

| Severity | Finding | Details |
|----------|---------|---------|
| Medium | DL3013: Unpinned pip install | `RUN pip install uv` does not pin version |
| Medium | No USER directive | Container runs as root; should add non-root user |
| Low | DL3008: Unpinned apt packages | `apt-get install` does not pin package versions (mitigated by `--no-install-recommends`) |
| Info | Multi-stage build | Correctly uses multi-stage (frontend-build + backend) |
| Info | HEALTHCHECK present | Proper health check configured |

**Helm chart findings:**

| Severity | Finding | Details |
|----------|---------|---------|
| Info | secretKeyRef pattern | Correctly uses existingSecret for credentials (no hardcoded secrets) |
| Info | Resource limits | CPU and memory limits defined in values.yaml |
| Low | No securityContext | deployment.yaml lacks explicit securityContext (runAsNonRoot, readOnlyRootFilesystem) |
| Low | No NetworkPolicy | No network policy template for pod-level network isolation |

**Docker Compose findings:**

| Severity | Finding | Details |
|----------|---------|---------|
| Low | Default passwords | docker-compose.multi.yml uses `${ALEA_DB_PASSWORD:-changeme}` default; acceptable for dev with env var override |
| Low | docker-compose.dev.yml hardcoded password | `POSTGRES_PASSWORD: devpassword` -- acceptable for local dev only |
| Info | No privileged mode | No containers run privileged |
| Info | No host network | All containers use default bridge networking |
| Info | Healthchecks present | DB and backend have healthchecks in multi.yml |
| Info | Version pinning | Base images pinned (node:22-slim, python:3.12-slim, pgvector:pg17) |

**Status: PASS -- no findings above medium severity; all medium findings documented for README security posture**

## Commits

| Task | Commit | Description |
|------|--------|-------------|
| Task 1 | (audit-only) | Secret scan, PII scrub, KMS verification -- no files modified |
| Task 2 | 849714a | THIRD_PARTY_LICENSES.md created with full dependency attribution |

## Deviations from Plan

None -- plan executed exactly as written.

## Known Stubs

None.

## Self-Check: PASSED

- FOUND: THIRD_PARTY_LICENSES.md
- FOUND: commit 849714a
- FOUND: 12-01-SUMMARY.md
