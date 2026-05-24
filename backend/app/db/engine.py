"""Async database engine factory supporting PostgreSQL and SQLite backends."""

from sqlalchemy.ext.asyncio import AsyncEngine, create_async_engine
from sqlalchemy.pool import NullPool

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
            # asyncpg connections are bound to the event loop that created them.
            # This app can initialize the engine outside the serving loop (e.g. at
            # import / first use), so a pooled connection would be reused across
            # loops and raise asyncpg's "got Future attached to a different loop"
            # (it also surfaces as "another operation is in progress"). NullPool
            # opens a fresh connection per checkout and closes it on return, so no
            # connection is ever reused across a loop boundary. Postgres handles the
            # extra connect churn fine at this scale; revisit with a loop-pinned
            # pool if connection-establishment latency ever matters.
            poolclass=NullPool,
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
