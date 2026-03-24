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
def mock_folio():
    """Create a MagicMock mimicking the FOLIO API surface for unit tests."""
    from unittest.mock import MagicMock

    folio = MagicMock()

    # Sample OWLClass-like mock objects from different branches
    def _make_concept(iri: str, label: str, branch: str = "", sub_class_of: list | None = None):
        concept = MagicMock()
        concept.iri = iri
        concept.label = label
        concept.sub_class_of = sub_class_of or []
        concept.parent_class_of = []
        concept.alternative_labels = []
        concept.definition = f"Definition of {label}"
        concept.examples = []
        return concept

    # Build a sample classes dict
    sample_classes = {
        "https://folio.openlegalstandard.org/objective001": _make_concept(
            "https://folio.openlegalstandard.org/objective001", "Wrongful Termination Claim", "Objectives"
        ),
        "https://folio.openlegalstandard.org/objective002": _make_concept(
            "https://folio.openlegalstandard.org/objective002", "Breach of Contract", "Objectives"
        ),
        "https://folio.openlegalstandard.org/areaoflaw001": _make_concept(
            "https://folio.openlegalstandard.org/areaoflaw001", "Employment Law", "Area of Law"
        ),
        "https://folio.openlegalstandard.org/areaoflaw002": _make_concept(
            "https://folio.openlegalstandard.org/areaoflaw002", "Family Law", "Area of Law"
        ),
        "https://folio.openlegalstandard.org/authority001": _make_concept(
            "https://folio.openlegalstandard.org/authority001", "Title VII", "Legal Authorities"
        ),
        "https://folio.openlegalstandard.org/location001": _make_concept(
            "https://folio.openlegalstandard.org/location001", "California", "Location"
        ),
        "https://folio.openlegalstandard.org/actor001": _make_concept(
            "https://folio.openlegalstandard.org/actor001", "Plaintiff", "Actor-Player"
        ),
        "https://folio.openlegalstandard.org/event001": _make_concept(
            "https://folio.openlegalstandard.org/event001", "Termination Event", "Event"
        ),
        "https://folio.openlegalstandard.org/entity001": _make_concept(
            "https://folio.openlegalstandard.org/entity001", "Corporation", "Legal Entity"
        ),
        "https://folio.openlegalstandard.org/doc001": _make_concept(
            "https://folio.openlegalstandard.org/doc001", "Employment Contract", "Document-Artifact"
        ),
        "https://folio.openlegalstandard.org/service001": _make_concept(
            "https://folio.openlegalstandard.org/service001", "Legal Representation", "Service"
        ),
        "https://folio.openlegalstandard.org/forum001": _make_concept(
            "https://folio.openlegalstandard.org/forum001", "Federal Court", "Forums and Venues"
        ),
    }
    folio.classes = sample_classes

    # search_by_label: simple label substring match
    def _search_by_label(label, limit=10, **kwargs):
        return [
            c for c in sample_classes.values()
            if label.lower() in c.label.lower()
        ][:limit]
    folio.search_by_label = _search_by_label

    # search_by_prefix: prefix match on IRI
    def _search_by_prefix(prefix, **kwargs):
        return [c for c in sample_classes.values() if c.iri.startswith(prefix)]
    folio.search_by_prefix = _search_by_prefix

    # get_children: return a fixed list of mock children
    child1 = _make_concept("https://folio.openlegalstandard.org/child001", "Child Concept 1")
    child2 = _make_concept("https://folio.openlegalstandard.org/child002", "Child Concept 2")
    folio.get_children = MagicMock(return_value=[child1, child2])

    # get_parents: return a fixed parent
    parent1 = _make_concept("https://folio.openlegalstandard.org/parent001", "Parent Concept 1")
    folio.get_parents = MagicMock(return_value=[parent1])

    # find_connections: return tuples of (subject, property, object)
    prop_mock = MagicMock()
    prop_mock.iri = "https://folio.openlegalstandard.org/prop001"
    prop_mock.label = "relates_to"
    prop_mock.domain = []
    prop_mock.range = []
    folio.find_connections = MagicMock(return_value=[
        (sample_classes["https://folio.openlegalstandard.org/objective001"], prop_mock,
         sample_classes["https://folio.openlegalstandard.org/areaoflaw001"]),
    ])

    # Branch accessors
    folio.get_objectives = MagicMock(return_value=[
        sample_classes["https://folio.openlegalstandard.org/objective001"],
        sample_classes["https://folio.openlegalstandard.org/objective002"],
    ])
    folio.get_areas_of_law = MagicMock(return_value=[
        sample_classes["https://folio.openlegalstandard.org/areaoflaw001"],
        sample_classes["https://folio.openlegalstandard.org/areaoflaw002"],
    ])
    folio.get_legal_authorities = MagicMock(return_value=[
        sample_classes["https://folio.openlegalstandard.org/authority001"],
    ])
    folio.get_locations = MagicMock(return_value=[
        sample_classes["https://folio.openlegalstandard.org/location001"],
    ])

    # Object properties dict
    folio.object_properties = {
        prop_mock.iri: prop_mock,
    }

    return folio


@pytest.fixture(scope="session")
def real_folio():
    """Load the actual FOLIO ontology for integration tests.

    Skips if folio-python is not installed or FOLIO can't load.
    """
    folio_mod = pytest.importorskip("folio")
    return folio_mod.FOLIO(github_repo_branch="main")


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
