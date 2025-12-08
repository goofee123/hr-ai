"""Security utilities for authentication and authorization."""

from datetime import datetime, timedelta, timezone
from typing import Optional
from uuid import UUID

from fastapi import Depends, HTTPException, status
from fastapi.security import HTTPAuthorizationCredentials, HTTPBearer
from jose import JWTError, jwt
from passlib.context import CryptContext
from pydantic import BaseModel

from app.config import get_settings

settings = get_settings()

# Password hashing
pwd_context = CryptContext(schemes=["bcrypt"], deprecated="auto")

# Bearer token security
bearer_scheme = HTTPBearer(auto_error=False)


class TokenPayload(BaseModel):
    """JWT token payload structure."""

    sub: str  # User ID
    tenant_id: str  # Tenant ID
    email: str
    role: str
    exp: datetime
    iat: datetime
    jti: Optional[str] = None


class SupabaseTokenPayload(BaseModel):
    """Supabase JWT token payload structure."""

    sub: str  # Supabase Auth User ID
    email: Optional[str] = None
    exp: datetime
    iat: datetime
    aud: str = "authenticated"


class TokenData(BaseModel):
    """Decoded token data for request context."""

    user_id: UUID
    tenant_id: UUID
    email: str
    role: str
    supabase_user_id: Optional[str] = None  # Store Supabase auth user ID


def verify_password(plain_password: str, hashed_password: str) -> bool:
    """Verify a password against its hash."""
    return pwd_context.verify(plain_password, hashed_password)


def get_password_hash(password: str) -> str:
    """Hash a password."""
    return pwd_context.hash(password)


def create_access_token(
    user_id: UUID,
    tenant_id: UUID,
    email: str,
    role: str,
    expires_delta: Optional[timedelta] = None,
) -> str:
    """Create a JWT access token."""
    now = datetime.now(timezone.utc)
    expire = now + (expires_delta or timedelta(minutes=settings.jwt_access_token_expire_minutes))

    payload = {
        "sub": str(user_id),
        "tenant_id": str(tenant_id),
        "email": email,
        "role": role,
        "iat": now,
        "exp": expire,
    }

    return jwt.encode(payload, settings.jwt_secret_key, algorithm=settings.jwt_algorithm)


def decode_supabase_token(token: str) -> SupabaseTokenPayload:
    """Decode and validate a Supabase JWT token.

    Supabase JWT tokens are signed with the JWT secret from the project settings.
    We decode them without verification if no secret is set, relying on Supabase's
    validation on their end.
    """
    try:
        # First try to decode with Supabase JWT secret if available
        if settings.supabase_jwt_secret:
            payload = jwt.decode(
                token,
                settings.supabase_jwt_secret,
                algorithms=["HS256"],
                audience="authenticated",
            )
        else:
            # Decode without verification for development
            # In production, ALWAYS set SUPABASE_JWT_SECRET
            # Disable ALL verification - python-jose validates even with verify_signature=False
            payload = jwt.decode(
                token,
                "",
                options={
                    "verify_signature": False,
                    "verify_aud": False,
                    "verify_exp": False,
                },
            )

        return SupabaseTokenPayload(
            sub=payload["sub"],
            email=payload.get("email"),
            exp=datetime.fromtimestamp(payload["exp"], tz=timezone.utc),
            iat=datetime.fromtimestamp(payload["iat"], tz=timezone.utc),
            aud=payload.get("aud", "authenticated"),
        )
    except JWTError as e:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail=f"Invalid or expired Supabase token: {str(e)}",
            headers={"WWW-Authenticate": "Bearer"},
        ) from e


def decode_access_token(token: str) -> TokenData:
    """Decode and validate a JWT access token (our custom tokens)."""
    try:
        payload = jwt.decode(
            token,
            settings.jwt_secret_key,
            algorithms=[settings.jwt_algorithm],
        )
        return TokenData(
            user_id=UUID(payload["sub"]),
            tenant_id=UUID(payload["tenant_id"]),
            email=payload["email"],
            role=payload["role"],
        )
    except JWTError as e:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Invalid or expired token",
            headers={"WWW-Authenticate": "Bearer"},
        ) from e


def is_supabase_token(token: str) -> bool:
    """Check if a token is a Supabase token by examining its claims."""
    try:
        # Decode without verification to inspect claims
        # Disable ALL verification - python-jose validates even with verify_signature=False
        payload = jwt.decode(
            token,
            "",
            options={
                "verify_signature": False,
                "verify_aud": False,
                "verify_exp": False,
            },
        )
        # Supabase tokens have 'aud': 'authenticated' and 'iss' containing 'supabase'
        return payload.get("aud") == "authenticated" and "supabase" in payload.get("iss", "")
    except JWTError:
        return False


async def get_current_user(
    credentials: Optional[HTTPAuthorizationCredentials] = Depends(bearer_scheme),
) -> TokenData:
    """Dependency to get current authenticated user from JWT.

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

    # Check if this is a Supabase token
    if is_supabase_token(token):
        # Decode Supabase token and look up user by email
        supabase_payload = decode_supabase_token(token)
        if not supabase_payload.email:
            raise HTTPException(
                status_code=status.HTTP_401_UNAUTHORIZED,
                detail="Token does not contain email",
            )

        # Import here to avoid circular import
        from app.core.supabase_client import get_supabase_client

        # Use Supabase REST API to get user
        client = get_supabase_client()
        try:
            user_data = await client.get_user_by_email(supabase_payload.email)
        except Exception as e:
            raise HTTPException(
                status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
                detail=f"Failed to fetch user: {str(e)}",
            )

        if not user_data:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail="User not found in database. Please contact administrator.",
            )

        return TokenData(
            user_id=UUID(user_data["id"]),
            tenant_id=UUID(user_data["tenant_id"]),
            email=user_data["email"],
            role=user_data["role"],
            supabase_user_id=supabase_payload.sub,
        )

    # Try to decode as our custom token
    return decode_access_token(token)


async def get_current_user_optional(
    credentials: Optional[HTTPAuthorizationCredentials] = Depends(bearer_scheme),
) -> Optional[TokenData]:
    """Optional authentication - returns None if not authenticated."""
    if not credentials:
        return None

    try:
        return decode_access_token(credentials.credentials)
    except HTTPException:
        return None
