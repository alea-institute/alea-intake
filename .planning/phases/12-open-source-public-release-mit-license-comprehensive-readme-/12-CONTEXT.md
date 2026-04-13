# Phase 12: Open-Source Public Release — Context

**Gathered:** 2026-04-09
**Status:** Ready for planning
**Source:** Interactive Q&A with Damien Riehl (5 rounds via AskUserQuestion)

<domain>
## Phase Boundary

This phase prepares the `alea-intake` repository for public open-source release. It is a documentation, licensing, and release-hygiene phase — not a feature phase. No new runtime code is introduced. The phase produces:

1. An updated **LICENSE** file with corrected copyright attribution.
2. A **comprehensive README.md** at the repository root — the primary artifact — written for legal aid / court program leaders as the primary audience, technically complete but plain-language first. Self-contained (no required companion docs to understand the project).
3. A **SECURITY.md** for responsible disclosure via GitHub private vulnerability reporting.
4. A **CONTRIBUTING.md** for open PR contributions (no CLA).
5. A **CODE_OF_CONDUCT.md** (Contributor Covenant).
6. Supporting visual assets: architecture diagram, UI screenshots, deployment topology diagrams, data-flow/security-model diagram.
7. **Pre-flight hygiene audits** (secret scan, dependency license audit, PII scrub, security linting of Dockerfile/Helm/configs).
8. A verified factual audit of claims the README makes (especially: Cloud KMS status).

Explicitly **out of scope**:
- No code refactoring or new features.
- No new CMS connectors.
- No changes to product behavior.
- No migration of `.planning/` contents (they ship as-is per user decision — full transparency).

</domain>

<decisions>
## Implementation Decisions

### Legal / Attribution
- **D-01:** Copyright line becomes: `Copyright (c) 2026 Damien Riehl and ALEA Institute`. Update `LICENSE` file accordingly. Single year (2026), both parties named.
- **D-02:** License remains MIT. No change in permissions, warranty, or disclaimer text — only the copyright line.
- **D-03:** ALEA Institute described in README as: *"A research institute building open infrastructure to support justice and the public good — for example, advancing access to justice through open technology."*

### Project Identity
- **D-04:** Public repo URL: `github.com/alea-institute/alea-intake`. All badge URLs, clone commands, and issue links assume this path.
- **D-05:** Tagline at top of README: **"Open-source, privacy-first legal intake for access to justice."**
- **D-06:** No marketing puffery. Factual, confident, plain-language tone throughout.

### README Audience & Structure
- **D-07:** Primary audience: **legal aid and court program leaders** (non-technical). Technical evaluators are secondary — their needs are met by technical sub-sections and a linked `TECHNICAL.md` (or equivalent section anchor) within the same README.
- **D-08:** **One comprehensive README.** Long (~1500–2500 lines) but self-contained with a clickable table of contents. Users don't have to click around companion files to understand the project.
- **D-09:** Configuration documentation uses **BOTH** a comprehensive reference table of every `ALEA_*` env var + every org-level config field, **AND** scenario walkthroughs ("Configure it this way for a legal aid kiosk", "Configure it this way for a court SRL portal", etc.).
- **D-10:** Include a forward-looking **Roadmap** section listing planned capabilities (e.g., full Cloud KMS wiring, additional CMS connectors, additional languages) — signals active development.

### Use Cases to Document (Exhaustive)
Each use case gets a sub-section with: who deploys it, what problem it solves, recommended configuration, safeguards that matter most, and a short deployment scenario.

**Core use cases (first-class, each fully detailed):**
- **D-11a:** Legal aid intake (LSC-funded orgs and non-LSC legal aid societies)
- **D-11b:** Court SRL / navigator portals (self-represented litigant portals, courthouse lobby kiosks)
- **D-11c:** Domestic violence / victim services (DV shelters, victim advocates — leveraging the built-in DV-default safety protocol from Phase 5)
- **D-11d:** Tenant rights / eviction defense (housing justice programs, tenant unions)

**Specialty use cases (each a shorter sub-section):**
- **D-12a:** Law school clinics
- **D-12b:** Public defender intake
- **D-12c:** Immigration services (asylum, removal defense, USCIS triage)
- **D-12d:** Bar association lawyer referral services
- **D-12e:** Veterans' benefits assistance (VA claims, discharge upgrades)
- **D-12f:** Disability benefits (SSDI/SSI)
- **D-12g:** Consumer protection / debt defense
- **D-12h:** Family law / mediation intake

**Umbrella framing:** The README must explicitly state: *"Any legal service provider — especially those serving low-income consumers — can adapt this system."* Use cases above are illustrative, not exclusive.

