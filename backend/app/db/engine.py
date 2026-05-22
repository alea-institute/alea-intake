"""Async database engine factory supporting PostgreSQL and SQLite backends."""

from sqlalchemy.ext.asyncio import AsyncEngine, create_async_engine

from app.config import DatabaseBackend, get_settings

_engine: AsyncEngine | None = None


def create_engine() -> AsyncEngine:
    """Create an AsyncEngine based on the configured database backend.

    PostgreSQL: Uses asyncpg driver with connection pooling.
    SQLite: Uses aiosqlite driver (single-tenant only).
    """
    settings = get_settings()

    if settings.database_backend == DatabaseBackend.POSTGRESQL:
        url = (
            f"postgresql+asyncpg://{settings.db_user}:{settings.db_password}"
            f"@{settings.db_host}:{settings.db_port}/{settings.db_name}"
        )
        return create_async_engine(
            url,
            pool_size=20,
            max_overflow=10,
            # pre_ping validates a pooled connection with a lightweight check
            # before handing it out, dropping dead/poisoned asyncpg connections;
            # recycle (1800s) caps connection lifetime so long-lived poisoned
            # connections rotate out of the pool.
            pool_pre_ping=True,
            pool_recycle=1800,
            echo=settings.debug,
        )
    else:
        url = f"sqlite+aiosqlite:///{settings.sqlite_path}"
        return create_async_engine(
            url,
            echo=settings.debug,
        )


def get_engine() -> AsyncEngine:
    """Return the cached engine, creating it on first call."""
    global _engine
    if _engine is None:
        _engine = create_engine()
    return _engine


async def dispose_engine() -> None:
    """Dispose the cached engine and release all connections."""
    global _engine
    if _engine is not None:
        await _engine.dispose()
        _engine = None
