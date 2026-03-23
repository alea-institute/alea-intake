"""Test fixtures for async database and FastAPI test client.

Uses aiosqlite database for fast, isolated tests.
The async_client fixture uses a temp file-based SQLite (for multi-connection
support by audit middleware); async_session uses in-memory for speed.
Overrides get_settings() to use SQLite backend with test credentials.
"""

import asyncio
import os
import tempfile
from collections.abc import AsyncGenerator

import pytest
from httpx import ASGITransport, AsyncClient
from sqlalchemy import MetaData
from sqlalchemy.ext.asyncio import AsyncEngine, AsyncSession, async_sessionmaker, create_async_engine

from app.config import Settings, get_settings
from app.db.base import SharedBase, TenantBase
from app.db.engine import _engine as _module_engine


def get_test_settings() -> Settings:
    """Return test settings with SQLite backend and known test credentials."""
    return Settings(
        secret_key="test-secret-key-for-testing-only-not-production",
        database_backend="sqlite",
        sqlite_path=":memory:",
        debug=False,
        cors_origins=["http://localhost:5173"],
    )


@pytest.fixture(scope="session")
def event_loop():
    """Create a session-scoped event loop for async tests."""
    loop = asyncio.new_event_loop()
    yield loop
    loop.close()


@pytest.fixture
async def async_engine() -> AsyncGenerator[AsyncEngine, None]:
    """Create an async SQLite engine and initialize all tables."""
    engine = create_async_engine(
        "sqlite+aiosqlite://",
        echo=False,
    )

    # Import all models so they register with metadata
    import app.models  # noqa: F401

    # Create schemaless table copies (SQLite doesn't support named schemas)
    from app.db.base import convention

    _tenant_meta = MetaData(naming_convention=convention)
    _shared_meta = MetaData(naming_convention=convention)
    for table in TenantBase.metadata.tables.values():
        table.to_metadata(_tenant_meta, schema=None)
    for table in SharedBase.metadata.tables.values():
        table.to_metadata(_shared_meta, schema=None)

    async with engine.begin() as conn:
        await conn.run_sync(_shared_meta.create_all)
        await conn.run_sync(_tenant_meta.create_all)

    yield engine

    # Cleanup
    async with engine.begin() as conn:
        await conn.run_sync(_tenant_meta.drop_all)
        await conn.run_sync(_shared_meta.drop_all)

    await engine.dispose()


@pytest.fixture
async def async_session(async_engine: AsyncEngine) -> AsyncGenerator[AsyncSession, None]:
    """Yield an AsyncSession against the test engine with schema_translate_map for SQLite."""
    async with async_engine.connect() as conn:
        conn = await conn.execution_options(
            schema_translate_map={"tenant": None, "shared": None}
        )
        async with AsyncSession(bind=conn, expire_on_commit=False) as session:
            yield session
            await session.rollback()


@pytest.fixture
async def async_client() -> AsyncGenerator[AsyncClient, None]:
    """Create an httpx AsyncClient with the FastAPI app using ASGITransport.

    Sets up an in-memory SQLite database with all tables created,
    overrides settings and engine for test isolation.
    """
    import app.config
    import app.db.engine as engine_module

    # Save originals
    original_config_get_settings = app.config.get_settings

    # Override get_settings at the source module
    get_settings.cache_clear()
    app.config.get_settings = get_test_settings  # type: ignore[assignment]

    # Create a temp-file SQLite engine (not in-memory) so the audit middleware's
    # separate DB connection can access the same database. In-memory SQLite with
    # StaticPool only has one raw connection, causing isolation issues.
    _tmp_db_fd, _tmp_db_path = tempfile.mkstemp(suffix=".db")
    os.close(_tmp_db_fd)

    test_engine = create_async_engine(
        f"sqlite+aiosqlite:///{_tmp_db_path}",
        echo=False,
    )
    engine_module._engine = test_engine

    # Import all models so they register with metadata
    import app.models  # noqa: F401

    # Create schemaless table copies (SQLite doesn't support named schemas)
    from app.db.base import convention

    _tenant_meta = MetaData(naming_convention=convention)
    _shared_meta = MetaData(naming_convention=convention)
    for table in TenantBase.metadata.tables.values():
        table.to_metadata(_tenant_meta, schema=None)
    for table in SharedBase.metadata.tables.values():
        table.to_metadata(_shared_meta, schema=None)

    async with test_engine.begin() as conn:
        await conn.run_sync(_shared_meta.create_all)
        await conn.run_sync(_tenant_meta.create_all)

    # Seed a test Organization so auth and admin endpoints can look it up
    from app.models.shared import Organization

    async with test_engine.connect() as conn:
        conn = await conn.execution_options(
            schema_translate_map={"tenant": None, "shared": None}
        )
        async with AsyncSession(bind=conn, expire_on_commit=False) as seed_session:
            seed_session.add(
                Organization(
                    name="Test Legal Aid",
                    slug="test-legal-aid",
                    auth_mode="email_password",
                    llm_data_policy="cloud_optout",
                    consent_mode="granular",
                    deletion_policy="anonymize",
                )
            )
            await seed_session.commit()

    # Patch get_settings in all modules that import it locally
    patched_modules: list[tuple] = []
    for mod_name in ["app.core.permissions", "app.services.auth_service", "app.routers.auth", "app.middleware.consent"]:
        try:
            import importlib
            mod = importlib.import_module(mod_name)
            if hasattr(mod, "get_settings"):
                patched_modules.append((mod, mod.get_settings))
                mod.get_settings = get_test_settings  # type: ignore[assignment]
        except ImportError:
            pass

    from app.main import app as fastapi_app

    transport = ASGITransport(app=fastapi_app)
    async with AsyncClient(transport=transport, base_url="http://test") as client:
        yield client

    # Cleanup tables and temp file
    async with test_engine.begin() as conn:
        await conn.run_sync(_tenant_meta.drop_all)
        await conn.run_sync(_shared_meta.drop_all)
    await test_engine.dispose()
    engine_module._engine = None
    try:
        os.unlink(_tmp_db_path)
    except OSError:
        pass

    # Restore originals
    app.config.get_settings = original_config_get_settings  # type: ignore[assignment]
    for mod, original_fn in patched_modules:
        mod.get_settings = original_fn  # type: ignore[assignment]
    get_settings.cache_clear()


@pytest.fixture
async def test_org(async_session: AsyncSession):
    """Create a test Organization record."""
    from app.models.shared import Organization

    org = Organization(
        name="Test Legal Aid",
        slug="test-legal-aid",
        auth_mode="email_password",
        llm_data_policy="cloud_optout",
        consent_mode="granular",
        deletion_policy="anonymize",
    )
    async_session.add(org)
    await async_session.flush()
    return org


@pytest.fixture
async def test_user(async_session: AsyncSession, test_org):
    """Create a test User record with known credentials."""
    from app.models.user import User

    user = User(
        email="testuser@example.com",
        hashed_password="$placeholder_hash$",  # Will be real hash after Plan 02
        full_name=b"Test User",  # Unencrypted for tests; encryption in Plan 03
        role="consumer",
        org_id=test_org.id,
    )
    async_session.add(user)
    await async_session.flush()
    return user
