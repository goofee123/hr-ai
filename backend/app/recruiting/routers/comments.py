"""Comments router for candidate discussions and @mentions."""

from datetime import datetime, timezone
from typing import List, Optional
from uuid import UUID, uuid4

import httpx
from fastapi import APIRouter, Depends, HTTPException, Query, status

from app.config import get_settings
from app.core.permissions import Permission, require_permission
from app.core.security import TokenData
from app.recruiting.schemas.comment import (
    CommentCreate,
    CommentUpdate,
    CommentResponse,
    CommentThread,
)


router = APIRouter()
settings = get_settings()


def _get_headers():
    """Get headers for Supabase REST API calls."""
    return {
        "apikey": settings.supabase_service_role_key,
        "Authorization": f"Bearer {settings.supabase_service_role_key}",
        "Content-Type": "application/json",
        "Prefer": "return=representation",
    }


@router.post(
    "",
    response_model=CommentResponse,
    status_code=status.HTTP_201_CREATED,
    summary="Create a comment",
)
async def create_comment(
    request: CommentCreate,
    current_user: TokenData = Depends(require_permission(Permission.CANDIDATES_VIEW)),
):
    """Create a new comment on a candidate profile."""
    now = datetime.now(timezone.utc).isoformat()

    async with httpx.AsyncClient() as client:
        # Verify candidate exists
        candidate_response = await client.get(
            f"{settings.supabase_url}/rest/v1/candidates",
            headers=_get_headers(),
            params={
                "id": f"eq.{request.candidate_id}",
                "tenant_id": f"eq.{current_user.tenant_id}",
                "select": "id",
            },
            timeout=15,
        )

        if candidate_response.status_code != 200 or not candidate_response.json():
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail="Candidate not found",
            )

        # If parent_id provided, verify it exists
        if request.parent_id:
            parent_response = await client.get(
                f"{settings.supabase_url}/rest/v1/candidate_comments",
                headers=_get_headers(),
                params={
                    "id": f"eq.{request.parent_id}",
                    "tenant_id": f"eq.{current_user.tenant_id}",
                    "select": "id,candidate_id",
                },
                timeout=15,
            )

            if parent_response.status_code != 200 or not parent_response.json():
                raise HTTPException(
                    status_code=status.HTTP_404_NOT_FOUND,
                    detail="Parent comment not found",
                )

            # Ensure parent comment is on same candidate
            parent_data = parent_response.json()[0]
            if parent_data["candidate_id"] != str(request.candidate_id):
                raise HTTPException(
                    status_code=status.HTTP_400_BAD_REQUEST,
                    detail="Parent comment belongs to different candidate",
                )

        comment_data = {
            "id": str(uuid4()),
            "tenant_id": str(current_user.tenant_id),
            "candidate_id": str(request.candidate_id),
            "author_id": str(current_user.user_id),
            "content": request.content,
            "mentions": [str(m) for m in request.mentions] if request.mentions else None,
            "parent_id": str(request.parent_id) if request.parent_id else None,
            "is_edited": False,
            "created_at": now,
            "updated_at": now,
        }

        response = await client.post(
            f"{settings.supabase_url}/rest/v1/candidate_comments",
            headers=_get_headers(),
            json=comment_data,
            timeout=15,
        )

        if response.status_code not in (200, 201):
            raise HTTPException(
                status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
                detail=f"Failed to create comment: {response.text}",
            )

        created = response.json()[0]

        # TODO: Send notification to mentioned users

        return CommentResponse(**created)


@router.get(
    "",
    response_model=List[CommentResponse],
    summary="List comments",
)
async def list_comments(
    candidate_id: UUID,
    include_replies: bool = Query(False, description="Include nested replies"),
    limit: int = Query(50, ge=1, le=200),
    offset: int = Query(0, ge=0),
    current_user: TokenData = Depends(require_permission(Permission.CANDIDATES_VIEW)),
):
    """List comments for a candidate."""
    async with httpx.AsyncClient() as client:
        params = {
            "candidate_id": f"eq.{candidate_id}",
            "tenant_id": f"eq.{current_user.tenant_id}",
            "select": "*",
            "order": "created_at.desc",
            "limit": str(limit),
            "offset": str(offset),
        }

        # If not including replies, only get top-level comments
        if not include_replies:
            params["parent_id"] = "is.null"

        response = await client.get(
            f"{settings.supabase_url}/rest/v1/candidate_comments",
            headers=_get_headers(),
            params=params,
            timeout=15,
        )

        if response.status_code != 200:
            raise HTTPException(
                status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
                detail="Failed to fetch comments",
            )

        comments = response.json()

        # Enrich with author names (batch lookup)
        author_ids = list(set(c["author_id"] for c in comments))
        if author_ids:
            users_response = await client.get(
                f"{settings.supabase_url}/rest/v1/users",
                headers=_get_headers(),
                params={
                    "id": f"in.({','.join(author_ids)})",
                    "select": "id,full_name,email",
                },
                timeout=15,
            )

            if users_response.status_code == 200:
                users_map = {u["id"]: u for u in users_response.json()}
                for comment in comments:
                    user = users_map.get(comment["author_id"], {})
                    comment["author_name"] = user.get("full_name")
                    comment["author_email"] = user.get("email")

        return [CommentResponse(**c) for c in comments]


