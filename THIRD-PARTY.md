# Third-Party Licenses & Attribution

alea-intake is licensed **MIT** (see `LICENSE`). It incorporates the
open-source components and openly-licensed data below. This inventory satisfies
the portfolio OSS-licensing policy; update it whenever dependencies change.

> **Two files, one story.** *This* file is the authoritative attribution notice —
> bundled data, fonts, and the copyleft components that need a decision.
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
| sentence-transformers, faiss-cpu, pgvector | Apache-2.0 / MIT | permissive |
| **psycopg[binary]** | **LGPL-3.0** | weak copyleft; used unmodified as a dependency — compatible |
| **pymupdf** | **AGPL-3.0-only / commercial** | ⚠ **OPEN — needs Damien's decision.** See below. |
| React 19, Radix, TanStack, d3-*, i18next, wavesurfer.js, jspdf | MIT / BSD / ISC | permissive |

Frontend `@fontsource` fonts: OFL-1.1 (above).

## Open compliance question — PyMuPDF (AGPL-3.0) in an MIT project

**Status as of 2026-07-24: unresolved.** `pymupdf>=1.27.0` is a **required**
entry in `backend/pyproject.toml`, `backend/app/services/document/extractors/pdf_extractor.py`
imports it, and the `Dockerfile`'s `uv sync --no-dev` installs it into the built
image. `THIRD_PARTY_LICENSES.md` currently argues that "end users install PyMuPDF
independently" — that is not what the manifest and the image do.

Why it matters: AGPL §13 reaches users who interact with a *hosted* service, and
ALEA Intake is designed to be deployed as one. The same question was answered
differently in two sibling repos, so the portfolio is currently inconsistent:

- **folio-enrich** removed PyMuPDF and replaced it with **pypdf** (BSD) to stay
  cleanly MIT (2026-07-05, Damien-approved).
- **book-indexer** kept PyMuPDF and **relicensed itself AGPL-3.0-only**, saying so
  in its LICENSE, NOTICE, and README.

alea-intake has done neither. The three live options are the same three:

1. **Replace** the extractor's backend with a permissive library (pypdf / pdfplumber),
   or put PyMuPDF behind an optional `[pymupdf]` extra that no default install pulls.
2. **Buy** an Artifex commercial license for PyMuPDF.
3. **Relicense** alea-intake AGPL-3.0 and say so everywhere, as book-indexer did.

Until one is chosen, do not represent a distributed alea-intake build or hosted
deployment as "MIT with no copyleft dependencies."
