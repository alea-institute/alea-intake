"""Deployment mode branching logic and mode-aware helpers.

This is the SINGLE place where schema naming is determined. All other code
calls these functions rather than constructing schema names directly.
"""

from app.config import DeploymentMode, get_settings


def get_deployment_mode() -> DeploymentMode:
    """Return the current deployment mode from settings."""
    return get_settings().deployment_mode


def is_multi_tenant() -> bool:
    """Convenience helper: True only for MULTI_TENANT mode."""
    return get_deployment_mode() == DeploymentMode.MULTI_TENANT


def get_schema_translate_map(slug: str | None = None) -> dict[str, str | None]:
    """Return SQLAlchemy schema_translate_map for the current deployment mode.

    Multi-tenant: {"tenant": "tenant_{slug}", "shared": "shared"}
    Single-tenant: {"tenant": None, "shared": None}  (Pitfall 7 -- public schema)

    Args:
        slug: Tenant slug (required for multi-tenant, ignored for single-tenant).

    Returns:
        Dict mapping logical schema names to physical schema names.
    """
    if is_multi_tenant():
        if slug is None:
            raise ValueError("slug is required in multi-tenant mode")
        return {"tenant": f"tenant_{slug}", "shared": "shared"}
    else:
        # Single-tenant: all tables in public schema, no schema prefixes
        return {"tenant": None, "shared": None}
