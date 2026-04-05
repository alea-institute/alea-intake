# Phase 7: Output & Export - Research

**Researched:** 2026-04-05
**Domain:** Structured legal document generation, template rendering, multi-format export
**Confidence:** HIGH

## Summary

Phase 7 transforms the analysis pipeline's structured data (claims, elements, fact mappings, gaps, authorities) into configurable output documents -- CIRAC-format case memos, triage/routing recommendations, and prioritized action items -- with per-deployment-type profiles controlling content, language complexity, and section visibility. The canonical output format is structured Markdown, rendered to PDF (WeasyPrint), DOCX (python-docx), and JSON via adapter pattern.

The technology stack is well-understood. python-docx 1.2.0 and Jinja2 3.1.6 are already installed. markdown-it-py 4.0.0 is available for Markdown-to-HTML conversion. WeasyPrint 68.1 is NOT installed but all system dependencies (Pango, HarfBuzz, libjpeg, libopenjp2, libffi) are present on the target machine. WeasyPrint supports CSS Paged Media for professional legal formatting (page numbers, headers/footers, page breaks, TOC via CSS counters). eyecite 2.7.6 is available for citation extraction but Bluebook formatting must be hand-built (no Python library provides automatic Bluebook compliance).

The architecture follows the established service-class pattern with Pydantic schemas for structured data contracts and async SQLAlchemy for persistence. Output generation is triggered after analysis convergence and produces OutputDocument records with rendered content stored per format.

**Primary recommendation:** Build a three-layer architecture: (1) DataAssembler that queries all analysis/research models into a unified OutputContext Pydantic model, (2) TemplateEngine that renders OutputContext through Jinja2 templates per profile into Markdown, (3) ExportAdapter classes (PDF, DOCX, JSON) that convert Markdown to final format. All three layers are pure functions of their inputs, making them independently testable.

<user_constraints>
## User Constraints (from CONTEXT.md)

### Locked Decisions
- **D-01:** Case memo in CIRAC format -- Conclusion (executive summary) first, then per-claim sections: Issue, Rule (authorities with binding/persuasive indicators), Application (fact-to-element mapping with confidence), Conclusion. Grouped by jurisdiction for multi-jurisdiction cases.
- **D-02:** Multi-factor triage/routing with ranked recommendations. Score destinations by: (1) practice area match from FOLIO taxonomy, (2) jurisdiction match, (3) complexity/urgency assessment, (4) org-specific routing rules. Ranked list with scores and rationale.
- **D-03:** Prioritized action item checklist grouped by category: (1) Documents to gather, (2) Follow-up steps with deadlines, (3) Referrals. Each item has priority (urgent/important/helpful), deadline if applicable, and the claim/element it supports.
- **D-04:** Template profiles with section visibility rules. Three built-in profiles: law_firm (full CIRAC memo + all authorities + detailed action items + professional legal language), legal_aid (triage routing + simplified memo + referrals + accessible language with legal terms explained), court_self_help (plain-language guidance at ~8th grade reading level + forms checklist + next steps). Org selects profile + can customize section visibility.
- **D-05:** LLM adapts language complexity per profile. Law firm = professional legal language with citations. Legal aid = accessible with terms explained. Court self-help = plain language at ~8th grade level.
- **D-06:** A single matter can generate multiple output profiles simultaneously. Multiple profiles are first-class, not a workaround.
- **D-07:** Actionable gap summary per claim (inline) AND a consolidated Gap Report Appendix. Within each claim's CIRAC section: "Gaps & Open Questions" subsection lists unsupported elements, unanswered questions, weak mappings -- each linking to an action item. Appendix consolidates all gaps for easy review/remedy. Executive summary includes overall completeness score.
- **D-08:** Markdown rendering pipeline. Generate output as structured Markdown (canonical format). Render to: PDF via WeasyPrint (CSS-styled HTML to PDF), DOCX via python-docx (already installed), JSON as structured data matching internal schema. Markdown is single source of truth; renderers are output adapters.
- **D-09:** Professional legal formatting. PDF/DOCX follow legal document conventions: numbered paragraphs, Bluebook citation formatting, table of contents for long documents, headers/footers with matter info. Configurable org branding (logo, colors) via org settings.

### Claude's Discretion
- Specific CIRAC section templates and Markdown structure
- Triage scoring algorithm weights and defaults
- WeasyPrint CSS stylesheet design
- TOC generation logic for long documents
- Org branding configuration schema

### Deferred Ideas (OUT OF SCOPE)
None -- discussion stayed within phase scope
</user_constraints>

<phase_requirements>
## Phase Requirements

