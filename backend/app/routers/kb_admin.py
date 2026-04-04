"""Knowledge base admin API endpoints: document CRUD and bulk import.

Provides admin-only endpoints for managing an organization's knowledge base:
- Upload, list, get, update, and delete documents
- Bulk import from ZIP archives
- All endpoints require Role.ADMIN via router-level dependency

Follows the screening_admin.py router pattern per D-02.
"""

from __future__ import annotations

from fastapi import APIRouter, Depends, File, Form, HTTPException, UploadFile, status
from pydantic import BaseModel
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.permissions import require_role
from app.db.session import get_tenant_session
from app.models.user import Role

router = APIRouter(
    prefix="/api/v1/admin/kb",
    tags=["kb-admin"],
    dependencies=[Depends(require_role(Role.ADMIN))],
)


# -- Response Schemas ---------------------------------------------------------


class DocumentResponse(BaseModel):
    id: int
    title: str
    status: str
    version: int
    format: str | None = None


class DocumentDetailResponse(BaseModel):
    id: int
    title: str
    version: int
    status: str
    folio_iris: list[str] = []


# -- Helper -------------------------------------------------------------------


def _get_kb_service(session: AsyncSession):
    """Create KBService with dependencies.

    In production, dependencies would be injected via DI container.
    For now, creates minimal instances inline.
    """
    from app.services.knowledge_base.chunker import SemanticChunker
    from app.services.knowledge_base.folio_tagger import FolioTagger
    from app.services.knowledge_base.kb_service import KBService

    return KBService(
        db_session=session,
        chunker=SemanticChunker(),
        folio_tagger=FolioTagger(concept_resolver=None),
    )


# -- Endpoints ----------------------------------------------------------------


@router.post("/documents", status_code=status.HTTP_201_CREATED)
async def upload_document(
    file: UploadFile = File(...),
    title: str = Form(...),
    session: AsyncSession = Depends(get_tenant_session),
):
    """Upload a document to the organization's knowledge base.

    Accepts multipart form with file + title. Extracts text, chunks,
    FOLIO-tags, and indexes the document.
    """
    svc = _get_kb_service(session)
    content = await file.read()
    filename = file.filename or "upload.txt"

    try:
        doc = await svc.upload(
            org_id=0,  # Will be set from request context in production
            file_content=content,
            filename=filename,
            title=title,
        )
    except ValueError as e:
        raise HTTPException(status_code=400, detail=str(e))

    return DocumentResponse(
        id=doc.id,
        title=doc.title,
        status=doc.status,
        version=doc.version,
        format=doc.format,
    )


@router.get("/documents")
async def list_documents(
    page: int = 1,
    page_size: int = 20,
    session: AsyncSession = Depends(get_tenant_session),
):
    """List documents in the organization's knowledge base with pagination."""
    svc = _get_kb_service(session)
    docs = await svc.list_documents(org_id=0, page=page, page_size=page_size)
    return docs


@router.get("/documents/{document_id}")
async def get_document(
    document_id: int,
    session: AsyncSession = Depends(get_tenant_session),
):
    """Get document detail with chunk count and FOLIO tags."""
    svc = _get_kb_service(session)
    doc = await svc.get_document(document_id)
    if doc is None:
        raise HTTPException(status_code=404, detail="Document not found")
    return doc


@router.put("/documents/{document_id}")
async def update_document(
    document_id: int,
    file: UploadFile = File(...),
    session: AsyncSession = Depends(get_tenant_session),
):
    """Update a document by re-extracting, re-chunking, and re-embedding.

    Increments the document version.
    """
    svc = _get_kb_service(session)
    content = await file.read()
    filename = file.filename or "upload.txt"

    try:
        doc = await svc.update(
            document_id=document_id,
            file_content=content,
            filename=filename,
        )
    except ValueError as e:
        raise HTTPException(status_code=404, detail=str(e))

    return DocumentResponse(
        id=doc.id,
        title=doc.title,
        status=doc.status,
        version=doc.version,
        format=doc.format,
    )


@router.delete("/documents/{document_id}", status_code=status.HTTP_204_NO_CONTENT)
async def delete_document(
    document_id: int,
    session: AsyncSession = Depends(get_tenant_session),
):
    """Delete a document and all its chunks from the knowledge base."""
    svc = _get_kb_service(session)
    try:
        await svc.delete(document_id=document_id)
    except ValueError as e:
        raise HTTPException(status_code=404, detail=str(e))


@router.post("/documents/bulk-import", status_code=status.HTTP_201_CREATED)
async def bulk_import(
    file: UploadFile = File(...),
    session: AsyncSession = Depends(get_tenant_session),
):
    """Upload a ZIP archive for bulk document import.

    Extracts all supported files from the ZIP and processes each one.
    """
    svc = _get_kb_service(session)
    content = await file.read()

    try:
        docs = await svc.bulk_import(org_id=0, zip_content=content)
    except Exception as e:
        raise HTTPException(status_code=400, detail=str(e))

    return {
        "imported": len(docs),
        "documents": [
            DocumentResponse(
                id=d.id,
                title=d.title,
                status=d.status,
                version=d.version,
                format=d.format,
            )
            for d in docs
        ],
    }
