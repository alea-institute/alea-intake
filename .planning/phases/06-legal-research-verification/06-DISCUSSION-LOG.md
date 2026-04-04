# Phase 6: Legal Research & Verification - Discussion Log

> **Audit trail only.** Do not use as input to planning, research, or execution agents.
> Decisions are captured in CONTEXT.md — this log preserves the alternatives considered.

**Date:** 2026-04-04
**Phase:** 06-legal-research-verification
**Areas discussed:** Research tool adapter architecture, Citation verification pipeline, FOLIO ecosystem integration, Knowledge base & RAG, Research stage integration, Rate limiting & cost control, folio-mcp as LLM agent tool, Element-per-jurisdiction research depth, Verification database architecture, KB document lifecycle, Research result ranking & deduplication, Authority type taxonomy

---

## Research Tool Adapter Architecture

### Adapter Interface
| Option | Selected |
|--------|----------|
| Dual-mode: MCP + HTTP with unified interface | ✓ |
| MCP-only via folio-mcp | |
| HTTP-only with tool registry | |

### Tool Configuration
**User's choice:** BOTH platform-level registry AND org-level activation with credentials ("bring your own research tools")

### Default Tools
**User's choice:** ALL mentioned tools ship as adapter stubs. Free/open tools pre-configured. Commercial tools require org credentials. Org admins can add any research database.

---

## Citation Verification Pipeline

### Verification Approach
| Option | Selected |
|--------|----------|
| Multi-source verification with confidence | ✓ |
| Single-source verification | |
| LLM self-verification | |

### Unverifiable Citations
| Option | Selected |
|--------|----------|
| Flag but include with warning | ✓ |
| Exclude entirely | |
| Quarantine for review | |

---

## FOLIO Ecosystem Integration

### folio-insights
**User's choice:** Researcher must survey ALL repos at github.com/alea-institute/ and determine integration for all applicable tools, not just folio-insights.

### folio-enrich
**User's choice:** Reuse folio-enrich pipeline (not just API call). Two modes: (1) backend pipeline invisible to end users, (2) UI-visible annotations for org admin precision/recall validation.

### Primary vs Secondary Sources
**User's choice:** Research tools (cases, statutes, regs) are PRIMARY authority for legal elements. folio-insights provides SECONDARY/PRACTICAL knowledge (advocacy tips, best practices).

### Ecosystem Survey Scope
| Option | Selected |
|--------|----------|
| Research all repos, integrate what fits Phase 6 | ✓ |
| Integrate known tools only | |
| Deep integration of everything | |

---

## Knowledge Base & RAG

### KB Architecture
| Option | Selected |
|--------|----------|
| Dual-backend RAG reusing EmbeddingService | ✓ |
| External vector DB | |
| Simple keyword search + LLM | |

### Document Formats
| Option | Selected |
|--------|----------|
| Extended: PDF, DOCX, images, HTML, plain text | ✓ |
| PDF only | |
| Reuse Phase 3 extractors only | |

### Chunking Strategy
| Option | Selected |
|--------|----------|
| Semantic chunking with overlap | ✓ |
| Fixed-size chunking | |

**User addition:** FOLIO concept tagging on chunk headings — headings containing FOLIO tags create strong retrieval signals for dual retrieval (vector similarity + FOLIO IRI matching).

---

## Research Stage Integration

### Stage Architecture
| Option | Selected |
|--------|----------|
| ResearchStage replaces stub, queries tools in parallel | ✓ |
| Sequential tool queries by priority | |

### Research Feedback Loop
| Option | Selected |
|--------|----------|
| Research informs gap analysis for re-iteration | ✓ |
| One-shot research | |

---

## Rate Limiting & Cost Control

### Cost Management
| Option | Selected |
|--------|----------|
| Per-org usage tracking with budget caps | ✓ |
| Global rate limiting only | |

### Caching
**User's choice:** TTL cache per query+tool AND live API query in parallel — cached results shown immediately, live query refreshes in background.

---

## folio-mcp as LLM Agent Tool

| Option | Selected |
|--------|----------|
| MCP client in analysis orchestrator | ✓ |
| Standalone folio-mcp queries | |

---

## Element-per-Jurisdiction Research Depth

**User's choice:** Research tools (primary legal sources) are the PRIMARY authority for elements. folio-insights supplements with SECONDARY/PRACTICAL knowledge. Hierarchy: primary sources > secondary sources.

---

## Verification Database Architecture

| Option | Selected |
|--------|----------|
| Local citation cache with live refresh | ✓ |
| Live verification only | |

---

## KB Document Lifecycle

| Option | Selected |
|--------|----------|
| Full lifecycle with re-indexing | ✓ |
| Upload-only, no updates | |

---

## Research Result Ranking & Deduplication

| Option | Selected |
|--------|----------|
| Multi-signal relevance scoring | ✓ |
| Tool-priority ranking | |
| Present all, let professional sort | |

---

## Authority Type Taxonomy

### Taxonomy
| Option | Selected |
|--------|----------|
| FOLIO Legal Authority branch as canonical | ✓ |
| Simplified 3-tier | |

### Presentation
| Option | Selected |
|--------|----------|
| Grouped by type with binding/persuasive indicators | ✓ |
| Flat ranked list | |

---

## Claude's Discretion
- Adapter implementation details per tool
- Citation normalization algorithm
- folio-enrich pipeline reuse details
- KB chunk size tuning
- MCP client implementation
- Rate limiting algorithm

## Deferred Ideas
None
