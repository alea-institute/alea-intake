"""User API endpoints: profile, user management."""

from fastapi import APIRouter, Depends
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.permissions import get_current_active_user, require_role
from app.db.session import get_tenant_session
from app.models.user import Role, User
from app.schemas.user import UserResponse

router = APIRouter(prefix="/api/v1/users", tags=["users"])


def _user_to_response(user: User) -> UserResponse:
    """Convert a User model to a UserResponse, decoding full_name bytes."""
    full_name = None
    if user.full_name is not None:
        full_name = user.full_name.decode("utf-8") if isinstance(user.full_name, bytes) else str(user.full_name)

    return UserResponse(
        id=user.id,
        email=user.email,
        full_name=full_name,
        role=user.role,
        is_active=user.is_active,
        created_at=user.created_at,
    )


@router.get("/me", response_model=UserResponse)
async def get_my_profile(
    current_user: User = Depends(get_current_active_user),
):
    """Return the current user's profile."""
    return _user_to_response(current_user)


@router.get("", response_model=list[UserResponse])
async def list_users(
    current_user: User = Depends(require_role(Role.ADMIN)),
    session: AsyncSession = Depends(get_tenant_session),
):
    """List all users in the tenant. Admin only."""
    result = await session.execute(select(User))
    users = result.scalars().all()
    return [_user_to_response(u) for u in users]


@router.get("/{user_id}", response_model=UserResponse)
async def get_user(
    user_id: int,
    current_user: User = Depends(get_current_active_user),
    session: AsyncSession = Depends(get_tenant_session),
):
    """Get a specific user. Admin/professional can view any; consumer only self."""
    from fastapi import HTTPException, status

    # Consumer can only read own profile
    if current_user.role == Role.CONSUMER.value and current_user.id != user_id:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="Insufficient permissions for this action",
        )

    # Admin and professional can read any user
    if current_user.role not in {Role.ADMIN.value, Role.PROFESSIONAL.value} and current_user.id != user_id:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="Insufficient permissions for this action",
        )

    result = await session.execute(select(User).where(User.id == user_id))
    user = result.scalar_one_or_none()
    if user is None:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="User not found",
        )

    return _user_to_response(user)
