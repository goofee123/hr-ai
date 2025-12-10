"""Scorecards router for structured interviewing and feedback."""

from datetime import datetime, timezone
from typing import List, Optional
from uuid import UUID, uuid4

import httpx
from fastapi import APIRouter, Depends, HTTPException, Query, status

from app.config import get_settings
from app.core.permissions import Permission, require_permission
from app.core.security import TokenData
from app.recruiting.schemas.scorecard import (
    ScorecardTemplateCreate,
    ScorecardTemplateUpdate,
    ScorecardTemplateResponse,
    InterviewFeedbackCreate,
    InterviewFeedbackUpdate,
    InterviewFeedbackResponse,
    PanelSummary,
    InterviewKitResponse,
    ScorecardAttribute,
    InterviewQuestion,
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


# =============================================================================
# Scorecard Templates
# =============================================================================

@router.get(
    "/templates",
    response_model=List[ScorecardTemplateResponse],
    summary="List scorecard templates",
)
async def list_templates(
    stage_name: Optional[str] = None,
    requisition_id: Optional[UUID] = None,
    is_active: bool = True,
    current_user: TokenData = Depends(require_permission(Permission.APPLICATIONS_VIEW)),
):
    """List scorecard templates for the tenant."""
    async with httpx.AsyncClient() as client:
        params = {
            "tenant_id": f"eq.{current_user.tenant_id}",
            "is_active": f"eq.{str(is_active).lower()}",
            "select": "*",
            "order": "stage_name,name",
        }

        if stage_name:
            params["stage_name"] = f"eq.{stage_name}"
        if requisition_id:
            # Get templates for specific requisition or global (null requisition_id)
            params["or"] = f"(requisition_id.eq.{requisition_id},requisition_id.is.null)"

        response = await client.get(
            f"{settings.supabase_url}/rest/v1/scorecard_templates",
            headers=_get_headers(),
            params=params,
            timeout=15,
        )

        if response.status_code != 200:
            raise HTTPException(
                status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
                detail="Failed to fetch scorecard templates",
            )

        return response.json()


@router.post(
    "/templates",
    response_model=ScorecardTemplateResponse,
    status_code=status.HTTP_201_CREATED,
    summary="Create scorecard template",
)
async def create_template(
    request: ScorecardTemplateCreate,
    current_user: TokenData = Depends(require_permission(Permission.ADMIN_PIPELINE_TEMPLATES)),
):
    """Create a new scorecard template."""
    now = datetime.now(timezone.utc).isoformat()

    async with httpx.AsyncClient() as client:
        template_data = {
            "id": str(uuid4()),
            "tenant_id": str(current_user.tenant_id),
            "name": request.name,
            "stage_name": request.stage_name,
            "description": request.description,
            "requisition_id": str(request.requisition_id) if request.requisition_id else None,
            "attributes": [attr.model_dump() for attr in request.attributes],
            "interview_questions": [q.model_dump() for q in request.interview_questions] if request.interview_questions else None,
            "version": 1,
            "is_active": True,
            "created_by": str(current_user.user_id),
            "created_at": now,
            "updated_at": now,
        }

        response = await client.post(
            f"{settings.supabase_url}/rest/v1/scorecard_templates",
            headers=_get_headers(),
            json=template_data,
            timeout=15,
        )

        if response.status_code not in (200, 201):
            raise HTTPException(
                status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
                detail=f"Failed to create template: {response.text}",
            )

        return response.json()[0]


@router.get(
    "/templates/{template_id}",
    response_model=ScorecardTemplateResponse,
    summary="Get scorecard template",
)
async def get_template(
    template_id: UUID,
    current_user: TokenData = Depends(require_permission(Permission.APPLICATIONS_VIEW)),
):
    """Get a specific scorecard template."""
    async with httpx.AsyncClient() as client:
        response = await client.get(
            f"{settings.supabase_url}/rest/v1/scorecard_templates",
            headers=_get_headers(),
            params={
                "id": f"eq.{template_id}",
                "tenant_id": f"eq.{current_user.tenant_id}",
                "select": "*",
            },
            timeout=15,
        )

        if response.status_code != 200 or not response.json():
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail="Template not found",
            )

        return response.json()[0]


