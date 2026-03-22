# Feature Research

**Domain:** Legal intake, issue-spotting, and structured legal analysis
**Researched:** 2026-03-22
**Confidence:** HIGH (core features well-documented across competitor landscape, differentiators verified against PROJECT.md requirements and ecosystem gaps)

## Feature Landscape

### Table Stakes (Users Expect These)

Features users assume exist. Missing these = product feels incomplete.

| Feature | Why Expected | Complexity | Notes |
|---------|--------------|------------|-------|
| Text-based narrative capture | Every intake system starts with capturing the client's story; Clio Grow, Lawmatics, LawDroid, and every legal aid platform support web forms or chat input | LOW | Conversational chat interface preferred over static forms; conditional logic is baseline |
| Intake form customization | Organizations need different fields, conditional logic, and workflows; Clio Grow and Lawmatics both offer this as core; legal aid orgs require eligibility-specific fields | MEDIUM | Must support per-org field configuration, conditional branching, and custom validation rules |
| Voice/audio input with transcription | 74% of legal aid orgs now use AI; voice is essential for access-to-justice (literacy barriers, disabilities, mobile-first users); Dragon Legal, Whisper, and Deepgram are mainstream | MEDIUM | Pluggable ASR architecture (local Whisper for privacy, cloud Deepgram/AssemblyAI for accuracy); must handle legal terminology |
| Document upload and extraction | Clients arrive with leases, court papers, contracts, medical records; every CMS and intake tool supports document attachment; CaseMap+ AI and folio-enrich handle extraction | MEDIUM | PDF, DOCX, image (OCR) support minimum; structured extraction via folio-enrich service; metadata preservation |
| Basic issue identification | CoCounsel, Paxton AI, and Harvey all do issue spotting; consumers and attorneys expect the system to identify what legal issues exist in a narrative | HIGH | LLM-powered with FOLIO ontology grounding; this is the entry point to the entire analysis pipeline |
| Structured output / case summary | Stanford's legal aid AI prototype produces structured text reports with client info, issue summary, and urgent flags; CaseMap+ generates fact summaries; every platform produces exportable summaries | MEDIUM | Multiple output formats: structured memo, triage routing sheet, action items; format configurable per deployment type |
| User authentication and access control | Any system handling privileged legal data needs role-based access; Clio, LegalServer, and all CMS platforms enforce this | MEDIUM | Role-based: admin, attorney, paralegal, consumer; per-org configuration; OAuth2/OIDC |
| Encryption and data security | Attorney-client privilege makes encryption non-negotiable; field-level PII encryption, TLS, encryption at rest are industry baseline per ABA guidelines | MEDIUM | At-rest and in-transit encryption, field-level PII encryption, audit logging, consent flows, no LLM training on case data |
| Audit trail and logging | Required by legal ethics rules and malpractice insurance; every legal CMS tracks who accessed what and when; agentic AI governance demands detailed logging | LOW | Immutable audit log of all actions, AI decisions, human overrides, and data access |
| Consent management | Legal ethics and privacy regulations (GDPR, state privacy laws) require explicit consent for data collection, AI processing, and data sharing | LOW | Consent capture at intake start, granular consent for AI processing, right-to-delete support |
| Mobile-responsive interface | Clio, Lawmatics, and all modern legal tools are mobile-first; consumers initiate intake from phones; Stanford's prototype targets web chat on mobile | LOW | Responsive design; touch-friendly; voice input especially important on mobile |
| Multi-language support | LawDroid targets Spanish; Stanford's prototype included multilingual capabilities; access-to-justice demands language accessibility | HIGH | Start with English + Spanish; architecture must support additional languages; affects prompts, UI, and ASR configuration |
| CMS integration (basic export) | Lawmatics syncs to Clio, MyCase, Filevine; LegalServer has API; legal aid orgs require LegalServer integration; law firms require Clio integration | MEDIUM | API-based export to Clio, MyCase, LegalServer at minimum; structured data mapping to CMS fields |

### Differentiators (Competitive Advantage)

