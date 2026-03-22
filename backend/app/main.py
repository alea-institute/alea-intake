"""ALEA Intake API - FastAPI application entry point."""

from contextlib import asynccontextmanager

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


@asynccontextmanager
async def lifespan(app: FastAPI):
    """Application lifespan: initialize engine on startup, dispose on shutdown."""
    get_engine()
    yield
    await dispose_engine()


settings = get_settings()

app = FastAPI(
    title="ALEA Intake API",
    version="0.1.0",
    lifespan=lifespan,
)

# CORS
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


# Health endpoint
@app.get("/health")
async def health():
    """Health check endpoint."""
    return {"status": "healthy", "version": "0.1.0"}
