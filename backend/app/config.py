"""Application configuration via Pydantic Settings."""

from enum import Enum
from functools import lru_cache

from pydantic_settings import BaseSettings, SettingsConfigDict


class DatabaseBackend(str, Enum):
    """Supported database backends."""

    POSTGRESQL = "postgresql"
    SQLITE = "sqlite"


class DeploymentMode(str, Enum):
    """Deployment topology modes."""

    MULTI_TENANT = "multi_tenant"
    SINGLE_TENANT = "single_tenant"


class PersistenceMode(str, Enum):
    """Data persistence strategies."""

    EPHEMERAL = "ephemeral"
    PERSISTENT = "persistent"
    CMS_INTEGRATED = "cms_integrated"


class LLMDataPolicy(str, Enum):
    """LLM data handling policies, org-configurable."""

    CLOUD_WITH_OPTOUT = "cloud_optout"
    CLOUD_WITH_BAA = "cloud_baa"
    LOCAL_ONLY = "local_only"


class Settings(BaseSettings):
    """Application settings loaded from environment variables with ALEA_ prefix."""

    app_name: str = "alea-intake"
    debug: bool = False
    secret_key: str  # Required -- no default

    # Database
    database_backend: DatabaseBackend = DatabaseBackend.POSTGRESQL
    db_host: str = "localhost"
    db_port: int = 5432
    db_name: str = "alea_intake"
    db_user: str = "alea"
    db_password: str = ""
    sqlite_path: str = "./data/alea_intake.db"

    # Encryption / KMS
    master_key_path: str = ""
    kms_provider: str = ""
    kms_key_id: str = ""

    # Auth tokens
    access_token_expire_minutes: int = 30
    refresh_token_expire_days: int = 7

    # FOLIO ontology
    folio_owl_branch: str = "main"
    folio_update_interval_hours: int = 24
    folio_cache_dir: str = "./data/folio_cache"
    folio_confidence_threshold: float = 0.5
    folio_traversal_depth: int = 2

    # Intake
    intake_upload_dir: str = "./data/uploads"
    intake_max_file_size_mb: int = 50
    intake_max_page_count: int = 200
    intake_max_recording_duration_sec: int = 900  # 15 minutes
    intake_default_session_mode: str = "multi_session"
    intake_fact_visibility: str = "internal"  # internal or consumer_visible

    # Admin auto-promote (set email to auto-grant admin role on startup)
    auto_admin_email: str = ""

    # Research
    courtlistener_base_url: str = "https://www.courtlistener.com/api/rest/v4"
    research_timeout_seconds: int = 30
    research_max_results_per_query: int = 20
    research_cache_ttl_case_hours: int = 24
    research_cache_ttl_statute_hours: int = 168  # 7 days

    # ASR
    asr_default_provider: str = "whisper"
    whisper_endpoint: str = "http://localhost:8790"
    asr_audio_storage_policy: str = "store_both"  # store_both, transcript_only, ephemeral

    # OAuth SSO
    google_client_id: str = ""
    google_client_secret: str = ""
    microsoft_client_id: str = ""
    microsoft_client_secret: str = ""
    oauth_redirect_base_url: str = "http://localhost:8000"
    frontend_base_url: str = "http://localhost:5173"
    session_secret_key: str = ""

    # Deployment
    deployment_mode: DeploymentMode = DeploymentMode.SINGLE_TENANT
    persistence_mode: PersistenceMode = PersistenceMode.PERSISTENT
    tenant_signup_mode: str = "admin_approval"

    # OpenTelemetry (empty = disabled / no-op)
    otel_endpoint: str = ""
    otel_service_name: str = "alea-intake"

    # Logging
    log_level: str = "INFO"
    log_format: str = "json"  # json or console

    # Rate limiting
    rate_limit_default: str = "100/minute"
    rate_limit_key_header: str = ""  # empty = use client IP
    rate_limit_storage: str = "memory"  # memory or redis://...

    # Security headers
    csp_script_src: str = "'self'"
    hsts_max_age: int = 31536000
    max_request_size_mb: int = 50

    # CMS integration
    cms_enabled: bool = False
    cms_sync_interval_seconds: int = 300

    # CORS
    cors_origins: list[str] = ["http://localhost:5173"]

    model_config = SettingsConfigDict(env_file=".env", env_prefix="ALEA_")


@lru_cache
def get_settings() -> Settings:
    """Return cached Settings instance. Use lru_cache for testability (clear cache in tests)."""
    return Settings()
