"""Output API endpoints: generate, retrieve, list, and export output documents.

Orchestrates the full output pipeline per request:
  1. DataAssembler loads analysis/research data into OutputContext
  2. TriageScorer produces routing recommendations
  3. ActionItemGenerator creates prioritized action items
  4. LanguageAdapter adapts language per profile (non-professional only)
  5. TemplateEngine renders Markdown from OutputContext
  6. Export adapters convert to PDF/DOCX/JSON on demand

Multiple output profiles per matter supported in a single API call (D-06).
"""

from __future__ import annotations

import logging
from datetime import datetime

from fastapi import APIRouter, Depends, HTTPException, status
from fastapi.responses import StreamingResponse
from pydantic import BaseModel
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.permissions import get_current_active_user
from app.db.session import get_tenant_session
from app.models.output import OutputDocument
from app.models.user import User
from app.services.output.action_item_generator import ActionItemGenerator
from app.services.output.data_assembler import DataAssembler
from app.services.output.language_adapter import LanguageAdapter
from app.services.output.export.docx_adapter import DOCXAdapter
from app.services.output.export.json_adapter import JSONAdapter
from app.services.output.export.pdf_adapter import PDFAdapter
from app.services.output.schemas import (
    LAW_FIRM_PROFILE,
    COURT_SELF_HELP_PROFILE,
    LEGAL_AID_PROFILE,
    OutputProfile,
)
from app.services.output.template_engine import TemplateEngine
from app.services.output.triage_scorer import TriageScorer

logger = logging.getLogger(__name__)

router = APIRouter(prefix="/api/v1/output", tags=["output"])

# ---------------------------------------------------------------------------
# Request / response schemas
# ---------------------------------------------------------------------------

_PROFILE_MAP: dict[str, OutputProfile] = {
    "law_firm": LAW_FIRM_PROFILE,
    "legal_aid": LEGAL_AID_PROFILE,
    "court_self_help": COURT_SELF_HELP_PROFILE,
}


class GenerateRequest(BaseModel):
    """Request body for output generation."""

    run_id: int
    intake_id: int
    profile_types: list[str] | None = None


class OutputDocumentSummary(BaseModel):
    """Lightweight output document summary for list responses."""

    id: int
    run_id: int
    intake_id: int
    profile_type: str
    completeness_score: float | None = None
    created_at: datetime

    model_config = {"from_attributes": True}


class OutputDocumentDetail(BaseModel):
    """Full output document detail with markdown content."""

    id: int
    run_id: int
    intake_id: int
    profile_type: str
    markdown_content: str
    completeness_score: float | None = None
    metadata_json: dict | None = None
    created_at: datetime

    model_config = {"from_attributes": True}


class GenerateResponse(BaseModel):
    """Response from output generation."""

    documents: list[OutputDocumentSummary]


# ---------------------------------------------------------------------------
# Export adapter registry
# ---------------------------------------------------------------------------

_EXPORT_ADAPTERS = {
    "pdf": PDFAdapter,
    "docx": DOCXAdapter,
    "json": JSONAdapter,
}


# ---------------------------------------------------------------------------
# Endpoints
# ---------------------------------------------------------------------------