| ID | Description | Research Support |
|----|-------------|------------------|
| OUTPUT-01 | System generates structured case memos mapping facts to claims to elements to authorities to jurisdictions | DataAssembler + CIRAC Jinja2 templates + OutputContext schema; all upstream models (AnalysisClaim, ClaimElement, FactClaimMapping, Authority) available via SQLAlchemy |
| OUTPUT-02 | System generates triage/routing recommendations (which practice area, which attorney, which program) | TriageScorer service using FOLIO taxonomy IRI matching + ResultRanker pattern for multi-signal scoring |
| OUTPUT-03 | System generates action items (documents to gather, follow-up steps, referrals) | ActionItemGenerator derives from AnalysisGap + FollowUpQuestion models; LLM categorizes and prioritizes |
| OUTPUT-04 | Output format is configurable per deployment (law firms get memos, legal aid gets triage, courts get self-help routing) | OutputProfile Pydantic config with section_visibility dict + language_level enum; stored in OrganizationConfig |
| OUTPUT-05 | Output includes gap analysis showing what evidence is missing and what questions remain | GapReportBuilder consolidates AnalysisGap records per claim + appendix; completeness score from ConvergenceEvaluator signals |
| INTEGRATE-06 | Export formats: PDF, DOCX, JSON | Three ExportAdapter classes: PDFAdapter (WeasyPrint), DOCXAdapter (python-docx), JSONAdapter (Pydantic serialization) |
</phase_requirements>

## Standard Stack

### Core
| Library | Version | Purpose | Why Standard |
|---------|---------|---------|--------------|
| weasyprint | 68.1 | HTML+CSS to PDF rendering | Industry standard for server-side PDF from HTML; supports CSS Paged Media (headers, footers, page numbers, TOC); no headless browser needed |
| python-docx | 1.2.0 | DOCX document generation | Already installed; direct XML manipulation of .docx format; supports headers, footers, styles, numbered paragraphs |
| Jinja2 | 3.1.6 | Template engine for Markdown/HTML generation | Already installed; standard Python templating; autoescaping, template inheritance, macros |
| markdown-it-py | 4.0.0 | Markdown to HTML conversion | Already installed; 100% CommonMark compliant; plugin architecture for tables, footnotes |
| pydantic | 2.12.5 | Structured output schemas and validation | Already installed; project standard for all data contracts |
| SQLAlchemy | 2.0.49 | Async DB access for analysis data loading | Already installed; project standard ORM |
| eyecite | 2.7.6 | Legal citation extraction and parsing | Already in pyproject.toml; extracts/parses citations from text for Bluebook formatting |

### Supporting
| Library | Version | Purpose | When to Use |
|---------|---------|---------|-------------|
| mdit-py-plugins | (latest) | markdown-it-py extensions (tables, footnotes) | When rendering Markdown tables and footnotes in CIRAC memos |
| alea-llm-client | 0.3.3 | LLM calls for language adaptation | Already installed; used by LLMService for profile-specific language rewriting |

### Alternatives Considered
| Instead of | Could Use | Tradeoff |
|------------|-----------|----------|
| WeasyPrint | reportlab | reportlab requires programmatic layout (no CSS); WeasyPrint lets us reuse CSS styling for both PDF and web |
| WeasyPrint | wkhtmltopdf / Playwright | External binary / headless browser; heavier deployment; WeasyPrint is pure Python with C deps already present |
| python-docx | docxtpl | docxtpl is template-based but less control over programmatic TOC and numbering; python-docx gives direct XML access |
| markdown-it-py | mistune | mistune is faster but lacks CommonMark compliance and plugin ecosystem |

**Installation:**
```bash
pip install weasyprint>=68.0 mdit-py-plugins
```

**Version verification:** WeasyPrint 68.1 confirmed on PyPI (released 2026-02-06). python-docx 1.2.0 confirmed installed. Jinja2 3.1.6 confirmed installed. markdown-it-py 4.0.0 confirmed installed.

## Architecture Patterns

### Recommended Project Structure
```
backend/app/
├── models/
│   └── output.py                    # OutputDocument, OutputProfile DB models
├── services/
│   └── output/
│       ├── __init__.py
│       ├── schemas.py               # OutputContext, CIRACSection, TriageResult, ActionItem Pydantic models
│       ├── data_assembler.py        # Queries all analysis/research models into OutputContext
│       ├── template_engine.py       # Jinja2 template rendering per profile
│       ├── language_adapter.py      # LLM language complexity rewriting
│       ├── triage_scorer.py         # Multi-factor triage/routing scoring
│       ├── action_item_generator.py # Gap-to-action-item transformation
│       ├── gap_report_builder.py    # Inline + appendix gap consolidation
│       ├── export/
│       │   ├── __init__.py
│       │   ├── base.py              # ExportAdapter ABC
│       │   ├── pdf_adapter.py       # WeasyPrint HTML→PDF with CSS
│       │   ├── docx_adapter.py      # python-docx DOCX generation
│       │   └── json_adapter.py      # Pydantic model serialization
│       └── templates/
│           ├── cirac_memo.md.j2     # CIRAC case memo template
│           ├── triage_report.md.j2  # Triage/routing template
│           ├── action_items.md.j2   # Action items checklist template
│           ├── gap_appendix.md.j2   # Gap Report Appendix template
│           └── css/
│               └── legal_pdf.css    # CSS for WeasyPrint PDF rendering
├── routers/
│   └── output.py                    # Output generation + export endpoints
```

