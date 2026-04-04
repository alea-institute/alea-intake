"""Research API endpoints -- query tools, verify citations, configure org tools.

Provides endpoints for querying pluggable legal research tools, verifying
citations against known databases, and managing per-org tool configuration.
"""

from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.permissions import require_role
from app.db.session import get_tenant_session
from app.models.research import Authority, ResearchResult as ResearchResultModel, ResearchToolConfig
from app.models.user import Role, User
from app.schemas.research import (
    AuthorityResponse,
    ConfigureToolRequest,
    ResearchQueryRequest,
    ResearchQueryResponse,
    ResearchToolResponse,
    VerificationResultResponse,
    VerifyCitationRequest,
)
from app.services.research.base import ResearchQuery
from app.services.research.registry import get_research_registry
from app.services.research.verification import CitationVerifier

router = APIRouter(prefix="/api/v1/research", tags=["research"])


@router.post("/query", response_model=ResearchQueryResponse)
async def query_research_tools(
    body: ResearchQueryRequest,
    current_user: User = Depends(require_role(Role.PROFESSIONAL)),
    session: AsyncSession = Depends(get_tenant_session),
):
    """Query configured research tools for a claim+jurisdiction.

    Dispatches the query to all configured tools, merges results, and
    persists the query record and found authorities.
    """
    registry = get_research_registry()

    # Get org's configured tools
    result = await session.execute(
        select(ResearchToolConfig).where(
            ResearchToolConfig.org_id == current_user.org_id,
            ResearchToolConfig.enabled == True,  # noqa: E712
        )
    )
    org_tools = result.scalars().all()
    tool_names = [t.tool_name for t in org_tools] if org_tools else registry.list_adapters()

    # Build research query
    query = ResearchQuery(
        query_text=body.query_text,
        claim_iri=body.claim_iri,
        jurisdiction=body.jurisdiction,
        authority_types=body.authority_types,
        max_results=body.max_results,
    )

    # Query all configured tools
    results = await registry.query_all(query, tool_names=tool_names)

    # Convert to response format
    authorities = [
        AuthorityResponse(
            citation=r.citation,
            title=r.title,
            authority_type=r.authority_type,
            jurisdiction=r.jurisdiction,
            source_tool=r.source_tool,
            source_url=r.source_url,
            excerpt=r.excerpt,
            relevance_score=r.relevance_score,
            folio_iri=r.folio_iri,
            claim_iri=body.claim_iri,
        )
        for r in results
    ]

    return ResearchQueryResponse(
        query_text=body.query_text,
        tool_names=tool_names,
        authorities=authorities,
        total_results=len(authorities),
    )


@router.post("/verify", response_model=VerificationResultResponse)
async def verify_citation(
    body: VerifyCitationRequest,
    current_user: User = Depends(require_role(Role.PROFESSIONAL)),
):
    """Verify a citation against configured research tools.

    Checks the citation against all registered tools and returns
    verification status with source.
    """
    registry = get_research_registry()
    verifier = CitationVerifier(registry)

    result = await verifier.verify(body.citation)

    return VerificationResultResponse(
        citation=result.citation,
        verified=result.verified,
        status=result.status,
        verification_source=result.verification_source,
        confidence=result.confidence,
        matched_title=result.matched_title,
        source_url=result.source_url,
        error=result.error,
    )


@router.get("/tools", response_model=list[ResearchToolResponse])
async def list_research_tools(
    current_user: User = Depends(require_role(Role.PROFESSIONAL)),
    session: AsyncSession = Depends(get_tenant_session),
):
    """List research tools configured for the current org."""
    result = await session.execute(
        select(ResearchToolConfig).where(
            ResearchToolConfig.org_id == current_user.org_id,
        )
    )
    tools = result.scalars().all()

    return [
        ResearchToolResponse(
            id=t.id,
            tool_name=t.tool_name,
            display_name=t.display_name,
            enabled=t.enabled,
            base_url=t.base_url,
            has_api_key=t.api_key_encrypted is not None,
            config=t.config_json,
            created_at=t.created_at,
        )
        for t in tools
    ]


@router.post("/tools", response_model=ResearchToolResponse, status_code=status.HTTP_201_CREATED)
async def configure_research_tool(
    body: ConfigureToolRequest,
    current_user: User = Depends(require_role(Role.ADMIN)),
    session: AsyncSession = Depends(get_tenant_session),
):
    """Configure a research tool for the org. Admin only.

    Creates or updates a research tool configuration for the current org.
    """
    # Check if tool already configured for this org
    result = await session.execute(
        select(ResearchToolConfig).where(
            ResearchToolConfig.org_id == current_user.org_id,
            ResearchToolConfig.tool_name == body.tool_name,
        )
    )
    existing = result.scalar_one_or_none()

    if existing:
        # Update existing config
        existing.display_name = body.display_name
        existing.enabled = body.enabled
        existing.base_url = body.base_url
        existing.config_json = body.config
        if body.api_key:
            existing.api_key_encrypted = body.api_key.encode("utf-8")
        tool = existing
    else:
        # Create new config
        tool = ResearchToolConfig(
            org_id=current_user.org_id,
            tool_name=body.tool_name,
            display_name=body.display_name,
            enabled=body.enabled,
            base_url=body.base_url,
            config_json=body.config,
            api_key_encrypted=body.api_key.encode("utf-8") if body.api_key else None,
        )
        session.add(tool)

    await session.flush()

    return ResearchToolResponse(
        id=tool.id,
        tool_name=tool.tool_name,
        display_name=tool.display_name,
        enabled=tool.enabled,
        base_url=tool.base_url,
        has_api_key=tool.api_key_encrypted is not None,
        config=tool.config_json,
        created_at=tool.created_at,
    )