Features that set the product apart. Not required by the market, but these are the reasons someone would choose ALEA Intake over Clio Grow, Lawmatics, or a custom chatbot.

| Feature | Value Proposition | Complexity | Notes |
|---------|-------------------|------------|-------|
| FOLIO ontology-grounded issue spotting | No competitor uses a structured legal ontology for issue identification. CoCounsel and Harvey rely purely on LLM reasoning. FOLIO provides 18,300+ standardized concepts across 22 branches, enabling systematic rather than probabilistic identification. Issues are identified by IRI, not free text. | HIGH | Core differentiator. Combines folio-python library queries, folio-mcp tool-use, and LLM semantic matching. Reduces hallucination risk by grounding in known concepts. |
| Pre-research exploration/triage phase | No competitor has a distinct exploration phase between issue identification and research. Current tools either skip triage (law firm tools) or do simple eligibility screening (legal aid tools). This system explores adjacent issues the consumer doesn't know to mention (e.g., DV in custody cases, wage theft in wrongful termination). | HIGH | Three-layer approach: FOLIO ontology relationships, curated screening protocols, LLM reasoning. Each layer catches what others miss. |
| Configurable mandatory safety screening | Haven AI does DV screening but as a standalone product, not integrated into a broader analysis pipeline. Stanford's prototype handles housing only. No tool combines safety screening with deep legal analysis in a configurable, per-org way. | MEDIUM | Organizations define which protocols are mandatory (e.g., DV screening always runs for family law). Protocols trigger expedited routing and priority flags. |
| Shared screening protocol library | No equivalent exists. Individual legal aid orgs develop their own protocols in isolation. An open community library (like FOLIO itself) enables knowledge sharing while allowing private org-specific protocols. | MEDIUM | Open community-contributed protocols + private org-specific protocols. Version-controlled. Importable/exportable. |
| Iterative analysis loop with multi-signal termination | Current tools do single-pass analysis. CoCounsel researches what you ask it to research. No tool iteratively identifies gaps, questions the consumer, and loops until diminishing returns using weighted multi-signal termination (coverage %, confidence plateau, iteration count, user fatigue, diminishing gaps). | HIGH | The loop (issue-spot -> research -> fact-map -> gap-analyze -> question -> loop) is the analytical engine. Multi-signal termination prevents both premature stopping and infinite loops. |
| Parallel multi-jurisdictional analysis | Regology and Bloomberg Law do multi-jurisdictional compliance research, but not at intake/analysis time. No intake tool simultaneously analyzes claims across jurisdictions in parallel. Most tools are single-jurisdiction by design. | HIGH | Consumer situations routinely span jurisdictions (state + federal, multiple states). Sequential analysis would be unacceptably slow. Requires parallel research orchestration. |
| Three fact-mapping views | CaseMap+ offers timeline and tabular views. Casefleet offers issue-tagged chronologies. No tool offers three complementary views: graph (exploration), matrix (completeness checking), and narrative-anchored (consumer understanding). | HIGH | Graph view shows relationships between facts, claims, and evidence. Matrix view shows coverage (fact x element). Narrative view anchors analysis back to the consumer's original story for comprehension. |
| Configurable autonomy levels | Haven AI and Stanford's prototype operate at fixed autonomy levels. No intake tool offers configurable autonomy per organization: chatbot (fully autonomous for consumer self-service), professional (human-guided for law firms), agent (AI with checkpoints for corporate legal). | MEDIUM | Maps directly to deployment context. Legal aid consumer-facing needs chatbot mode. BigLaw needs professional mode. In-house counsel needs agent mode. Autonomy level affects which actions require human approval. |
| Pluggable legal research tools via MCP + HTTP | No intake tool has a research tool registry. CoCounsel is locked to Thomson Reuters sources. Harvey uses its own data. This system integrates open (CourtListener, Google Scholar) and commercial (Westlaw, Clio Library, Midpage, Descrybe) research APIs via a pluggable adapter pattern and MCP tool registry. | HIGH | Organizations configure which tools they have access to. MCP enables LLM agent tool-use during analysis. HTTP adapters handle REST APIs. New tools added without code changes. |
| Ground truth verification | No competitor explicitly verifies LLM suggestions against known databases before presentation. This prevents hallucinated statutes, invented case law, and fabricated legal concepts from reaching users. | MEDIUM | LLM suggests -> system verifies against FOLIO ontology, legal databases, and configured research tools -> only verified information presented. Critical for legal reliability. |
| Configurable persistence modes | Most tools assume persistent storage. Legal aid may need ephemeral (privacy-first) processing where data is deleted after session. Law firms need persistent case tracking. Corporate legal needs CMS integration. No tool offers all three. | MEDIUM | Ephemeral (process and delete), persistent (full case tracking), CMS-integrated (sync to external system). Per-org configuration. |
| Admin-configurable knowledge base with RAG | CoCounsel has fixed training data. Most tools don't allow orgs to add their own legal knowledge. Admin-configurable RAG over curated legal documents means organizations can add their own practice guides, internal memos, and jurisdiction-specific resources. | MEDIUM | Default RAG over curated documents + org-uploadable custom knowledge base. Separate from research tools (which query external sources). |