### Pattern 1: Three-Layer Output Pipeline
**What:** DataAssembler -> TemplateEngine -> ExportAdapter chain where each layer is a pure function of its inputs.
**When to use:** All output generation follows this pattern.
**Example:**
```python
# Source: project pattern (service + Pydantic schema contracts)
class DataAssembler:
    """Queries all analysis/research data into a unified OutputContext."""

    def __init__(self, db_session: AsyncSession):
        self._session = db_session

    async def assemble(self, run_id: int, intake_id: int) -> OutputContext:
        """Load claims, elements, mappings, gaps, authorities into OutputContext."""
        claims = await self._load_claims(run_id)
        elements = await self._load_elements(claims)
        mappings = await self._load_mappings(run_id)
        gaps = await self._load_gaps(run_id)
        authorities = await self._load_authorities(intake_id)
        facts = await self._load_facts(intake_id)
        return OutputContext(
            claims=claims, elements=elements, mappings=mappings,
            gaps=gaps, authorities=authorities, facts=facts,
            # ... metadata
        )


class TemplateEngine:
    """Renders OutputContext through Jinja2 templates per profile."""

    def __init__(self, template_dir: str | None = None):
        self._env = Environment(
            loader=FileSystemLoader(template_dir or DEFAULT_TEMPLATE_DIR),
            autoescape=False,  # Markdown output, not HTML
        )

    def render_memo(self, context: OutputContext, profile: OutputProfile) -> str:
        """Render CIRAC memo as Markdown."""
        template = self._env.get_template("cirac_memo.md.j2")
        return template.render(ctx=context, profile=profile)


class ExportAdapter(ABC):
    """Base class for format-specific export."""

    @abstractmethod
    async def export(self, markdown: str, context: OutputContext, profile: OutputProfile) -> bytes:
        """Convert Markdown to target format bytes."""
        ...
```

### Pattern 2: Deployment Profile Configuration
**What:** OutputProfile stored as JSON in OrganizationConfig, controls section visibility and language level.
**When to use:** Every output generation reads the active profile.
**Example:**
```python
class OutputProfile(BaseModel):
    """Per-deployment output profile configuration (D-04)."""

    profile_type: Literal["law_firm", "legal_aid", "court_self_help"]
    language_level: Literal["professional", "accessible", "plain"]
    sections: dict[str, bool] = Field(default_factory=lambda: {
        "executive_summary": True,
        "cirac_memo": True,
        "triage_routing": True,
        "action_items": True,
        "gap_appendix": True,
        "authorities_table": True,
    })
    reading_grade_level: int | None = None  # 8 for court_self_help
    org_branding: OrgBranding | None = None

# Default profiles
LAW_FIRM_PROFILE = OutputProfile(
    profile_type="law_firm",
    language_level="professional",
    sections={"executive_summary": True, "cirac_memo": True,
              "triage_routing": False, "action_items": True,
              "gap_appendix": True, "authorities_table": True},
)
LEGAL_AID_PROFILE = OutputProfile(
    profile_type="legal_aid",
    language_level="accessible",
    sections={"executive_summary": True, "cirac_memo": True,
              "triage_routing": True, "action_items": True,
              "gap_appendix": True, "authorities_table": False},
)
COURT_SELF_HELP_PROFILE = OutputProfile(
    profile_type="court_self_help",
    language_level="plain",
    reading_grade_level=8,
    sections={"executive_summary": True, "cirac_memo": False,
              "triage_routing": False, "action_items": True,
              "gap_appendix": False, "authorities_table": False},
)
```

### Pattern 3: Simultaneous Multi-Profile Generation (D-06)
**What:** A single endpoint triggers generation of multiple output profiles for one matter.
**When to use:** When matter needs both lawyer and consumer versions.
**Example:**
```python
async def generate_outputs(
    run_id: int, intake_id: int, profiles: list[OutputProfile],
    db_session: AsyncSession, llm_service: LLMService,
) -> list[OutputDocument]:
    """Generate multiple output documents in parallel."""
    assembler = DataAssembler(db_session)
    context = await assembler.assemble(run_id, intake_id)  # Single data load

    # Generate each profile (LLM adaptation is profile-specific)
    results = []
    for profile in profiles:
        adapted_context = await language_adapter.adapt(context, profile, llm_service)
        markdown = template_engine.render_memo(adapted_context, profile)
        doc = OutputDocument(
            run_id=run_id, intake_id=intake_id,
            profile_type=profile.profile_type,
            markdown_content=markdown,
        )
        db_session.add(doc)
        results.append(doc)
    await db_session.flush()
    return results
```

