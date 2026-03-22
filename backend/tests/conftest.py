"""Test fixtures for async database and FastAPI test client.

Uses aiosqlite in-memory database for fast, isolated tests.
Overrides get_settings() to use SQLite backend with test credentials.
"""

import asyncio
from collections.abc import AsyncGenerator

import pytest
from httpx import ASGITransport, AsyncClient
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

    # Create all tables from both bases (SQLite ignores schema names)
    async with engine.begin() as conn:
        await conn.run_sync(SharedBase.metadata.create_all)
        await conn.run_sync(TenantBase.metadata.create_all)

    yield engine

    # Cleanup
    async with engine.begin() as conn:
        await conn.run_sync(TenantBase.metadata.drop_all)
        await conn.run_sync(SharedBase.metadata.drop_all)

    await engine.dispose()


@pytest.fixture
async def async_session(async_engine: AsyncEngine) -> AsyncGenerator[AsyncSession, None]:
    """Yield an AsyncSession against the test engine."""
    session_factory = async_sessionmaker(
        bind=async_engine,
        class_=AsyncSession,
        expire_on_commit=False,
    )

    async with session_factory() as session:
        yield session
        await session.rollback()


@pytest.fixture
async def async_client() -> AsyncGenerator[AsyncClient, None]:
    """Create an httpx AsyncClient with the FastAPI app using ASGITransport."""
    # Override settings before importing the app
    get_settings.cache_clear()

    import app.config

    app.config.get_settings = get_test_settings  # type: ignore[assignment]

    # Reset the engine module state
    import app.db.engine as engine_module

    engine_module._engine = None

    from app.main import app as fastapi_app

    transport = ASGITransport(app=fastapi_app)
    async with AsyncClient(transport=transport, base_url="http://test") as client:
        yield client

    # Restore original
    app.config.get_settings = get_settings  # type: ignore[assignment]
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
