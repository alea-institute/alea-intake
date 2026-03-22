# Pitfalls Research

**Domain:** Legal intake and AI-assisted legal analysis
**Researched:** 2026-03-22
**Confidence:** HIGH (multiple authoritative sources including Stanford CodeX, ABA, state bar opinions, peer-reviewed research, active 2026 litigation)

## Critical Pitfalls

### Pitfall 1: LLM Hallucination of Legal Citations and Authorities

**What goes wrong:**
The LLM fabricates case citations, statute numbers, or regulatory references that look plausible but do not exist. General-purpose LLMs hallucinate legal citations 30-45% of the time (Stanford CodeX, 2025). Even specialized legal AI tools from LexisNexis and Thomson Reuters hallucinate 17-33% of the time. Over 700 court cases now involve AI-generated hallucinations. Attorneys have been sanctioned, fined, and publicly disciplined for submitting fabricated citations. In the Alea Intake context, a hallucinated citation embedded in a structured case memo could cause a legal aid attorney to file a motion based on nonexistent authority, or a consumer in a direct-to-consumer deployment to believe they have rights they do not.

**Why it happens:**
LLMs generate tokens probabilistically. A citation like "Smith v. Jones, 523 F.3d 847 (7th Cir. 2008)" is assembled from patterns of real citations -- the model has no concept of whether that specific case exists. RAG mitigates but does not eliminate the problem: the LLM can still "blend" retrieved citations with fabricated details, misattribute holdings, or invent parallel citations.

**How to avoid:**
- Never present an LLM-generated citation without verification against a known database (CourtListener, Westlaw, Lexis). The PROJECT.md already specifies "Ground truth verification: LLM suggestions verified against known databases before presentation" -- this must be a hard gate, not a soft suggestion.
- Implement a citation extraction + verification pipeline: parse all citations from LLM output, query the legal research API, and either confirm, flag as unverified, or remove. Display verification status prominently in all output views.
- Use structured generation (constrained decoding or tool-use patterns) where the LLM selects from retrieved authorities rather than generating citations from scratch.
- For the RAG knowledge base: use passage-level attribution so the LLM cites specific retrieved chunks, and verify that the cited chunk actually supports the stated proposition.

**Warning signs:**
- Citations that look syntactically correct but have no corresponding entry in any legal database.
- Holdings that seem too perfectly aligned with the user's situation (LLMs tend to generate "convenient" precedent).
- Parallel citations that don't match (e.g., the F.3d cite and the S.Ct. cite point to different cases).
- Test: run 50 sample intakes and manually verify every citation. If more than 5% are unverifiable, the verification pipeline is broken.

**Phase to address:**
Core analysis loop phase. The citation verification pipeline must be built alongside (not after) the LLM integration. Without it, every output is legally dangerous.

---

### Pitfall 2: Attorney-Client Privilege Waiver Through Cloud Architecture

**What goes wrong:**
Sending privileged client communications to third-party LLM providers, storing privileged data in shared infrastructure without adequate isolation, or failing to establish proper engagement terms can inadvertently waive attorney-client privilege. Once waived, privilege is generally gone permanently. In multi-tenant deployments, a single architectural shortcut (missing tenant_id filter, shared cache key, SSO routing error) can expose one client's privileged data to another organization's users.

**Why it happens:**
Engineers treat LLM API calls like any other API call, without recognizing that the data payload may be privileged. Cloud providers' terms of service may grant broad data usage rights. LLM providers may retain prompts for abuse monitoring (Azure OpenAI retains for 30 days by default; zero-data-retention requires Enterprise Agreement approval). Fine-tuning operations may relocate data outside selected geography. In multi-tenant systems, every database query, cache operation, background job, and LLM prompt must be scoped to a tenant -- missing even one creates a leakage path.

**How to avoid:**
- Treat every piece of consumer narrative, case analysis, and LLM prompt/response as potentially privileged. This is the default assumption, not a configuration option.
- Require contractual guarantees from LLM providers: no training on customer data, data residency controls, and ideally zero-data-retention. Azure OpenAI provides this under EA/MCA; Anthropic excludes API/enterprise deployments from training; OpenAI API has ZDR for qualifying use cases. Document these guarantees per provider in the alea-llm-client configuration.
- Implement field-level encryption for PII and privileged content at rest, not just transport encryption. Decrypt only at the point of use, never in logs or error messages.
- For multi-tenant: use database-level isolation (separate schemas or databases per tenant) rather than row-level security alone. PostgreSQL RLS has had CVEs (CVE-2024-10976, CVE-2025-8713) that leaked data across RLS boundaries. Supplement RLS with application-level tenant context enforcement.
- Implement tenant context as a request-scoped middleware that is impossible to bypass -- every database query, cache key, background job, and LLM call must include tenant isolation.
- Audit logs must record every data access with tenant context, and be immutable (append-only).
- Never log full prompts or responses in shared logging infrastructure. Use structured log fields with tenant-scoped access controls.

**Warning signs:**
- Any LLM API call that does not go through a centralized client with data-handling guarantees.
- Cache keys that don't include tenant identifiers.
- Background jobs or async workers that don't carry tenant context.
- Database queries in shared tables without tenant_id in the WHERE clause.
- Error messages or stack traces that include client narrative text.
- Test: attempt to access Tenant B's data while authenticated as Tenant A at every layer (API, database, cache, search index, LLM prompt history).

