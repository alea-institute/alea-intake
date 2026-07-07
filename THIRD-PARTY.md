# Third-Party Licenses & Attribution

alea-intake is licensed **MIT** (see `LICENSE`). It incorporates the
open-source components and openly-licensed data below. This inventory satisfies
the portfolio OSS-licensing policy; update it whenever dependencies change.

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
| sentence-transformers, faiss-cpu, pgvector | Apache-2.0 / MIT | permissive |
| **psycopg[binary]** | **LGPL-3.0** | weak copyleft; used unmodified as a dependency — compatible |
| **pdfplumber** (+ pdfminer.six, Pillow, pypdfium2) | **MIT** (pdfplumber, pdfminer.six); Pillow MIT-CMU/HPND; pypdfium2 Apache-2.0 OR BSD-3-Clause | permissive — PDF text extraction backend |
| ~~pymupdf~~ | ~~AGPL-3.0 / commercial~~ | ✅ **REMOVED 2026-07-07 (S075.4)** — replaced with pdfplumber (MIT) to eliminate the AGPL copyleft obligation flagged in `EP-PORTFOLIO-OSSLICENSE-001`. Heading/bbox extraction preserved 1:1; suite green (1069 passed). |
| React 19, Radix, TanStack, d3-*, i18next, wavesurfer.js, jspdf | MIT / BSD / ISC | permissive |

Frontend `@fontsource` fonts: OFL-1.1 (above).
