"""Comment schemas for candidate discussions and @mentions."""

from datetime import datetime
from typing import List, Optional
from uuid import UUID

from pydantic import BaseModel, Field


class CommentCreate(BaseModel):
    """Create a new comment on a candidate."""

    candidate_id: UUID
    content: str = Field(..., min_length=1, max_length=5000)
    mentions: Optional[List[UUID]] = Field(
        None,
        description="User IDs mentioned with @"
    )
    parent_id: Optional[UUID] = Field(
        None,
        description="Parent comment ID for threading"
    )


class CommentUpdate(BaseModel):
    """Update a comment."""

    content: Optional[str] = Field(None, min_length=1, max_length=5000)


class CommentResponse(BaseModel):
    """Comment response with author info."""

    id: UUID
    tenant_id: UUID
    candidate_id: UUID
    author_id: UUID
    content: str
    mentions: Optional[List[UUID]] = None
    parent_id: Optional[UUID] = None
    is_edited: bool = False
    created_at: datetime
    updated_at: datetime

    # Joined author data
    author_name: Optional[str] = None
    author_email: Optional[str] = None

    # Nested replies (if fetched)
    replies: Optional[List["CommentResponse"]] = None

    class Config:
        from_attributes = True


# Allow recursive model for replies
CommentResponse.model_rebuild()


class CommentThread(BaseModel):
    """A comment with all its replies."""

    root_comment: CommentResponse
    replies: List[CommentResponse] = Field(default_factory=list)
    total_replies: int = 0