### Capabilities to Feature Prominently
Each of these gets its own dedicated README section with rationale, configuration, and deployment notes:
- **D-13:** Multi-language support (7 languages: en, es, zh, vi, ko, tl, ru) — framed as critical for legal aid / immigration / court access contexts.
- **D-14:** Three autonomy modes (chatbot / professional / agent) — configurable human-in-the-loop vs autonomous vs professional-mediated intake.
- **D-15:** Ephemeral mode & right-to-delete — kiosk-safe sessions with TTL, three deletion policies (full delete, anonymize, time-based), preview+hash confirmation pattern.
- **D-16:** FOLIO ontology grounding — every legal concept mapped to the FOLIO open legal ontology; interoperable, explainable, auditable.

### Security Documentation
- **D-17:** Compliance framing is **generic and universal**, not specific to HIPAA / CJIS / LSC / state bar ethics rules. Emphasize **"privacy by design"** and **"security by design"** as design philosophies that help implementing organizations meet *their* applicable laws, rules, and regulations. Do **not** claim the software is certified or compliant with any specific framework — that would be misleading since compliance depends on deployment choices.
- **D-18:** Security section must document, in detail:
  - AES-256-GCM envelope encryption (per-tenant DEKs wrapped by master KEK)
  - Field-level PII encryption with unique 12-byte nonces (NIST-recommended for GCM)
  - JWT access + refresh token rotation with `jti` uniqueness claim
  - OAuth 2.0 SSO (Google, Microsoft) with exempted tenant-middleware paths
  - Role-based access control with DB-authoritative role checks
  - Immutable append-only audit log (INSERT-only DB permissions in production)
  - Consent middleware + configurable per-org consent templates
  - Three-level LLM training opt-out (API-tier, provider headers, `local_only` policy)
  - Multi-tenant schema isolation (tenant_{slug}) with tenant middleware
  - Rate limiting (memory or Redis-backed, per-IP + per-org)
  - CSP, HSTS, security headers middleware
  - Master key file with 0o600 permissions; optional Cloud KMS (AWS/GCP) — **status to be verified before README claims it as production-ready**
  - Right-to-delete with three policies: full_delete, anonymize, time_based — including audit anonymization (actor_id=NULL)
  - Ephemeral persistence mode with TTL starting from session completion
  - Configurable CORS, max request size, CSP script-src
- **D-19:** **Cloud KMS claim verification** is a required task in this phase. Grep the codebase to confirm AWS/GCP KMS integration is actually wired up. If only partially implemented, README describes it as "roadmap" not "supported". No overstatement.
- **D-20:** `SECURITY.md` uses GitHub private vulnerability reporting as the disclosure channel (not email). Responsible disclosure policy must state: scope, SLA expectations, acknowledgment policy, and that embargo is requested until a fix ships.

### Configuration Reference (Granular)
The config reference must document every org-level and platform-level knob, including:
- **D-21a:** Deployment: `ALEA_DEPLOYMENT_MODE` (single_tenant / multi_tenant), `ALEA_PERSISTENCE_MODE` (persistent / ephemeral / cms_integrated), `ALEA_TENANT_SIGNUP_MODE`, `ALEA_AUTO_ADMIN_EMAIL`.
- **D-21b:** Database: `ALEA_DATABASE_BACKEND` (postgresql / sqlite), host/port/name/user/password, `ALEA_SQLITE_PATH`.
- **D-21c:** Encryption: `ALEA_MASTER_KEY_PATH`, `ALEA_KMS_PROVIDER`, `ALEA_KMS_KEY_ID`.
- **D-21d:** Auth: `ALEA_SECRET_KEY`, JWT lifetimes, OAuth client IDs/secrets, session secret.
- **D-21e:** Intake: upload dir, max file size, max page count, max recording duration, default session mode, fact visibility.
- **D-21f:** ASR: default provider, Whisper endpoint, audio storage policy.
- **D-21g:** LLM (per-org, not env-var): provider (openai / anthropic / google / vllm), model, encrypted API key, data policy (cloud_optout / cloud_baa / local_only).
- **D-21h:** FOLIO: OWL branch, update interval, cache dir, confidence threshold.
- **D-21i:** Observability: OTEL endpoint, service name, log level/format.
- **D-21j:** Rate limiting: default rate, storage backend, key header.
- **D-21k:** Security headers: CSP script-src, HSTS max-age, max request size.
- **D-21l:** CMS: enabled flag, sync interval, per-adapter credentials.
- **D-21m:** Research: CourtListener base URL, timeouts, max results.
- **D-21n:** Kiosk: audit enabled, consent required, session TTL hours.
- **D-21o:** Analysis / autonomy / output: org-level JSON config blobs.