### Anti-Features (Commonly Requested, Often Problematic)

Features that seem good but create problems. Explicitly NOT building these.

| Feature | Why Requested | Why Problematic | Alternative |
|---------|---------------|-----------------|-------------|
| Legal advice generation | Users want "tell me what to do"; seems like the natural endpoint of analysis | Unauthorized practice of law (UPL) liability; no system can replace attorney judgment; ABA Model Rules prohibit non-lawyer legal advice; LawDroid and every access-to-justice tool explicitly disclaims this | Provide structured legal information, issue identification, and fact-to-claim mapping that an attorney (or informed consumer) uses to make decisions. Clear disclaimers. |
| Autonomous case filing | "If you know the issues, just file the papers" | Procedural errors have severe consequences (missed deadlines, wrong venue, defective service); malpractice liability; varies wildly by jurisdiction and court | Generate draft documents and checklists; integrate with A2J Author or court e-filing systems for guided self-filing; never auto-file without explicit human confirmation |
| Real-time collaborative editing | Multiple attorneys editing the same analysis simultaneously | Adds massive complexity (CRDT/OT) with minimal value at intake stage; intake is typically single-user or sequential review; premature optimization | Sequential review workflow: AI generates -> reviewer edits -> approved version saved. Commenting/annotation on completed analyses. |
| Built-in video conferencing | "Clients should be able to video call from the intake tool" | Commoditized (Zoom, Teams, Google Meet); adds enormous complexity; security/compliance burden; licensing costs | Integrate with existing video platforms; provide meeting links in intake workflow; support transcript import from video calls |
| Predictive case outcome analysis | "Tell me my chances of winning" | Unreliable (insufficient data, jurisdiction variance, judge variance); creates false confidence; potential ethical issues; no competitor does this well | Focus on completeness analysis: "Here are the elements you need to prove, here is what you have, here are the gaps." Let attorneys assess strength. |
| Social media / public records scraping | "Automatically find information about the opposing party" | Privacy law violations (CCPA, GDPR); ethical concerns; data quality issues; scope creep from intake into investigation | Accept user-provided documents and information. Research tools query legal databases (case law, statutes), not personal data. |
| Payment processing / billing | Law firm intake tools often include retainer collection | Out of scope -- CMS systems handle billing; adding payment creates PCI compliance burden; dilutes focus from legal analysis | Integrate with CMS billing (Clio, MyCase) via API; intake captures engagement terms, CMS handles payment |
| Marketing automation / lead scoring | Clio Grow and Lawmatics are heavily marketing-focused (email campaigns, lead scoring, conversion tracking) | Not aligned with access-to-justice mission; legal aid orgs don't "market" to clients; adds CRM complexity that dilutes the analytical focus | Support referral source tracking for reporting purposes only. No lead scoring, no marketing campaigns, no conversion funnels. |
| Replacing case management systems | "Build a full CMS inside the intake tool" | CMS is a massive domain (Clio alone has 400+ API endpoints); organizations already have CMS investments; scope explosion | Integrate with existing CMS platforms. Export structured data. Sync case information. Never store what the CMS should store. |
| Urgency-gated research depth | "Only research urgent issues deeply; skip non-urgent ones" | Urgency affects routing and presentation, not thoroughness. A "non-urgent" issue today may become critical. Incomplete analysis creates liability. | Research all identified issues equally. Use urgency for output prioritization and routing, not for gating analysis depth. |

