"""Authentication router."""

from datetime import datetime, timezone
from typing import Optional

from fastapi import APIRouter, Depends, HTTPException, status
from fastapi.security import HTTPAuthorizationCredentials, HTTPBearer
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.config import get_settings
from app.core.database import get_db
from app.core.security import (
    TokenData,
    create_access_token,
    decode_supabase_token,
    get_current_user,
    get_password_hash,
    is_supabase_token,
    verify_password,
)
from app.core.supabase_client import get_supabase_client
from app.shared.models.user import User
from app.shared.schemas.user import TokenResponse, UserLogin, UserResponse

router = APIRouter()
settings = get_settings()
bearer_scheme = HTTPBearer(auto_error=False)


@router.post("/login", response_model=TokenResponse)
async def login(
    credentials: UserLogin,
    db: AsyncSession = Depends(get_db),
):
    """Authenticate user and return access token."""
    # Find user by email
    result = await db.execute(
        select(User).where(
            User.email == credentials.email,
            User.is_active == True,
        )
    )
    user = result.scalar_one_or_none()

    if not user or not verify_password(credentials.password, user.password_hash):
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Invalid email or password",
        )

    # Update last login
    user.last_login_at = datetime.now(timezone.utc)
    await db.commit()

    # Create access token
    access_token = create_access_token(
        user_id=user.id,
        tenant_id=user.tenant_id,
        email=user.email,
        role=user.role,
    )

    return TokenResponse(
        access_token=access_token,
        token_type="bearer",
        expires_in=settings.jwt_access_token_expire_minutes * 60,
        user=UserResponse.model_validate(user),
    )


@router.get("/me", response_model=UserResponse)
async def get_current_user_info(
    credentials: Optional[HTTPAuthorizationCredentials] = Depends(bearer_scheme),
):
    """Get current authenticated user information.

    Accepts both Supabase tokens (from frontend auth) and our custom tokens.
    For Supabase tokens, looks up user by email via Supabase REST API.
    """
    if not credentials:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Not authenticated",
            headers={"WWW-Authenticate": "Bearer"},
        )

    token = credentials.credentials
    user_data = None

    # Check if this is a Supabase token
    if is_supabase_token(token):
        # Decode Supabase token and look up user by email
        supabase_payload = decode_supabase_token(token)
        if not supabase_payload.email:
            raise HTTPException(
                status_code=status.HTTP_401_UNAUTHORIZED,
                detail="Token does not contain email",
            )

        # Use Supabase REST API to get user
        client = get_supabase_client()
        try:
            user_data = await client.get_user_by_email(supabase_payload.email)
        except Exception as e:
            raise HTTPException(
                status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
                detail=f"Failed to fetch user: {str(e)}",
            )
    else:
        # Try to decode as our custom token and use REST API
        from app.core.security import decode_access_token

        try:
            token_data = decode_access_token(token)
            client = get_supabase_client()
            user_data = await client.select(
                "users",
                "*",
                filters={"id": str(token_data.user_id)},
                single=True,
            )
        except HTTPException:
            raise HTTPException(
                status_code=status.HTTP_401_UNAUTHORIZED,
                detail="Invalid token",
                headers={"WWW-Authenticate": "Bearer"},
            )

    if not user_data:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="User not found in database. Please contact administrator.",
        )

    return UserResponse.model_validate(user_data)


@router.post("/refresh", response_model=TokenResponse)
async def refresh_token(
    current_user: TokenData = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    """Refresh access token."""
    result = await db.execute(select(User).where(User.id == current_user.user_id))
    user = result.scalar_one_or_none()

    if not user or not user.is_active:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="User not found or inactive",
        )

    # Create new access token
    access_token = create_access_token(
        user_id=user.id,
        tenant_id=user.tenant_id,
        email=user.email,
        role=user.role,
    )

    return TokenResponse(
        access_token=access_token,
        token_type="bearer",
        expires_in=settings.jwt_access_token_expire_minutes * 60,
        user=UserResponse.model_validate(user),
    )


@router.post("/logout")
async def logout(current_user: TokenData = Depends(get_current_user)):
    """Logout current user (client should discard token)."""
    # In a stateless JWT setup, we just return success
    # For token revocation, we'd add the token to a blacklist
    return {"message": "Successfully logged out"}