**Phase to address:**
Foundation/infrastructure phase. The data isolation architecture must be designed before any data flows through the system. Retrofitting tenant isolation is extremely expensive and error-prone.

---

### Pitfall 3: Unauthorized Practice of Law (UPL) Liability

**What goes wrong:**
The system crosses the line from "legal information tool" to "practicing law" by providing situation-specific legal advice, recommending specific legal strategies, drafting legal documents with substantive arguments, or telling consumers what claims to pursue. The Nippon Life v. OpenAI lawsuit (March 2026) -- the first major UPL case against an AI company -- alleges ChatGPT practiced law by analyzing a specific user's legal situation, questioning their attorney's conduct, recommending Federal Rule 60(b) arguments, and drafting motions. The insurer seeks $10M in punitive damages plus injunctive relief barring OpenAI from providing legal assistance in Illinois. New York Senate Bill 7263 would bar AI chatbot operators from providing "substantive" responses that would constitute UPL if provided by a human.

**Why it happens:**
The line between "legal information" and "legal advice" is blurry, jurisdiction-dependent, and actively being litigated. An LLM that analyzes a consumer's specific facts and recommends specific claims is closer to "practicing law" than one that provides general information about legal topics. The more tailored and actionable the output, the more it looks like legal advice. Consumer-facing deployments are at highest risk; professional-facing tools used by licensed attorneys are generally safer because the attorney exercises independent judgment.

**How to avoid:**
- Implement deployment-mode-aware output framing. Consumer-facing outputs must be framed as "information to discuss with an attorney" not "you should file a claim for X." Professional-facing outputs can be more direct because the attorney exercises judgment.
- Never generate ready-to-file legal documents in consumer-facing mode. Structured case memos for attorney review are fine; draft motions for pro se litigants are not.
- Include prominent, non-dismissable disclaimers that the system does not provide legal advice and is not a substitute for an attorney. But do not rely on disclaimers alone -- they are necessary but not sufficient.
- Build "attorney checkpoint" gates into consumer-facing workflows: at critical decision points (claim selection, strategy recommendation, document generation), route to a human attorney before the consumer acts.
- Track the regulatory landscape per jurisdiction. Colorado has a nonprosecution policy for legal tech; California has strict UPL enforcement; New York is considering new AI-specific UPL legislation. The system's behavior may need to vary by jurisdiction.
- The PROJECT.md already states the system "does not constitute legal advice" -- this must be enforced architecturally, not just declared.

**Warning signs:**
- Output language that uses imperative mood ("You should file...", "Your best option is...", "Pursue this claim...") in consumer-facing mode.
- The system generating documents formatted as court filings.
- Consumer users treating outputs as final legal advice without consulting an attorney.
- Any deployment where there is no licensed attorney in the loop.
- Test: review 100 consumer-facing outputs for UPL-triggering language. Any instance of situation-specific directive advice is a failure.

**Phase to address:**
Output/presentation phase, but the architectural decision (deployment modes with different output behaviors) must be made in the foundation phase. The output framing, disclaimer system, and attorney checkpoint gates should be built as core infrastructure, not afterthoughts.

---

### Pitfall 4: Bias in Issue-Spotting That Systematically Disadvantages Populations

**What goes wrong:**
The LLM's issue-spotting disproportionately identifies or fails to identify legal issues based on how the consumer describes their situation -- which correlates with race, socioeconomic status, education level, and English proficiency. A consumer who describes a workplace dispute using legal vocabulary ("hostile work environment," "constructive dismissal") gets better issue-spotting than one who says "my boss is mean and I had to quit." The FOLIO ontology and screening protocols may encode biases from the legal profession itself: issues common in affluent communities (contract disputes, intellectual property) may be better represented than issues common in low-income communities (public benefits, housing code violations, wage theft).

**Why it happens:**
LLMs are trained on legal text written by and for lawyers, which encodes the profession's historical biases. Legal ontologies reflect what the profession has chosen to categorize, which skews toward areas of law that generate revenue. Screening protocols written by attorneys in one practice area may not cover issues experienced by populations outside their practice. Algorithmic bias in legal contexts has produced documented disparate impacts: risk assessment tools like COMPAS over-predict risk for minorities; insurance algorithms produce discriminatory outcomes through proxy variables like zip code.

**How to avoid:**
- Test issue-spotting across diverse consumer narratives: same underlying legal situation described in formal vs. informal language, different dialects, different education levels, different cultural contexts. Measure whether the same issues are identified regardless of how the consumer describes the situation.
- The three-layer exploration approach (FOLIO ontology + screening protocols + LLM reasoning) is a good architectural defense: if one layer misses an issue, the others may catch it. But each layer must be independently tested for bias.
- Build a "narrative normalization" step: before issue-spotting, the system should extract the factual situation from the consumer's narrative in a standardized form, reducing the impact of vocabulary and framing differences.
- Ensure screening protocols cover issues disproportionately affecting underserved populations: wage theft, public benefits denial, housing code violations, immigration-related employment issues, consumer debt collection abuse, utility shutoffs.
- Audit FOLIO ontology coverage for practice areas serving low-income communities. Flag gaps to the folio project.
- Implement outcome tracking: across deployments, do consumers from different demographics receive systematically different issue identification? This requires opt-in demographic data collection, which creates its own privacy challenges.