## Feature Dependencies

```
[Text Narrative Capture]
    |
    v
[Basic Issue Identification] --requires--> [FOLIO Ontology Integration]
    |                                           |
    v                                           v
[Pre-Research Exploration Phase] --requires--> [FOLIO Relationship Navigation]
    |                                    |
    |                                    v
    |                           [Screening Protocol Library]
    |                                    |
    v                                    v
[Safety Screening Protocols] --requires--> [Screening Protocol Library]
    |
    v
[Iterative Analysis Loop]
    |--requires--> [Pluggable Research Tools]
    |--requires--> [Fact-to-Claim Mapping (any view)]
    |--requires--> [Gap Analysis Engine]
    |--requires--> [Follow-up Question Generation]
    |
    v
[Multi-Jurisdictional Analysis] --requires--> [Pluggable Research Tools]
    |                                          |
    v                                          v
[Three Fact-Mapping Views]              [Ground Truth Verification]
    |--Graph View                              |
    |--Matrix View (requires element mapping)  |
    |--Narrative-Anchored View                 v
    |                                   [Structured Output]
    v                                          |
[Structured Output / Case Summary]             v
    |                                   [CMS Integration]
    v
[CMS Integration] --requires--> [Structured Output]

[Configurable Autonomy] --enhances--> [Iterative Analysis Loop]
                        --enhances--> [Safety Screening Protocols]
                        --enhances--> [Follow-up Question Generation]

[Voice Input] --enhances--> [Text Narrative Capture]
[Document Upload] --enhances--> [Text Narrative Capture]

[Admin Knowledge Base + RAG] --enhances--> [Pluggable Research Tools]

[Configurable Persistence] --independent-- (architectural decision, not feature dependency)

[Multi-Language Support] --enhances--> [Text Narrative Capture]
                         --enhances--> [Follow-up Question Generation]
                         --enhances--> [Structured Output]

[Encryption / Security] --independent-- (cross-cutting concern, all features depend on it)
[Audit Trail] --independent-- (cross-cutting concern, all features depend on it)
[Consent Management] --independent-- (cross-cutting concern, must be first in flow)
```

### Dependency Notes

- **Issue Identification requires FOLIO Integration:** The system identifies issues by mapping narratives to FOLIO concepts (IRIs), not free-text labels. Without FOLIO, issue identification degrades to generic LLM guessing.
- **Pre-Research Exploration requires FOLIO Relationship Navigation:** The exploration phase traverses FOLIO ontology edges (e.g., child custody -> domestic violence -> protective orders). Without FOLIO's structured relationships, adjacent issue discovery relies solely on LLM reasoning.
- **Iterative Analysis Loop requires Research Tools + Fact Mapping + Gap Analysis:** The loop cannot function without the ability to research claims (pluggable tools), map facts to elements (fact mapping), identify missing evidence (gap analysis), and generate questions (follow-up questioning).
- **Multi-Jurisdictional Analysis requires Pluggable Research Tools:** Parallel jurisdiction research needs tools that can query jurisdiction-specific sources concurrently.
- **Three Fact-Mapping Views are parallel implementations:** Graph, matrix, and narrative views can be built incrementally. Matrix view requires element-level mapping. Graph view requires relationship data. Narrative view requires original transcript anchoring.
- **Configurable Autonomy enhances (does not block) the analysis loop:** The loop works at any autonomy level; autonomy configuration determines which steps require human confirmation.
- **Security, audit, and consent are cross-cutting:** These must be designed into the architecture from day one, not bolted on later. Every feature depends on them.

## MVP Definition

### Launch With (v1)

