"""Role-based access control: permission sets and FastAPI dependencies.

Defines the ROLE_PERMISSIONS mapping and FastAPI dependency functions
for enforcing role and permission checks on protected endpoints.
"""

from fastapi import Depends, HTTPException, Request, status
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.security import decode_token
from app.config import get_settings
from app.db.session import get_tenant_session
from app.models.user import Role, User

# Permission sets for each role
ROLE_PERMISSIONS: dict[Role, set[str]] = {
    Role.ADMIN: {
        "users.read",
        "users.write",
        "audit.read",
        "org.manage",
        "cases.read",
        "cases.write",
        "consent.manage",
        "deletion.execute",
    },
    Role.PROFESSIONAL: {
        "cases.read",
        "cases.write",
        "audit.read.own",
        "consent.read",
    },
    Role.CONSUMER: {
        "cases.read.own",
        "cases.write.own",
        "consent.manage.own",
        "deletion.request",
    },
}


async def get_current_user(
    request: Request,
    session: AsyncSession = Depends(get_tenant_session),
) -> User:
    """Extract and validate the JWT from the Authorization header, return the User.

    Raises:
        HTTPException 401: If token is missing, invalid, expired, or user not found.
    """
    import jwt as pyjwt

    auth_header = request.headers.get("Authorization")
    if not auth_header or not auth_header.startswith("Bearer "):
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Not authenticated",
            headers={"WWW-Authenticate": "Bearer"},
        )

    token = auth_header.split(" ", 1)[1]
    settings = get_settings()

    try:
        payload = decode_token(token, settings.secret_key)
    except pyjwt.ExpiredSignatureError:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Token has expired. Please log in again.",
            headers={"WWW-Authenticate": "Bearer"},
        )
    except pyjwt.InvalidTokenError:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Invalid token",
            headers={"WWW-Authenticate": "Bearer"},
        )

    user_id = int(payload["sub"])
    result = await session.execute(select(User).where(User.id == user_id))
    user = result.scalar_one_or_none()

    if user is None:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="User not found",
            headers={"WWW-Authenticate": "Bearer"},
        )

    return user


async def get_current_active_user(
    current_user: User = Depends(get_current_user),
) -> User:
    """Ensure the current user is active.

    Raises:
        HTTPException 403: If the user account is deactivated.
    """
    if not current_user.is_active:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="Account is deactivated",
        )
    return current_user


def require_role(*allowed_roles: Role):
    """Return a FastAPI dependency that enforces role-based access.

    Usage:
        @router.get("/admin-only", dependencies=[Depends(require_role(Role.ADMIN))])

    Or as a parameter dependency:
        async def endpoint(user: User = Depends(require_role(Role.ADMIN))):
    """

    async def role_checker(
        current_user: User = Depends(get_current_active_user),
    ) -> User:
        # Compare against both the enum value and the raw string
        user_role_str = current_user.role
        if user_role_str not in {r.value for r in allowed_roles}:
            raise HTTPException(
                status_code=status.HTTP_403_FORBIDDEN,
                detail="Insufficient permissions for this action",
            )
        return current_user

    return role_checker


def require_permission(permission: str):
    """Return a FastAPI dependency that enforces permission-based access.

    Checks if the user's role has the requested permission in ROLE_PERMISSIONS.

    Usage:
        @router.get("/reports", dependencies=[Depends(require_permission("audit.read"))])
    """

    async def permission_checker(
        current_user: User = Depends(get_current_active_user),
    ) -> User:
        user_role_str = current_user.role
        try:
            role_enum = Role(user_role_str)
        except ValueError:
            raise HTTPException(
                status_code=status.HTTP_403_FORBIDDEN,
                detail="Insufficient permissions for this action",
            )

        user_permissions = ROLE_PERMISSIONS.get(role_enum, set())
        if permission not in user_permissions:
            raise HTTPException(
                status_code=status.HTTP_403_FORBIDDEN,
                detail="Insufficient permissions for this action",
            )
        return current_user

    return permission_checker
