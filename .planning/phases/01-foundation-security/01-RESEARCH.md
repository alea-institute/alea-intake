# Phase 1: Foundation & Security - Research

**Researched:** 2026-03-22
**Domain:** Authentication, encryption, multi-tenant data isolation, audit logging, consent management, Docker infrastructure
**Confidence:** HIGH

## Summary

Phase 1 establishes the entire trusted data layer for a legal intake tool handling attorney-client privileged information. The technical domain spans JWT authentication with role-based access control, AES-256 field-level envelope encryption with per-tenant keys, schema-per-tenant PostgreSQL isolation (single-tenant only for SQLite), immutable append-only audit logging, granular consent management with configurable right-to-delete cascade, and LLM provider integration via `alea-llm-client` with training data opt-out enforcement.

The stack is anchored by FastAPI + SQLAlchemy 2.0 async + Alembic + PostgreSQL (with SQLite fallback for self-hosted single-tenant). The project follows the same architectural patterns as the sibling `folio-mapper` project: FastAPI backend with routers/services/models separation, pnpm monorepo for the frontend (React/Vite/TypeScript/Tailwind), and Docker containerization. This phase is backend-only -- no frontend work -- but scaffolds the monorepo structure and Docker compose for both services.

**Primary recommendation:** Use FastAPI's built-in OAuth2PasswordBearer + PyJWT + pwdlib (Argon2) for auth, SQLAlchemy 2.0 async with `schema_translate_map` for tenant isolation, the `cryptography` library's Fernet for envelope encryption, and Alembic with per-schema migration runs for database versioning.

<user_constraints>
## User Constraints (from CONTEXT.md)

### Locked Decisions
- Three auth modes, org-configurable: email+password, OAuth/SSO, and kiosk/anonymous (no auth)
- Kiosk mode is fully org-configurable: the deploying org decides audit logging behavior, consent requirements, and data lifecycle for anonymous sessions
- Flat three-role model: admin, professional, consumer -- fixed roles with predefined permission sets. Custom roles deferred.
- One org per user -- if someone works across orgs, they have separate accounts
- Schema-per-tenant on PostgreSQL for multi-tenant deployments
- SQLite mode is single-tenant only (self-hosted deployments) -- no multi-tenancy on SQLite
- Kiosk/anonymous sessions live in the deploying org's schema with null/anonymous user reference -- org controls retention
- LLM API keys configurable per org: orgs can bring their own keys OR use platform-provided keys
- Cloud KMS (AWS KMS / GCP KMS) for cloud deployments with envelope encryption; local key file fallback for self-hosted
- Per-tenant encryption keys -- each org gets its own data encryption key wrapped by the master key
- Targeted field-level encryption for PII only: names, contact info, narrative text, document contents, voice transcripts
- Non-PII fields (timestamps, status, FOLIO IRIs, config) remain plaintext for queryability
- LLM training opt-out enforcement is org-configurable: cloud with provider opt-out flags, cloud with BAA, or local-only -- platform enforces whatever the org configures
- Consent granularity is org-configurable -- orgs define what consent options their consumers see (from all-or-nothing to per-feature granular)
- Right-to-delete audit trail handling is org-configurable: full deletion, anonymized retention, or time-based retention
- Cascade deletion: full cascade with admin confirmation preview showing what will be deleted
- Audit log stored in a separate append-only table within the tenant schema, INSERT-only permissions -- immutable by application code (except by the deletion cascade when org policy requires it)

### Claude's Discretion
- JWT token structure and refresh strategy specifics
- Exact PII field classification beyond the explicit list above
- Database migration tooling choice
- Docker compose structure and service layout
- API framework middleware ordering
- Test infrastructure setup

### Deferred Ideas (OUT OF SCOPE)
None -- discussion stayed within phase scope
</user_constraints>

<phase_requirements>
## Phase Requirements

| ID | Description | Research Support |
|----|-------------|-----------------|
| SECURITY-01 | JWT authentication with refresh tokens | PyJWT + OAuth2PasswordBearer + rotating refresh tokens pattern; pwdlib for password hashing |
| SECURITY-02 | Role-based access control: admin, professional, consumer | FastAPI dependency injection with role-checking decorators; permission sets per role |
| SECURITY-03 | AES-256 encryption at rest, TLS 1.3 in transit | Fernet envelope encryption via `cryptography` library; TLS handled at reverse proxy/uvicorn level |
| SECURITY-04 | Field-level encryption for PII data | Custom SQLAlchemy TypeDecorator + Python descriptor pattern for transparent encrypt/decrypt |
| SECURITY-05 | Immutable audit log of all actions, AI decisions, human overrides, and data access | Append-only audit table with INSERT-only DB role; PostgreSQL trigger-based capture |
| SECURITY-06 | Attorney-client privilege awareness | All data treated as privileged; encryption defaults to maximum; no data leaves tenant boundary without explicit config |
| SECURITY-07 | Consent capture before AI processing begins, with granular consent options | Consent model with configurable granularity; middleware enforcement before LLM-touching endpoints |
| SECURITY-08 | Right-to-delete with cascade deletion and anonymized audit trail preservation | Cascade deletion service with preview; configurable audit trail handling (delete/anonymize/retain) |
| SECURITY-09 | No case data sent to LLM training endpoints; configurable data residency | alea-llm-client integration with org-level LLM config; provider API policies enforced at service layer |
| SECURITY-10 | Multi-tenant data isolation (beyond RLS alone) | Schema-per-tenant via SQLAlchemy `schema_translate_map`; Alembic per-schema migrations |
| DEPLOY-01 | Configurable database backend: PostgreSQL+pgvector and SQLite+FAISS | Database abstraction layer with async engine factory; conditional imports for pg vs sqlite drivers |
| DEPLOY-04 | Docker containers for backend and frontend | Multi-stage Dockerfile (node frontend build + python backend); docker-compose with postgres service |
| INTEGRATE-04 | LLM integration via alea-llm-client supporting multiple providers | alea-llm-client v0.3.3 with OpenAI, Anthropic, Google, xAI, VLLM support; per-org key management |
</phase_requirements>