@router.patch(
    "/templates/{template_id}",
    response_model=ScorecardTemplateResponse,
    summary="Update scorecard template",
)
async def update_template(
    template_id: UUID,
    request: ScorecardTemplateUpdate,
    current_user: TokenData = Depends(require_permission(Permission.ADMIN_PIPELINE_TEMPLATES)),
):
    """Update a scorecard template (creates new version)."""
    now = datetime.now(timezone.utc).isoformat()

    async with httpx.AsyncClient() as client:
        # Get existing template
        check_response = await client.get(
            f"{settings.supabase_url}/rest/v1/scorecard_templates",
            headers=_get_headers(),
            params={
                "id": f"eq.{template_id}",
                "tenant_id": f"eq.{current_user.tenant_id}",
                "select": "*",
            },
            timeout=15,
        )

        if check_response.status_code != 200 or not check_response.json():
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail="Template not found",
            )

        existing = check_response.json()[0]

        # Build update data
        update_data = {
            "updated_at": now,
            "version": existing["version"] + 1,
        }

        if request.name is not None:
            update_data["name"] = request.name
        if request.description is not None:
            update_data["description"] = request.description
        if request.attributes is not None:
            update_data["attributes"] = [attr.model_dump() for attr in request.attributes]
        if request.interview_questions is not None:
            update_data["interview_questions"] = [q.model_dump() for q in request.interview_questions]
        if request.is_active is not None:
            update_data["is_active"] = request.is_active

        response = await client.patch(
            f"{settings.supabase_url}/rest/v1/scorecard_templates",
            headers=_get_headers(),
            params={"id": f"eq.{template_id}"},
            json=update_data,
            timeout=15,
        )

        if response.status_code not in (200, 204):
            raise HTTPException(
                status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
                detail="Failed to update template",
            )

        # Fetch and return updated
        get_response = await client.get(
            f"{settings.supabase_url}/rest/v1/scorecard_templates",
            headers=_get_headers(),
            params={"id": f"eq.{template_id}", "select": "*"},
            timeout=15,
        )

        return get_response.json()[0]


@router.delete(
    "/templates/{template_id}",
    status_code=status.HTTP_204_NO_CONTENT,
    summary="Delete scorecard template",
)
async def delete_template(
    template_id: UUID,
    current_user: TokenData = Depends(require_permission(Permission.ADMIN_PIPELINE_TEMPLATES)),
):
    """Soft delete a scorecard template (set is_active=false)."""
    async with httpx.AsyncClient() as client:
        response = await client.patch(
            f"{settings.supabase_url}/rest/v1/scorecard_templates",
            headers=_get_headers(),
            params={
                "id": f"eq.{template_id}",
                "tenant_id": f"eq.{current_user.tenant_id}",
            },
            json={
                "is_active": False,
                "updated_at": datetime.now(timezone.utc).isoformat(),
            },
            timeout=15,
        )

        if response.status_code not in (200, 204):
            raise HTTPException(
                status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
                detail="Failed to delete template",
            )


# =============================================================================
# Interview Feedback
# =============================================================================