**Warning signs:**
- Issue-spotting accuracy varies significantly based on the reading level or formality of the consumer narrative.
- Screening protocols cluster around "big law" practice areas and underrepresent legal aid practice areas.
- Consumer testers from different backgrounds receive different issues identified for the same underlying situation.
- Test: create 20 scenario pairs (same legal situation, different narrative styles) and measure issue identification parity.

**Phase to address:**
Issue-spotting and exploration phase. Bias testing must be part of the acceptance criteria for the issue-spotting pipeline, not a post-launch audit.

---

### Pitfall 5: Iterative Analysis Loop That Never Converges or Converges Prematurely

**What goes wrong:**
The iterative loop (issue-spot, research, fact-map, gap-analyze, question, loop) either runs indefinitely -- consuming tokens, time, and user patience -- or terminates too early, producing incomplete analysis. Three specific failure modes: (1) same-tool retry loops where the LLM keeps asking the same question with minor variations; (2) oscillation loops where identifying Issue A suggests Issue B, but researching Issue B suggests reconsidering Issue A; (3) re-planning loops where each failed research query triggers a complete re-analysis. On the premature side, the LLM's self-assessment of "completeness" is unreliable -- it may declare analysis complete when critical gaps remain because it lacks awareness of what it does not know.

**Why it happens:**
LLM agents lack native loop detection. The agent makes locally reasonable decisions at each step but has no global state representation tracking progress, cycle detection, or diminishing returns. The PROJECT.md specifies "multi-signal loop termination: coverage %, confidence plateau, iteration count, user fatigue, diminishing gaps" -- this is the right approach, but the devil is in implementation. If these signals are poorly calibrated, the loop either never fires termination or fires too early.

**How to avoid:**
- Implement hard iteration limits as a safety net (e.g., maximum 10 iterations regardless of other signals). This prevents runaway costs and user frustration.
- Use external objective criteria for convergence, not the LLM's self-assessment. Track: (a) number of new issues discovered per iteration (should decrease); (b) number of new facts elicited per iteration (should decrease); (c) coverage percentage across identified elements (should increase and plateau); (d) user engagement signals (response length, response time, explicit "I don't know more" signals).
- Implement cycle detection: log all questions asked and flag near-duplicate questions. If the system asks a question semantically similar to one already asked, skip it and count it as a signal of convergence.
- For oscillation detection: track the issue set across iterations. If the set is oscillating (adding and removing the same issues), freeze the issue set and proceed to depth analysis.
- Expose loop state to the user: "Round 3 of up to 8. We've identified 4 issues and have questions about 2 gaps." Transparency builds trust and lets the user signal when to stop.
- Make termination configurable per deployment: legal aid may want shallow and fast (2-3 rounds); law firms may want deep and thorough (8-10 rounds); the system should support both.

**Warning signs:**
- Average iteration count in testing exceeds the configured maximum (suggests the multi-signal termination is not firing).
- Users abandoning sessions mid-loop (suggests too many iterations or repetitive questions).
- Completed analyses missing obvious issues (suggests premature termination).
- Token costs per intake exceeding budget projections (suggests runaway loops).
- Test: run 50 sample intakes with logging. Plot issues-discovered-per-iteration and facts-elicited-per-iteration curves. They should show clear diminishing returns. If they are flat, the loop is not converging.

**Phase to address:**
Core analysis loop phase. The termination logic is as important as the analysis logic itself. Build termination criteria and loop state tracking before building the analysis pipeline.

---

### Pitfall 6: Safety Screening That Misses Urgent Situations

**What goes wrong:**
The system fails to detect that a consumer is in immediate danger -- domestic violence, suicidal ideation, child abuse, imminent eviction, protective order violations -- and proceeds with routine legal analysis instead of escalating. Or the system detects danger but responds inadequately: providing a phone number instead of connecting to emergency services, or generating a generic safety message that fails to account for the consumer's specific situation (e.g., advising a DV victim to "contact local authorities" when the abuser is law enforcement).

**Why it happens:**
Safety screening requires detecting distress signals that consumers often minimize, code, or disclose indirectly ("things have been really bad at home" instead of "my partner hits me"). LLMs can miss these signals, especially across cultural contexts where distress is expressed differently. Curated screening protocols may not cover every permutation of urgent situations. The system may not have a reliable escalation path -- who gets notified, how quickly, and what happens if the notification fails?

**How to avoid:**
- Mandatory safety screening must run before any other analysis, not as an optional step. The PROJECT.md specifies "configurable mandatory safety screening protocols per organization" -- the "mandatory" part must be enforced architecturally (the analysis pipeline cannot proceed until screening completes).
- Use multiple detection layers: keyword/pattern matching for explicit signals, LLM-based inference for implicit signals, and structured screening questions for high-risk issue areas (family law, housing, employment).
- Define escalation protocols with specific actions, not just notifications: (a) immediate danger = display crisis resources with local hotline numbers + attempt to connect a human; (b) urgent but not immediate = flag for priority attorney review within 24 hours; (c) safety concern = include safety resources in output and route to appropriate services.
- Test with scenarios that represent realistic disclosure patterns, including minimization, indirect disclosure, and coded language. Test across languages and cultural contexts.
- Build a "safety override" that lets any user at any point in the process signal an emergency, bypassing the normal flow.
- For DV situations specifically: the system must be aware that the consumer's device may be monitored. Offer a "quick exit" button and do not send follow-up emails or notifications unless the consumer explicitly opts in.