## Standard Stack

### Core

| Library | Version | Purpose | Why Standard |
|---------|---------|---------|--------------|
| fastapi | 0.135.1 | Web framework | Official stack choice; matches folio-mapper pattern |
| uvicorn[standard] | 0.42.0 | ASGI server | Standard FastAPI server; production-ready |
| sqlalchemy[asyncio] | 2.0.48 | ORM + async DB access | Industry standard; schema_translate_map for multi-tenancy |
| alembic | 1.18.4 | Database migrations | Only SQLAlchemy migration tool; per-schema support via -x flag |
| pydantic | 2.12.5 | Data validation/serialization | FastAPI's native validation layer |
| pydantic-settings | 2.13.1 | Configuration management | .env file loading + type-safe settings |
| pyjwt | 2.12.1 | JWT token creation/validation | FastAPI official docs recommend PyJWT (not python-jose) |
| pwdlib[argon2] | 0.3.0 | Password hashing | FastAPI official docs recommend pwdlib (replaces deprecated passlib) |
| cryptography | 46.0.5 | Fernet envelope encryption | Industry standard; Fernet provides AES-128-CBC+HMAC (use raw AES-256-GCM for requirement compliance) |
| bcrypt | 5.0.0 | Backup password hashing | Fallback for pwdlib if Argon2 unavailable |
| python-multipart | 0.0.22 | Form data parsing | Required by FastAPI for OAuth2 form login |
| python-dotenv | 1.2.2 | Environment variable loading | Standard .env file support |
| alea-llm-client | 0.3.3 | Multi-provider LLM abstraction | Project requirement; supports OpenAI, Anthropic, Google, xAI, VLLM |
| httpx | 0.28+ | Async HTTP client | Required by alea-llm-client; useful for internal service calls |

### Database Drivers

| Library | Version | Purpose | When to Use |
|---------|---------|---------|-------------|
| asyncpg | 0.31.0 | Async PostgreSQL driver | PostgreSQL deployments (default) |
| psycopg[binary] | 3.3.3 | PostgreSQL adapter (sync Alembic) | Migration runs, admin operations |
| aiosqlite | 0.22.1 | Async SQLite driver | Single-tenant self-hosted deployments |
| pgvector | 0.4.2 | Vector similarity for PostgreSQL | Future phases (RAG, embeddings) -- install now for schema readiness |

### Development & Testing

| Library | Version | Purpose | When to Use |
|---------|---------|---------|-------------|
| pytest | 8.x | Test framework | All testing |
| pytest-asyncio | 0.24+ | Async test support | Testing async endpoints and DB operations |
| httpx | 0.28+ | Test client | FastAPI TestClient replacement for async |
| factory-boy | 3.x | Test fixtures | Database model factories |
| ruff | 0.x | Linting + formatting | Code quality (replaces black + isort + flake8) |

### Alternatives Considered

| Instead of | Could Use | Tradeoff |
|------------|-----------|----------|
| PyJWT | python-jose | python-jose last released 2023, less maintained; PyJWT is FastAPI official recommendation |
| pwdlib | passlib | passlib unmaintained since 2020, broken with bcrypt 5.0; pwdlib is the replacement |
| cryptography (raw AES-256-GCM) | Fernet | Fernet uses AES-128-CBC; requirement says AES-256. Use `cryptography` AESGCM directly for AES-256 compliance |
| asyncpg | psycopg[async] | psycopg3 has async support too, but asyncpg is more mature for pure async workloads |
| SQLAlchemy | SQLModel | SQLModel adds Pydantic integration but has gaps with advanced features like schema_translate_map |
| Alembic | manual SQL | Never -- Alembic handles the schema-per-tenant migration pattern correctly |

**Installation:**
```bash
# Backend dependencies (in pyproject.toml)
pip install "fastapi>=0.135.0,<1.0" "uvicorn[standard]>=0.42.0" "sqlalchemy[asyncio]>=2.0.48" \
  "alembic>=1.18.0" "pydantic>=2.12.0" "pydantic-settings>=2.13.0" \
  "pyjwt>=2.12.0" "pwdlib[argon2]>=0.3.0" "cryptography>=46.0.0" \
  "python-multipart>=0.0.22" "python-dotenv>=1.2.0" \
  "alea-llm-client>=0.3.0" "httpx>=0.28.0" \
  "asyncpg>=0.31.0" "psycopg[binary]>=3.3.0" "aiosqlite>=0.22.0" \
  "pgvector>=0.4.0"
```

## Architecture Patterns

