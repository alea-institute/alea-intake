---
phase: 12-open-source-public-release
plan: 03
subsystem: documentation
tags: [readme, documentation, use-cases, architecture, mermaid, i18n, folio]
dependency_graph:
  requires:
    - phase: 12-01
      provides: audit findings, KMS status, THIRD_PARTY_LICENSES.md
    - phase: 12-02
      provides: LICENSE, CONTRIBUTING.md, SECURITY.md, CODE_OF_CONDUCT.md
  provides:
    - README.md with project identity, architecture diagram, 12 use cases, 4 key capabilities, quick start
    - docs/images/ directory for future screenshots
  affects: [12-04-PLAN.md, 12-05-PLAN.md]
tech_stack:
  added: []
  patterns: [mermaid-architecture-diagram, plain-language-first-documentation]
key_files:
  created:
    - README.md
    - docs/images/.gitkeep
  modified: []
decisions:
  - "README structure: project identity -> architecture -> use cases -> capabilities -> quick start -> license/contributing, with Plan 04 placeholder sections for security/config/deployment"
  - "Core use cases include full deployment scenario tables with recommended config settings drawn from codebase enums"
  - "Cloud KMS described as not yet implemented per 12-01 audit findings (NotImplementedError at key_management.py:46)"
  - "FOLIO ontology section includes resolution weights (embedding=0.3, label=0.3, LLM=0.4) verified from codebase"
  - "LLM providers documented from codebase: openai, anthropic, google, vllm with three-level training opt-out"
patterns-established:
  - "README uses plain-language-first tone for legal aid program leaders per D-06/D-07"
  - "END PLAN 03 CONTENT HTML comment marker for Plan 04 append point"
  - "Placeholder sections with HTML comments for Plan 04 to fill"
requirements-completed: []
metrics:
  duration: 4min
  completed: "2026-04-13T00:42:00Z"
  tasks_completed: 1
  tasks_total: 1
  files_created: 2
  files_modified: 0
---

# Phase 12 Plan 03: README.md -- Project Identity, Architecture, Use Cases, and Capabilities Summary

**487-line README.md with Mermaid architecture diagram, all 12 use cases (4 core with deployment scenarios, 8 specialty), multi-language/autonomy/ephemeral/FOLIO capability sections, and Docker Compose quick start**

## Performance

- **Duration:** 4 min
- **Started:** 2026-04-13T00:38:19Z
- **Completed:** 2026-04-13T00:42:12Z
- **Tasks:** 1
- **Files created:** 2

## Accomplishments

- Created README.md (487 lines) covering the "what and who" portion of the README
- Mermaid flowchart diagram showing full intake pipeline (input -> normalization -> FOLIO resolution -> analysis -> pre-research -> research -> output) with supporting platform services
- All 4 core use cases (Legal Aid Intake, Court SRL Portals, DV/Victim Services, Tenant Rights) with who-deploys, problem-solved, recommended-config tables, key-safeguards, and deployment scenarios
- All 8 specialty use cases (Law School Clinics, Public Defender, Immigration, Bar Association Referral, Veterans' Benefits, Disability Benefits, Consumer Protection, Family Law)
- Four key capability sections: Multi-Language (7 languages confirmed from locales/), Three Autonomy Modes, Ephemeral Mode and Right-to-Delete (3 persistence modes, 3 deletion policies), FOLIO Ontology Grounding
- Quick Start section with Docker Compose commands
- License and Contributing sections linking to all community files
- docs/images/ directory with .gitkeep for future screenshots

## Task Commits

Each task was committed atomically:

1. **Task 1: Write README.md -- project identity, architecture diagram, use cases, featured capabilities** - `16fb186` (feat)

## Files Created/Modified

- `README.md` -- Full project README with identity, architecture, use cases, capabilities, quick start, license, contributing
- `docs/images/.gitkeep` -- Placeholder directory for future screenshots (Plan 05)

## Decisions Made

- **README structure follows plan exactly:** Project identity -> TOC -> architecture -> screenshots placeholder -> use cases -> key capabilities -> quick start -> placeholder sections for Plan 04 -> license -> contributing -> END PLAN 03 marker
- **Config tables in core use cases:** Each core use case includes a table of recommended settings drawn from verified codebase enums (DeploymentMode, PersistenceMode, LLMDataPolicy)
- **Cloud KMS accurately described:** Not mentioned as available; only local file-based master KEK documented, consistent with 12-01 audit finding
- **FOLIO resolution weights from codebase:** 0.3 embedding, 0.3 label, 0.4 LLM; high-confidence threshold 0.85 for direct acceptance
- **Deletion service details from codebase:** SHA-256 hash preview confirmation, three deletion policies (full_delete, anonymize, time_based), audit anonymization via actor_id=NULL

## Deviations from Plan

None -- plan executed exactly as written.

## Known Stubs

None. All sections within Plan 03 scope are fully written. Plan 04 placeholder sections (Security, Configuration Reference, Scenario Walkthroughs, Deployment Topologies, Data Flow, Roadmap) contain HTML comments indicating they will be filled by Plan 04.

## User Setup Required

None -- no external service configuration required.

## Next Phase Readiness

- README.md is ready for Plan 04 to append security, configuration reference, scenario walkthroughs, deployment topologies, data flow diagram, and roadmap sections at the `<!-- END PLAN 03 CONTENT -->` marker
- Plan 05 can add screenshots to docs/images/ and update the Screenshots section

---
*Phase: 12-open-source-public-release*
*Completed: 2026-04-13*