@router.post(
    "/feedback",
    response_model=InterviewFeedbackResponse,
    status_code=status.HTTP_201_CREATED,
    summary="Submit interview feedback",
)
async def create_feedback(
    request: InterviewFeedbackCreate,
    current_user: TokenData = Depends(require_permission(Permission.APPLICATIONS_VIEW)),
):
    """Submit interview feedback for an application."""
    now = datetime.now(timezone.utc).isoformat()

    async with httpx.AsyncClient() as client:
        # Verify application exists
        app_response = await client.get(
            f"{settings.supabase_url}/rest/v1/applications",
            headers=_get_headers(),
            params={
                "id": f"eq.{request.application_id}",
                "tenant_id": f"eq.{current_user.tenant_id}",
                "select": "id",
            },
            timeout=15,
        )

        if app_response.status_code != 200 or not app_response.json():
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail="Application not found",
            )

        # Verify template exists
        template_response = await client.get(
            f"{settings.supabase_url}/rest/v1/scorecard_templates",
            headers=_get_headers(),
            params={
                "id": f"eq.{request.template_id}",
                "tenant_id": f"eq.{current_user.tenant_id}",
                "select": "id,attributes",
            },
            timeout=15,
        )

        if template_response.status_code != 200 or not template_response.json():
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail="Scorecard template not found",
            )

        template = template_response.json()[0]

        # Validate required attributes are rated
        required_attrs = {
            attr["name"]
            for attr in template["attributes"]
            if attr.get("required", True)
        }
        rated_attrs = {rating.attribute_name for rating in request.ratings}

        missing = required_attrs - rated_attrs
        if missing:
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail=f"Missing required ratings: {', '.join(missing)}",
            )

        feedback_data = {
            "id": str(uuid4()),
            "tenant_id": str(current_user.tenant_id),
            "application_id": str(request.application_id),
            "template_id": str(request.template_id),
            "stage_name": request.stage_name,
            "interviewer_id": str(current_user.user_id),
            "ratings": [r.model_dump() for r in request.ratings],
            "overall_recommendation": request.overall_recommendation,
            "strengths": request.strengths,
            "concerns": request.concerns,
            "notes": request.notes,
            "is_submitted": True,
            "submitted_at": now,
            "created_at": now,
            "updated_at": now,
        }

        response = await client.post(
            f"{settings.supabase_url}/rest/v1/interview_feedback",
            headers=_get_headers(),
            json=feedback_data,
            timeout=15,
        )

        if response.status_code not in (200, 201):
            raise HTTPException(
                status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
                detail=f"Failed to submit feedback: {response.text}",
            )

        return response.json()[0]


@router.get(
    "/feedback",
    response_model=List[InterviewFeedbackResponse],
    summary="List interview feedback",
)
async def list_feedback(
    application_id: Optional[UUID] = None,
    stage_name: Optional[str] = None,
    interviewer_id: Optional[UUID] = None,
    current_user: TokenData = Depends(require_permission(Permission.APPLICATIONS_VIEW)),
):
    """List interview feedback with optional filters."""
    async with httpx.AsyncClient() as client:
        params = {
            "tenant_id": f"eq.{current_user.tenant_id}",
            "select": "*",
            "order": "created_at.desc",
        }

        if application_id:
            params["application_id"] = f"eq.{application_id}"
        if stage_name:
            params["stage_name"] = f"eq.{stage_name}"
        if interviewer_id:
            params["interviewer_id"] = f"eq.{interviewer_id}"

        response = await client.get(
            f"{settings.supabase_url}/rest/v1/interview_feedback",
            headers=_get_headers(),
            params=params,
            timeout=15,
        )

        if response.status_code != 200:
            raise HTTPException(
                status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
                detail="Failed to fetch feedback",
            )

        return response.json()


@router.get(
    "/feedback/{feedback_id}",
    response_model=InterviewFeedbackResponse,
    summary="Get specific feedback",
)
async def get_feedback(
    feedback_id: UUID,
    current_user: TokenData = Depends(require_permission(Permission.APPLICATIONS_VIEW)),
):
    """Get a specific interview feedback entry."""
    async with httpx.AsyncClient() as client:
        response = await client.get(
            f"{settings.supabase_url}/rest/v1/interview_feedback",
            headers=_get_headers(),
            params={
                "id": f"eq.{feedback_id}",
                "tenant_id": f"eq.{current_user.tenant_id}",
                "select": "*",
            },
            timeout=15,
        )

        if response.status_code != 200 or not response.json():
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail="Feedback not found",
            )

        return response.json()[0]