### Recommended Project Structure
```
alea-intake/
├── backend/
│   ├── pyproject.toml
│   ├── uv.lock
│   ├── alembic/
│   │   ├── alembic.ini
│   │   ├── env.py              # Multi-schema aware
│   │   └── versions/
│   ├── app/
│   │   ├── __init__.py
│   │   ├── main.py             # FastAPI app, lifespan, middleware
│   │   ├── config.py           # Pydantic Settings
│   │   ├── core/
│   │   │   ├── security.py     # JWT, password hashing, token utils
│   │   │   ├── encryption.py   # Envelope encryption, field-level crypto
│   │   │   ├── permissions.py  # Role definitions, permission checking
│   │   │   └── exceptions.py   # Custom exception classes
│   │   ├── db/
│   │   │   ├── engine.py       # Async engine factory (pg/sqlite)
│   │   │   ├── session.py      # Session dependency with schema routing
│   │   │   ├── base.py         # Declarative base with tenant schema
│   │   │   └── tenant.py       # Tenant resolution, schema management
│   │   ├── models/
│   │   │   ├── user.py         # User, Role models
│   │   │   ├── organization.py # Org, org config models
│   │   │   ├── audit.py        # Audit log model
│   │   │   ├── consent.py      # Consent records model
│   │   │   └── shared.py       # Shared-schema models (tenant registry)
│   │   ├── schemas/            # Pydantic request/response schemas
│   │   │   ├── auth.py
│   │   │   ├── user.py
│   │   │   ├── organization.py
│   │   │   ├── audit.py
│   │   │   └── consent.py
│   │   ├── routers/
│   │   │   ├── auth.py         # Login, register, refresh, logout
│   │   │   ├── users.py        # User CRUD
│   │   │   ├── organizations.py
│   │   │   ├── audit.py        # Audit log read endpoints
│   │   │   ├── consent.py      # Consent flow endpoints
│   │   │   └── admin.py        # Admin operations, deletion
│   │   ├── services/
│   │   │   ├── auth_service.py
│   │   │   ├── user_service.py
│   │   │   ├── audit_service.py
│   │   │   ├── consent_service.py
│   │   │   ├── deletion_service.py  # Right-to-delete cascade
│   │   │   ├── llm_service.py       # alea-llm-client wrapper
│   │   │   └── tenant_service.py    # Schema creation, key provisioning
│   │   └── middleware/
│   │       ├── tenant.py       # Tenant resolution middleware
│   │       ├── audit.py        # Request-level audit capture
│   │       └── consent.py      # Consent enforcement middleware
│   └── tests/
│       ├── conftest.py         # Fixtures, test DB setup
│       ├── test_auth.py
│       ├── test_rbac.py
│       ├── test_encryption.py
│       ├── test_audit.py
│       ├── test_consent.py
│       ├── test_tenancy.py
│       └── test_deletion.py
├── frontend/                    # Scaffolded but minimal in Phase 1
│   ├── package.json
│   └── ...
├── docker-compose.yml
├── docker-compose.dev.yml
├── Dockerfile                   # Multi-stage (matches folio-mapper pattern)
├── package.json                 # Root pnpm workspace
├── pnpm-workspace.yaml
└── pyproject.toml               # Root (optional, for tooling)
```

### Pattern 1: Schema-Per-Tenant Isolation

**What:** Each organization gets its own PostgreSQL schema. A `shared` schema holds the tenant registry and global config. All tenant-specific tables (users, cases, audit logs, consent records) live in `tenant_{org_slug}` schemas.

**When to use:** PostgreSQL multi-tenant deployments (the default).

**Implementation:**

```python
# db/base.py -- Declarative base with placeholder schema
import sqlalchemy as sa
from sqlalchemy.orm import DeclarativeBase

# "tenant" is a placeholder that gets remapped per-request
tenant_metadata = sa.MetaData(schema="tenant")
shared_metadata = sa.MetaData(schema="shared")

class TenantBase(DeclarativeBase):
    metadata = tenant_metadata

class SharedBase(DeclarativeBase):
    metadata = shared_metadata


# db/session.py -- Per-request session with schema translation
from sqlalchemy.ext.asyncio import create_async_engine, async_sessionmaker, AsyncSession
from fastapi import Depends, Request

async def get_tenant_session(request: Request) -> AsyncSession:
    tenant_schema = request.state.tenant_schema  # Set by middleware
    engine = get_engine()  # Cached async engine
    connectable = engine.execution_options(
        schema_translate_map={"tenant": tenant_schema}
    )
    session_factory = async_sessionmaker(connectable, expire_on_commit=False)
    async with session_factory() as session:
        yield session
```

### Pattern 2: Envelope Encryption with Per-Tenant Keys

**What:** Each tenant gets a unique Data Encryption Key (DEK). The DEK is wrapped by a Key Encryption Key (KEK) -- either from cloud KMS or a local master key file. Field-level encryption uses AES-256-GCM via the `cryptography` library.

**When to use:** All PII fields in all deployment modes.

**Implementation:**

```python
# core/encryption.py
import os
from cryptography.hazmat.primitives.ciphers.aead import AESGCM

class EnvelopeEncryption:
    """Per-tenant envelope encryption with AES-256-GCM."""

    def __init__(self, kek: bytes):
        """kek: 32-byte Key Encryption Key (from KMS or local file)."""
        self.kek = kek

    def generate_dek(self) -> bytes:
        """Generate a new 256-bit Data Encryption Key."""
        return AESGCM.generate_key(bit_length=256)

    def wrap_dek(self, dek: bytes) -> bytes:
        """Encrypt DEK with KEK for storage."""
        nonce = os.urandom(12)
        aesgcm = AESGCM(self.kek)
        encrypted = aesgcm.encrypt(nonce, dek, None)
        return nonce + encrypted  # prepend nonce for decryption

    def unwrap_dek(self, wrapped_dek: bytes) -> bytes:
        """Decrypt DEK using KEK."""
        nonce = wrapped_dek[:12]
        encrypted = wrapped_dek[12:]
        aesgcm = AESGCM(self.kek)
        return aesgcm.decrypt(nonce, encrypted, None)

    def encrypt_field(self, dek: bytes, plaintext: str) -> bytes:
        """Encrypt a single field value with the tenant's DEK."""
        nonce = os.urandom(12)
        aesgcm = AESGCM(dek)
        encrypted = aesgcm.encrypt(nonce, plaintext.encode("utf-8"), None)
        return nonce + encrypted

    def decrypt_field(self, dek: bytes, ciphertext: bytes) -> str:
        """Decrypt a single field value with the tenant's DEK."""
        nonce = ciphertext[:12]
        encrypted = ciphertext[12:]
        aesgcm = AESGCM(dek)
        return aesgcm.decrypt(nonce, encrypted, None).decode("utf-8")
```