@router.post("/generate", response_model=GenerateResponse, status_code=status.HTTP_201_CREATED)
async def generate_output(
    request: GenerateRequest,
    db: AsyncSession = Depends(get_tenant_session),
    current_user: User = Depends(get_current_active_user),
) -> GenerateResponse:
    """Generate output documents for one or more profiles.

    Orchestrates the full output pipeline: assemble data, score triage,
    generate action items, adapt language, render Markdown, persist.

    Multiple profile_types can be requested in a single call (D-06).
    """
    # Determine profiles
    profile_types = request.profile_types or ["law_firm"]
    profiles: list[OutputProfile] = []
    for pt in profile_types:
        profile = _PROFILE_MAP.get(pt)
        if not profile:
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail=f"Unknown profile type: {pt}. Valid: {list(_PROFILE_MAP.keys())}",
            )
        profiles.append(profile)

    assembler = DataAssembler(db)
    triage_scorer = TriageScorer()
    action_gen = ActionItemGenerator()
    language_adapter = LanguageAdapter()
    engine = TemplateEngine()

    # LLM service for language adaptation (RUB-10). Instantiated lazily; if
    # construction fails we adapt with a null service (adapter keeps original
    # text) so output generation never hard-fails on LLM wiring.
    llm_service = None
    try:
        from app.services.llm_service import LLMService

        llm_service = LLMService()
    except Exception:
        logger.warning(
            "LLMService unavailable; language adaptation will no-op", exc_info=True
        )

    documents: list[OutputDocument] = []

    for profile in profiles:
        # Step 1: Assemble data
        context = await assembler.assemble(request.run_id, request.intake_id, profile)

        # Step 2: Score triage
        triage = triage_scorer.score(context)
        context.triage = triage

        # Step 3: Generate action items
        action_items = action_gen.generate(
            context.gap_report, context.claims_by_jurisdiction, context.deadlines
        )
        context.action_items = action_items

        # Step 4: Language adaptation (RUB-10). Rewrites the professional CIRAC
        # prose to the profile's reading level BEFORE rendering. Only the
        # consumer-facing profiles are rewritten:
        #   - court_self_help (plain, ~6th grade)  -> rewritten
        #   - legal_aid       (accessible, ~10th)  -> rewritten
        #   - law_firm        (professional)       -> left untouched (attorney memo)
        # The adapter self-skips professional (system_prompt is None) and falls
        # back to original text on a null/failed LLM. Previously this was never
        # invoked, so plain-language memos rendered at the professional grade level.
        if profile.language_level == "professional":
            logger.info(
                "Language adaptation skipped for professional profile %s",
                profile.profile_type,
            )
        elif llm_service is None:
            logger.warning(
                "Language adaptation no-op for profile %s: no LLM service; "
                "prose renders at original (professional) reading level",
                profile.profile_type,
            )
        else:
            context = await language_adapter.adapt(context, profile, llm_service)

        # Step 5: Render Markdown
        markdown = engine.render_full(context, profile)

        # Step 6: Persist OutputDocument
        #
        # BUG-18: the JSON export serializes the structured OutputContext, but
        # historically only `markdown_content` was persisted — the export
        # endpoint then rebuilt an EMPTY minimal context, so every JSON export
        # was an empty shell (claims_by_jurisdiction={}, deadlines=[],
        # executive_summary="") while the PDF (which renders markdown) was
        # complete. Fix: serialize the FINAL context (post triage / action
        # items / language adaptation) into `rendered_json` here at generation
        # time. This is the exact payload JSONAdapter produces, so the export
        # endpoint's cache-hit path returns full structured content.
        rendered_json = context.model_dump_json(indent=2)
        doc = OutputDocument(
            run_id=request.run_id,
            intake_id=request.intake_id,
            profile_type=profile.profile_type,
            markdown_content=markdown,
            rendered_json=rendered_json,
            metadata_json={
                "completeness_score": context.completeness_score,
                "matter_title": context.matter_title,
            },
        )
        db.add(doc)
        documents.append(doc)

    await db.flush()
    await db.commit()

    # Refresh to get generated IDs and timestamps
    for doc in documents:
        await db.refresh(doc)

    return GenerateResponse(
        documents=[
            OutputDocumentSummary(
                id=doc.id,
                run_id=doc.run_id,
                intake_id=doc.intake_id,
                profile_type=doc.profile_type,
                completeness_score=(doc.metadata_json or {}).get("completeness_score"),
                created_at=doc.created_at,
            )
            for doc in documents
        ]
    )