Minimum viable product -- what's needed to validate the core value proposition: "transforms unstructured consumer narratives into structured legal analysis."

- [ ] **Text narrative capture** -- conversational chat interface with conditional logic; the entry point for everything
- [ ] **FOLIO ontology integration** -- folio-python library for concept lookup, taxonomy navigation, semantic matching; canonical IRIs for all legal concepts
- [ ] **Basic issue identification** -- LLM-powered issue spotting grounded in FOLIO concepts; the core analytical capability
- [ ] **Pre-research exploration (single layer)** -- FOLIO ontology relationship traversal for adjacent issue discovery; start with ontology edges before adding protocols and LLM reasoning
- [ ] **Safety screening (hardcoded protocols)** -- DV screening for family law as proof of concept; hardcoded before building protocol library
- [ ] **Single research tool integration** -- One pluggable research tool (CourtListener or Google Scholar as open/free option) to validate the adapter pattern
- [ ] **Basic fact-to-claim mapping** -- Matrix view (fact x element) as the simplest completeness-checking view
- [ ] **Gap analysis and follow-up questioning** -- Identify missing elements and generate questions; single iteration (no loop yet)
- [ ] **Structured output** -- Case memo format with identified issues, mapped facts, gaps, and next steps
- [ ] **Single-jurisdiction analysis** -- One jurisdiction at a time; parallel comes later
- [ ] **Basic authentication and authorization** -- Role-based access (admin, attorney, consumer)
- [ ] **Encryption and audit logging** -- Foundational security from day one
- [ ] **Consent capture** -- Basic consent flow before AI processing begins
- [ ] **Professional autonomy mode** -- Human-guided mode only for v1; attorney reviews every AI decision

### Add After Validation (v1.x)

Features to add once the core analysis pipeline is proven.

- [ ] **Iterative analysis loop** -- Full loop with multi-signal termination; add after validating single-pass analysis quality
- [ ] **Screening protocol library** -- Community-contributed + private protocols; add after DV screening proves the pattern
- [ ] **Three-layer exploration** -- Add curated protocols and LLM reasoning layers to FOLIO ontology traversal
- [ ] **Voice input with transcription** -- Pluggable ASR (Whisper local, Deepgram cloud); critical for access-to-justice but not for initial validation
- [ ] **Document upload and extraction** -- PDF/DOCX upload with text extraction; integrates with folio-enrich for annotation
- [ ] **Graph fact-mapping view** -- Visual exploration of relationships between facts, claims, and evidence
- [ ] **Narrative-anchored fact-mapping view** -- Map analysis back to original consumer narrative for comprehension
- [ ] **Parallel multi-jurisdictional analysis** -- Concurrent research across jurisdictions; add after single-jurisdiction research is reliable
- [ ] **Configurable autonomy** -- Chatbot and agent modes in addition to professional mode
- [ ] **Additional research tool integrations** -- Westlaw, Clio Library, Midpage, Descrybe adapters
- [ ] **Ground truth verification** -- Verify LLM suggestions against databases before presentation
- [ ] **CMS integration** -- Clio, MyCase, LegalServer sync connectors
- [ ] **Multi-language support** -- Spanish first, then extensible

### Future Consideration (v2+)

Features to defer until product-market fit is established.

- [ ] **Admin-configurable knowledge base + RAG** -- Organization-uploaded custom legal documents for RAG; requires content management UI and vector store management
- [ ] **Configurable persistence modes** -- Ephemeral vs persistent vs CMS-integrated; requires significant architectural flexibility
- [ ] **Hybrid deployment (cloud + self-hosted)** -- Multi-tenant cloud and single-tenant self-hosted; defer until demand is validated
- [ ] **Configurable database backend** -- PostgreSQL+pgvector and SQLite+FAISS abstraction; build on PostgreSQL first, abstract later
- [ ] **Configurable exploration depth** -- 1 round to "until stable"; requires tuning based on real usage data
- [ ] **Configurable transparency for exploration questions** -- Explain rationale vs. conversational; UX decision that needs user research
- [ ] **Full protocol library governance** -- Versioning, review workflows, quality scoring for community protocols

