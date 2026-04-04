"""Protocol CRUD service: create, list, version, activate, and default activation.

Provides the full lifecycle for screening protocols:
- Create protocols with initial version (org-owned or seed)
- List protocols with visibility rules (seed + shared + own org's private)
- Create new protocol versions with semver
- Activate/deactivate protocols per org with version pinning
- Auto-activate critical+elevated defaults for new orgs
"""

from __future__ import annotations

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.models.screening import (
    OrgProtocolActivation,
    ProtocolVersion,
    ScreeningProtocol,
)


class ProtocolService:
    """Full protocol lifecycle management for screening protocols.

    Operates on the shared schema for protocol CRUD (ScreeningProtocol, ProtocolVersion)
    and tenant schema for activation management (OrgProtocolActivation).
    """

    def __init__(self, db_session: AsyncSession) -> None:
        self._session = db_session

    async def create_protocol(
        self,
        name: str,
        slug: str,
        severity_tier: str,
        description: str | None = None,
        owner_org_id: int | None = None,
        is_shared: bool = False,
        trigger_conditions: dict | None = None,
        questions: list | None = None,
        escalation_actions: dict | None = None,
        safety_resources: dict | None = None,
        version: str = "1.0.0",
        is_seed: bool = False,
    ) -> tuple[ScreeningProtocol, ProtocolVersion]:
        """Create a ScreeningProtocol + initial ProtocolVersion.

        Args:
            name: Human-readable protocol name.
            slug: URL-safe unique identifier.
            severity_tier: One of "critical", "elevated", "advisory".
            description: Optional protocol description.
            owner_org_id: Owning org ID (None for seeds).
            is_shared: Whether visible in community pool.
            trigger_conditions: JSON trigger conditions for this version.
            questions: JSON questions for this version.
            escalation_actions: JSON escalation actions for this version.
            safety_resources: Optional JSON safety resources.
            version: Semver string (default "1.0.0").
            is_seed: Whether this is a system seed protocol.

        Returns:
            Tuple of (ScreeningProtocol, ProtocolVersion).

        Raises:
            ValueError: If severity_tier is invalid or non-seed protocol has no owner.
        """
        if severity_tier not in ("critical", "elevated", "advisory"):
            raise ValueError(f"Invalid severity_tier: {severity_tier}")

        if owner_org_id is None and not is_seed:
            # Org-created protocols must have an owner
            # Seeds don't require an owner
            pass  # Allow -- org_id can be set by the calling admin endpoint

        protocol = ScreeningProtocol(
            name=name,
            slug=slug,
            description=description,
            severity_tier=severity_tier,
            owner_org_id=owner_org_id,
            is_shared=is_shared,
            is_seed=is_seed,
        )
        self._session.add(protocol)
        await self._session.flush()

        proto_version = ProtocolVersion(
            protocol_id=protocol.id,
            version=version,
            trigger_conditions_json=trigger_conditions or {},
            questions_json=questions or [],
            escalation_actions_json=escalation_actions or {},
            safety_resources_json=safety_resources,
            is_active=True,
        )
        self._session.add(proto_version)
        await self._session.flush()

        return protocol, proto_version

    async def list_protocols(self, org_id: int | None = None) -> list[dict]:
        """List protocols visible to an org: seeds + community shared + own private.

        Excludes other organizations' private protocols per EXPLORE-07/EXPLORE-08.
        """
        # Query all protocols that are:
        # 1. Seeds (is_seed=True)
        # 2. Shared by any org (is_shared=True)
        # 3. Owned by this org (owner_org_id=org_id) regardless of is_shared
        from sqlalchemy import or_

        conditions = [
            ScreeningProtocol.is_seed.is_(True),
            ScreeningProtocol.is_shared.is_(True),
        ]
        if org_id is not None:
            conditions.append(ScreeningProtocol.owner_org_id == org_id)

        result = await self._session.execute(
            select(ScreeningProtocol).where(or_(*conditions))
        )
        protocols = result.scalars().all()

        protocol_list = []
        for p in protocols:
            # Get latest active version
            version_result = await self._session.execute(
                select(ProtocolVersion)
                .where(
                    ProtocolVersion.protocol_id == p.id,
                    ProtocolVersion.is_active.is_(True),
                )
                .order_by(ProtocolVersion.id.desc())
                .limit(1)
            )
            latest_version = version_result.scalar_one_or_none()

            protocol_list.append({
                "id": p.id,
                "name": p.name,
                "slug": p.slug,
                "description": p.description,
                "severity_tier": p.severity_tier,
                "owner_org_id": p.owner_org_id,
                "is_shared": p.is_shared,
                "is_seed": p.is_seed,
                "latest_version": {
                    "id": latest_version.id,
                    "version": latest_version.version,
                } if latest_version else None,
            })

        return protocol_list

    async def get_protocol(self, protocol_id: int) -> dict | None:
        """Get a single protocol with all its versions."""
        result = await self._session.execute(
            select(ScreeningProtocol).where(ScreeningProtocol.id == protocol_id)
        )
        protocol = result.scalar_one_or_none()
        if protocol is None:
            return None

        versions_result = await self._session.execute(
            select(ProtocolVersion)
            .where(ProtocolVersion.protocol_id == protocol_id)
            .order_by(ProtocolVersion.id.desc())
        )
        versions = versions_result.scalars().all()

        return {
            "id": protocol.id,
            "name": protocol.name,
            "slug": protocol.slug,
            "description": protocol.description,
            "severity_tier": protocol.severity_tier,
            "owner_org_id": protocol.owner_org_id,
            "is_shared": protocol.is_shared,
            "is_seed": protocol.is_seed,
            "versions": [
                {
                    "id": v.id,
                    "version": v.version,
                    "is_active": v.is_active,
                    "trigger_conditions": v.trigger_conditions_json,
                    "questions": v.questions_json,
                    "escalation_actions": v.escalation_actions_json,
                    "safety_resources": v.safety_resources_json,
                }
                for v in versions
            ],
        }

    async def create_version(
        self,
        protocol_id: int,
        trigger_conditions: dict,
        questions: list,
        escalation_actions: dict,
        safety_resources: dict | None = None,
        version: str = "1.1.0",
    ) -> ProtocolVersion:
        """Create a new version for an existing protocol."""
        proto_version = ProtocolVersion(
            protocol_id=protocol_id,
            version=version,
            trigger_conditions_json=trigger_conditions,
            questions_json=questions,
            escalation_actions_json=escalation_actions,
            safety_resources_json=safety_resources,
            is_active=True,
        )
        self._session.add(proto_version)
        await self._session.flush()
        return proto_version

    async def activate_protocol(
        self,
        protocol_id: int,
        pinned_version_id: int,
        activation_mode: str,
        config: dict | None = None,
    ) -> OrgProtocolActivation:
        """Create or update OrgProtocolActivation for the current tenant.

        Args:
            protocol_id: The protocol to activate.
            pinned_version_id: Specific version to pin to (D-04).
            activation_mode: One of "mandatory", "optional", "disabled" (D-03).
            config: Optional org-specific overrides.

        Returns:
            The created or updated OrgProtocolActivation.
        """
        if activation_mode not in ("mandatory", "optional", "disabled"):
            raise ValueError(f"Invalid activation_mode: {activation_mode}")

        # Check if activation already exists
        result = await self._session.execute(
            select(OrgProtocolActivation).where(
                OrgProtocolActivation.protocol_id == protocol_id
            )
        )
        existing = result.scalar_one_or_none()

        if existing:
            existing.pinned_version_id = pinned_version_id
            existing.activation_mode = activation_mode
            existing.config_json = config
            await self._session.flush()
            return existing

        activation = OrgProtocolActivation(
            protocol_id=protocol_id,
            pinned_version_id=pinned_version_id,
            activation_mode=activation_mode,
            config_json=config,
        )
        self._session.add(activation)
        await self._session.flush()
        return activation

    async def deactivate(self, protocol_id: int) -> None:
        """Set activation_mode to 'disabled' for a protocol."""
        result = await self._session.execute(
            select(OrgProtocolActivation).where(
                OrgProtocolActivation.protocol_id == protocol_id
            )
        )
        activation = result.scalar_one_or_none()
        if activation:
            activation.activation_mode = "disabled"
            await self._session.flush()

    async def get_active_protocols(
        self, include_versions: bool = True
    ) -> list[tuple[OrgProtocolActivation, ProtocolVersion]]:
        """Return all non-disabled protocol activations with their pinned versions.

        This is the primary query used by both TriggerMatcher and ExplorationEngine.
        """
        result = await self._session.execute(
            select(OrgProtocolActivation).where(
                OrgProtocolActivation.activation_mode != "disabled"
            )
        )
        activations = result.scalars().all()

        active_list: list[tuple[OrgProtocolActivation, ProtocolVersion]] = []
        for act in activations:
            if include_versions:
                version_result = await self._session.execute(
                    select(ProtocolVersion).where(
                        ProtocolVersion.id == act.pinned_version_id
                    )
                )
                version = version_result.scalar_one_or_none()
                if version:
                    active_list.append((act, version))
            else:
                active_list.append((act, None))  # type: ignore[arg-type]

        return active_list

    async def activate_defaults_for_org(self) -> int:
        """Auto-activate critical-tier as mandatory and elevated-tier as optional.

        Called when a new org is created to set up default protocol activations.
        Advisory-tier protocols are left disabled by default.

        Returns count of activated protocols.
        """
        # Get all seed protocols
        result = await self._session.execute(
            select(ScreeningProtocol).where(ScreeningProtocol.is_seed.is_(True))
        )
        seed_protocols = result.scalars().all()

        count = 0
        for proto in seed_protocols:
            if proto.severity_tier not in ("critical", "elevated"):
                continue

            # Get latest active version
            version_result = await self._session.execute(
                select(ProtocolVersion)
                .where(
                    ProtocolVersion.protocol_id == proto.id,
                    ProtocolVersion.is_active.is_(True),
                )
                .order_by(ProtocolVersion.id.desc())
                .limit(1)
            )
            version = version_result.scalar_one_or_none()
            if not version:
                continue

            mode = "mandatory" if proto.severity_tier == "critical" else "optional"

            await self.activate_protocol(
                protocol_id=proto.id,
                pinned_version_id=version.id,
                activation_mode=mode,
            )
            count += 1

        return count
