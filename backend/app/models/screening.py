"""Screening protocol DB models -- community protocol library and per-org activation.

Four models support the screening protocol lifecycle:
- ScreeningProtocol (SharedBase): Community protocol library with seed + org-created protocols
- ProtocolVersion (SharedBase): Versioned protocol content with trigger conditions and questions
- OrgProtocolActivation (TenantBase): Per-org activation with version pinning and mode control
- ScreeningEvent (TenantBase): Audit trail for triggered screenings during intake sessions
"""

from datetime import datetime

from sqlalchemy import Boolean, Integer, JSON, String, Text, UniqueConstraint, func
from sqlalchemy.orm import Mapped, mapped_column

from app.db.base import SharedBase, TenantBase


class ScreeningProtocol(SharedBase):
    """Community protocol library entry -- seed or org-created.

    Protocols with owner_org_id=None are system seeds (shipped with the app).
    Org-created protocols are private by default; orgs opt-in to share via is_shared.
    """

    __tablename__ = "screening_protocols"

    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    name: Mapped[str] = mapped_column(String(255), nullable=False)
    slug: Mapped[str] = mapped_column(String(100), unique=True, nullable=False)
    description: Mapped[str | None] = mapped_column(Text, nullable=True)
    severity_tier: Mapped[str] = mapped_column(String(20), nullable=False)
    owner_org_id: Mapped[int | None] = mapped_column(Integer, nullable=True)
    is_shared: Mapped[bool] = mapped_column(Boolean, default=False, nullable=False)
    is_seed: Mapped[bool] = mapped_column(Boolean, default=False, nullable=False)
    created_at: Mapped[datetime] = mapped_column(server_default=func.now())


class ProtocolVersion(SharedBase):
    """Versioned protocol content -- trigger conditions, questions, escalation actions.

    Each protocol can have multiple versions. Orgs pin to a specific version via
    OrgProtocolActivation.pinned_version_id. Running intakes use the pinned version.

    trigger_conditions_json schema:
        {keywords, keyword_match_mode, folio_concept_iris, area_of_law_iris,
         regex_patterns, exclude_keywords, min_confidence}

    questions_json schema: list of question objects with:
        {question_id, text, text_transparent, priority, is_mandatory,
         follow_up_if_yes, follow_up_if_no, trauma_informed_framing}
    """

    __tablename__ = "protocol_versions"
    __table_args__ = (
        UniqueConstraint("protocol_id", "version", name="uq_protocol_versions_protocol_version"),
    )

    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    protocol_id: Mapped[int] = mapped_column(Integer, nullable=False)
    version: Mapped[str] = mapped_column(String(20), nullable=False)
    trigger_conditions_json: Mapped[dict] = mapped_column(JSON, nullable=False)
    questions_json: Mapped[list] = mapped_column(JSON, nullable=False)
    escalation_actions_json: Mapped[dict] = mapped_column(JSON, nullable=False)
    safety_resources_json: Mapped[dict | None] = mapped_column(JSON, nullable=True)
    is_active: Mapped[bool] = mapped_column(Boolean, default=True, nullable=False)
    created_at: Mapped[datetime] = mapped_column(server_default=func.now())


class OrgProtocolActivation(TenantBase):
    """Per-org protocol activation with version pinning and mode control.

    activation_mode: "mandatory" (always runs), "optional" (professional toggle),
                     "disabled" (turned off for this org).
    pinned_version_id: FK to protocol_versions.id -- ensures running intakes
                       use the version active when intake started.
    """

    __tablename__ = "org_protocol_activations"
    __table_args__ = (
        UniqueConstraint("protocol_id", name="uq_org_protocol_activations_protocol_id"),
    )

    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    protocol_id: Mapped[int] = mapped_column(Integer, nullable=False)
    pinned_version_id: Mapped[int] = mapped_column(Integer, nullable=False)
    activation_mode: Mapped[str] = mapped_column(String(20), nullable=False)
    config_json: Mapped[dict | None] = mapped_column(JSON, nullable=True)
    created_at: Mapped[datetime] = mapped_column(server_default=func.now())
    updated_at: Mapped[datetime] = mapped_column(server_default=func.now(), onupdate=func.now())


class ScreeningEvent(TenantBase):
    """Audit trail for a triggered screening during an intake session.

    Records which protocol was triggered, by what content, and what action was taken.
    """

    __tablename__ = "screening_events"

    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    session_id: Mapped[int] = mapped_column(Integer, nullable=False)
    protocol_id: Mapped[int] = mapped_column(Integer, nullable=False)
    protocol_version_id: Mapped[int] = mapped_column(Integer, nullable=False)
    severity_tier: Mapped[str] = mapped_column(String(20), nullable=False)
    trigger_details_json: Mapped[dict] = mapped_column(JSON, nullable=False)
    action_taken: Mapped[str] = mapped_column(String(50), nullable=False)
    created_at: Mapped[datetime] = mapped_column(server_default=func.now())