### Pattern 4: CSS Paged Media for Legal PDF
**What:** WeasyPrint CSS stylesheet using @page rules for legal formatting.
**When to use:** PDF export.
**Example:**
```css
/* Source: WeasyPrint CSS Paged Media specification */
@page {
    size: letter;
    margin: 1in 1in 1.25in 1in;

    @top-center {
        content: string(matter-title);
        font-size: 9pt;
        color: #666;
    }
    @bottom-center {
        content: "Page " counter(page) " of " counter(pages);
        font-size: 9pt;
    }
    @bottom-right {
        content: string(org-name);
        font-size: 9pt;
        color: #666;
    }
}

@page :first {
    @top-center { content: none; }
    @bottom-center { content: none; }
    counter-reset: page 0;
}

h1 { string-set: matter-title content(); }
.org-name { string-set: org-name content(); }
h2 { page-break-before: auto; }
.page-break { page-break-after: always; }

/* Numbered paragraphs for legal formatting */
body { counter-reset: paragraph; }
.numbered-para::before {
    counter-increment: paragraph;
    content: counter(paragraph) ". ";
    font-weight: bold;
}
```

### Anti-Patterns to Avoid
- **Embedding format-specific logic in data assembly:** The DataAssembler must produce a format-neutral OutputContext. All format decisions happen in templates and adapters. Otherwise every new format requires changes to the data layer.
- **Generating each format from scratch:** Markdown is the single source of truth (D-08). PDF and DOCX are derived from Markdown, not generated independently. This prevents content divergence between formats.
- **Synchronous LLM calls for language adaptation:** Language adaptation requires LLM calls which are I/O-bound. Use async patterns consistent with the project. When generating multiple profiles, the data assembly is done once; only the LLM language adaptation step runs per profile.
- **Storing rendered output as files on disk:** Store rendered bytes in DB (OutputDocument model) for tenant isolation and consistent backup/delete semantics. File export is a download endpoint, not a stored file.

## Don't Hand-Roll

| Problem | Don't Build | Use Instead | Why |
|---------|-------------|-------------|-----|
| HTML to PDF conversion | Custom headless browser rendering | WeasyPrint `HTML(string=html).write_pdf()` | CSS Paged Media support, no browser dependency, deterministic output |
| Markdown to HTML conversion | Custom regex parser | markdown-it-py `MarkdownIt().render(md)` | CommonMark compliant, extensible via plugins, handles edge cases |
| DOCX generation from scratch | Manual XML construction | python-docx `Document()` API | Handles complex OOXML relationships, styles, headers/footers |
| Citation extraction | Custom regex for legal citations | eyecite `get_citations(text)` | Trained on 55M+ citations, handles all Bluebook forms (full, short, supra, id.) |
| Template rendering | String concatenation / f-strings | Jinja2 `Environment.get_template().render()` | Template inheritance, macros, filters, autoescaping, caching |
| Completeness scoring | Custom calculation | Reuse ConvergenceEvaluator signals | Already computes coverage_pct from satisfied elements vs total |
| Authority ranking in output | Custom sorting | Reuse ResultRanker from Phase 6 | Already implements 5-signal scoring + binding strength determination |

**Key insight:** The upstream analysis and research phases have already built the hard parts (claim/element graphs, authority verification, gap analysis, convergence scoring). This phase is primarily about presentation and formatting -- assembling existing data into templates and rendering to multiple formats. Resist the urge to re-derive analytical results.

## Common Pitfalls

### Pitfall 1: WeasyPrint System Dependencies Missing
**What goes wrong:** `pip install weasyprint` succeeds but PDF rendering fails at runtime with Pango/Cairo/HarfBuzz errors.
**Why it happens:** WeasyPrint is a Python package but depends on system C libraries (libpango, libcairo, libharfbuzz) that pip cannot install.
**How to avoid:** Verify system deps are present BEFORE adding weasyprint to pyproject.toml. On Ubuntu/Debian: `apt install libpango-1.0-0 libpangoft2-1.0-0 libharfbuzz-subset0`. All are confirmed present on this machine.
**Warning signs:** `ImportError` or `OSError` mentioning pango, cairo, or gobject at import time.

