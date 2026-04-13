# Third-Party Licenses

This project uses the following open-source dependencies. Each is listed with
its SPDX license identifier. All licenses are compatible with this project's
MIT license.

## Python Dependencies (backend)

| Package | License (SPDX) | Notes |
|---------|---------------|-------|
| fastapi | MIT | |
| uvicorn | BSD-3-Clause | |
| sqlalchemy | MIT | |
| alembic | MIT | |
| pydantic | MIT | |
| pydantic-settings | MIT | |
| pyjwt | MIT | |
| pwdlib | MIT | |
| cryptography | Apache-2.0 AND BSD-3-Clause | Dual-licensed |
| python-multipart | Apache-2.0 | |
| python-dotenv | BSD-3-Clause | |
| alea-llm-client | MIT | ALEA Institute project |
| httpx | BSD-3-Clause | |
| asyncpg | Apache-2.0 | |
| psycopg | LGPL-3.0-or-later | Dynamic linking via pip install; see compatibility notes below |
| aiosqlite | MIT | |
| pgvector | MIT | |
| folio-python | MIT | ALEA Institute project |
| faiss-cpu | MIT | |
| sentence-transformers | Apache-2.0 | |
| lxml | BSD-3-Clause | |
| python-docx | MIT | |
| pymupdf | AGPL-3.0-only | Used as a library via pip; not modified or redistributed; see compatibility notes below |
| pytesseract | Apache-2.0 | |
| mcp | MIT | |
| eyecite | BSD-2-Clause | |
| weasyprint | BSD-3-Clause | |
| markdown-it-py | MIT | |
| authlib | BSD-3-Clause | |
| itsdangerous | BSD-3-Clause | |
| opentelemetry-api | Apache-2.0 | |
| opentelemetry-sdk | Apache-2.0 | |
| opentelemetry-exporter-otlp-proto-http | Apache-2.0 | |
| opentelemetry-instrumentation-fastapi | Apache-2.0 | |
| structlog | Apache-2.0 OR MIT | Dual-licensed |
| slowapi | MIT | |
| prometheus-client | Apache-2.0 | |
| prometheus-fastapi-instrumentator | ISC | |

## Frontend Dependencies (frontend)

| Package | License (SPDX) | Notes |
|---------|---------------|-------|
| react | MIT | |
| react-dom | MIT | |
| react-router-dom | MIT | |
| react-hook-form | MIT | |
| react-markdown | MIT | |
| react-i18next | MIT | |
| @radix-ui/react-alert-dialog | MIT | |
| @radix-ui/react-avatar | MIT | |
| @radix-ui/react-checkbox | MIT | |
| @radix-ui/react-dialog | MIT | |
| @radix-ui/react-dropdown-menu | MIT | |
| @radix-ui/react-icons | MIT | |
| @radix-ui/react-label | MIT | |
| @radix-ui/react-progress | MIT | |
| @radix-ui/react-radio-group | MIT | |
| @radix-ui/react-scroll-area | MIT | |
| @radix-ui/react-select | MIT | |
| @radix-ui/react-separator | MIT | |
| @radix-ui/react-slot | MIT | |
| @radix-ui/react-switch | MIT | |
| @radix-ui/react-tabs | MIT | |
| @radix-ui/react-tooltip | MIT | |
| @tanstack/react-query | MIT | |
| @tanstack/react-virtual | MIT | |
| @hookform/resolvers | MIT | |
| @fontsource/inter | OFL-1.1 | Font license |
| @fontsource/libre-caslon-text | OFL-1.1 | Font license |
| @fontsource/libre-franklin | OFL-1.1 | Font license |
| @fontsource/source-serif-4 | OFL-1.1 | Font license |
| @wavesurfer/react | BSD-3-Clause | |
| wavesurfer.js | BSD-3-Clause | |
| tailwindcss | MIT | devDependency used at build time |
| tailwindcss-animate | MIT | |
| tailwind-merge | MIT | |
| class-variance-authority | Apache-2.0 | |
| clsx | MIT | |
| d3-drag | ISC | |
| d3-force | ISC | |
| d3-scale | ISC | |
| d3-selection | ISC | |
| d3-zoom | ISC | |
| html-to-image | MIT | |
| i18next | MIT | |
| i18next-browser-languagedetector | MIT | |
| i18next-http-backend | MIT | |
| jspdf | MIT | |
| lucide-react | ISC | |
| rehype-sanitize | MIT | |
| rehype-slug | MIT | |
| remark-gfm | MIT | |
| sonner | MIT | |
| vite | MIT | devDependency used at build time |
| zod | MIT | |
| zustand | MIT | |

## License Compatibility Notes

- **AGPL-3.0 (PyMuPDF):** PyMuPDF is licensed under AGPL-3.0-only. This project
  uses PyMuPDF as a runtime library installed separately via pip. The ALEA Intake
  source code is MIT-licensed and does not contain, modify, or redistribute any
  PyMuPDF source code. End users install PyMuPDF independently as a Python package
  dependency. The AGPL obligations apply to PyMuPDF itself, not to this project's
  MIT-licensed code that calls its API. Organizations with AGPL concerns may
  substitute an alternative PDF library.

- **LGPL-3.0 (psycopg):** psycopg is licensed under LGPL-3.0-or-later. This
  project uses psycopg as a dynamically-linked library installed via pip. The
  LGPL permits use of the library by proprietary and permissively-licensed
  software without imposing copyleft on the calling code, provided the library
  is not statically linked or modified. pip installation satisfies the dynamic
  linking requirement.

- **OFL-1.1 (Fontsource packages):** The SIL Open Font License permits free use,
  modification, and redistribution of fonts, including bundling with software
  under any license. OFL-1.1 is fully compatible with MIT distribution.

---
Generated: 2026-04-09