### Pattern 3: Immutable Audit Log

**What:** Append-only audit table within each tenant schema. The application DB role has INSERT-only permission on the audit table -- no UPDATE, no DELETE (except when org policy permits deletion cascade).

**When to use:** Every state-changing operation, every data access, every AI decision.

**Implementation:**

```python
# models/audit.py
from sqlalchemy import Column, Integer, String, DateTime, JSON, text
from sqlalchemy.sql import func
from app.db.base import TenantBase

class AuditLog(TenantBase):
    __tablename__ = "audit_log"

    id = Column(Integer, primary_key=True, autoincrement=True)
    timestamp = Column(DateTime(timezone=True), server_default=func.now(), nullable=False)
    actor_id = Column(Integer, nullable=True)  # null for system/anonymous
    actor_role = Column(String(20), nullable=True)
    action = Column(String(100), nullable=False)  # e.g., "user.login", "case.view", "ai.decision"
    resource_type = Column(String(50), nullable=True)
    resource_id = Column(Integer, nullable=True)
    details = Column(JSON, nullable=True)  # Action-specific metadata
    ip_address = Column(String(45), nullable=True)
    request_id = Column(String(36), nullable=True)  # Correlation ID

# PostgreSQL: REVOKE UPDATE, DELETE ON audit_log FROM app_role;
# Only the migration/admin role can modify the audit table structure
```

### Pattern 4: JWT with Rotating Refresh Tokens

**What:** Short-lived access tokens (15-30 min) + long-lived refresh tokens (7 days) stored in DB. Each refresh rotates the token (old one invalidated). Refresh token family tracking detects reuse attacks.

**When to use:** Email+password auth mode. OAuth/SSO uses provider tokens. Kiosk mode uses session-scoped ephemeral tokens.

**Implementation:**

```python
# core/security.py
import jwt
from datetime import datetime, timedelta, timezone
from pwdlib import PasswordHash

password_hash = PasswordHash.recommended()  # Argon2 by default

ACCESS_TOKEN_EXPIRE_MINUTES = 30
REFRESH_TOKEN_EXPIRE_DAYS = 7

def create_access_token(
    user_id: int,
    org_id: int,
    role: str,
    secret_key: str,
    expires_delta: timedelta | None = None,
) -> str:
    expire = datetime.now(timezone.utc) + (expires_delta or timedelta(minutes=ACCESS_TOKEN_EXPIRE_MINUTES))
    payload = {
        "sub": str(user_id),
        "org": str(org_id),
        "role": role,
        "exp": expire,
        "type": "access",
    }
    return jwt.encode(payload, secret_key, algorithm="HS256")

def create_refresh_token(
    user_id: int,
    org_id: int,
    token_family: str,
    secret_key: str,
) -> str:
    expire = datetime.now(timezone.utc) + timedelta(days=REFRESH_TOKEN_EXPIRE_DAYS)
    payload = {
        "sub": str(user_id),
        "org": str(org_id),
        "family": token_family,
        "exp": expire,
        "type": "refresh",
    }
    return jwt.encode(payload, secret_key, algorithm="HS256")
```

### Pattern 5: Database Abstraction Layer

**What:** A factory that creates the appropriate async engine based on configuration. PostgreSQL uses `asyncpg`, SQLite uses `aiosqlite`. The abstraction sits in `db/engine.py` and is selected at startup.

**When to use:** Always -- never hard-code a database driver.

**Implementation:**

```python
# db/engine.py
from sqlalchemy.ext.asyncio import create_async_engine, AsyncEngine
from app.config import settings

def create_engine() -> AsyncEngine:
    if settings.database_backend == "postgresql":
        url = f"postgresql+asyncpg://{settings.db_user}:{settings.db_password}@{settings.db_host}:{settings.db_port}/{settings.db_name}"
        return create_async_engine(url, pool_size=20, max_overflow=10)
    elif settings.database_backend == "sqlite":
        url = f"sqlite+aiosqlite:///{settings.sqlite_path}"
        return create_async_engine(url, echo=False)
    else:
        raise ValueError(f"Unsupported database backend: {settings.database_backend}")
```

### Anti-Patterns to Avoid

- **Row-Level Security alone for tenant isolation:** The user locked in schema-per-tenant. RLS is insufficient for the required isolation level with privileged legal data. Schema boundaries provide stronger guarantees.
- **Storing encryption keys in the database:** KEKs must come from environment/KMS, never from the same database that holds the encrypted data.
- **Mutable audit logs:** Never allow UPDATE/DELETE on audit tables. Even soft-delete is not "immutable." Use INSERT-only DB permissions.
- **Shared password hashing between auth modes:** Kiosk mode has no passwords. OAuth/SSO delegates to providers. Only email+password mode needs password hashing. Don't force a password column on users who don't have one.
- **Synchronous database operations:** FastAPI is async-first. Using synchronous SQLAlchemy calls blocks the event loop and kills throughput.
- **Using Fernet for "AES-256" claims:** Fernet uses AES-128-CBC, not AES-256. The requirement specifies AES-256. Use `AESGCM` from `cryptography` with a 256-bit key for compliance.

