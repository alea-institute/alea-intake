---
phase: 11-integration-production-deployment
plan: 04
subsystem: infra
tags: [docker, helm, kubernetes, license, mit, skills-registry, distribution, packaging]

# Dependency graph
requires:
  - phase: 11-integration-production-deployment (plans 01-03)
    provides: observability, security, CMS connectors, deployment mode, persistence, migrations
provides:
  - MIT LICENSE at project root
  - Single-tenant Docker Compose with SQLite quick start
  - Multi-tenant Docker Compose with PostgreSQL + optional Redis and OTel
  - Helm chart for Kubernetes with configurable values
  - install.sh one-liner for self-hosted setup
  - Skills registry with bundled DV screening and general intake skills
  - Marketplace index for community skills via Git-based registry
  - Final main.py wiring with all Phase 11 components at version 1.0.0
affects: [release, deployment, open-source-distribution]

# Tech tracking
tech-stack:
  added: [yaml (frontmatter parsing), httpx (marketplace fetch)]
  patterns: [Markdown-with-YAML-frontmatter skills, Git-based marketplace index, entrypoint.sh migration runner]

key-files:
  created:
    - LICENSE
    - entrypoint.sh
    - docker-compose.multi.yml
    - helm/alea-intake/Chart.yaml
    - helm/alea-intake/values.yaml
    - helm/alea-intake/templates/_helpers.tpl
    - helm/alea-intake/templates/deployment.yaml
    - helm/alea-intake/templates/service.yaml
    - helm/alea-intake/templates/ingress.yaml
    - helm/alea-intake/templates/configmap.yaml
    - helm/alea-intake/templates/secret.yaml
    - scripts/install.sh
    - backend/app/skills/__init__.py
    - backend/app/skills/registry.py
    - backend/app/skills/marketplace.py
    - backend/app/skills/bundled/dv_screening.md
    - backend/app/skills/bundled/general_intake.md
    - backend/tests/test_distribution.py
    - backend/tests/test_skills_registry.py
  modified:
    - Dockerfile
    - docker-compose.yml
    - backend/app/main.py

key-decisions:
  - "Helm secret.yaml uses secretKeyRef pattern with existingSecret support (Pitfall 6)"
  - "install.sh generates cryptographic secrets via openssl with python3 fallback"
  - "Skills use Markdown with YAML frontmatter for human-readable, version-controlled definitions"
  - "Marketplace index is a simple JSON file in a Git repo (no registry server needed)"
  - "Dockerfile entrypoint.sh runs Alembic migrations before uvicorn (skippable via env var)"
  - "Healthcheck changed from python httpx to curl for simpler container setup"

patterns-established:
  - "Markdown-with-YAML-frontmatter: skills are .md files with --- delimited metadata"
  - "Git-based marketplace: community skills indexed by index.json in a GitHub repo"
  - "Docker Compose split: single-tenant (SQLite) vs multi-tenant (PostgreSQL)"

requirements-completed: [DEPLOY-02, DEPLOY-03]

# Metrics
duration: 10min
completed: 2026-04-06
---

# Phase 11 Plan 04: Distribution Packaging Summary

**MIT license, Docker/Helm packaging, skills registry, marketplace, and v1.0.0 final wiring -- the capstone for open-source distribution**

## Performance

- **Duration:** 10 min
- **Started:** 2026-04-06T21:40:35Z
- **Completed:** 2026-04-06T21:50:42Z
- **Tasks:** 2
- **Files modified:** 21

## Accomplishments
- MIT LICENSE at project root with ALEA copyright
- Docker Compose split into single-tenant SQLite quick start and multi-tenant PostgreSQL production setup
- Helm chart with 6 templates, configurable values, and proper secret management (no inline secrets)
- install.sh one-liner for self-hosted deployment with auto-generated cryptographic secrets
- Skills registry loading bundled DV screening and general intake skills from Markdown frontmatter
- Marketplace index supporting community skills from Git-based registry with offline graceful degradation
- All Phase 11 components verified wired: version 1.0.0, observability, security headers, rate limiting, CMS admin, migrations, persistence, skills registry