### Pitfall 2: python-docx TOC Requires Word Application
**What goes wrong:** python-docx can insert a TOC field code placeholder, but page numbers in the TOC are NOT populated until the document is opened in Microsoft Word or LibreOffice and fields are updated.
**Why it happens:** TOC page numbers require a layout engine to compute; python-docx manipulates XML but does not perform page layout.
**How to avoid:** For DOCX: insert a TOC field placeholder that auto-updates when opened. For PDF: use CSS-based TOC with WeasyPrint (target-counter or manual heading list). Document this limitation clearly -- DOCX TOC requires opening in Word to see page numbers.
**Warning signs:** TOC appears blank or shows "Error! Bookmark not defined" in generated DOCX.

### Pitfall 3: LLM Language Adaptation Inconsistency
**What goes wrong:** LLM rewrites legal content at different reading levels but introduces factual errors, drops citations, or changes legal meanings.
**Why it happens:** Language simplification models may not understand legal precision requirements. "Negligence" simplified to "fault" changes legal meaning.
**How to avoid:** (1) Provide LLM with explicit instructions to preserve all citation strings, legal terms of art, and element names verbatim. (2) Use a structured approach: LLM rewrites explanatory text but legal terms remain as-is with inline definitions. (3) Post-process to verify all citations from the source survive in the output.
**Warning signs:** Missing citations in simplified output; legal terms replaced with colloquial equivalents.

### Pitfall 4: WeasyPrint CSS Rendering Differences
**What goes wrong:** CSS that renders correctly in a browser does not render identically in WeasyPrint.
**Why it happens:** WeasyPrint implements its own CSS engine, not a browser engine. Some CSS properties (advanced grid, some flexbox edge cases) may behave differently.
**How to avoid:** Use WeasyPrint-tested CSS patterns: flexbox for simple layouts, CSS tables for data, @page rules for headers/footers. Test PDF output early and iterate on CSS. Prefer `@page` margin boxes over `position: fixed` for repeating headers/footers.
**Warning signs:** Layout breaks, missing elements, or different spacing in PDF vs browser preview.

### Pitfall 5: Multi-Jurisdiction Content Ordering
**What goes wrong:** Claims spanning multiple jurisdictions produce a confusing output where the reader cannot track which jurisdiction applies to which analysis.
**Why it happens:** Flat claim lists without jurisdiction grouping interleave California and New York analyses unpredictably.
**How to avoid:** Group CIRAC sections by jurisdiction first, then by claim within each jurisdiction (per D-01). Use clear jurisdiction headers and ensure every authority citation includes its jurisdiction. Template must enforce this grouping order.
**Warning signs:** Reader confusion in test output; same claim appears multiple times without clear jurisdiction context.

### Pitfall 6: Overly Large Markdown for Single-Pass HTML Rendering
**What goes wrong:** Complex cases with 10+ claims, dozens of authorities, and extensive gap analysis produce Markdown documents that are very large, causing WeasyPrint to consume excessive memory or time.
**Why it happens:** WeasyPrint loads the entire HTML document into memory for layout computation.
**How to avoid:** Set reasonable limits (warn on documents > 100 pages). For very large cases, consider section-by-section PDF generation and concatenation. In practice, most intake memos will be 5-20 pages.
**Warning signs:** PDF generation taking > 30 seconds; memory consumption spikes during rendering.

## Code Examples

### WeasyPrint PDF Generation
```python
# Source: WeasyPrint 68.1 API documentation
# https://doc.courtbouillon.org/weasyprint/stable/api_reference.html
from weasyprint import HTML
from pathlib import Path

async def render_pdf(html_content: str, css_path: Path | None = None) -> bytes:
    """Render HTML string to PDF bytes via WeasyPrint."""
    html = HTML(string=html_content, base_url=str(css_path.parent) if css_path else None)
    if css_path:
        from weasyprint import CSS
        css = CSS(filename=str(css_path))
        return html.write_pdf(stylesheets=[css])
    return html.write_pdf()
```

### Markdown to HTML via markdown-it-py
```python
# Source: markdown-it-py 4.0.0 documentation
# https://markdown-it-py.readthedocs.io/en/latest/using.html
from markdown_it import MarkdownIt

def markdown_to_html(md_content: str) -> str:
    """Convert Markdown to HTML with table and footnote support."""
    md = MarkdownIt("commonmark", {"breaks": True, "html": True}).enable("table")
    return md.render(md_content)
```