## Don't Hand-Roll

| Problem | Don't Build | Use Instead | Why |
|---------|-------------|-------------|-----|
| Password hashing | Custom bcrypt wrapper | pwdlib[argon2] | Timing attack resistance, future algorithm migration, work factor tuning |
| JWT creation/validation | Manual base64 + HMAC | PyJWT | Clock skew handling, algorithm confusion prevention, claim validation |
| AES encryption | Raw PyCryptodome calls | `cryptography` AESGCM | Audited implementation, nonce management, authenticated encryption |
| Database migrations | Raw SQL scripts | Alembic | Rollback support, version tracking, autogenerate from models |
| Environment config | os.getenv() everywhere | pydantic-settings | Type validation, nested config, .env file support, secrets file support |
| UUID generation | time-based custom IDs | Python stdlib uuid4 | Cryptographic randomness, no timing leaks |
| Request validation | Manual dict checking | Pydantic models | Automatic OpenAPI docs, type coercion, error messages |
| CORS handling | Manual headers | FastAPI CORSMiddleware | Preflight handling, credential support, origin validation |

**Key insight:** Security primitives are where hand-rolling is most dangerous. A single missed edge case (timing attack, nonce reuse, algorithm confusion) can invalidate the entire security model. Use audited libraries for every cryptographic and authentication operation.

## Common Pitfalls

### Pitfall 1: Fernet vs AES-256 Confusion
**What goes wrong:** Many tutorials use Fernet for "encryption at rest" and claim AES-256. Fernet actually uses AES-128-CBC with HMAC-SHA256. The requirement explicitly says "AES-256."
**Why it happens:** Fernet's HMAC uses SHA-256, which people confuse with the AES key size.
**How to avoid:** Use `cryptography.hazmat.primitives.ciphers.aead.AESGCM` with a 256-bit (32-byte) key. This gives true AES-256-GCM with authenticated encryption.
**Warning signs:** Any code importing `from cryptography.fernet import Fernet` for "AES-256" compliance.

### Pitfall 2: Schema Translation Map and Connections
**What goes wrong:** Trying to change `schema_translate_map` mid-connection. SQLAlchemy sets it at connection establishment time -- you cannot switch schemas on an existing connection.
**Why it happens:** Developers try to reuse connections across tenants for efficiency.
**How to avoid:** Always create a new connection/session per request with the correct `schema_translate_map`. Use `engine.execution_options()` which returns a new engine copy, not a mutation.
**Warning signs:** "Wrong tenant data" errors, cross-tenant data leakage in tests.

### Pitfall 3: Alembic Schema Migrations
**What goes wrong:** Alembic autogenerate produces migrations with hardcoded schema names. Running these against different tenant schemas fails or corrupts data.
**Why it happens:** Alembic doesn't natively support multi-schema operations.
**How to avoid:** Use Alembic's `-x tenant=schema_name` flag. In `env.py`, run migrations in "schemaless" mode by setting `search_path` to the target schema. Run Alembic once per tenant schema.
**Warning signs:** Migration files containing literal `"tenant_orgname"` references instead of parameterized schema.

### Pitfall 4: passlib Incompatibility
**What goes wrong:** passlib breaks with bcrypt >= 5.0.0 and Python >= 3.13. Import errors, deprecation warnings that become exceptions.
**Why it happens:** passlib has not been updated since 2020. Many FastAPI tutorials still reference it.
**How to avoid:** Use `pwdlib[argon2]` -- the FastAPI docs now recommend it as the replacement.
**Warning signs:** `from passlib.context import CryptContext` in any new code.

### Pitfall 5: Encrypted Fields Break Queryability
**What goes wrong:** Encrypting a field means the database cannot index, search, or filter on it. Developers encrypt everything then realize they can't query by name.
**Why it happens:** Overzealous encryption without considering access patterns.
**How to avoid:** The user decision already addresses this: encrypt PII only (names, contact info, narratives, documents, transcripts). Leave timestamps, status, FOLIO IRIs, and config plaintext for queryability.
**Warning signs:** SQL queries with WHERE clauses on encrypted columns returning no results.

### Pitfall 6: Audit Log in Deletion Cascade
**What goes wrong:** The audit log is append-only and immutable -- but the right-to-delete cascade might need to touch audit records per org policy.
**Why it happens:** Tension between GDPR/right-to-delete and immutability.
**How to avoid:** The user decision makes this org-configurable: full deletion, anonymized retention, or time-based retention. Implement deletion as a separate privileged operation (not the normal app role) that the cascade service invokes with elevated permissions when the org policy requires it.
**Warning signs:** Application code that can UPDATE audit_log records during normal operation.

### Pitfall 7: SQLite Multi-Tenancy Attempts
**What goes wrong:** Trying to implement schema-per-tenant on SQLite. SQLite doesn't have schema support -- it uses ATTACH for multi-database access, which is fundamentally different.
**Why it happens:** Developers try to make the abstraction too uniform.
**How to avoid:** The user decision locks this: SQLite is single-tenant only. When `database_backend == "sqlite"`, skip all multi-tenancy logic. The tenant is implicit (the entire database).
**Warning signs:** Code trying to create schemas in SQLite.