## Task Commits

Each task was committed atomically (TDD: test then feat):

1. **Task 1: MIT license, Docker packaging, Helm chart, and install script**
   - `85d2741` (test) - Failing tests for distribution artifacts
   - `0a3dcff` (feat) - LICENSE, Dockerfile, Docker Compose x2, Helm chart, install script
2. **Task 2: Skills registry, final main.py wiring, and version 1.0.0**
   - `729024c` (test) - Failing tests for skills registry and main.py wiring
   - `9cd81de` (feat) - Skills registry, marketplace, bundled skills, main.py lifespan integration

## Files Created/Modified
- `LICENSE` - MIT License with ALEA copyright 2026
- `entrypoint.sh` - Docker entrypoint running Alembic migrations then uvicorn
- `Dockerfile` - Updated with OCI labels, curl healthcheck, entrypoint, data dir
- `docker-compose.yml` - Single-tenant quick start with SQLite
- `docker-compose.multi.yml` - Multi-tenant with PostgreSQL, optional Redis/OTel
- `helm/alea-intake/Chart.yaml` - Helm chart v1.0.0 metadata
- `helm/alea-intake/values.yaml` - Configurable defaults (deployment, DB, observability, security)
- `helm/alea-intake/templates/_helpers.tpl` - Standard name/label helpers
- `helm/alea-intake/templates/deployment.yaml` - Pod spec with secretKeyRef, probes, resources
- `helm/alea-intake/templates/service.yaml` - ClusterIP on port 8000
- `helm/alea-intake/templates/ingress.yaml` - Optional ingress with TLS
- `helm/alea-intake/templates/configmap.yaml` - Non-sensitive env vars from values
- `helm/alea-intake/templates/secret.yaml` - Placeholder secrets with existingSecret support
- `scripts/install.sh` - One-liner with prereq checks, secret generation, Docker Compose up
- `backend/app/skills/__init__.py` - Skills package init
- `backend/app/skills/registry.py` - SkillsRegistry with load_bundled, list/get/register
- `backend/app/skills/marketplace.py` - MarketplaceIndex with fetch_index/fetch_skill
- `backend/app/skills/bundled/dv_screening.md` - Bundled DV screening protocol skill
- `backend/app/skills/bundled/general_intake.md` - Bundled general intake template skill
- `backend/app/main.py` - Added SkillsRegistry to lifespan Step 9b
- `backend/tests/test_distribution.py` - 33 tests for distribution artifacts
- `backend/tests/test_skills_registry.py` - 17 tests for skills registry and main.py wiring

## Decisions Made
- Helm secret.yaml uses existingSecret pattern: never inline real credentials in values.yaml
- install.sh uses openssl for secret generation with python3 fallback for environments without openssl
- Skills are Markdown files with YAML frontmatter: human-readable, version-controlled, easy to contribute
- Marketplace index is a simple JSON file in a Git repo (no registry server or package manager needed)
- Dockerfile entrypoint.sh runs migrations before app start, skippable via ALEA_SKIP_MIGRATIONS=true
- Healthcheck changed from python httpx to curl (lighter dependency, works without Python in healthcheck context)

## Deviations from Plan

None - plan executed exactly as written.

## Issues Encountered
- Two pre-existing test failures in test_owl_updater.py (health key renamed from 'folio' to 'folio_owl' in Phase 11 Plan 01, and CMS mock setup issue) -- not caused by this plan's changes, logged as deferred.

## Known Stubs

None - all functionality is fully wired.

## User Setup Required

None - no external service configuration required.

## Next Phase Readiness
- This is the FINAL PLAN of the v1.0.0 milestone
- All 11 phases complete: foundation, FOLIO integration, input capture, screening, analysis, research, output, frontend, visualization, orchestration, integration/deployment
- Application is packaged for open-source distribution via Docker, Kubernetes, or install script
- Version 1.0.0 with MIT License ready for release

## Self-Check: PASSED

All 20 created files verified present. All 4 commit hashes verified in git log.

---
*Phase: 11-integration-production-deployment*
*Completed: 2026-04-06*
