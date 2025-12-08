"""Users router."""

from typing import List, Optional
from uuid import UUID

from fastapi import APIRouter, Depends, HTTPException, Query, status
from sqlalchemy import func, select
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.database import get_db
from app.core.permissions import Permission, require_permission
from app.core.security import TokenData, get_current_user, get_password_hash
from app.core.tenant import get_tenant_id
from app.shared.models.user import User
from app.shared.schemas.common import PaginatedResponse
from app.shared.schemas.user import UserCreate, UserResponse, UserUpdate

router = APIRouter()


@router.get("/", response_model=PaginatedResponse[UserResponse])
async def list_users(
    page: int = Query(1, ge=1),
    page_size: int = Query(20, ge=1, le=100),
    role: Optional[str] = None,
    is_active: Optional[bool] = None,
    search: Optional[str] = None,
    db: AsyncSession = Depends(get_db),
    tenant_id: UUID = Depends(get_tenant_id),
    _: TokenData = Depends(require_permission(Permission.ADMIN_USERS)),
):
    """List users with pagination and filters."""
    # Base query
    query = select(User).where(User.tenant_id == tenant_id)

    # Apply filters
    if role:
        query = query.where(User.role == role)
    if is_active is not None:
        query = query.where(User.is_active == is_active)
    if search:
        search_term = f"%{search}%"
        query = query.where(
            (User.full_name.ilike(search_term)) | (User.email.ilike(search_term))
        )

    # Get total count
    count_query = select(func.count()).select_from(query.subquery())
    total = (await db.execute(count_query)).scalar() or 0

    # Apply pagination
    offset = (page - 1) * page_size
    query = query.offset(offset).limit(page_size).order_by(User.full_name)

    result = await db.execute(query)
    users = result.scalars().all()

    return PaginatedResponse.create(
        items=[UserResponse.model_validate(u) for u in users],
        total=total,
        page=page,
        page_size=page_size,
    )


@router.post("/", response_model=UserResponse, status_code=status.HTTP_201_CREATED)
async def create_user(
    user_data: UserCreate,
    db: AsyncSession = Depends(get_db),
    tenant_id: UUID = Depends(get_tenant_id),
    _: TokenData = Depends(require_permission(Permission.ADMIN_USERS)),
):
    """Create a new user."""
    # Check if email already exists
    result = await db.execute(
        select(User).where(
            User.tenant_id == tenant_id,
            User.email == user_data.email,
        )
    )
    if result.scalar_one_or_none():
        raise HTTPException(
            status_code=status.HTTP_409_CONFLICT,
            detail="User with this email already exists",
        )

    # Create user
    user = User(
        tenant_id=tenant_id,
        email=user_data.email,
        password_hash=get_password_hash(user_data.password),
        full_name=user_data.full_name,
        role=user_data.role,
        employee_id=user_data.employee_id,
        department_id=user_data.department_id,
        phone=user_data.phone,
    )

    db.add(user)
    await db.commit()
    await db.refresh(user)

    return UserResponse.model_validate(user)


@router.get("/{user_id}", response_model=UserResponse)
async def get_user(
    user_id: UUID,
    db: AsyncSession = Depends(get_db),
    tenant_id: UUID = Depends(get_tenant_id),
    current_user: TokenData = Depends(get_current_user),
):
    """Get a user by ID."""
    # Users can view themselves, admins can view anyone
    if user_id != current_user.user_id:
        # Check permission
        from app.core.permissions import has_permission, Permission

        if not has_permission(current_user.role, Permission.ADMIN_USERS):
            raise HTTPException(
                status_code=status.HTTP_403_FORBIDDEN,
                detail="Not authorized to view this user",
            )

    result = await db.execute(
        select(User).where(
            User.id == user_id,
            User.tenant_id == tenant_id,
        )
    )
    user = result.scalar_one_or_none()

    if not user:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="User not found",
        )

    return UserResponse.model_validate(user)


@router.patch("/{user_id}", response_model=UserResponse)
async def update_user(
    user_id: UUID,
    user_data: UserUpdate,
    db: AsyncSession = Depends(get_db),
    tenant_id: UUID = Depends(get_tenant_id),
    current_user: TokenData = Depends(get_current_user),
):
    """Update a user."""
    # Users can update themselves (limited fields), admins can update anyone
    is_self = user_id == current_user.user_id
    from app.core.permissions import has_permission, Permission

    is_admin = has_permission(current_user.role, Permission.ADMIN_USERS)

    if not is_self and not is_admin:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="Not authorized to update this user",
        )

    result = await db.execute(
        select(User).where(
            User.id == user_id,
            User.tenant_id == tenant_id,
        )
    )
    user = result.scalar_one_or_none()

    if not user:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="User not found",
        )

    # Apply updates
    update_data = user_data.model_dump(exclude_unset=True)

    # Non-admins can only update certain fields
    if not is_admin:
        allowed_fields = {"full_name", "phone", "avatar_url", "preferences"}
        update_data = {k: v for k, v in update_data.items() if k in allowed_fields}

    for field, value in update_data.items():
        setattr(user, field, value)

    await db.commit()
    await db.refresh(user)

    return UserResponse.model_validate(user)


@router.delete("/{user_id}", status_code=status.HTTP_204_NO_CONTENT)
async def delete_user(
    user_id: UUID,
    db: AsyncSession = Depends(get_db),
    tenant_id: UUID = Depends(get_tenant_id),
    current_user: TokenData = Depends(require_permission(Permission.ADMIN_USERS)),
):
    """Deactivate a user (soft delete)."""
    if user_id == current_user.user_id:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Cannot delete yourself",
        )

    result = await db.execute(
        select(User).where(
            User.id == user_id,
            User.tenant_id == tenant_id,
        )
    )
    user = result.scalar_one_or_none()

    if not user:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="User not found",
        )

    # Soft delete
    user.is_active = False
    await db.commit()

    return None
