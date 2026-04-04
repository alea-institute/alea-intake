"""Application configuration via Pydantic Settings."""

from enum import Enum
from functools import lru_cache

from pydantic_settings import BaseSettings, SettingsConfigDict


class DatabaseBackend(str, Enum):
    """Supported database backends."""

    POSTGRESQL = "postgresql"
    SQLITE = "sqlite"


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

    # Research tools
    courtlistener_base_url: str = "https://www.courtlistener.com/api/rest/v4"
    research_timeout_seconds: int = 30
    research_max_results_per_query: int = 20

    # CORS
    cors_origins: list[str] = ["http://localhost:5173"]

    model_config = SettingsConfigDict(env_file=".env", env_prefix="ALEA_")


@lru_cache
def get_settings() -> Settings:
    """Return cached Settings instance. Use lru_cache for testability (clear cache in tests)."""
    return Settings()
