# Phase 7: Output & Export - Discussion Log

> **Audit trail only.** Decisions are in CONTEXT.md.

**Date:** 2026-04-04
**Phase:** 07-output-export
**Areas discussed:** Output document structure, Deployment-type configuration, Export formats & rendering, Gap analysis in output

---

## Output Document Structure

### Case Memo Format
**User's choice:** CIRAC format — Conclusion (executive summary) first, then Issue→Rule→Application→Conclusion per claim. Structured like a traditional legal brief.

### Triage/Routing
| Option | Selected |
|--------|----------|
| Multi-factor scoring with ranked recommendations | ✓ |
| Rule-based routing only | |

### Action Items
| Option | Selected |
|--------|----------|
| Prioritized checklist grouped by category | ✓ |
| Flat action list | |

---

## Deployment-Type Configuration

### Output Profiles
| Option | Selected |
|--------|----------|
| Template profiles with section visibility rules | ✓ |
| Single template with togglable sections | |
| Fully custom templates | |

### Language Adaptation
**User's choice:** LLM adapts per profile. Also: a single matter can generate MULTIPLE profiles simultaneously (lawyer version + consumer version).

---

## Export Formats & Rendering

### Implementation
| Option | Selected |
|--------|----------|
| Markdown → rendering pipeline | ✓ |
| Template-per-format | |

### Styling
| Option | Selected |
|--------|----------|
| Professional legal formatting (Bluebook, numbered paragraphs, TOC, branding) | ✓ |
| Basic formatting only | |

---

## Gap Analysis in Output

**User's choice:** BOTH inline per claim AND consolidated Gap Report Appendix.

---

## Claude's Discretion
- CIRAC section templates, triage scoring weights, WeasyPrint CSS, TOC logic, branding schema

## Deferred Ideas
None