### python-docx Legal Document Generation
```python
# Source: python-docx 1.2.0 documentation
# https://python-docx.readthedocs.io/en/latest/user/quickstart.html
from docx import Document
from docx.shared import Pt, Inches
from docx.enum.text import WD_ALIGN_PARAGRAPH

def create_legal_docx(title: str, sections: list[dict]) -> bytes:
    """Create a DOCX with legal formatting."""
    doc = Document()

    # Set default font
    style = doc.styles["Normal"]
    font = style.font
    font.name = "Times New Roman"
    font.size = Pt(12)

    # Title
    heading = doc.add_heading(title, level=0)
    heading.alignment = WD_ALIGN_PARAGRAPH.CENTER

    # Headers/footers
    section = doc.sections[0]
    header = section.header
    header_para = header.paragraphs[0]
    header_para.text = title

    footer = section.footer
    footer_para = footer.paragraphs[0]
    footer_para.text = "Confidential - Attorney Work Product"
    footer_para.alignment = WD_ALIGN_PARAGRAPH.CENTER

    # Add sections
    for sec in sections:
        doc.add_heading(sec["heading"], level=sec.get("level", 1))
        for para_text in sec.get("paragraphs", []):
            doc.add_paragraph(para_text)

    # Return bytes
    from io import BytesIO
    buffer = BytesIO()
    doc.save(buffer)
    return buffer.getvalue()
```

### python-docx TOC Placeholder
```python
# Source: python-docx issue #36 workaround
# https://github.com/python-openxml/python-docx/issues/36
from docx.oxml.ns import qn
from docx.oxml import OxmlElement

def add_toc_placeholder(doc: Document) -> None:
    """Insert a TOC field that Word will populate on open."""
    paragraph = doc.add_paragraph()
    run = paragraph.add_run()
    fld_char_begin = OxmlElement("w:fldChar")
    fld_char_begin.set(qn("w:fldCharType"), "begin")
    run._r.append(fld_char_begin)

    instr_text = OxmlElement("w:instrText")
    instr_text.set(qn("xml:space"), "preserve")
    instr_text.text = ' TOC \\o "1-3" \\h \\z \\u '
    run._r.append(instr_text)

    fld_char_separate = OxmlElement("w:fldChar")
    fld_char_separate.set(qn("w:fldCharType"), "separate")
    run._r.append(fld_char_separate)

    # Placeholder text visible before field update
    fld_text = OxmlElement("w:t")
    fld_text.text = "Table of Contents (update field to populate)"
    run._r.append(fld_text)

    fld_char_end = OxmlElement("w:fldChar")
    fld_char_end.set(qn("w:fldCharType"), "end")
    run._r.append(fld_char_end)
```

### Jinja2 CIRAC Template Pattern
```jinja2
{# cirac_memo.md.j2 -- CIRAC format case memo #}
# {{ ctx.matter_title }}

**Prepared:** {{ ctx.generated_at | datetimeformat }}
**Matter ID:** {{ ctx.intake_id }}
**Profile:** {{ profile.profile_type }}

---

## Executive Summary

{{ ctx.executive_summary }}

**Overall Completeness:** {{ "%.0f" | format(ctx.completeness_score * 100) }}%

---

{% for jurisdiction, claims in ctx.claims_by_jurisdiction.items() %}
## {{ jurisdiction }}

{% for claim in claims %}
### {{ claim.claim_name }}

#### Issue
{{ claim.issue_statement }}

#### Rule
{% for authority in claim.authorities %}
- {% if authority.binding_strength == "binding" %}**[Binding]**{% elif authority.binding_strength == "persuasive" %}*[Persuasive]*{% else %}[Secondary]{% endif %} {{ authority.citation }}{% if authority.verified %} (Verified){% else %} (Unverified){% endif %}
  {{ authority.excerpt | truncate(200) }}
{% endfor %}

#### Application
{% for element in claim.elements %}
- **{{ element.element_name }}**: {% if element.is_satisfied %}Supported ({{ "%.0f" | format(element.satisfaction_confidence * 100) }}% confidence){% else %}**Unsupported** -- gap identified{% endif %}
  {% for mapping in element.fact_mappings %}
  - Fact: "{{ mapping.fact_text | truncate(150) }}" ({{ "%.0f" | format(mapping.confidence * 100) }}% confidence)
  {% endfor %}
{% endfor %}

{% if claim.gaps %}
#### Gaps & Open Questions
{% for gap in claim.gaps %}
- **{{ gap.gap_type | replace("_", " ") | title }}**: {{ gap.description }}
  {% if gap.action_item_ref %}*See Action Item #{{ gap.action_item_ref }}*{% endif %}
{% endfor %}
{% endif %}

#### Conclusion
{{ claim.conclusion }}

{% endfor %}
{% endfor %}
```

### eyecite Citation Extraction
```python
# Source: eyecite 2.7.6
# https://github.com/freelawproject/eyecite
from eyecite import get_citations, clean_text

def extract_citations(text: str) -> list[dict]:
    """Extract legal citations from text for Bluebook formatting."""
    cleaned = clean_text(text, ["all_whitespace", "underscores"])
    citations = get_citations(cleaned)
    return [
        {
            "citation_text": str(c),
            "reporter": getattr(c, "reporter", None),
            "volume": getattr(c, "volume", None),
            "page": getattr(c, "page", None),
            "year": getattr(c, "year", None),
        }
        for c in citations
    ]
```