@router.get(
    "/threads/{candidate_id}",
    response_model=List[CommentThread],
    summary="Get threaded comments",
)
async def get_comment_threads(
    candidate_id: UUID,
    current_user: TokenData = Depends(require_permission(Permission.CANDIDATES_VIEW)),
):
    """Get comments organized as threads (parent with nested replies)."""
    async with httpx.AsyncClient() as client:
        # Get all comments for candidate
        response = await client.get(
            f"{settings.supabase_url}/rest/v1/candidate_comments",
            headers=_get_headers(),
            params={
                "candidate_id": f"eq.{candidate_id}",
                "tenant_id": f"eq.{current_user.tenant_id}",
                "select": "*",
                "order": "created_at.asc",
            },
            timeout=15,
        )

        if response.status_code != 200:
            raise HTTPException(
                status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
                detail="Failed to fetch comments",
            )

        all_comments = response.json()

        # Enrich with author names
        author_ids = list(set(c["author_id"] for c in all_comments))
        users_map = {}
        if author_ids:
            users_response = await client.get(
                f"{settings.supabase_url}/rest/v1/users",
                headers=_get_headers(),
                params={
                    "id": f"in.({','.join(author_ids)})",
                    "select": "id,full_name,email",
                },
                timeout=15,
            )

            if users_response.status_code == 200:
                users_map = {u["id"]: u for u in users_response.json()}

        for comment in all_comments:
            user = users_map.get(comment["author_id"], {})
            comment["author_name"] = user.get("full_name")
            comment["author_email"] = user.get("email")

        # Organize into threads
        comments_by_id = {c["id"]: CommentResponse(**c) for c in all_comments}
        threads = []

        for comment in all_comments:
            if comment["parent_id"] is None:
                # This is a root comment
                root = comments_by_id[comment["id"]]
                replies = [
                    comments_by_id[c["id"]]
                    for c in all_comments
                    if c["parent_id"] == comment["id"]
                ]
                threads.append(CommentThread(
                    root_comment=root,
                    replies=sorted(replies, key=lambda r: r.created_at),
                    total_replies=len(replies),
                ))

        # Sort threads by most recent activity (root or latest reply)
        def thread_sort_key(t: CommentThread):
            latest = t.root_comment.created_at
            if t.replies:
                latest = max(latest, max(r.created_at for r in t.replies))
            return latest

        threads.sort(key=thread_sort_key, reverse=True)

        return threads


@router.get(
    "/{comment_id}",
    response_model=CommentResponse,
    summary="Get comment",
)
async def get_comment(
    comment_id: UUID,
    current_user: TokenData = Depends(require_permission(Permission.CANDIDATES_VIEW)),
):
    """Get a specific comment."""
    async with httpx.AsyncClient() as client:
        response = await client.get(
            f"{settings.supabase_url}/rest/v1/candidate_comments",
            headers=_get_headers(),
            params={
                "id": f"eq.{comment_id}",
                "tenant_id": f"eq.{current_user.tenant_id}",
                "select": "*",
            },
            timeout=15,
        )

        if response.status_code != 200 or not response.json():
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail="Comment not found",
            )

        return CommentResponse(**response.json()[0])


