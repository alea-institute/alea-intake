"""ALEA Intake API - FastAPI application entry point."""

import asyncio
from contextlib import asynccontextmanager
from pathlib import Path

from fastapi import FastAPI, Request
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import JSONResponse

from app.config import get_settings
from app.core.exceptions import (
    ConsentRequiredError,
    EncryptionError,
    InsufficientPermissionsError,
    TenantNotFoundError,
)
from app.db.engine import dispose_engine, get_engine
from app.middleware.audit import AuditMiddleware
from app.middleware.consent import ConsentMiddleware
from app.middleware.tenant import TenantMiddleware
from app.routers.admin import router as admin_router
from app.routers.auth import router as auth_router
from app.routers.audit import router as audit_router
from app.routers.consent import router as consent_router
from app.routers.folio_admin import router as folio_admin_router
from app.routers.intake import router as intake_router
from app.routers.intake import ws_router as intake_ws_router
from app.routers.intake_professional import router as intake_professional_router
from app.routers.organizations import router as organizations_router
from app.routers.users import router as users_router
from app.services.embedding.service import EmbeddingService
from app.services.folio.folio_service import get_folio
from app.services.folio.owl_cache import ensure_owl_fresh
from app.services.folio.owl_updater import OWLUpdateManager, _periodic_owl_check


@asynccontextmanager
async def lifespan(app: FastAPI):
    """Application lifespan: initialize engine, load FOLIO, start update checker."""
    settings = get_settings()
    loop = asyncio.get_event_loop()

    # Step 1: Ensure OWL cache is fresh (sync httpx call in executor)
    await loop.run_in_executor(None, ensure_owl_fresh)

    # Step 2: Load FOLIO singleton (sync OWL parsing in executor)
    await loop.run_in_executor(None, get_folio)

    # Step 3: Build embedding index from FOLIO concepts
    folio = get_folio()  # already loaded in step 2
    emb_service = EmbeddingService.get_instance()
    await loop.run_in_executor(None, emb_service.build_index, folio)

    # Step 4: Start periodic OWL update checker
    update_manager = OWLUpdateManager.get_instance()
    update_task = asyncio.create_task(
        _periodic_owl_check(update_manager, settings.folio_update_interval_hours)
    )

    # Step 5: Ensure intake upload directory exists
    intake_upload_dir = Path(settings.intake_upload_dir)
    intake_upload_dir.mkdir(parents=True, exist_ok=True)

    # Step 6: Initialize DB engine
    get_engine()

    yield

    # Shutdown
    update_task.cancel()
    try:
        await update_task
    except asyncio.CancelledError:
        pass
    await dispose_engine()


settings = get_settings()

app = FastAPI(
    title="ALEA Intake API",
    version="0.1.0",
    lifespan=lifespan,
)

# Middleware (order matters -- last added = outermost/first executed):
# Execution order: CORS -> Audit -> Tenant -> Consent -> route handler
app.add_middleware(ConsentMiddleware)
app.add_middleware(TenantMiddleware)
app.add_middleware(AuditMiddleware)
app.add_middleware(
    CORSMiddleware,
    allow_origins=settings.cors_origins,
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)


# Exception handlers
@app.exception_handler(TenantNotFoundError)
async def tenant_not_found_handler(request: Request, exc: TenantNotFoundError):
    return JSONResponse(status_code=404, content={"detail": exc.message})


@app.exception_handler(EncryptionError)
async def encryption_error_handler(request: Request, exc: EncryptionError):
    return JSONResponse(status_code=500, content={"detail": exc.message})


@app.exception_handler(ConsentRequiredError)
async def consent_required_handler(request: Request, exc: ConsentRequiredError):
    return JSONResponse(status_code=403, content={"detail": exc.message})


@app.exception_handler(InsufficientPermissionsError)
async def insufficient_permissions_handler(request: Request, exc: InsufficientPermissionsError):
    return JSONResponse(status_code=403, content={"detail": exc.message})


# Routers
app.include_router(auth_router)
app.include_router(organizations_router)
app.include_router(users_router)
app.include_router(audit_router)
app.include_router(consent_router)
app.include_router(admin_router)
app.include_router(folio_admin_router)
app.include_router(intake_router)
app.include_router(intake_ws_router)
app.include_router(intake_professional_router)


# Health endpoint
@app.get("/health")
async def health():
    """Health check endpoint with FOLIO OWL cache status."""
    from app.services.folio.owl_cache import get_owl_status

    owl_status = get_owl_status()
    return {
        "status": "healthy",
        "version": "0.1.0",
        "folio": owl_status,
    }