@router.get("/intake/{intake_id}", response_model=list[OutputDocumentSummary])
async def list_outputs(
    intake_id: int,
    db: AsyncSession = Depends(get_tenant_session),
    current_user: User = Depends(get_current_active_user),
) -> list[OutputDocumentSummary]:
    """List all output documents for an intake."""
    result = await db.execute(
        select(OutputDocument)
        .where(OutputDocument.intake_id == intake_id)
        .order_by(OutputDocument.created_at.desc())
    )
    docs = result.scalars().all()
    return [
        OutputDocumentSummary(
            id=doc.id,
            run_id=doc.run_id,
            intake_id=doc.intake_id,
            profile_type=doc.profile_type,
            completeness_score=(doc.metadata_json or {}).get("completeness_score"),
            created_at=doc.created_at,
        )
        for doc in docs
    ]


@router.get("/{document_id}", response_model=OutputDocumentDetail)
async def get_output(
    document_id: int,
    db: AsyncSession = Depends(get_tenant_session),
    current_user: User = Depends(get_current_active_user),
) -> OutputDocumentDetail:
    """Get full output document detail including markdown content."""
    result = await db.execute(
        select(OutputDocument).where(OutputDocument.id == document_id)
    )
    doc = result.scalars().first()
    if not doc:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Output document not found")

    return OutputDocumentDetail(
        id=doc.id,
        run_id=doc.run_id,
        intake_id=doc.intake_id,
        profile_type=doc.profile_type,
        markdown_content=doc.markdown_content,
        completeness_score=(doc.metadata_json or {}).get("completeness_score"),
        metadata_json=doc.metadata_json,
        created_at=doc.created_at,
    )


@router.get("/{document_id}/export/{format}")
async def export_output(
    document_id: int,
    format: str,
    db: AsyncSession = Depends(get_tenant_session),
    current_user: User = Depends(get_current_active_user),
):
    """Export output document in PDF, DOCX, or JSON format.

    Renders on first request and caches the result on the OutputDocument
    for subsequent requests.
    """
    # Validate format
    if format not in _EXPORT_ADAPTERS:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=f"Unsupported format: {format}. Valid: {list(_EXPORT_ADAPTERS.keys())}",
        )

    # Load document
    result = await db.execute(
        select(OutputDocument).where(OutputDocument.id == document_id)
    )
    doc = result.scalars().first()
    if not doc:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Output document not found")

    # Check cache
    cache_field = f"rendered_{format}"
    cached = getattr(doc, cache_field, None)
    if cached is not None:
        # For JSON, cached is text; for PDF/DOCX, cached is bytes
        content = cached if isinstance(cached, bytes) else cached.encode("utf-8")
    else:
        # Build context for adapter (minimal for export)
        profile = _PROFILE_MAP.get(doc.profile_type, LAW_FIRM_PROFILE)

        from app.services.output.schemas import GapReport, OutputContext

        context = OutputContext(
            intake_id=doc.intake_id,
            run_id=doc.run_id,
            org_id=0,
            matter_title=(doc.metadata_json or {}).get("matter_title", f"Document #{doc.id}"),
            generated_at=doc.created_at,
            completeness_score=(doc.metadata_json or {}).get("completeness_score", 0.0),
            gap_report=GapReport(),
            profile=profile,
        )

        adapter = _EXPORT_ADAPTERS[format]()
        content = await adapter.export(doc.markdown_content, context, profile)

        # Cache the rendered output
        if format in ("pdf", "docx"):
            setattr(doc, cache_field, content)
        elif format == "json":
            setattr(doc, cache_field, content.decode("utf-8"))
        await db.commit()

    # Build response
    adapter_instance = _EXPORT_ADAPTERS[format]()
    filename = f"output_{document_id}.{adapter_instance.file_extension}"

    from io import BytesIO

    return StreamingResponse(
        BytesIO(content),
        media_type=adapter_instance.content_type,
        headers={"Content-Disposition": f'attachment; filename="{filename}"'},
    )