### Pitfall 8: LLM Training Opt-Out Assumptions
**What goes wrong:** Assuming all LLM providers have the same training data policies. OpenAI API doesn't train on API data by default. Anthropic's consumer products changed policy in 2025 but API/commercial access remains non-training. Each provider is different.
**Why it happens:** Developers treat all providers uniformly without checking policies.
**How to avoid:** The user decision makes this org-configurable. The platform should: (1) use API-tier access (not consumer-tier), (2) set provider-specific headers when available, (3) respect org-level configuration (cloud+opt-out, cloud+BAA, local-only).
**Warning signs:** Sending data to consumer LLM endpoints, not checking provider terms.

## Code Examples

### Configuration Management

```python
# config.py
from pydantic_settings import BaseSettings
from enum import Enum

class DatabaseBackend(str, Enum):
    POSTGRESQL = "postgresql"
    SQLITE = "sqlite"

class LLMDataPolicy(str, Enum):
    CLOUD_WITH_OPTOUT = "cloud_optout"
    CLOUD_WITH_BAA = "cloud_baa"
    LOCAL_ONLY = "local_only"

class Settings(BaseSettings):
    # Application
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

    # Encryption
    master_key_path: str = ""  # Path to local key file (self-hosted)
    kms_provider: str = ""     # "aws" or "gcp" (cloud)
    kms_key_id: str = ""       # KMS key ARN/ID

    # Auth
    access_token_expire_minutes: int = 30
    refresh_token_expire_days: int = 7

    model_config = {"env_file": ".env", "env_prefix": "ALEA_"}
```

### RBAC Dependency Injection

```python
# core/permissions.py
from enum import Enum
from fastapi import Depends, HTTPException, status
from typing import Annotated

class Role(str, Enum):
    ADMIN = "admin"
    PROFESSIONAL = "professional"
    CONSUMER = "consumer"

ROLE_PERMISSIONS = {
    Role.ADMIN: {"users.read", "users.write", "audit.read", "org.manage", "cases.read", "cases.write", "consent.manage", "deletion.execute"},
    Role.PROFESSIONAL: {"cases.read", "cases.write", "audit.read.own", "consent.read"},
    Role.CONSUMER: {"cases.read.own", "cases.write.own", "consent.manage.own", "deletion.request"},
}

def require_role(*allowed_roles: Role):
    """Dependency that checks the current user has one of the allowed roles."""
    async def check_role(current_user = Depends(get_current_active_user)):
        if current_user.role not in allowed_roles:
            raise HTTPException(
                status_code=status.HTTP_403_FORBIDDEN,
                detail="Insufficient permissions",
            )
        return current_user
    return check_role

def require_permission(permission: str):
    """Dependency that checks the current user has a specific permission."""
    async def check_permission(current_user = Depends(get_current_active_user)):
        user_permissions = ROLE_PERMISSIONS.get(current_user.role, set())
        if permission not in user_permissions:
            raise HTTPException(
                status_code=status.HTTP_403_FORBIDDEN,
                detail=f"Missing permission: {permission}",
            )
        return current_user
    return check_permission
```

### Consent Model

```python
# models/consent.py
from sqlalchemy import Column, Integer, String, Boolean, DateTime, ForeignKey, JSON
from sqlalchemy.sql import func
from app.db.base import TenantBase

class ConsentRecord(TenantBase):
    __tablename__ = "consent_records"

    id = Column(Integer, primary_key=True)
    user_id = Column(Integer, ForeignKey("users.id"), nullable=True)  # null for anonymous/kiosk
    session_id = Column(String(36), nullable=True)  # For kiosk sessions
    consent_version = Column(String(20), nullable=False)
    granted_at = Column(DateTime(timezone=True), server_default=func.now())
    revoked_at = Column(DateTime(timezone=True), nullable=True)
    consent_items = Column(JSON, nullable=False)  # {"ai_processing": true, "data_storage": true, ...}
    ip_address = Column(String(45), nullable=True)

class ConsentTemplate(TenantBase):
    """Org-configurable consent options."""
    __tablename__ = "consent_templates"

    id = Column(Integer, primary_key=True)
    org_id = Column(Integer, nullable=False)
    version = Column(String(20), nullable=False)
    items = Column(JSON, nullable=False)  # [{"key": "ai_processing", "label": "...", "required": true}, ...]
    is_active = Column(Boolean, default=True)
```

### Middleware Ordering

```python
# main.py -- Middleware stack (outermost first)
from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware

app = FastAPI(title="ALEA Intake API", version="0.1.0")

# 1. Security headers (outermost -- always applied)
app.add_middleware(SecurityHeadersMiddleware)

# 2. CORS (must be before auth to handle preflight)
app.add_middleware(CORSMiddleware, allow_origins=settings.cors_origins, ...)

# 3. Request ID / correlation ID
app.add_middleware(RequestIdMiddleware)

# 4. Tenant resolution (extracts org from JWT or host header)
app.add_middleware(TenantMiddleware)

# 5. Audit capture (logs request metadata)
app.add_middleware(AuditMiddleware)

# Note: Auth is NOT middleware -- it's a per-route dependency via Depends()
# This allows unauthenticated routes (health, login, kiosk) to coexist
```

### Docker Compose