@router.patch(
    "/feedback/{feedback_id}",
    response_model=InterviewFeedbackResponse,
    summary="Update feedback",
)
async def update_feedback(
    feedback_id: UUID,
    request: InterviewFeedbackUpdate,
    current_user: TokenData = Depends(require_permission(Permission.APPLICATIONS_VIEW)),
):
    """Update interview feedback (only by original author before submission)."""
    now = datetime.now(timezone.utc).isoformat()

    async with httpx.AsyncClient() as client:
        # Verify feedback exists and belongs to current user
        check_response = await client.get(
            f"{settings.supabase_url}/rest/v1/interview_feedback",
            headers=_get_headers(),
            params={
                "id": f"eq.{feedback_id}",
                "tenant_id": f"eq.{current_user.tenant_id}",
                "select": "*",
            },
            timeout=15,
        )

        if check_response.status_code != 200 or not check_response.json():
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail="Feedback not found",
            )

        existing = check_response.json()[0]

        # Only author can update their own feedback
        if existing["interviewer_id"] != str(current_user.user_id):
            raise HTTPException(
                status_code=status.HTTP_403_FORBIDDEN,
                detail="Can only update your own feedback",
            )

        # Build update data
        update_data = {"updated_at": now}

        if request.ratings is not None:
            update_data["ratings"] = [r.model_dump() for r in request.ratings]
        if request.overall_recommendation is not None:
            update_data["overall_recommendation"] = request.overall_recommendation
        if request.strengths is not None:
            update_data["strengths"] = request.strengths
        if request.concerns is not None:
            update_data["concerns"] = request.concerns
        if request.notes is not None:
            update_data["notes"] = request.notes

        response = await client.patch(
            f"{settings.supabase_url}/rest/v1/interview_feedback",
            headers=_get_headers(),
            params={"id": f"eq.{feedback_id}"},
            json=update_data,
            timeout=15,
        )

        if response.status_code not in (200, 204):
            raise HTTPException(
                status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
                detail="Failed to update feedback",
            )

        # Fetch and return updated
        get_response = await client.get(
            f"{settings.supabase_url}/rest/v1/interview_feedback",
            headers=_get_headers(),
            params={"id": f"eq.{feedback_id}", "select": "*"},
            timeout=15,
        )

        return get_response.json()[0]


# =============================================================================
# Panel Summary / Aggregated View
# =============================================================================

@router.get(
    "/panel/{application_id}",
    response_model=PanelSummary,
    summary="Get panel summary",
)
async def get_panel_summary(
    application_id: UUID,
    stage_name: Optional[str] = None,
    current_user: TokenData = Depends(require_permission(Permission.APPLICATIONS_VIEW)),
):
    """Get aggregated feedback from all interviewers for an application."""
    async with httpx.AsyncClient() as client:
        params = {
            "application_id": f"eq.{application_id}",
            "tenant_id": f"eq.{current_user.tenant_id}",
            "select": "*",
            "order": "created_at.desc",
        }

        if stage_name:
            params["stage_name"] = f"eq.{stage_name}"

        response = await client.get(
            f"{settings.supabase_url}/rest/v1/interview_feedback",
            headers=_get_headers(),
            params=params,
            timeout=15,
        )

        if response.status_code != 200:
            raise HTTPException(
                status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
                detail="Failed to fetch feedback",
            )

        feedbacks = response.json()

        # Build summary
        summary = PanelSummary(
            application_id=application_id,
            stage_name=stage_name or "all",
            total_interviewers=len(feedbacks),
            submitted_count=len([f for f in feedbacks if f.get("is_submitted")]),
            pending_count=len([f for f in feedbacks if not f.get("is_submitted")]),
            feedbacks=[InterviewFeedbackResponse(**f) for f in feedbacks],
        )

        # Count recommendations
        for f in feedbacks:
            rec = f.get("overall_recommendation", "").lower()
            if rec == "strong_yes":
                summary.strong_yes_count += 1
            elif rec == "yes":
                summary.yes_count += 1
            elif rec == "no":
                summary.no_count += 1
            elif rec == "strong_no":
                summary.strong_no_count += 1
            elif rec == "needs_more_info":
                summary.needs_more_info_count += 1

        # Calculate average scores
        all_scores: dict = {}
        for f in feedbacks:
            for rating in f.get("ratings", []):
                attr_name = rating.get("attribute_name")
                score = rating.get("score", 0)
                if score >= 0:  # Exclude -1 (N/A)
                    if attr_name not in all_scores:
                        all_scores[attr_name] = []
                    all_scores[attr_name].append(score)

        for attr_name, scores in all_scores.items():
            if scores:
                summary.average_scores[attr_name] = round(sum(scores) / len(scores), 2)

        # Overall average
        all_avg = list(summary.average_scores.values())
        if all_avg:
            summary.overall_average = round(sum(all_avg) / len(all_avg), 2)

        # Determine consensus
        yes_votes = summary.strong_yes_count + summary.yes_count
        no_votes = summary.strong_no_count + summary.no_count
        total_votes = yes_votes + no_votes

        if total_votes == 0:
            summary.consensus = "pending"
        elif yes_votes > 0 and no_votes == 0:
            summary.consensus = "hire"
        elif no_votes > 0 and yes_votes == 0:
            summary.consensus = "no_hire"
        else:
            summary.consensus = "split"

        return summary


