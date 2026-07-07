---
date: 2026-07-07
tags: [licensing, pdf, pdfplumber, pymupdf, folio-python, oracle, uat]
repos: [alea-intake, folio-mapper, generative-folio]
problem: Swap AGPL PyMuPDF without regressing extraction; build a deterministic FOLIO IRI oracle against folio-python's real API.
---

# PyMuPDF→pdfplumber swap + folio-python resolution API

Two reusable learnings from the Lane-3 / S075.4 close-out.

## 1. Removing AGPL PyMuPDF: pdfplumber, not pypdf, when you need font size

**Problem.** PyMuPDF is AGPL-3.0 — incompatible with an MIT repo. folio-enrich
already swapped it for **pypdf** (pure-Python BSD). Naively matching that choice
here would have **regressed** alea-intake: its PDF extractor classifies headings by
per-span **font size** (`>=16pt`) and records **bbox** provenance, and pypdf's
`extract_text()` exposes neither cleanly (only a fiddly `visitor_text` callback).

**Solution.** Use **pdfplumber** (MIT, over pdfminer.six). It exposes per-character
`size` + bbox, so the exact heading/bbox logic is preserved 1:1:

```python
import pdfplumber
from collections import defaultdict
with pdfplumber.open(path) as pdf:
    for pnum, page in enumerate(pdf.pages, 1):
        words = page.extract_words(extra_attrs=["size"], use_text_flow=True)
        lines = defaultdict(list)
        for w in words:
            lines[round(w["top"])].append(w)      # group words into visual lines
        for top in sorted(lines):
            ws = lines[top]
            size = max(w["size"] for w in ws)
            element_type = "heading" if size >= 16.0 else "paragraph"
```

**Rule of thumb.** "Match the sibling repo's choice" is a default, not a mandate —
when the sibling's choice would regress *this* repo's behavior, pick the option that
preserves quality (policy 10). Both libs remove the AGPL dependency equally.

**Test gotcha.** The old tests used `pymupdf` *to author* fixture PDFs
(`doc.new_page(); page.insert_text(...)`). Removing PyMuPDF entirely means those
helpers break. Fix: reuse a committed fixture (`tests/fixtures/sample.pdf`, a 20pt
heading + 12pt paragraph) instead of generating PDFs — no PDF-authoring dep needed
just for tests. Suite stayed at 1069 passed.

## 2. Resolving a FOLIO IRI to a concept via folio-python (for deterministic oracles)

**Problem.** Building `scripts/folio_check.py` (RUB-INTAKE-05 oracle) needed to turn
a mapped `folio_iri` into a real concept + branch. The folio-python API is not
obvious and a prior stub guessed wrong (`get_by_iri` — does not exist).

**Solution — the actual API (folio-python 0.3.3):**

- `FOLIO()` — constructs + loads OWL (cached after first load; ~seconds).
- `search_by_label(q)` returns **`list[(OWLClass, score)]` tuples** — NOT bare objects.
- Resolve an IRI: **`iri in folio`** (`__contains__`) then **`folio[iri]`**
  (`__getitem__`, str only). `folio.normalize_iri(iri)` accepts a bare `R…` id too.
- `OWLClass` is a pydantic model: `.iri`, `.label`, `.preferred_label`, `.definition`,
  `.deprecated`, `.sub_class_of` (list of **parent IRIs**), `.see_also`, `.translations`.
- **Top-level branch** = walk `.sub_class_of[0]` up until the parent is
  `http://www.w3.org/2002/07/owl#Thing`; the last real FOLIO node before it is the
  branch (e.g. Eviction → Regulatory Events → Event → owl:Thing ⇒ branch "Event").
  `get_folio_branches()` returns objects whose `.label` is None — don't rely on it.
- A concept is "well-rooted" iff that walk reaches owl:Thing through ≥1 real node —
  a good deterministic sanity gate (orphan/typo IRIs fail it).

**Reuse:** this is the deterministic **lane-1** half of the gestalt (folio-python for
mechanical checks; FOLIO-MCP only for semantic judgment). Any campaign oracle that
validates mapped IRIs can copy `folio_check.py`'s `check_iri` / `branch_of`.

## 3. Bonus: the "Standards Compatibility" taxonomy branch (for II.6.0)

While verifying the above, confirmed `folio.get_standards_compatibilities()` returns
**868 concepts** under a top-level **"Standards Compatibility"** branch
(IRI `RB4cFSLB4xvycDlKv73dOg6`) — external standards (e.g. LegalXML OASIS) are
imported as a **node-per-external-concept subtree**, not annotation properties. This
corrected the standards→OWL investigation (folio-mapper II.6.0): the SSSOM→OWL
converter should mint nodes under that branch, following the OASIS precedent. Beware:
"branch" in the plan means a **taxonomy** branch, not a git branch.
