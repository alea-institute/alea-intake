---
title: alea-intake Public Showcase on openlegalstandard.org - Plan
type: feat
date: 2026-11-08
topic: public-showcase-launch
artifact_contract: ce-unified-plan/v1
product_contract_source: ce-brainstorm
execution: code
---

# alea-intake Public Showcase on openlegalstandard.org - Plan

## Goal Capsule

- **Objective:** A visitor who opens the intake showcase from `openlegalstandard.org/intake` can describe a legal situation, or pick a curated example, and get an analysis that finds every relevant legal issue, links claims and elements to their facts, maps them to FOLIO concepts, and computes cited deadlines for their state. The analysis must be good enough to put in public under FOLIO's name.
- **Product authority:** Damien Riehl (ALEA Institute). The audience and the launch quality bar were chosen in dialogue on 2026-11-08. The legal-aid professional and public self-help audiences are later milestones and are not active scope.
- **Open blockers:** None. Hosting uses only access ALEA already has (see Key Decisions). Server capacity is a risk that planning must measure (see Dependencies).

---

## Product Contract

### Summary

Launch alea-intake as a public, no-login FOLIO showcase. A landing page at `openlegalstandard.org/intake` introduces it, and the app runs at `intake.dev.openlegalstandard.org`. Visitors bring their own LLM key, and nothing they enter is kept. The site goes public only after all 8 persona tests pass every gate in the locked rubric, and only with correct, primary-source-cited deadlines or a plain "no verified rule" label for each state.

### Problem Frame

openlegalstandard.org is FOLIO's public home, and `mapper.` and `enrich.openlegalstandard.org` already show FOLIO at work. Nothing there yet shows FOLIO's hardest job: turning someone's messy story into a complete map of legal issues, including the ones the person never mentioned.

alea-intake does that job, but it has no running deployment. The Railway dev server was drained on 2026-07-26 and now returns "Application not found." Its last persona campaign (`docs/evidence/persona-campaign/pack.html`, rubric `intake-quality-v1.3`, last run 2026-07-11) failed its gates. The failures came from the deadline engine (BUG-12) and from missed legal issues (GATE-01). Deadlines are computed and cited only for Minnesota plus a few generic rules.

Three decisions Damien made on 2026-07-26 were never carried out. All three change the output the persona tests measure, so they need to land before the persona tests run again.

A showcase that misses an issue or states a wrong deadline with confidence would damage FOLIO's credibility more than having no showcase at all.

### Key Decisions

- **Audience is a FOLIO showcase.** Visitors are legal technologists, legal aid organizations, and FOLIO adopters exploring what FOLIO-powered intake can do. (session-settled: user-directed — chosen over legal-aid professionals, public self-help, and showcase-then-pros: it is the lowest-risk audience and the fastest path to launch.) Governs R8, R10.
- **Hold the launch until every gate passes.** (session-settled: user-directed — chosen over "fix issues and label deadlines," "ship now and iterate live," and "curated scenarios only": Damien chose the strictest bar, "Let's get this right.") Governs R1, R2, R3, R4, R5, R6, R7.
- **Curated scenarios and free-text input both launch.** Damien named both, so neither waits for the other. Governs R13, R14.
- **Deadline coverage spans all 50 states for the covered practice areas.** Free-text visitors can be in any state, and the locked rubric judges deadlines against the client's actual state. Governs R5, R6.
- **Visitors bring their own LLM key, with no accounts and no retention.** This matches mapper and enrich and removes server-side AI cost and key-drain risk. Governs R9, R11, R15.
- **Host only on access we already have.** The app runs on the hetzner-dev box through Coolify, under the existing `*.dev.openlegalstandard.org` wildcard, and the landing page ships through the site repo's existing push-to-deploy. A path proxy at `openlegalstandard.org/intake` would need AWS Amplify console access, and a new subdomain would need Route 53 access; both belong to Mike. (session-settled: user-directed — chosen over the ALEA EC2 host and a new `intake.` record: "so we don't have to bug Mike.") Governs R19, R20.
- **The decisions already answered land first.** Calibration (q1, q2), the expansion-vocabulary calibration (q3), and the PyMuPDF replacement were decided on 2026-07-26 and change what the gates measure. Governs R16, R17, R18.

### Actors

