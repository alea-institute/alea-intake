# Third-Party Licenses & Attribution

alea-intake is licensed **MIT** (see `LICENSE`). It incorporates the
open-source components and openly-licensed data below. This inventory satisfies
the portfolio OSS-licensing policy; update it whenever dependencies change.

> **Two files, one story.** *This* file is the authoritative attribution notice —
> bundled data, fonts, and notable dependency licenses.
> [`THIRD_PARTY_LICENSES.md`](THIRD_PARTY_LICENSES.md) is its per-package appendix:
> every backend and frontend dependency with an SPDX identifier. Where the two
> disagree, this file governs; keep both current in the same change.

## Openly-licensed data

### FOLIO ontology — CC-BY 4.0
This project bundles FOLIO ontology data (`backend/data/folio_cache/folio.owl`)
and queries FOLIO via `folio-python`. **FOLIO** (Federated Open Legal
Information Ontology) is maintained by the **ALEA Institute** and originates
from the **SALI Alliance**, licensed **Creative Commons Attribution 4.0
International (CC-BY 4.0)**.
- Source: https://github.com/alea-institute/FOLIO
- License: https://creativecommons.org/licenses/by/4.0/

## Bundled fonts — SIL Open Font License 1.1
The frontend bundles these `@fontsource` families under **OFL-1.1** (attribution
required on redistribution):
- Inter, Libre Caslon Text, Libre Franklin, Source Serif 4
- License: https://openfontlicense.org/

## Notable dependencies

| Component | License | Notes |
|-----------|---------|-------|
| fastapi, uvicorn, pydantic, sqlalchemy, alembic, httpx, authlib, structlog, slowapi, prometheus-client, opentelemetry-* | MIT / BSD / Apache-2.0 | permissive |
| folio-python, alea-llm-client, eyecite, weasyprint, python-docx, lxml | MIT / BSD | permissive |
| **folio-resolve** | **MIT** | the shared FOLIO source-text→concept matching engine (Damien Riehl). Supplies Stage-2 label scoring and the semantic-fit `PlaceNameGate`; see `backend/migration/`. Pure-Python core, depends only on `pydantic` |
| sentence-transformers, faiss-cpu, pgvector, torch | Apache-2.0 / MIT / BSD-3-Clause | permissive; torch uses CPU wheels |
| **psycopg[binary]** | **LGPL-3.0** | weak copyleft; used unmodified as a dependency — compatible |
| pdfplumber, pdfminer.six | MIT | PDF text, font sizes, and bounding-box provenance |
| pypdfium2 | Apache-2.0 OR BSD-3-Clause | PDFium rendering bindings; bundled PDFium uses BSD-3-Clause and third-party notices |
| React 19, Radix, TanStack, d3-*, i18next, wavesurfer.js, jspdf | MIT / BSD / ISC | permissive |

Frontend `@fontsource` fonts: OFL-1.1 (above).

## PDF extraction

The PDF extractor uses **pdfplumber** (MIT) over **pdfminer.six** (MIT).
It preserves heading classification by font size and page/bounding-box provenance.
The former AGPL PDF dependency has been removed from the dependency manifest
and application source.

**pypdfium2**, a pdfplumber dependency, is available under Apache-2.0 or
BSD-3-Clause. Its bundled PDFium library is BSD-3-Clause; retain the wheel's
PDFium third-party license notices when redistributing it.