**Warning signs:**
- Safety screening is implemented as a keyword list rather than a multi-signal detection system.
- No defined escalation protocol -- the system detects danger but has nowhere to route it.
- Safety screening only runs at the beginning of the intake, not continuously throughout the conversation (consumers often disclose dangerous situations later in the conversation as trust builds).
- No testing with realistic DV/crisis scenarios.
- Test: create 30 safety-critical scenarios with varying levels of explicit vs. implicit disclosure. Measure detection rate. Anything below 95% is unacceptable for explicit signals; below 80% for implicit signals should trigger protocol expansion.

**Phase to address:**
Pre-research exploration phase (the screening/triage phase specifically). Safety screening is the single most ethically critical feature and must be built with extreme care. It should be the first feature tested with real users (under supervision).

---

### Pitfall 7: Over-Engineering the Configuration System

**What goes wrong:**
The system's extensive configurability (deployment modes, autonomy levels, persistence options, database backends, ASR providers, research tools, screening protocols, output formats, exploration depth, transparency levels) creates a configuration space so large that no single configuration is well-tested, the configuration UI becomes as complex as the product itself, and every new feature requires considering its interaction with all configuration options. 50% of initial CLM implementations fail (Gartner), often due to configuration complexity. The system becomes a "framework for building legal intake tools" rather than a legal intake tool, and no deployment actually works well out of the box.

**Why it happens:**
The system serves diverse deployment contexts (law firms, legal aid, courts, in-house counsel, direct-to-consumer) with genuinely different needs. The temptation is to make everything configurable to serve everyone. But each configuration option multiplies the testing surface, and interactions between options create combinatorial explosions. Engineers build abstractions for hypothetical future configurability that is never used, while the core happy path remains undertested.

**How to avoid:**
- Define 3-4 deployment profiles (archetypes) with opinionated defaults: (a) Legal Aid = consumer-facing, ephemeral persistence, shallow exploration, safety screening mandatory, local ASR; (b) Law Firm = professional-facing, persistent, deep exploration, CMS integration, cloud ASR; (c) Court = triage/routing focus, moderate exploration, case tracking; (d) Direct-to-Consumer = consumer-facing, maximum disclaimers, attorney checkpoints mandatory.
- Build and test the Legal Aid profile first as the MVP. It is the most constrained (privacy, UPL, accessibility, safety) and solving for it creates a solid foundation for the others.
- Configuration should be "choose a profile then override specific settings" not "configure 40 independent options."
- Defer configurability until there is a concrete deployment requesting it. Do not build SQLite+FAISS support until someone needs it. Do not build Clio integration until a Clio customer exists. The PROJECT.md lists these as requirements -- but requirements without customers are hypotheses.
- Apply the "rule of three": do not abstract until you have three concrete uses for the abstraction.

**Warning signs:**
- More time spent on configuration infrastructure than on the core analysis pipeline.
- Configuration options that have never been tested in combination.
- No deployment profile works well out of the box -- every deployment requires extensive configuration.
- The configuration documentation is longer than the user documentation.
- Test: can a new deployment go from zero to working intake in under 30 minutes with a profile selection? If not, the configuration system is too complex.

**Phase to address:**
Foundation phase (establish profiles) and every subsequent phase (resist adding configuration until needed). This is a continuous discipline, not a one-time decision.

---

### Pitfall 8: FOLIO Ontology Coupling That Creates Rigidity

**What goes wrong:**
The system becomes so tightly coupled to the FOLIO ontology's current structure that it cannot handle: (a) concepts that FOLIO does not yet cover (FOLIO has 18,300+ concepts but law is vast); (b) FOLIO taxonomy changes between versions (branch restructuring, concept merging, IRI changes); (c) jurisdictional legal concepts that do not map cleanly to FOLIO's universal taxonomy (e.g., Louisiana civil law concepts, tribal law, non-US jurisdictions). The system fails silently when it encounters a legal issue that falls between FOLIO concepts, or breaks when FOLIO releases a new version with structural changes.

**Why it happens:**
The PROJECT.md mandates "FOLIO IRIs as the canonical identifier for legal concepts -- no parallel taxonomy." This is architecturally correct for interoperability but creates tight coupling. Legal ontologies must evolve as law evolves -- new statutes create new concepts, court decisions redefine existing ones, and the ontology's categorization may not match how practitioners think about issues. Research on legal ontologies highlights that "the wording of a component evolves with each amendment" and that the abstract concept is permanent but its textual manifestation is not.

**How to avoid:**
- Treat FOLIO IRIs as stable references but design for graceful degradation when a concept is not found. The system should be able to work with "unclassified" or "provisional" concepts that are not yet in FOLIO, tagging them for later classification.
- Build a FOLIO version migration strategy from day one. When FOLIO releases a new version: (a) map old IRIs to new IRIs using FOLIO's own change tracking; (b) support running two versions simultaneously during migration; (c) never hard-code IRI strings -- use the folio-python library's resolution methods.
- Use FOLIO as the primary taxonomy but allow the LLM reasoning layer (the third layer of exploration) to identify issues that do not map to any FOLIO concept. These should be flagged as "emerging" or "unmapped" rather than silently dropped.
- Implement a concept resolution pipeline: user narrative -> LLM extraction -> folio-python semantic matching -> verified FOLIO IRI (or "unmapped" flag). The semantic matching step (which folio-python provides via LLM-powered matching) is the bridge between natural language and the ontology.
- Design the data model so that changing a FOLIO IRI does not require migrating all historical records -- use an indirection layer (local concept ID -> FOLIO IRI mapping) so that historical data can be re-mapped.