### Scenario Walkthroughs (Configuration)
Document at minimum these end-to-end configuration walkthroughs:
- **D-22a:** Legal aid kiosk (ephemeral mode, kiosk consent required, vLLM local-only, multi-language enabled, DV protocol active).
- **D-22b:** Court SRL portal (single-tenant, persistent mode, all 7 languages, accessibility-first configuration, no LLM API keys — vLLM local).
- **D-22c:** Multi-tenant cloud deployment (multi-tenant mode, PostgreSQL + pgvector, Cloud KMS, rate limiting, OTEL observability, CMS integration).
- **D-22d:** Small legal aid office (single-tenant Docker Compose, SQLite, Clio CMS sync, admin OAuth, persistent mode).
- **D-22e:** Domestic violence shelter (ephemeral mode, kiosk consent required, DV default protocol, audio storage policy = never, local vLLM, no cloud providers).

### Visual Assets
All four visual asset types will be produced in Phase 12:
- **D-23a:** Architecture diagram — Mermaid diagram (renders in GitHub) showing intake → FOLIO resolution → analysis loop → research → output pipeline and component boundaries.
- **D-23b:** UI screenshots — captured via MCP chrome-devtools after bringing up dev servers. At minimum: landing / login, chat interface, dashboard, admin configuration page, visualization views. Screenshots live in `docs/images/` and are referenced from the README.
- **D-23c:** Deployment topology diagrams — Mermaid diagrams for (1) single-tenant Docker Compose (SQLite), (2) multi-tenant PostgreSQL, (3) kiosk deployment, (4) Kubernetes multi-tenant with Helm.
- **D-23d:** Data flow / security model diagram — Mermaid diagram showing how PII flows through encryption, audit, consent, and tenant-isolation layers, including where DEKs are unwrapped and where audit events are written.

### .planning/ Directory
- **D-24:** Ship `.planning/` **as-is** in the public repo. Full transparency — implementing organizations can see exactly how the project was built, what decisions were made and why, and what the development process looked like. This is a deliberate choice: treat the GSD planning history as a public asset that models rigorous open-source development.
- **D-24a:** Before public release, run a sanity pass on `.planning/` for any accidentally-committed secrets or internal-only references (covered by pre-flight audits).

### Contributing
- **D-25:** Open PRs welcome, no CLA. MIT license already grants the needed permissions.
- **D-26:** `CONTRIBUTING.md` covers: how to report bugs, how to propose features, how to run tests, PR review expectations, commit message conventions, branch naming, and where to discuss design changes (Issues vs Discussions).
- **D-27:** `CODE_OF_CONDUCT.md` uses the Contributor Covenant 2.1 verbatim (standard, no modifications).

### Pre-Flight Release Audits (All Four Required)
- **D-28a:** **Secret scan:** Run `gitleaks detect` (or `trufflehog git`) over the **full git history**. Any findings must be remediated (via BFG Repo-Cleaner or `git filter-repo`) before the repo goes public. Zero secrets tolerance.
- **D-28b:** **Dependency license audit:** Enumerate every direct and transitive dependency in `backend/pyproject.toml` / `backend/requirements*.txt` / `frontend/package.json` / `pnpm-lock.yaml`. Verify each is compatible with MIT release (allow: MIT, BSD-2, BSD-3, Apache-2.0, ISC, MPL-2.0; flag: LGPL, GPL, AGPL for review). Produce a `THIRD_PARTY_LICENSES.md` attribution file.
- **D-28c:** **PII / internal-reference scrub:** Grep for (i) real email addresses that aren't public, (ii) internal Slack/Notion/Jira URLs, (iii) references to unreleased ALEA projects, (iv) test fixtures with real PII, (v) hardcoded tokens or staging URLs.
- **D-28d:** **Infrastructure security linting:** `hadolint` on all Dockerfiles, `checkov` (or `kubesec`) on Helm charts, basic review of `docker-compose*.yml` and `railway.toml`. Remediate findings above "low" severity.

### Claude's Discretion
- Exact README table of contents structure and section ordering.
- Mermaid diagram content (as long as it accurately reflects the codebase).
- Specific screenshot selection (Claude picks the best representative views).
- Exact wording of use-case sub-sections (as long as tone is plain-language first, factually accurate).
- Choice of Mermaid vs ASCII vs external SVG for diagrams (Mermaid preferred — renders natively in GitHub).
- Whether THIRD_PARTY_LICENSES.md is generated by tool (e.g., `pip-licenses`, `license-checker`) or hand-curated.
- Order of task execution within the phase.

</decisions>

<canonical_refs>
## Canonical References

**Downstream agents MUST read these before planning or implementing.**