## State of the Art

| Old Approach | Current Approach | When Changed | Impact |
|--------------|------------------|--------------|--------|
| wkhtmltopdf for HTML-to-PDF | WeasyPrint (pure Python + C deps) | ~2020 onwards | No headless browser dependency; better CSS Paged Media support |
| ReportLab for programmatic PDF | WeasyPrint for template-driven; ReportLab for data-heavy | Coexistence | WeasyPrint better for document-style PDF; ReportLab better for charts/forms |
| python-docx 0.x | python-docx 1.2.0 | 2024 | Stable API; header/footer support; modern Python typing |
| Markdown (python library) | markdown-it-py 4.0.0 | 2025 | CommonMark compliant; pluggable; faster; better maintained |
| Manual citation regex | eyecite 2.7.6 | Ongoing | Trained on 55M+ citations; handles all Bluebook forms |
| Bluebook 21st edition | Bluebook 22nd edition | May 2025 | Major revision to Rule 18 (digital/AI sources); new abbreviation tables |

**Deprecated/outdated:**
- wkhtmltopdf: Unmaintained; depends on old WebKit fork; WeasyPrint is the modern replacement.
- pdfkit: Python wrapper for wkhtmltopdf; same issues.
- markdown (Python Markdown library): Less actively maintained than markdown-it-py; not CommonMark compliant.

## Open Questions

1. **Bluebook formatting completeness**
   - What we know: eyecite can extract and parse citations. No Python library provides automatic Bluebook formatting (e.g., italicization rules, signal words, short-form generation).
   - What's unclear: How much Bluebook formatting the LLM can handle vs how much must be rule-based.
   - Recommendation: Use eyecite for citation extraction/parsing. Build a lightweight BluebookFormatter utility for the most common rules (case italicization, statute formatting, signal words). Let the LLM handle contextual formatting in the memo text. Mark as best-effort -- perfect Bluebook compliance requires human review.

2. **Org branding configuration storage**
   - What we know: OrganizationConfig has JSON columns for settings. Branding needs logo (binary), colors (strings), fonts (strings).
   - What's unclear: Whether to store logo bytes in DB vs filesystem.
   - Recommendation: Store logo path reference in org settings JSON; actual logo file in the existing upload directory (`{upload_dir}/{org_slug}/branding/logo.png`). Colors and fonts in JSON. This aligns with existing file storage patterns.

3. **Reading level validation for court_self_help profile**
   - What we know: D-05 specifies ~8th grade reading level for court_self_help.
   - What's unclear: Whether to validate reading level post-LLM-adaptation or trust the prompt.
   - Recommendation: Trust the LLM prompt for MVP. Optionally implement Flesch-Kincaid grade level check as a post-generation validation. textstat library can compute this but is not currently installed.

## Environment Availability

| Dependency | Required By | Available | Version | Fallback |
|------------|------------|-----------|---------|----------|
| libpango-1.0-0 | WeasyPrint PDF | Yes | 1.56.3 | -- |
| libpangoft2-1.0-0 | WeasyPrint PDF | Yes | 1.56.3 | -- |
| libharfbuzz-subset0 | WeasyPrint PDF | Yes | 10.2.0 | -- |
| libjpeg | WeasyPrint PDF | Yes | 8c-2 | -- |
| libopenjp2-7 | WeasyPrint PDF | Yes | 2.5.3 | -- |
| libffi-dev | WeasyPrint PDF | Yes | 3.5.2 | -- |
| python-docx | DOCX export | Yes | 1.2.0 | -- |
| Jinja2 | Template rendering | Yes | 3.1.6 | -- |
| markdown-it-py | Markdown to HTML | Yes | 4.0.0 | -- |
| eyecite | Citation parsing | Yes | 2.7.6 | -- |
| weasyprint (pip) | PDF rendering | No (not installed) | -- | Must be added to pyproject.toml |

**Missing dependencies with no fallback:**
- `weasyprint` pip package: Must be added to pyproject.toml dependencies and installed. System C dependencies are all present.

**Missing dependencies with fallback:**
- `mdit-py-plugins`: Not installed but optional. markdown-it-py tables can be enabled without it via `.enable("table")`. Only needed for footnotes.

## Validation Architecture

### Test Framework
| Property | Value |
|----------|-------|
| Framework | pytest 8.x + pytest-asyncio 0.24.x |
| Config file | `backend/pyproject.toml` [tool.pytest.ini_options] |
| Quick run command | `cd backend && .venv/bin/python -m pytest tests/test_output.py -x --timeout=30` |
| Full suite command | `cd backend && .venv/bin/python -m pytest tests/ --timeout=30` |