```yaml
# docker-compose.yml
services:
  db:
    image: pgvector/pgvector:pg17
    environment:
      POSTGRES_DB: alea_intake
      POSTGRES_USER: alea
      POSTGRES_PASSWORD: ${DB_PASSWORD}
    volumes:
      - pgdata:/var/lib/postgresql/data
    ports:
      - "5432:5432"
    healthcheck:
      test: ["CMD-SHELL", "pg_isready -U alea -d alea_intake"]
      interval: 5s
      timeout: 3s
      retries: 5

  backend:
    build:
      context: .
      dockerfile: Dockerfile
      target: backend
    environment:
      ALEA_DATABASE_BACKEND: postgresql
      ALEA_DB_HOST: db
      ALEA_DB_PORT: 5432
      ALEA_DB_NAME: alea_intake
      ALEA_DB_USER: alea
      ALEA_DB_PASSWORD: ${DB_PASSWORD}
      ALEA_SECRET_KEY: ${SECRET_KEY}
    ports:
      - "8000:8000"
    depends_on:
      db:
        condition: service_healthy

volumes:
  pgdata:
```

## State of the Art

| Old Approach | Current Approach | When Changed | Impact |
|--------------|------------------|--------------|--------|
| passlib + bcrypt | pwdlib + Argon2 | 2024-2025 | passlib unmaintained; pwdlib is now FastAPI official recommendation |
| python-jose for JWT | PyJWT | 2024 | python-jose last release 2023; PyJWT actively maintained, FastAPI switched recommendation |
| Fernet "AES-256" | AESGCM from cryptography | Always | Fernet is AES-128-CBC; AESGCM with 32-byte key gives true AES-256-GCM |
| Sync SQLAlchemy + threads | Async SQLAlchemy 2.0 + asyncpg | 2023 | Native async engine, no thread pool overhead, better FastAPI integration |
| RLS for multi-tenancy | Schema-per-tenant | Varies | Stronger isolation for privileged data; RLS can be bypassed by superuser |
| Manual schema management | Alembic -x tenant flag | Alembic 1.x | Per-schema migration execution without hardcoded schema names |

**Deprecated/outdated:**
- **passlib**: Last release 2020. Breaks with bcrypt 5.0+. Use pwdlib instead.
- **python-jose**: Last release 2023. PyJWT is the active standard.
- **SQLAlchemy 1.x patterns**: Session.query() style is legacy. Use 2.0-style select() statements.
- **Synchronous FastAPI DB patterns**: Any tutorial using `Session` instead of `AsyncSession` is outdated for new projects.

## Open Questions

1. **Cloud KMS Integration Depth**
   - What we know: AWS KMS and GCP KMS both support envelope encryption with wrap/unwrap operations. The `cryptography` library doesn't directly interface with cloud KMS -- you need `boto3` (AWS) or `google-cloud-kms` (GCP).
   - What's unclear: Whether to add cloud KMS SDK dependencies in Phase 1 or defer to Phase 11 (production deployment), using local key file for all development.
   - Recommendation: Use local key file for Phase 1. Add KMS provider abstraction interface now (to avoid refactoring later) but implement only the local key file backend. Cloud KMS backends are a production concern.

2. **alea-llm-client Training Data Controls**
   - What we know: The library (v0.3.3) provides multi-provider LLM access. OpenAI API does not train on API data by default. Anthropic API/commercial access also does not train by default. No explicit "training opt-out header" mechanism found in the library docs.
   - What's unclear: Whether alea-llm-client exposes provider-specific configuration for data handling policies, or if this must be handled at the account/contract level with each provider.
   - Recommendation: Enforce training opt-out at three levels: (1) use API-tier access (not consumer), (2) pass provider-specific headers when available (e.g., OpenAI organization headers), (3) make LLM provider selection org-configurable so orgs choosing "local-only" never hit cloud APIs.

3. **Kiosk Mode Session Management**
   - What we know: Kiosk mode has no user authentication. Sessions need some form of tracking for audit and consent.
   - What's unclear: Whether to use ephemeral JWT-like tokens for kiosk sessions or simple session IDs.
   - Recommendation: Issue short-lived session tokens (not JWTs -- simpler opaque tokens) for kiosk sessions. Store in the audit/consent tables with `user_id=null` and `session_id` for correlation. Org configures retention.

## Validation Architecture

### Test Framework
| Property | Value |
|----------|-------|
| Framework | pytest 8.x + pytest-asyncio 0.24+ |
| Config file | none -- Wave 0 |
| Quick run command | `cd backend && python -m pytest tests/ -x -q` |
| Full suite command | `cd backend && python -m pytest tests/ -v --tb=short` |

### Phase Requirements to Test Map
| Req ID | Behavior | Test Type | Automated Command | File Exists? |
|--------|----------|-----------|-------------------|-------------|
| SECURITY-01 | User registers, logs in with JWT, gets access+refresh tokens | integration | `pytest tests/test_auth.py -x` | Wave 0 |
| SECURITY-02 | Admin/professional/consumer access only permitted resources | integration | `pytest tests/test_rbac.py -x` | Wave 0 |
| SECURITY-03 | PII fields stored as ciphertext; decrypted on read | unit | `pytest tests/test_encryption.py -x` | Wave 0 |
| SECURITY-04 | Field-level encryption round-trips correctly with per-tenant keys | unit | `pytest tests/test_encryption.py::test_field_level -x` | Wave 0 |
| SECURITY-05 | Actions produce audit log entries; audit table is append-only | integration | `pytest tests/test_audit.py -x` | Wave 0 |
| SECURITY-06 | All data treated as privileged (tested via encryption + isolation) | integration | Covered by SECURITY-03/04/10 tests | -- |
| SECURITY-07 | Consent required before AI-touching endpoints; granular options | integration | `pytest tests/test_consent.py -x` | Wave 0 |
| SECURITY-08 | Right-to-delete cascades all records; audit handling per org config | integration | `pytest tests/test_deletion.py -x` | Wave 0 |
| SECURITY-09 | LLM service uses org-configured provider; no training endpoint | unit | `pytest tests/test_llm_service.py -x` | Wave 0 |
| SECURITY-10 | Tenant A cannot access Tenant B's data | integration | `pytest tests/test_tenancy.py -x` | Wave 0 |
| DEPLOY-01 | App starts with PostgreSQL; app starts with SQLite | smoke | `pytest tests/test_db_backend.py -x` | Wave 0 |
| DEPLOY-04 | Docker build succeeds; container starts and responds to health check | smoke | `docker compose build && docker compose up -d && curl localhost:8000/health` | Wave 0 |
| INTEGRATE-04 | LLM client initializes with org config; can make a test call | integration | `pytest tests/test_llm_service.py::test_init -x` | Wave 0 |