**Warning signs:**
- Issue-spotting fails to identify issues in practice areas with sparse FOLIO coverage.
- A FOLIO version update breaks the system or requires a database migration.
- The system cannot represent a legal concept that a human attorney would recognize.
- folio-python semantic matching returns low-confidence matches for common legal issues.
- Test: deliberately input scenarios involving emerging legal issues (AI liability, cryptocurrency disputes, gig economy worker classification) and verify the system handles them even if FOLIO coverage is incomplete.

**Phase to address:**
FOLIO integration phase. The concept resolution pipeline and graceful degradation must be built into the initial FOLIO integration, not bolted on later.

---

### Pitfall 9: Voice Transcription Errors Corrupting Legal Analysis

**What goes wrong:**
ASR misrecognizes legal terms, proper nouns, dollar amounts, dates, or case-specific details, and the corrupted transcript feeds into the analysis pipeline, producing incorrect issue-spotting. General-purpose ASR (including Whisper) achieves 25% word error rate on domain-specific terminology without fine-tuning, compared to 4.6% WER for domain-specific models. Legal terms that sound similar but mean very different things ("tortious" vs. "tortuous," "statute" vs. "status," "liable" vs. "libel," "mediation" vs. "medication") can produce catastrophically wrong analysis. Dollar amounts and dates -- critical for statutes of limitations and damages calculations -- are particularly error-prone.

**Why it happens:**
General ASR models are trained on conversational speech, not legal terminology. Consumers describe legal situations using colloquial language mixed with (often imprecise) legal terms. Background noise, accents, emotional distress (common in legal intake), and code-switching further degrade accuracy. The pipeline from voice -> transcript -> analysis has no built-in verification step -- the LLM trusts the transcript.

**How to avoid:**
- Use ASR with custom vocabulary/hotword boosting for legal terms. Both Deepgram and AssemblyAI support custom vocabularies. For local Whisper deployment, fine-tune on legal audio or use vocabulary-constrained decoding.
- Build a transcript review step before analysis begins. Display the transcript to the user with an option to correct errors. Highlight low-confidence words (most ASR engines provide word-level confidence scores).
- For critical data (dollar amounts, dates, names), use structured follow-up questions to confirm: "I heard you mention $50,000 -- is that correct?" This is standard in human legal intake and the AI should replicate it.
- Implement a "legal term normalization" layer between ASR and analysis: detect potential legal terms in the transcript and verify them against a legal terminology dictionary, flagging likely misrecognitions.
- Track and report ASR error rates in production. If error rates on legal terms exceed 5%, the ASR configuration needs adjustment.

**Warning signs:**
- Analysis outputs reference legal concepts that do not match what the user described (a sign the transcript was misrecognized).
- Users frequently correct the transcript (good if the correction step exists; bad if it means the ASR is consistently wrong).
- Dollar amounts or dates in the analysis do not match what the user stated.
- Test: record 20 legal intake scenarios with varying audio quality and accents. Compare ASR output to ground truth transcript. Measure WER overall and specifically for legal terms, numbers, and dates.

**Phase to address:**
Input/modality phase. ASR accuracy validation must be part of the voice input feature's acceptance criteria, not a future optimization.

---

### Pitfall 10: Multi-Jurisdictional Analysis That Produces Contradictory or Stale Results

**What goes wrong:**
The system analyzes a consumer's situation across multiple jurisdictions but produces results that are internally contradictory (telling the consumer they have a claim in State A but not State B for the same facts, without explaining why), based on outdated law (citing a statute that was amended or repealed), or overwhelming (presenting 5 jurisdictions' worth of analysis when the consumer only needs 1-2). Parallel jurisdictional research compounds hallucination risk -- the LLM must generate correct analysis for multiple legal systems simultaneously, and errors in one jurisdiction may not be caught by verification focused on another.

**Why it happens:**
Law varies dramatically across jurisdictions: statutes of limitations differ, elements of claims differ, available remedies differ, and procedural requirements differ. The system must know which jurisdiction's law applies (choice-of-law analysis is itself a complex legal question). Legal research tools may have uneven coverage across jurisdictions (strong federal coverage, weak state coverage, minimal tribal or territorial coverage). Laws change constantly -- a statute valid when the knowledge base was built may be amended by the time a consumer uses the system.

**How to avoid:**
- Build jurisdiction determination as an explicit step before multi-jurisdictional research, not an implicit assumption. Ask the consumer where they live, where the events occurred, and where the other party is located. Use these to determine potentially applicable jurisdictions.
- Present multi-jurisdictional results comparatively, not as independent analyses. "In California, the statute of limitations is 2 years; in Nevada, it is 3 years. Based on where the events occurred, California law likely applies."
- Include recency metadata on all legal research results. Display "last verified: [date]" on every authority cited. Flag any authority older than 1 year for potential staleness.
- Implement jurisdiction-specific verification: when citing a state statute, verify it against the current version in the state's official code (if available via research tools).
- Limit the number of jurisdictions analyzed by default (2-3 most likely applicable) with an option to expand. Do not analyze all 50 states plus federal by default.