- A1. Visitor: a legal technologist, legal aid staffer, or FOLIO adopter using the public site with their own LLM key.
- A2. Persona campaign: the 8 scripted personas plus the rubric judge. Together they set the launch gate.
- A3. Damien: product authority.

### Requirements

**Launch quality gate**

- R1. The site goes public only after all 8 personas pass every gate in `intake-quality-v1.3` and its practice-area addenda in one campaign run. The 8 personas are landlord-tenant, immigration, family-custody, wage-theft, benefits-denial, employment-discrimination, consumer-debt, and elder-exploitation.
- R2. The launch campaign runs against the production stack, with the same build and configuration that will serve the public.
- R3. Gates are judged on one reference model, and the UI recommends that same model to visitors.
- R4. The issue-completeness gates (GATE-01 and each addendum's issue-spotting gates) pass for every persona, including issues the persona never names.

**Deadlines**

- R5. Each deadline shown is computed to a specific date for the client's actual state and cited to that state's primary source: a statute, regulation, court rule, local rule, or standing order. Immigration deadlines cite federal authority instead, per the immigration addendum.
- R6. When the tool has no verified rule for a deadline in the client's state, it says so plainly and points the visitor to where to check. It never estimates, and it never applies another state's rule.
- R7. A rule counts as verified only after its citation has been checked against the primary source text. Unverified rules fall under R6.

**Showcase experience**

- R8. The site presents itself as a FOLIO demonstration and says on every page that it is not legal advice.
- R9. Visitors supply their own LLM API key. The server never uses a key of its own to serve a request.
- R10. No account or login is required, and the SSO, case-management connectors, admin, and multi-tenant surfaces stay hidden.
- R11. Nothing a visitor enters, including their story, documents, results, and key, is kept after the session ends. Application logs and error reports count.
- R12. Visitors can see the full analysis: issues, claims and elements linked to their facts, FOLIO concepts with resolvable IRIs, deadlines, the visualizations, and an exportable memo.
- R13. Visitors can start from curated example scenarios, each of which passes the gates under R1.
- R14. Visitors can describe their own situation in free text or upload a document.
- R15. When the visitor uses a model other than the reference model, the UI says that quality is verified only on the reference model.

**Prerequisite cleanup (already decided)**

- R16. The calibration operating point (`SINGLE_STAGE_PENALTY` 0.85, `confidence_threshold` 0.55) and the "floor" combine rule are adopted, per `alea-intake-2026-07-24-calibration` q1 and q2.
- R17. The expansion-vocabulary calibration runs, and any operating point it recommends goes to Damien before adoption, per q3.
- R18. PyMuPDF (AGPL) is removed from the shipped product, with no loss in PDF heading or provenance extraction, per `portfolio-2026-07-24-license-sweep` q1. The README and THIRD-PARTY files no longer list it as an open question.

**Hosting and entry point**

- R19. The app is served at `intake.dev.openlegalstandard.org` and stays unlisted and access-gated until the R1 gate passes.
- R20. A page at `openlegalstandard.org/intake` introduces the showcase, states that it is a demonstration and not legal advice, and launches the app. It appears in the site's Tools menu alongside Enrich and Mapper.

### Key Flows

- F1. Curated example
  - **Trigger:** A1 opens the site and picks an example scenario.
  - **Steps:** The visitor enters their own key, the analysis runs with progress shown, results appear in each view, and the visitor exports the memo.
  - **Covered by:** R8, R9, R12, R13
- F2. Visitor's own situation
  - **Trigger:** A1 types their own story or uploads a document.
  - **Steps:** Same as F1. Deadlines show a computed, cited date or the R6 "no verified rule" message. When the session ends, nothing is kept.
  - **Covered by:** R5, R6, R11, R14, R15
- F3. Launch gate
  - **Trigger:** R16–R18 have landed and the production stack is up.
  - **Steps:** A2 runs all 8 personas on the production stack with the reference model, and the judge scores them under v1.3. Every failure is fixed and the full campaign reruns until one run passes every gate. Then the access gate comes off and the landing page ships.
  - **Covered by:** R1, R2, R3, R4, R19, R20

### Acceptance Examples

- AE1. **Covers R5, R6.** Given a free-text visitor in a state where the eviction-answer rule is verified, the tool shows the computed answer date and cites the rule. Given the same facts in a state whose rule has not passed verification, it shows "no verified rule for your state" with a pointer to the court self-help center, and no date.
- AE2. **Covers R6.** Given a family-custody story set in Wisconsin, no Minnesota answer period appears anywhere in the output.
- AE3. **Covers R9.** Given a visitor who has not entered a key, analysis does not start, and the server makes no LLM call.
- AE4. **Covers R11.** Given a finished session, neither the database nor the application logs nor any error report holds the visitor's story text or key.
- AE5. **Covers R1.** Given a campaign where 7 personas pass and one fails a single gate, the site stays private.
- AE6. **Covers R15.** Given a visitor whose key is for a model other than the reference model, a notice says quality is verified only on the reference model, and the analysis still runs.

### Success Criteria

- One campaign run on the production stack scores every gate as passing for all 8 personas, and it is recorded as a new evidence pack revision linked from `EVIDENCE.md`.
- `https://openlegalstandard.org/intake` launches the app at `https://intake.dev.openlegalstandard.org/`, and a real browser run of F1 and F2 completes there.
- Every shown deadline in that campaign has a citation that resolves to the primary source text.

### Scope Boundaries

**Deferred for later**

- Accounts, saved intakes, and organization workspaces for legal aid professionals (the next audience milestone).
- Public self-help positioning aimed at people seeking help with their own legal problem.
- Voice input. It needs its own speech-to-text key and privacy review.
- Practice areas beyond the 8 the personas cover.
- Exposing case-management connectors (Clio, MyCase, LegalServer) and autonomy or approval modes.

**Outside this product's identity**

- Legal advice or attorney-client relationships.
- A server-paid free tier of LLM usage.

### Dependencies / Assumptions

- Hosting follows the folio-insights pattern: Coolify on hetzner-dev under `*.dev.openlegalstandard.org` (`folio-insights/docs/deploying.md`). The wildcard already resolves `intake.dev.openlegalstandard.org` to that box.
- hetzner-dev is shared and tight: on 2026-11-08 it showed 7 GB RAM with about 1 GB available and 86% disk use. If alea-intake will not fit, a larger box is spend, which needs Damien's approval.
- The landing page ships through the `openlegalstandard.org` repo, where a push to `main` triggers the Amplify deploy. Another session is building that repo's Tools showcase (`feat/folio-tools-showcase`), so the intake page coordinates with it. Damien line-edits the page copy before it ships, per that repo's copy rule.
- Primary-source verification for 50 states is agent-performed: fetch and check each citation, then run a judging pass. Damien does not review states one by one.
- The reference model is cheap enough that visitors with their own keys will accept the cost of a typical intake.

### Outstanding Questions

**Deferred to Planning**

- Which reference model gives the best gate pass rate per dollar.
- Whether the 50-state rule set is built as one pass or in waves ordered by persona states first, given that only the full campaign gates the launch.
- Whether to finish the stale `feat/s075.4-pymupdf-to-pdfplumber` branch or redo the swap on current master.
- How ephemeral persistence and log scrubbing are enforced and tested for R11.

### Sources / Research

- `docs/evidence/persona-campaign/pack.html` and `manifest.json`: the last campaign (22 pass, 3 borderline, 10 fail).
- `docs/rubrics/intake-quality-v1.3.md` and `docs/rubrics/practice-areas/`: the locked rubric and its addenda.
- `docs/plans/deadline-detection-v1.md`: the deadline engine framework and the 50-state scaling notes.
- `docs/plans/2026-07-11-round7-expansion-domain-rules.md`: the last round of quality work.
- `docs/solutions/2026-07-07-pdf-agpl-swap-and-folio-python-resolve.md`: why pdfplumber over pypdf.
- `docs/solutions/live-validation-unit-green-integration-dead.md`: passing unit tests did not prove the live system worked.
- Commit `1e3af71` (calibration study) and branch `feat/s075.4-pymupdf-to-pdfplumber` (commit `980c255`).
- BYOK pattern: folio-enrich `docs/HANDOFF-2026-06-28-byok-prod-deploy-DONE.md`.
- Hosting pattern: folio-insights `docs/deploying.md` (Coolify on hetzner-dev); `openlegalstandard.org` `docs/plans/2026-11-07-0913-feat-folio-tools-showcase-plan.md` (Amplify deploy, Tools menu).
