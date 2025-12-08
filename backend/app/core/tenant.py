"""Multi-tenant context management."""

from contextvars import ContextVar
from typing import Optional
from uuid import UUID

from fastapi import Depends

from app.core.security import TokenData, get_current_user

# Context variable to store the current tenant ID
tenant_context: ContextVar[Optional[UUID]] = ContextVar("tenant_id", default=None)


def get_current_tenant_id() -> Optional[UUID]:
    """Get the current tenant ID from context."""
    return tenant_context.get()


def set_current_tenant_id(tenant_id: UUID) -> None:
    """Set the current tenant ID in context."""
    tenant_context.set(tenant_id)


async def get_tenant_id(current_user: TokenData = Depends(get_current_user)) -> UUID:
    """Dependency to get and set the current tenant ID from the authenticated user."""
    set_current_tenant_id(current_user.tenant_id)
    return current_user.tenant_id


class TenantContext:
    """Context manager for tenant-scoped operations."""

    def __init__(self, tenant_id: UUID):
        self.tenant_id = tenant_id
        self.token: Optional[object] = None

    def __enter__(self):
        self.token = tenant_context.set(self.tenant_id)
        return self

    def __exit__(self, exc_type, exc_val, exc_tb):
        if self.token is not None:
            tenant_context.reset(self.token)
        return False