### Authoritative Inputs (Upstream)
- `.planning/phases/01-foundation-security/01-CONTEXT.md` — Encryption, audit, consent, tenant isolation, right-to-delete
- `.planning/phases/05-pre-research-exploration-safety/05-CONTEXT.md` — DV default protocol and safety screening
- `.planning/phases/06-legal-research-verification/06-CONTEXT.md` — Pluggable research (CourtListener, MCP)
- `.planning/phases/07-output-export/07-CONTEXT.md` — Output generation, triage, export formats
- `.planning/phases/08-frontend-application/08-CONTEXT.md` — Chat UI, admin config, 7-language i18n
- `.planning/phases/10-autonomy-orchestration-modes/10-CONTEXT.md` — Three autonomy modes (chatbot / professional / agent)
- `.planning/phases/11-integration-production-deployment/11-CONTEXT.md` — CMS connectors, deployment, KMS, MIT license decision (D-12)

### Live Code (Authoritative State)
- `LICENSE` — current copyright to be updated
- `.env.example` — env var reference
- `backend/app/config.py` — platform settings (source of truth for env vars)
- `backend/app/models/organization.py` — org-level config model (source of truth for org knobs)
- `backend/app/core/encryption.py` — encryption implementation
- `backend/app/models/audit.py` — audit log implementation
- `backend/app/models/consent.py` — consent records
- `backend/app/services/deletion_service.py` — right-to-delete
- `backend/app/middleware/tenant.py` — tenant isolation
- `backend/app/services/llm_service.py` — LLM providers + data policy enforcement
- `backend/app/integrations/cms/` — Clio, MyCase, LegalServer adapters
- `frontend/public/locales/` — 7 languages
- `docker-compose.yml`, `docker-compose.multi.yml`, `docker-compose.dev.yml` — deployment shapes
- `helm/alea-intake/` — Kubernetes Helm chart
- `railway.toml` — Railway deployment
- `Dockerfile` — multi-stage build
- `entrypoint.sh` — container startup

### External Standards (Referenced but not embedded)
- Contributor Covenant 2.1 — used verbatim in CODE_OF_CONDUCT.md
- SPDX license identifiers — used in THIRD_PARTY_LICENSES.md
- Mermaid syntax — used for all diagrams (GitHub-native rendering)

</canonical_refs>

<goal_backward>
## Goal-Backward Verification

**Phase 12 goal:** The `alea-intake` repository is ready to go public — licensed correctly, documented comprehensively for legal aid / court program audiences, cleared of secrets and license contamination, with visuals that make the project approachable.

**Verification questions (each must be answerable YES before phase is complete):**

1. Does `LICENSE` say `Copyright (c) 2026 Damien Riehl and ALEA Institute`? ✅ directly observable
2. Does `README.md` exist at the repo root, with a clickable table of contents and all twelve use cases documented? ✅ directly observable
3. Can a legal aid program leader, reading the README without technical help, understand what this is, how it protects their clients, and whether they can deploy it? ✅ readability audit via skimming with fresh eyes
4. Does the README security section document every feature listed in D-18, with no overstatement of Cloud KMS status? ✅ side-by-side with codebase grep
5. Does the configuration reference enumerate every `ALEA_*` env var and every org-level config field that exists in the codebase? ✅ diff against `config.py` + `organization.py`
6. Does the README include a visible Mermaid architecture diagram, UI screenshots, deployment topology diagrams, and a data-flow/security model diagram? ✅ directly observable
7. Does `SECURITY.md` exist with a GitHub-private-vulnerability-reporting disclosure policy? ✅ directly observable
8. Does `CONTRIBUTING.md` exist? Does `CODE_OF_CONDUCT.md` exist with the Contributor Covenant 2.1 text? ✅ directly observable
9. Has `gitleaks` (or equivalent) scanned the full git history with **zero findings**? ✅ scan output attached to phase summary
10. Has every runtime dependency been license-audited, and does `THIRD_PARTY_LICENSES.md` exist with SPDX identifiers? ✅ directly observable
11. Has a PII / internal-reference scrub run with all findings remediated? ✅ audit log in phase summary
12. Have `hadolint` and `checkov` (or equivalent) run on Dockerfile and Helm with all above-low-severity findings remediated? ✅ scan output attached
13. Does the README Roadmap section accurately reflect current state (no over-promises)? ✅ reviewer pass

</goal_backward>

<out_of_scope>
## Explicitly Out of Scope

- Code refactoring, bug fixes, new features (use a separate phase if needed).
- New CMS connectors, research adapters, or LLM providers.
- Rebranding, logo design, marketing site.
- Hosted demo deployment (referenced only if one exists; not created in this phase).
- Product changes triggered by anything noticed during documentation (capture as backlog / new phase).
- Translation of the README itself into non-English languages (the *product* is multi-language; the README remains English for v1 public release — backlog item).
- Moving `.planning/` out of the repo (explicitly decided against — D-24).
- Rewriting the LICENSE text body (only the copyright line changes — D-02).

</out_of_scope>
</content>
</invoke>