**Warning signs:**
- Analysis for different jurisdictions uses the same statute of limitations or elements (a sign the system is not actually differentiating between jurisdictions).
- Research tool queries return no results for certain jurisdictions (coverage gap).
- Users report confusion from too many jurisdictional results.
- Test: input a scenario involving parties in different states. Verify that the analysis correctly identifies different applicable laws and explains why.

**Phase to address:**
Research and analysis phase. Multi-jurisdictional support is a differentiator but must be built carefully to avoid producing dangerous output.

---

## Technical Debt Patterns

| Shortcut | Immediate Benefit | Long-term Cost | When Acceptable |
|----------|-------------------|----------------|-----------------|
| Hard-coding a single LLM provider | Faster initial development | Vendor lock-in; cannot switch when pricing, capabilities, or policies change | Never -- alea-llm-client abstraction exists for this reason |
| Skipping citation verification in dev/test | Faster iteration on analysis pipeline | Habits form; verification gets deprioritized; developers test with unverified output and miss the failure mode | Never -- use mock verification that returns "unverified" status |
| Using RLS-only tenant isolation | Simpler schema, faster queries | RLS CVEs (CVE-2024-10976, CVE-2025-8713) demonstrate that RLS alone is insufficient for privileged data | Only in single-tenant self-hosted deployments where tenant isolation is not needed |
| Deferring voice input to "later" | Focus on text-first, which is simpler | Access-to-justice users who need voice input most are excluded from testing; voice integration is harder to add later because it affects the entire pipeline | Only if the first deployment is professional-facing (attorneys type); never for consumer-facing |
| Storing FOLIO IRIs as raw strings | Simple, readable data model | FOLIO version changes require find-and-replace across the entire database; no indirection for historical data | Early prototyping only; must be replaced before production data is stored |
| Building all configuration options at once | "Complete" product | Undertested combinatorial space; no single configuration is well-validated; effort spent on options no one uses | Never -- build profiles first, expand based on demand |

## Integration Gotchas

| Integration | Common Mistake | Correct Approach |
|-------------|----------------|------------------|
| LLM providers (via alea-llm-client) | Assuming all providers have the same capabilities (context window, tool use, structured output) | Abstract at the capability level: check provider capabilities at runtime, degrade gracefully when a capability is missing |
| FOLIO API (folio.openlegalstandard.org) | Treating the API as always-available and low-latency | Cache FOLIO data locally with periodic sync. The API is a public service; do not make it a single point of failure for real-time intake |
| CourtListener / legal research APIs | Assuming search results are comprehensive; treating absence of results as "no relevant law exists" | Always caveat: "Based on available databases. Additional authorities may exist." Never present a negative result ("no relevant cases found") as definitive |
| CMS connectors (Clio, MyCase, Legal Server) | Building one-way sync (push to CMS) and assuming it is sufficient | CMS integration must be bidirectional: matters created in the CMS should be importable, and updates in either system should sync. One-way sync creates data divergence |
| ASR providers (Whisper, Deepgram, AssemblyAI) | Using the provider's default model without legal domain customization | Configure custom vocabularies, hotword boosting, and speaker diarization. Test with legal audio specifically, not just general speech benchmarks |
| folio-python library | Using it for real-time ontology queries in the request path | folio-python loads the full ontology into memory. Initialize once at startup and reuse. Do not create new instances per request |

## Performance Traps

| Trap | Symptoms | Prevention | When It Breaks |
|------|----------|------------|----------------|
| Synchronous multi-jurisdictional research | Intake takes 5+ minutes as jurisdictions are researched sequentially | Parallelize research across jurisdictions using async tasks; stream partial results to the user as they complete | At 3+ jurisdictions with 2+ research tool queries each |
| Unbounded iterative loops consuming LLM tokens | Single intake costs $5-50 in API calls; monthly bills explode | Hard iteration limits; token budget per intake; track and alert on per-intake costs | At production scale with "until stable" exploration depth configured |
| Full ontology search on every issue-spotting query | Issue-spotting takes 10+ seconds per round | Pre-compute FOLIO relationship graphs; use vector similarity for initial matching, then refine with graph traversal | At 18,300+ FOLIO concepts with naive full-text search |
| Storing all three fact-mapping views in the database | Database bloat; slow writes on every analysis update | Store the canonical graph representation; compute matrix and narrative-anchored views on read | At 1,000+ intakes per tenant with 10+ issues each |
| Vector similarity search without index optimization | pgvector queries become slow as the embedding table grows | Use HNSW or IVFFlat indexes; partition embeddings by tenant and document type | At 100K+ embeddings per tenant |

## Security Mistakes

| Mistake | Risk | Prevention |
|---------|------|------------|
| Sending full consumer narratives to LLM providers without scrubbing | Privileged data in third-party systems; potential privilege waiver | PII detection and optional redaction before LLM calls; use pseudonymization where possible; contractual ZDR guarantees |
| Logging LLM prompts and responses in plaintext | Privileged data in log aggregation systems accessible to ops teams | Encrypt log entries containing user data; implement log access controls scoped to tenant; or do not log prompts/responses at all (log metadata only) |
| Shared LLM context across tenants in multi-tenant deployment | One tenant's privileged data leaks into another tenant's LLM context | Isolate LLM sessions per tenant; never share conversation history, RAG context, or fine-tuned models across tenants |
| OAuth tokens or API keys for legal research tools stored in the database without encryption | Compromised database exposes access to Westlaw, Lexis, CMS systems | Encrypt API keys at rest with a key management service (AWS KMS, HashiCorp Vault); rotate keys regularly |
| Consumer-facing endpoint without rate limiting | Abuse; denial of service; cost explosion from automated LLM queries | Rate limit per session, per IP, and per tenant; implement CAPTCHA or progressive challenges for suspicious patterns |
| Ephemeral mode that is not actually ephemeral | Consumer believes data is deleted but it persists in backups, logs, or LLM provider retention | Verify ephemeral mode purges from: database, cache, search index, file storage, logs, and confirm LLM provider ZDR is active |

