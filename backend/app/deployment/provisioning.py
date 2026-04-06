"""Enhanced tenant provisioning: schema creation, protocol seeding, admin user.

Supports both multi-tenant (schema per org) and single-tenant (public schema)
deployment modes. Handles self-service and admin-approval signup modes (D-10).
"""

import logging
import os
import secrets
import subprocess
import string

from sqlalchemy import select, text
from sqlalchemy.ext.asyncio import AsyncSession

from app.config import DeploymentMode, get_settings

logger = logging.getLogger(__name__)


class TenantProvisioner:
    """Provision new tenants with schema, protocols, and admin user."""

    def __init__(self, session: AsyncSession, deployment_mode: DeploymentMode) -> None:
        self.session = session
        self.deployment_mode = deployment_mode

    @property
    def signup_mode(self) -> str:
        """Read tenant signup mode from settings (D-10)."""
        return get_settings().tenant_signup_mode

    async def provision_tenant(
        self,
        name: str,
        slug: str,
        admin_email: str,
        admin_name: str,
    ) -> dict:
        """Provision a new tenant with all required resources.

        Multi-tenant: Creates DB schema, runs migration, seeds protocols, creates admin.
        Single-tenant: Skips schema creation, seeds protocols, creates admin.

        Args:
            name: Organization display name.
            slug: URL-safe org identifier (used for schema naming).
            admin_email: Email for the initial admin user.
            admin_name: Display name for the admin user.

        Returns:
            Dict with org_id, admin_user_id, admin_password, slug.
        """
        logger.info("Provisioning tenant: %s (slug=%s, mode=%s)", name, slug, self.deployment_mode.value)

        # Multi-tenant: create schema and run migration
        if self.deployment_mode == DeploymentMode.MULTI_TENANT:
            await self._create_schema(slug)
            await self._run_tenant_migration(slug)

        # Create org record in shared schema
        org = await self._create_org_record(name=name, slug=slug)

        # Create org config in tenant schema
        await self._create_org_config(org_id=org.id)

        # Seed default screening protocols
        await self._seed_screening_protocols()

        # Create admin user
        admin_result = await self._create_admin_user(
            org_id=org.id, email=admin_email, name=admin_name
        )

        result = {
            "org_id": org.id,
            "admin_user_id": admin_result["user_id"],
            "admin_password": admin_result["password"],
            "slug": slug,
        }

        logger.info("Tenant provisioned: %s (org_id=%d)", slug, org.id)
        return result

    async def approve_tenant(self, org_id: int) -> None:
        """Approve a pending tenant (admin-approval mode).

        Marks org as active and triggers any post-approval setup.
        """
        from app.models.shared import Organization

        result = await self.session.execute(
            select(Organization).where(Organization.id == org_id)
        )
        org = result.scalar_one_or_none()
        if org is None:
            raise ValueError(f"Organization {org_id} not found")

        org.is_active = True
        await self.session.flush()
        logger.info("Tenant approved: org_id=%d", org_id)

    async def _create_schema(self, slug: str) -> None:
        """Create tenant schema in PostgreSQL (multi-tenant only)."""
        schema_name = f"tenant_{slug}"
        logger.info("Creating schema: %s", schema_name)
        await self.session.execute(
            text(f'CREATE SCHEMA IF NOT EXISTS "{schema_name}"')
        )
        await self.session.flush()

    async def _run_tenant_migration(self, slug: str) -> None:
        """Run Alembic migration for a new tenant schema."""
        schema_name = f"tenant_{slug}"
        logger.info("Running migration for schema: %s", schema_name)

        cmd = ["alembic", "-x", f"tenant={schema_name}", "upgrade", "head"]
        result = subprocess.run(
            cmd,
            capture_output=True,
            text=True,
            cwd=os.path.join(os.path.dirname(__file__), "..", ".."),
        )
        if result.returncode != 0:
            logger.error("Migration failed for %s: %s", schema_name, result.stderr)
            raise RuntimeError(f"Migration failed for {schema_name}: {result.stderr}")

    async def _create_org_record(self, name: str, slug: str):
        """Create Organization record in shared schema."""
        from app.models.shared import Organization

        org = Organization(
            name=name,
            slug=slug,
            is_active=self.signup_mode == "self_service",
        )
        self.session.add(org)
        await self.session.flush()
        return org

    async def _create_org_config(self, org_id: int) -> None:
        """Create OrganizationConfig in tenant schema."""
        from app.models.organization import OrganizationConfig

        config = OrganizationConfig(org_id=org_id)
        self.session.add(config)
        await self.session.flush()

    async def _seed_screening_protocols(self) -> None:
        """Seed default screening protocols for the new tenant."""
        try:
            from app.services.screening.seed_protocols import seed_protocols_to_db

            await seed_protocols_to_db(self.session)
        except Exception:
            logger.warning("Failed to seed screening protocols", exc_info=True)

    async def _create_admin_user(
        self, org_id: int, email: str, name: str
    ) -> dict:
        """Create admin user with a random password.

        Returns dict with user_id and plaintext password (for initial delivery).
        """
        from app.models.user import User

        # Generate a secure random password
        alphabet = string.ascii_letters + string.digits + string.punctuation
        password = "".join(secrets.choice(alphabet) for _ in range(20))

        # Hash password
        try:
            from passlib.hash import bcrypt

            hashed = bcrypt.hash(password)
        except ImportError:
            # Fallback: store password hash using hashlib (less secure but functional)
            import hashlib

            hashed = hashlib.sha256(password.encode()).hexdigest()

        user = User(
            email=email,
            hashed_password=hashed,
            full_name=name.encode("utf-8"),
            role="admin",
            is_active=True,
            org_id=org_id,
        )
        self.session.add(user)
        await self.session.flush()

        return {"user_id": user.id, "password": password}