### Sampling Rate
- **Per task commit:** `cd backend && python -m pytest tests/ -x -q`
- **Per wave merge:** `cd backend && python -m pytest tests/ -v --tb=short`
- **Phase gate:** Full suite green before `/gsd:verify-work`

### Wave 0 Gaps
- [ ] `backend/tests/conftest.py` -- shared fixtures (async test DB, test tenant, test users per role)
- [ ] `backend/tests/test_auth.py` -- covers SECURITY-01
- [ ] `backend/tests/test_rbac.py` -- covers SECURITY-02
- [ ] `backend/tests/test_encryption.py` -- covers SECURITY-03, SECURITY-04
- [ ] `backend/tests/test_audit.py` -- covers SECURITY-05
- [ ] `backend/tests/test_consent.py` -- covers SECURITY-07
- [ ] `backend/tests/test_deletion.py` -- covers SECURITY-08
- [ ] `backend/tests/test_llm_service.py` -- covers SECURITY-09, INTEGRATE-04
- [ ] `backend/tests/test_tenancy.py` -- covers SECURITY-10
- [ ] `backend/tests/test_db_backend.py` -- covers DEPLOY-01
- [ ] `backend/pyproject.toml` -- project definition with all dependencies
- [ ] `backend/pytest.ini` or `[tool.pytest.ini_options]` in pyproject.toml -- pytest + asyncio config
- [ ] Framework install: `pip install "pytest>=8.0" "pytest-asyncio>=0.24" "httpx>=0.28"` (via pyproject.toml dev deps)

## Sources

### Primary (HIGH confidence)
- [FastAPI Official Docs - OAuth2 JWT](https://fastapi.tiangolo.com/tutorial/security/oauth2-jwt/) -- PyJWT + pwdlib recommendation, dependency injection pattern
- [SQLAlchemy Wiki - SymmetricEncryptionClientSide](https://github.com/sqlalchemy/sqlalchemy/wiki/SymmetricEncryptionClientSide) -- TypeDecorator encryption pattern
- [PyPI package versions](https://pypi.org/) -- All version numbers verified via `pip index versions`
- [alea-llm-client GitHub](https://github.com/alea-institute/alea-llm-client) -- v0.3.3, multi-provider support, API surface
- [folio-mapper project](../../../folio-mapper/) -- Reference architecture for FastAPI + React + pnpm monorepo

### Secondary (MEDIUM confidence)
- [MergeBoard - Multitenancy with FastAPI, SQLAlchemy and PostgreSQL](https://mergeboard.com/blog/6-multitenancy-fastapi-sqlalchemy-postgresql/) -- schema_translate_map pattern, Alembic migration strategy
- [Miguel Grinberg - Encryption at Rest with SQLAlchemy](https://blog.miguelgrinberg.com/post/encryption-at-rest-with-sqlalchemy) -- TypeDecorator encryption, Fernet pattern, limitations
- [DevHuddle - Envelope Encryption for SQLAlchemy Fields](https://devhuddle.ai/envelope-encryption-for-sqlalchemy-fields/) -- KEK/DEK pattern, Python descriptor approach
- [Alembic Cookbook](https://alembic.sqlalchemy.org/en/latest/cookbook.html) -- Multi-schema migration with -x flag
- [FastAPI Discussion #11773](https://github.com/fastapi/fastapi/discussions/11773) -- passlib deprecation, pwdlib recommendation
- [OpenAI Data Controls](https://developers.openai.com/api/docs/guides/your-data) -- API data not used for training by default

### Tertiary (LOW confidence)
- [Anthropic Training Data Policy Changes](https://techcrunch.com/2025/08/28/anthropic-users-face-a-new-choice-opt-out-or-share-your-data-for-ai-training/) -- Consumer vs. commercial/API access policies (August 2025)
- alea-llm-client training opt-out capabilities -- No explicit documentation found; needs validation against library source

## Metadata

**Confidence breakdown:**
- Standard stack: HIGH -- All versions verified against PyPI. Library choices match FastAPI official docs and folio-mapper precedent.
- Architecture: HIGH -- Schema-per-tenant pattern verified via SQLAlchemy docs and community implementations. Envelope encryption pattern well-documented.
- Pitfalls: HIGH -- Each pitfall verified against multiple sources (broken passlib, Fernet vs AES-256, schema_translate_map limitations).
- LLM integration: MEDIUM -- alea-llm-client features confirmed via GitHub, but training opt-out enforcement details are thin.
- Kiosk mode session management: MEDIUM -- No standard pattern exists; recommendation is based on security principles rather than established precedent.

**Research date:** 2026-03-22
**Valid until:** 2026-04-22 (30 days -- stable domain, but check alea-llm-client for updates)