## UX Pitfalls

| Pitfall | User Impact | Better Approach |
|---------|-------------|-----------------|
| Asking too many questions before providing any analysis | Consumer abandons session feeling interrogated; 60%+ drop-off in lengthy intake forms | Provide preliminary issue identification after the initial narrative; ask follow-up questions in context of what the system has already found |
| Legal jargon in consumer-facing output | Consumer does not understand their own case analysis; feels alienated | Use plain language with optional "legal term" tooltips; follow plain-language legal writing guidelines (e.g., Federal Plain Language Guidelines) |
| Showing confidence scores to consumers | Consumers misinterpret 70% confidence as "30% chance I lose" | Show confidence as qualitative categories ("strong support," "some support," "needs more information") not percentages |
| Not explaining why the system is asking a question | Consumer feels the questions are invasive or irrelevant | Configurable transparency: "I'm asking about your living situation because it may be relevant to housing rights" (the PROJECT.md already plans for this) |
| Presenting all issues with equal visual weight | Consumer is overwhelmed; cannot distinguish between primary claims and tangential issues | Visual hierarchy: primary issues prominently, secondary issues in a "related issues" section, safety concerns with urgent styling |
| Requiring account creation before any value is delivered | Privacy-conscious consumers (especially in DV, immigration contexts) will not create accounts | Allow anonymous intake with optional account creation to save progress; ephemeral mode must work without any account |

## "Looks Done But Isn't" Checklist

- [ ] **Citation verification:** Often missing verification for secondary citations (citations within cited passages) -- verify the pipeline checks all citation levels, not just top-level LLM output
- [ ] **Tenant isolation:** Often missing isolation in background jobs, scheduled tasks, and async workers -- verify tenant context propagates through the entire async pipeline, not just HTTP request handlers
- [ ] **Safety screening:** Often missing continuous screening (only screens at the start) -- verify screening runs on every consumer message, not just the initial narrative
- [ ] **Ephemeral mode:** Often missing purge from secondary storage (search indexes, embedding stores, cache) -- verify deletion cascades to all data stores, not just the primary database
- [ ] **Multi-jurisdictional analysis:** Often missing choice-of-law analysis -- verify the system explains which jurisdiction's law applies and why, not just what each jurisdiction says
- [ ] **Voice input:** Often missing transcript correction UX -- verify the consumer can review and correct the transcript before analysis proceeds
- [ ] **Configurability:** Often missing configuration validation -- verify invalid configuration combinations are rejected at startup, not discovered at runtime
- [ ] **Audit logs:** Often missing immutability -- verify audit logs cannot be modified or deleted, even by administrators
- [ ] **Right-to-delete:** Often missing cascading deletion across integrations -- verify deletion propagates to CMS connectors, not just local storage
- [ ] **Screening protocols:** Often missing version control -- verify protocol changes are versioned and auditable, not silently overwritten

## Recovery Strategies

| Pitfall | Recovery Cost | Recovery Steps |
|---------|---------------|----------------|
| Hallucinated citations in published output | HIGH | Issue correction notices to all affected users; implement verification pipeline; re-run all past analyses through verification; consider legal liability exposure |
| Privilege waiver through data leakage | VERY HIGH | Cannot un-ring this bell. Engage ethics counsel. Notify affected clients. May require withdrawal from representation. Technical fix is secondary to legal/ethical obligations |
| UPL enforcement action | HIGH | Engage regulatory counsel; modify system behavior for affected jurisdiction; implement attorney checkpoint gates; may need to suspend consumer-facing deployment |
| Bias discovered in production | MEDIUM | Retrain/re-prompt with debiased inputs; expand screening protocols; notify affected users that analysis may be incomplete; implement ongoing bias auditing |
| Loop convergence failure (runaway costs) | LOW-MEDIUM | Implement hard limits immediately; refund affected users/organizations; analyze logs to calibrate termination signals; set up cost alerting |
| Safety screening miss | VERY HIGH | If harm resulted, this is a crisis -- engage legal counsel and crisis response. Technically: expand screening protocols, add detection layers, reduce false-negative tolerance |
| FOLIO version break | MEDIUM | Roll back to previous FOLIO version; build migration tooling; implement the IRI indirection layer that should have been built initially |
| ASR error corrupting analysis | LOW-MEDIUM | Add transcript review step; re-run affected analyses with corrected transcripts; implement legal term verification layer |

## Pitfall-to-Phase Mapping