## Feature Prioritization Matrix

| Feature | User Value | Implementation Cost | Priority |
|---------|------------|---------------------|----------|
| Text narrative capture | HIGH | LOW | P1 |
| FOLIO ontology integration | HIGH | MEDIUM | P1 |
| Basic issue identification | HIGH | HIGH | P1 |
| Pre-research exploration (FOLIO layer) | HIGH | MEDIUM | P1 |
| Safety screening (hardcoded) | HIGH | LOW | P1 |
| Single research tool integration | HIGH | MEDIUM | P1 |
| Basic fact-to-claim mapping (matrix) | HIGH | MEDIUM | P1 |
| Gap analysis + follow-up questioning | HIGH | MEDIUM | P1 |
| Structured output | HIGH | LOW | P1 |
| Authentication + authorization | HIGH | MEDIUM | P1 |
| Encryption + audit logging | HIGH | MEDIUM | P1 |
| Consent management | HIGH | LOW | P1 |
| Iterative analysis loop | HIGH | HIGH | P2 |
| Screening protocol library | HIGH | MEDIUM | P2 |
| Voice input + transcription | HIGH | MEDIUM | P2 |
| Document upload + extraction | MEDIUM | MEDIUM | P2 |
| Graph fact-mapping view | MEDIUM | HIGH | P2 |
| Narrative-anchored view | MEDIUM | MEDIUM | P2 |
| Multi-jurisdictional analysis | HIGH | HIGH | P2 |
| Configurable autonomy | HIGH | MEDIUM | P2 |
| Additional research tools | MEDIUM | MEDIUM | P2 |
| Ground truth verification | HIGH | MEDIUM | P2 |
| CMS integration | MEDIUM | MEDIUM | P2 |
| Multi-language support | HIGH | HIGH | P2 |
| Admin knowledge base + RAG | MEDIUM | HIGH | P3 |
| Configurable persistence | LOW | HIGH | P3 |
| Hybrid deployment | MEDIUM | HIGH | P3 |
| Configurable DB backend | LOW | HIGH | P3 |

**Priority key:**
- P1: Must have for launch -- validates the core value proposition
- P2: Should have, add when possible -- completes the vision
- P3: Nice to have, future consideration -- deployment flexibility

## Competitor Feature Analysis

| Feature | Clio Grow / Lawmatics | CoCounsel (Thomson Reuters) | LawDroid LawAnswers AI | Haven AI | Stanford Legal Aid Prototype | ALEA Intake |
|---------|----------------------|----------------------------|----------------------|----------|------------------------------|-------------|
| **Narrative capture** | Web forms with conditional logic | Chat interface | Conversational AI chat | Phone-based AI | Web chat prototype | Conversational chat + voice + documents |
| **Issue identification** | None (lead qualification only) | LLM-based, no ontology | General legal info, no issue spotting | Eligibility screening only | Housing issues only | FOLIO ontology-grounded, systematic |
| **Adjacent issue discovery** | None | None | None | DV detection during calls | None | Three-layer exploration (FOLIO + protocols + LLM) |
| **Safety screening** | None | None | None | DV screening (standalone) | None | Configurable mandatory protocols per org |
| **Legal research** | None | Locked to TR sources | None | None | None | Pluggable (open + commercial via MCP + HTTP) |
| **Fact-to-claim mapping** | None | Basic analysis | None | None | None | Three views (graph, matrix, narrative) |
| **Iterative analysis** | None | Single-pass | None | None | None | Multi-pass loop with multi-signal termination |
| **Multi-jurisdictional** | None | Manual per-jurisdiction | None | None | None | Parallel automated analysis |
| **Autonomy configuration** | N/A (professional only) | N/A (professional only) | Consumer only | Consumer-facing with staff review | Fixed (AI + human review) | Configurable per org (chatbot / professional / agent) |
| **CMS integration** | Deep (Clio ecosystem) | TR ecosystem | None | LegalServer | None (prototype) | Pluggable (Clio, MyCase, LegalServer) |
| **Ontology/taxonomy** | None | None | None | None | None | FOLIO (18,300+ concepts, 22 branches) |
| **Target users** | Law firm marketing/intake staff | Licensed attorneys | Self-help consumers | Legal aid intake staff | Legal aid intake staff | All: law firms, legal aid, courts, consumers, corporate |
| **Open source** | No | No | No | No | Research prototype | Open architecture, open protocol library |