### Phase Requirements to Test Map
| Req ID | Behavior | Test Type | Automated Command | File Exists? |
|--------|----------|-----------|-------------------|-------------|
| OUTPUT-01 | CIRAC memo generation with claims/elements/authorities/jurisdictions | unit | `pytest tests/test_output_memo.py -x` | Wave 0 |
| OUTPUT-02 | Triage/routing recommendations with scored destinations | unit | `pytest tests/test_output_triage.py -x` | Wave 0 |
| OUTPUT-03 | Action items generation grouped by category with priorities | unit | `pytest tests/test_output_actions.py -x` | Wave 0 |
| OUTPUT-04 | Profile-based section visibility (law_firm, legal_aid, court_self_help) | unit | `pytest tests/test_output_profiles.py -x` | Wave 0 |
| OUTPUT-05 | Gap analysis in output (inline per claim + appendix + completeness score) | unit | `pytest tests/test_output_gaps.py -x` | Wave 0 |
| INTEGRATE-06 | PDF/DOCX/JSON export from Markdown | unit + integration | `pytest tests/test_output_export.py -x` | Wave 0 |

### Sampling Rate
- **Per task commit:** `cd backend && .venv/bin/python -m pytest tests/test_output*.py -x --timeout=30`
- **Per wave merge:** `cd backend && .venv/bin/python -m pytest tests/ --timeout=30`
- **Phase gate:** Full suite green before `/gsd:verify-work`

### Wave 0 Gaps
- [ ] `tests/test_output_memo.py` -- DataAssembler + CIRAC template rendering
- [ ] `tests/test_output_triage.py` -- TriageScorer multi-factor scoring
- [ ] `tests/test_output_actions.py` -- ActionItemGenerator from gaps
- [ ] `tests/test_output_profiles.py` -- Profile configuration + section visibility
- [ ] `tests/test_output_gaps.py` -- Gap report builder (inline + appendix)
- [ ] `tests/test_output_export.py` -- PDF/DOCX/JSON export adapters
- [ ] Framework install: `pip install weasyprint>=68.0` -- WeasyPrint not yet in venv

## Sources

### Primary (HIGH confidence)
- WeasyPrint 68.1 API documentation: https://doc.courtbouillon.org/weasyprint/stable/api_reference.html -- HTML class, write_pdf method, CSS Paged Media support
- python-docx 1.2.0 documentation: https://python-docx.readthedocs.io/en/latest/ -- headers/footers, styles, document generation
- markdown-it-py 4.0.0 documentation: https://markdown-it-py.readthedocs.io/en/latest/using.html -- render API, plugin system
- eyecite GitHub: https://github.com/freelawproject/eyecite -- citation extraction API, 55M+ training citations
- Jinja2 3.1.6 documentation (installed, well-known) -- template inheritance, macros, filters
- Existing codebase: `backend/app/models/analysis.py`, `backend/app/models/research.py`, `backend/app/services/analysis/orchestrator.py` -- upstream data models

### Secondary (MEDIUM confidence)
- WeasyPrint CSS Paged Media patterns: https://www.naveenmk.me/blog/weasyprint/ -- headers/footers, page numbers, running elements
- python-docx TOC workaround: https://github.com/python-openxml/python-docx/issues/36 -- XML-based TOC field insertion
- WeasyPrint + Jinja2 integration: https://medium.com/@engineering_holistic_ai/using-weasyprint-and-jinja2-to-create-pdfs-from-html-and-css-267127454dbd

### Tertiary (LOW confidence)
- Bluebook 22nd Edition changes (May 2025): General awareness of Rule 18 rewrite for digital/AI sources. No Python library for automatic Bluebook compliance; citation formatting must be partially hand-built.

## Metadata

**Confidence breakdown:**
- Standard stack: HIGH -- all libraries verified installed or installable; system deps confirmed present; APIs verified against current documentation
- Architecture: HIGH -- follows established project patterns (service classes, Pydantic schemas, async SQLAlchemy); three-layer pipeline is well-understood
- Pitfalls: HIGH -- WeasyPrint system deps verified on target; python-docx TOC limitation documented in official issues; LLM adaptation risks well-characterized from project experience
- Export formats: HIGH -- WeasyPrint API confirmed; python-docx API confirmed; JSON is native Pydantic serialization
- Bluebook formatting: MEDIUM -- eyecite handles extraction; formatting rules are complex and no automated solution exists; LLM-assisted approach is pragmatic

**Research date:** 2026-04-05
**Valid until:** 2026-05-05 (stable domain; library versions unlikely to change significantly)