| Pitfall | Prevention Phase | Verification |
|---------|------------------|--------------|
| LLM hallucination of citations | Core analysis loop | Run 50 sample intakes; manually verify every citation; <5% unverifiable rate |
| Attorney-client privilege waiver | Foundation/infrastructure | Cross-tenant access testing at every layer; LLM provider contract audit; penetration testing |
| UPL liability | Foundation (architecture) + Output (implementation) | Review 100 consumer-facing outputs for UPL-triggering language; zero tolerance |
| Bias in issue-spotting | Issue-spotting/exploration | 20 scenario pairs (same situation, different narrative styles); measure identification parity |
| Loop convergence failure | Core analysis loop | 50 sample intakes with logging; plot diminishing returns curves; verify termination fires |
| Safety screening misses | Pre-research exploration | 30 safety-critical scenarios; >95% detection for explicit signals, >80% for implicit |
| Over-engineering configuration | Foundation (profiles) + all phases (discipline) | New deployment operational in <30 minutes with profile selection |
| FOLIO ontology coupling | FOLIO integration | Input scenarios with emerging legal issues; verify graceful degradation for unmapped concepts |
| Voice transcription errors | Input/modality | 20 legal audio samples; measure WER for legal terms, numbers, dates; <5% target |
| Multi-jurisdictional contradictions | Research/analysis | Cross-jurisdiction scenarios; verify differentiated analysis with choice-of-law explanation |

## Sources

- [Large Legal Fictions: Profiling Legal Hallucinations in Large Language Models](https://academic.oup.com/jla/article/16/1/64/7699227) -- Oxford Academic, 2024
- [Hallucination-Free? Assessing the Reliability of Leading AI Legal Research Tools](https://onlinelibrary.wiley.com/doi/full/10.1111/jels.12413) -- Stanford CodeX / Journal of Empirical Legal Studies, 2025
- [Stanford Legal RAG Hallucinations Study](https://dho.stanford.edu/wp-content/uploads/Legal_RAG_Hallucinations.pdf) -- Stanford, 2025
- [AI Hallucinations in Legal Work: How to Avoid Getting Sanctioned](https://thelegalprompts.com/blog/ai-hallucinations-legal-work-avoid-sanctions-2026) -- 2026
- [AI Hallucination Cases Database](https://www.damiencharlotin.com/hallucinations/) -- 700+ cases tracked
- [A Legal Practitioner's Guide to AI & Hallucinations](https://www.ncsc.org/resources-courts/legal-practitioners-guide-ai-hallucinations) -- NCSC
- [Cloud Computing Ethics Opinions for Lawyers](https://www.clio.com/blog/cloud-computing-lawyers-ethics-opinions/) -- Clio, compilation of state bar opinions
- [Attorney-Client Privilege in the Age of AI](https://www.spellbook.legal/learn/attorney-client-privilege-ai) -- Spellbook
- [Azure OpenAI Data Privacy](https://learn.microsoft.com/en-us/azure/foundry/responsible-ai/openai/data-privacy) -- Microsoft official docs
- [Nippon Life v. OpenAI -- Unauthorized Practice of Law](https://www.gallaghersharp.com/ai-on-trial-nippon-life-takes-openai-to-court-over-alleged-unauthorized-practice-of-law/) -- Gallagher Sharp, March 2026
- [Designed to Cross: Why Nippon Life v. OpenAI Is a Product Liability Case](https://law.stanford.edu/2026/03/07/designed-to-cross-why-nippon-life-v-openai-is-a-product-liability-case/) -- Stanford Law CodeX, March 2026
- [Colorado AI Nonprosecution Policy / ABA Journal](https://www.abajournal.com/web/article/ai-legal-tool-developers-could-avoid-upl-in-these-states) -- ABA
- [AI and Racial Bias in Legal Decision-Making](https://clp.law.harvard.edu/knowledge-hub/insights/ai-and-racial-bias-in-legal-decision-making-a-student-fellow-project/) -- Harvard Law School
- [Legal Aid Intake & Screening AI](https://justiceinnovation.law.stanford.edu/legal-aid-intake-screening-ai/) -- Stanford Legal Design Lab
- [Six Common Pitfalls in Legal Tech Adoption](https://www.americanbar.org/groups/law_practice/resources/law-technology-today/2025/six-common-pitfalls-in-legal-tech-adoption/) -- ABA
- [Why Does Your AI Agent Get Stuck in Infinite Loops?](https://www.pithycyborg.com/why-does-your-ai-agent-get-stuck-in-infinite-loops/) -- Pithy Cyborg
- [Designing Agentic Loops](https://simonwillison.net/2025/Sep/30/designing-agentic-loops/) -- Simon Willison
- [Multi-Tenant Leakage: When Row-Level Security Fails in SaaS](https://medium.com/@instatunnel/multi-tenant-leakage-when-row-level-security-fails-in-saas-da25f40c788c) -- 2026
- [Preventing Cross-Tenant Data Leakage in Multi-Tenant SaaS Systems](https://agnitestudio.com/blog/preventing-cross-tenant-leakage/) -- Agnite Studio
- [An Ontology-Driven Graph RAG for Legal Norms](https://arxiv.org/html/2505.00039v5) -- arXiv, 2025
- [Ethical Implications of AI-Driven Chatbots in Domestic Violence](https://www.cogitatiopress.com/socialinclusion/article/viewFile/9998/4604) -- Social Inclusion journal
- [OpenAI Court Order Concerns for Survivors of Abuse](https://nnedv.org/latest_update/new-openai-court-order-raises-serious-concerns-about-ai-privacy-and-safety-for-survivors-of-abuse/) -- NNEDV

---
*Pitfalls research for: Legal intake and AI-assisted legal analysis (ALEA Intake)*
*Researched: 2026-03-22*