# =============================================================================
# Interview Kit
# =============================================================================

@router.get(
    "/kit/{application_id}/{stage_name}",
    response_model=InterviewKitResponse,
    summary="Get interview kit",
)
async def get_interview_kit(
    application_id: UUID,
    stage_name: str,
    current_user: TokenData = Depends(require_permission(Permission.APPLICATIONS_VIEW)),
):
    """Get the interview kit for a specific application and stage."""
    async with httpx.AsyncClient() as client:
        # Get application with candidate and job info
        app_response = await client.get(
            f"{settings.supabase_url}/rest/v1/applications",
            headers=_get_headers(),
            params={
                "id": f"eq.{application_id}",
                "tenant_id": f"eq.{current_user.tenant_id}",
                "select": "id,candidate_id,requisition_id",
            },
            timeout=15,
        )

        if app_response.status_code != 200 or not app_response.json():
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail="Application not found",
            )

        app_data = app_response.json()[0]

        # Get candidate name
        candidate_response = await client.get(
            f"{settings.supabase_url}/rest/v1/candidates",
            headers=_get_headers(),
            params={
                "id": f"eq.{app_data['candidate_id']}",
                "select": "first_name,last_name",
            },
            timeout=15,
        )

        candidate = candidate_response.json()[0] if candidate_response.json() else {}
        candidate_name = f"{candidate.get('first_name', '')} {candidate.get('last_name', '')}".strip()

        # Get job title
        job_response = await client.get(
            f"{settings.supabase_url}/rest/v1/job_requisitions",
            headers=_get_headers(),
            params={
                "id": f"eq.{app_data['requisition_id']}",
                "select": "title",
            },
            timeout=15,
        )

        job = job_response.json()[0] if job_response.json() else {}
        position_title = job.get("title", "Unknown Position")

        # Get scorecard template for this stage
        template_response = await client.get(
            f"{settings.supabase_url}/rest/v1/scorecard_templates",
            headers=_get_headers(),
            params={
                "tenant_id": f"eq.{current_user.tenant_id}",
                "stage_name": f"eq.{stage_name}",
                "is_active": "eq.true",
                "or": f"(requisition_id.eq.{app_data['requisition_id']},requisition_id.is.null)",
                "select": "*",
                "order": "requisition_id.desc.nullslast",  # Prefer requisition-specific
                "limit": "1",
            },
            timeout=15,
        )

        if template_response.status_code != 200 or not template_response.json():
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail=f"No scorecard template found for stage: {stage_name}",
            )

        template_data = template_response.json()[0]
        template = ScorecardTemplateResponse(**template_data)

        # Get existing feedback from current user
        existing_feedback = None
        feedback_response = await client.get(
            f"{settings.supabase_url}/rest/v1/interview_feedback",
            headers=_get_headers(),
            params={
                "application_id": f"eq.{application_id}",
                "interviewer_id": f"eq.{current_user.user_id}",
                "stage_name": f"eq.{stage_name}",
                "select": "*",
            },
            timeout=15,
        )

        if feedback_response.json():
            existing_feedback = InterviewFeedbackResponse(**feedback_response.json()[0])

        # Get panel summary (other interviewers' feedback)
        other_feedbacks = await get_panel_summary(
            application_id=application_id,
            stage_name=stage_name,
            current_user=current_user,
        )

        # Parse interview questions
        interview_questions = []
        if template_data.get("interview_questions"):
            interview_questions = [
                InterviewQuestion(**q) for q in template_data["interview_questions"]
            ]

        return InterviewKitResponse(
            template=template,
            candidate_name=candidate_name or "Unknown Candidate",
            position_title=position_title,
            stage_name=stage_name,
            interview_questions=interview_questions,
            existing_feedback=existing_feedback,
            other_feedbacks_summary=other_feedbacks,
        )