@router.patch(
    "/{comment_id}",
    response_model=CommentResponse,
    summary="Update comment",
)
async def update_comment(
    comment_id: UUID,
    request: CommentUpdate,
    current_user: TokenData = Depends(require_permission(Permission.CANDIDATES_VIEW)),
):
    """Update a comment (only by original author)."""
    now = datetime.now(timezone.utc).isoformat()

    async with httpx.AsyncClient() as client:
        # Verify comment exists and belongs to current user
        check_response = await client.get(
            f"{settings.supabase_url}/rest/v1/candidate_comments",
            headers=_get_headers(),
            params={
                "id": f"eq.{comment_id}",
                "tenant_id": f"eq.{current_user.tenant_id}",
                "select": "*",
            },
            timeout=15,
        )

        if check_response.status_code != 200 or not check_response.json():
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail="Comment not found",
            )

        existing = check_response.json()[0]

        # Only author can edit their comment
        if existing["author_id"] != str(current_user.user_id):
            raise HTTPException(
                status_code=status.HTTP_403_FORBIDDEN,
                detail="Can only edit your own comments",
            )

        update_data = {
            "updated_at": now,
            "is_edited": True,
        }

        if request.content is not None:
            update_data["content"] = request.content

        response = await client.patch(
            f"{settings.supabase_url}/rest/v1/candidate_comments",
            headers=_get_headers(),
            params={"id": f"eq.{comment_id}"},
            json=update_data,
            timeout=15,
        )

        if response.status_code not in (200, 204):
            raise HTTPException(
                status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
                detail="Failed to update comment",
            )

        # Fetch and return updated
        get_response = await client.get(
            f"{settings.supabase_url}/rest/v1/candidate_comments",
            headers=_get_headers(),
            params={"id": f"eq.{comment_id}", "select": "*"},
            timeout=15,
        )

        return CommentResponse(**get_response.json()[0])


@router.delete(
    "/{comment_id}",
    status_code=status.HTTP_204_NO_CONTENT,
    summary="Delete comment",
)
async def delete_comment(
    comment_id: UUID,
    current_user: TokenData = Depends(require_permission(Permission.CANDIDATES_VIEW)),
):
    """Delete a comment (only by original author or admin)."""
    async with httpx.AsyncClient() as client:
        # Verify comment exists
        check_response = await client.get(
            f"{settings.supabase_url}/rest/v1/candidate_comments",
            headers=_get_headers(),
            params={
                "id": f"eq.{comment_id}",
                "tenant_id": f"eq.{current_user.tenant_id}",
                "select": "id,author_id",
            },
            timeout=15,
        )

        if check_response.status_code != 200 or not check_response.json():
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail="Comment not found",
            )

        existing = check_response.json()[0]

        # Check if user can delete (author or admin)
        is_author = existing["author_id"] == str(current_user.user_id)
        is_admin = current_user.role in ["hr_admin", "super_admin"]

        if not is_author and not is_admin:
            raise HTTPException(
                status_code=status.HTTP_403_FORBIDDEN,
                detail="Can only delete your own comments",
            )

        # Delete the comment (and cascade to replies if any)
        response = await client.delete(
            f"{settings.supabase_url}/rest/v1/candidate_comments",
            headers=_get_headers(),
            params={"id": f"eq.{comment_id}"},
            timeout=15,
        )

        if response.status_code not in (200, 204):
            raise HTTPException(
                status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
                detail="Failed to delete comment",
            )


@router.get(
    "/mentions/me",
    response_model=List[CommentResponse],
    summary="Get my mentions",
)
async def get_my_mentions(
    unread_only: bool = Query(False),
    limit: int = Query(50, ge=1, le=100),
    current_user: TokenData = Depends(require_permission(Permission.CANDIDATES_VIEW)),
):
    """Get comments where current user was mentioned."""
    async with httpx.AsyncClient() as client:
        # Use contains filter for JSONB array
        response = await client.get(
            f"{settings.supabase_url}/rest/v1/candidate_comments",
            headers=_get_headers(),
            params={
                "tenant_id": f"eq.{current_user.tenant_id}",
                "mentions": f"cs.[\"{current_user.user_id}\"]",  # Contains in array
                "select": "*",
                "order": "created_at.desc",
                "limit": str(limit),
            },
            timeout=15,
        )

        if response.status_code != 200:
            raise HTTPException(
                status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
                detail="Failed to fetch mentions",
            )

        comments = response.json()

        # Enrich with author names
        author_ids = list(set(c["author_id"] for c in comments))
        if author_ids:
            users_response = await client.get(
                f"{settings.supabase_url}/rest/v1/users",
                headers=_get_headers(),
                params={
                    "id": f"in.({','.join(author_ids)})",
                    "select": "id,full_name,email",
                },
                timeout=15,
            )

            if users_response.status_code == 200:
                users_map = {u["id"]: u for u in users_response.json()}
                for comment in comments:
                    user = users_map.get(comment["author_id"], {})
                    comment["author_name"] = user.get("full_name")
                    comment["author_email"] = user.get("email")

        return [CommentResponse(**c) for c in comments]
