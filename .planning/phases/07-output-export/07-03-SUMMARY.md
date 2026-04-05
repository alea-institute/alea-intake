---
phase: 07-output-export
plan: 03
subsystem: output
tags: [weasyprint, python-docx, pdf, docx, json, export, rest-api, css-paged-media]

# Dependency graph
requires:
  - phase: 07-output-export
    provides: OutputContext, CIRACSection, OutputProfile schemas; DataAssembler; TriageScorer; ActionItemGenerator; TemplateEngine; LanguageAdapter
provides:
  - ExportAdapter ABC with PDF, DOCX, JSON concrete adapters
  - legal_pdf.css stylesheet for CSS Paged Media legal formatting
  - Output REST API router with generation, retrieval, and export endpoints
  - Full output pipeline orchestration in single API call (D-06)
  - WeasyPrint and markdown-it-py dependencies
affects: [08-frontend-output]

# Tech tracking
tech-stack:
  added: [weasyprint, markdown-it-py]
  patterns: [export-adapter-pattern, css-paged-media, streaming-response-export, render-cache]

key-files:
  created:
    - backend/app/services/output/export/__init__.py
    - backend/app/services/output/export/base.py
    - backend/app/services/output/export/pdf_adapter.py
    - backend/app/services/output/export/docx_adapter.py
    - backend/app/services/output/export/json_adapter.py
    - backend/app/services/output/templates/css/legal_pdf.css
    - backend/app/routers/output.py
    - backend/tests/test_output_export.py
    - backend/tests/test_output_api.py
  modified:
    - backend/pyproject.toml
    - backend/app/main.py

key-decisions:
  - "WeasyPrint for PDF generation via CSS Paged Media (not reportlab or wkhtmltopdf)"
  - "markdown-it-py for Markdown-to-HTML conversion (CommonMark-compliant)"
  - "Export render caching on OutputDocument model (rendered_pdf, rendered_docx, rendered_json)"
  - "CSS custom properties for org branding injection (--primary-color, --secondary-color)"
  - "TOC placeholder via Word field codes (XML workaround for python-docx)"

patterns-established:
  - "ExportAdapter ABC: async export(markdown, context, profile) -> bytes with content_type and file_extension"
  - "CSS Paged Media: @page rules for letter size, string-set for running headers/footers, counter for page numbers"
  - "Render cache: check rendered_{format} field before invoking adapter; cache result on commit"
  - "Output pipeline: DataAssembler -> TriageScorer -> ActionItemGenerator -> TemplateEngine -> persist"

requirements-completed: [INTEGRATE-06, OUTPUT-04]

# Metrics
duration: 10min
completed: 2026-04-05
---

# Phase 7 Plan 3: Export Adapters & Output API Summary

**PDF/DOCX/JSON export adapters via WeasyPrint, python-docx, and Pydantic with CSS Paged Media legal formatting, REST API orchestrating full output pipeline, and render caching**

## Performance

- **Duration:** 10 min
- **Started:** 2026-04-05T02:35:25Z
- **Completed:** 2026-04-05T02:45:18Z
- **Tasks:** 2
- **Files modified:** 11

## Accomplishments
- ExportAdapter ABC with PDF (WeasyPrint + CSS Paged Media), DOCX (python-docx with headers/footers/TOC), and JSON (Pydantic serialization) concrete adapters
- legal_pdf.css provides professional legal formatting: letter size, 1in margins, running headers/footers with page numbers, numbered paragraphs, authority formatting (binding/persuasive/secondary), and org branding via CSS custom properties
- REST API with POST /generate (multi-profile in single call per D-06), GET /{id} (detail), GET /intake/{id} (list), GET /{id}/export/{format} (PDF/DOCX/JSON with caching)
- Output pipeline orchestrated in single endpoint: DataAssembler -> TriageScorer -> ActionItemGenerator -> TemplateEngine -> persist -> export

## Task Commits

Each task was committed atomically:

1. **Task 1: Export adapters (PDF, DOCX, JSON) with CSS stylesheet** - `42b62f0` (test) + `f365c8a` (feat)
2. **Task 2: Output API router and main.py wiring** - `88fe44d` (test) + `ffedf4c` (feat)

_Note: TDD tasks have separate test (RED) and implementation (GREEN) commits._

## Files Created/Modified
- `backend/app/services/output/export/base.py` - ExportAdapter ABC defining export interface
- `backend/app/services/output/export/pdf_adapter.py` - PDFAdapter: Markdown -> HTML (markdown-it-py) -> PDF (WeasyPrint)
- `backend/app/services/output/export/docx_adapter.py` - DOCXAdapter: Markdown parsing -> DOCX with Times New Roman, headers/footers, TOC placeholder
- `backend/app/services/output/export/json_adapter.py` - JSONAdapter: OutputContext Pydantic serialization
- `backend/app/services/output/export/__init__.py` - Re-exports for all adapters
- `backend/app/services/output/templates/css/legal_pdf.css` - CSS Paged Media stylesheet for legal PDF formatting
- `backend/app/routers/output.py` - Output REST API with generate/retrieve/list/export endpoints
- `backend/app/main.py` - Added output_router inclusion
- `backend/pyproject.toml` - Added weasyprint and markdown-it-py dependencies
- `backend/tests/test_output_export.py` - 23 tests for export adapters and CSS
- `backend/tests/test_output_api.py` - 11 tests for API endpoints

## Decisions Made
- WeasyPrint for PDF generation via CSS Paged Media (produces high-quality PDFs from HTML+CSS; avoids wkhtmltopdf binary dependency issues and reportlab's low-level API)
- markdown-it-py for Markdown-to-HTML conversion (CommonMark-compliant, supports tables, same ecosystem as the rest of the pipeline)
- Export render caching: first export request renders via adapter and caches bytes on OutputDocument (rendered_pdf/rendered_docx/rendered_json); subsequent requests return cached bytes
- CSS custom properties (--primary-color, --secondary-color, --body-font) allow org branding injection without template changes
- TOC in DOCX uses Word field codes via XML workaround (python-docx doesn't have native TOC support; Word updates the TOC on open)

## Deviations from Plan

None - plan executed exactly as written.

## Issues Encountered
- Auth test pattern: initial tests used wrong `create_access_token` signature; fixed to use the project's existing pattern of registering a user via `/auth/register` and using the returned token with `X-Tenant-Slug` header

## Known Stubs

None in this plan. (The LanguageAdapter._rewrite_text stub from Plan 02 is still present but not introduced by this plan.)

## User Setup Required

None - no external service configuration required. WeasyPrint requires system libraries (libpango, libcairo, libgdk-pixbuf) which are already present.

## Next Phase Readiness
- Complete output pipeline: data assembly -> scoring/action items -> template rendering -> export to PDF/DOCX/JSON
- All three layers of Phase 07 output-export are complete and tested
- Ready for Phase 08 frontend output integration (consuming these API endpoints)
- LanguageAdapter LLM integration deferred to orchestrator wiring phase

## Self-Check: PASSED

---
*Phase: 07-output-export*
*Completed: 2026-04-05*