### Competitive Positioning

ALEA Intake occupies a unique position in the market:

1. **Law firm intake tools** (Clio Grow, Lawmatics) focus on lead management and marketing automation. They don't do legal analysis at all. ALEA Intake is not competing with them on CRM -- it picks up where they leave off.

2. **AI legal research tools** (CoCounsel, Harvey) focus on attorney-directed research. They don't do intake, issue discovery, or consumer-facing interaction. ALEA Intake bridges the gap between intake and research.

3. **Access-to-justice tools** (LawDroid, A2J Author) focus on guided self-help for specific legal issues. They don't do deep analysis, multi-issue discovery, or ontology-grounded identification. ALEA Intake provides the analytical depth these tools lack.

4. **Standalone safety tools** (Haven AI) do one thing well (DV screening) but aren't integrated into a broader analysis pipeline. ALEA Intake subsumes this capability as a configurable component.

5. **Fact management tools** (CaseMap+) focus on litigation preparation after issues are identified. ALEA Intake sits upstream -- identifying issues and mapping facts before CaseMap-style tools take over.

The unique value is the combination: ontology-grounded issue identification -> adjacent issue exploration -> pluggable research -> iterative fact-to-claim mapping -> structured output. No competitor connects these stages.

## Sources

- [Clio Grow - Client Intake Best Practices 2026](https://www.clio.com/blog/client-intake-law-firms/) -- MEDIUM confidence (marketing content)
- [Lawmatics - Legal Software](https://www.lawmatics.com) -- MEDIUM confidence
- [Stanford Justice Innovation - Legal Aid Intake & Screening AI](https://justiceinnovation.law.stanford.edu/legal-aid-intake-screening-ai/) -- HIGH confidence (academic research)
- [LawDroid LawAnswers AI Launch](https://www.lawnext.com/2025/09/lawdroid-launches-lawanswers-ai-nationwide-revolutionary-platform-tackles-americas-access-to-justice-crisis.html) -- HIGH confidence (product announcement)
- [Haven AI - DV Screening Case Study](https://www.safehavenai.org/case-study) -- HIGH confidence (product documentation)
- [CaseMap+ AI - LexisNexis](https://www.lexisnexis.com/en-us/products/casemap.page) -- HIGH confidence (product documentation)
- [FOLIO - Federated Open Legal Information Ontology](https://openlegalstandard.org/) -- HIGH confidence (primary source)
- [ABA - Access to Justice and AI](https://www.americanbar.org/groups/journal/articles/2025/access-to-justice-how-ai-powered-software-can-bridge-the-gap/) -- HIGH confidence (professional organization)
- [Multi-Jurisdictional Legal Research Challenges](https://www.regology.com/blog/understanding-the-challenges-of-multi-jurisdictional-legal-research) -- MEDIUM confidence
- [AI Agents for Multi-Jurisdictional Research](https://datagrid.com/blog/ai-agents-automate-multi-jurisdictional-legal-research) -- MEDIUM confidence
- [Agentic AI in Legal - Attorney At Work](https://www.attorneyatwork.com/what-is-agentic-ai-for-legal-and-why-should-it-matter-to-legal-professionals/) -- MEDIUM confidence
- [Autonomous AI in Law Firms - Above the Law](https://abovethelaw.com/2026/03/autonomous-ai-in-law-firms-what-could-possibly-go-wrong/) -- MEDIUM confidence
- [Best Intake Software for Lawyers 2026](https://inoriseo.com/law-firm-software/best-intake-software-for-lawyers-2026/) -- LOW confidence (SEO content)

---
*Feature research for: Legal intake, issue-spotting, and structured legal analysis*
*Researched: 2026-03-22*
