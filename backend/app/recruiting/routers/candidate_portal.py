"""
Candidate Portal Router - Public-facing endpoints for candidates.

These endpoints don't require standard JWT authentication. Instead, they use
magic link tokens for candidate verification.
"""

import json
import logging
import secrets
from datetime import datetime, timedelta
from typing import List, Optional
from uuid import UUID

from fastapi import APIRouter, HTTPException, status, Query, Header, Depends
from pydantic import EmailStr

from app.core.supabase_client import get_supabase_client
from app.services.email_service import get_email_service, EmailMessage, EmailType, EmailRecipient
from app.recruiting.schemas.candidate_portal import (
    PortalAccessRequest,
    PortalAccessResponse,
    PortalMagicLinkVerify,
    PortalSession,
    ApplicationListPublic,
    ApplicationDetailPublic,
    ApplicationStatusPublic,
    ApplicationStatusUpdate,
    InterviewInfoPublic,
    DocumentUploadRequest,
    DocumentUploadResponse,
    CandidateDocument,
    DocumentType,
    EEOFormOptions,
    EEOSelfIdentification,
    EEOSubmissionResponse,
    InterviewConfirmation,
    InterviewRescheduleRequest,
    InterviewRescheduleResponse,
    WithdrawalRequest,
    WithdrawalResponse,
    CandidateProfileUpdate,
    CandidateProfileResponse,
)

logger = logging.getLogger(__name__)
router = APIRouter()


# =============================================================================
# Helper Functions
# =============================================================================


async def _check_portal_enabled(tenant_id: str) -> bool:
    """Check if candidate portal is enabled for tenant."""
    client = get_supabase_client()

    settings = await client.select(
        "tenant_settings",
        "candidate_portal",
        filters={"tenant_id": tenant_id},
        single=True,
    )

    if not settings:
        return True  # Default to enabled if no settings

    portal_settings = settings.get("candidate_portal", {})
    if isinstance(portal_settings, str):
        portal_settings = json.loads(portal_settings)

    return portal_settings.get("enabled", True)


async def _verify_portal_session(session_token: str) -> dict:
    """Verify a portal session token and return candidate info."""
    client = get_supabase_client()

    session = await client.select(
        "candidate_portal_sessions",
        "*",
        filters={"session_token": session_token},
        single=True,
    )

    if not session:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Invalid or expired session",
        )

    # Check expiration
    expires_at = datetime.fromisoformat(session["expires_at"].replace("Z", "+00:00"))
    if expires_at < datetime.utcnow().replace(tzinfo=expires_at.tzinfo):
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Session has expired. Please request a new access link.",
        )

    return session


async def get_candidate_session(
    x_portal_token: str = Header(..., alias="X-Portal-Token")
) -> dict:
    """Dependency to get verified candidate session."""
    return await _verify_portal_session(x_portal_token)


def _map_internal_to_public_status(internal_status: str, stage_name: str = None) -> ApplicationStatusPublic:
    """Map internal application status to public-facing status."""
    status_map = {
        "new": ApplicationStatusPublic.RECEIVED,
        "screening": ApplicationStatusPublic.UNDER_REVIEW,
        "phone_screen": ApplicationStatusPublic.UNDER_REVIEW,
        "interview": ApplicationStatusPublic.INTERVIEW_SCHEDULED,
        "onsite": ApplicationStatusPublic.INTERVIEW_SCHEDULED,
        "final_interview": ApplicationStatusPublic.INTERVIEWS_COMPLETE,
        "reference_check": ApplicationStatusPublic.DECISION_PENDING,
        "offer_pending": ApplicationStatusPublic.DECISION_PENDING,
        "offer_extended": ApplicationStatusPublic.OFFER_EXTENDED,
        "offer_accepted": ApplicationStatusPublic.HIRED,
        "hired": ApplicationStatusPublic.HIRED,
        "rejected": ApplicationStatusPublic.NOT_SELECTED,
        "withdrawn": ApplicationStatusPublic.WITHDRAWN,
    }

    return status_map.get(internal_status.lower(), ApplicationStatusPublic.UNDER_REVIEW)


# =============================================================================
# Magic Link Authentication
# =============================================================================


@router.post("/request-access", response_model=PortalAccessResponse)
async def request_portal_access(
    request: PortalAccessRequest,
):
    """
    Request access to candidate portal via email.

    Sends a magic link to the candidate's email if they have applications.
    Always returns success message to prevent email enumeration.
    """
    client = get_supabase_client()
    email_service = get_email_service()

    # Find candidate by email
    candidate = await client.select(
        "candidates",
        "id, first_name, last_name, email, tenant_id",
        filters={"email": request.email.lower()},
        single=True,
    )

    if candidate:
        # Check if portal is enabled for this tenant
        portal_enabled = await _check_portal_enabled(candidate["tenant_id"])

        if portal_enabled:
            # Generate magic link token
            magic_token = secrets.token_urlsafe(32)
            expires_at = datetime.utcnow() + timedelta(hours=24)

            # Store magic link
            await client.insert("candidate_portal_magic_links", {
                "tenant_id": candidate["tenant_id"],
                "candidate_id": str(candidate["id"]),
                "token": magic_token,
                "expires_at": expires_at.isoformat(),
                "is_used": False,
            })

            # Send email with magic link
            from app.config import get_settings
            settings = get_settings()
            frontend_url = getattr(settings, 'frontend_url', 'http://localhost:3002')
            portal_link = f"{frontend_url}/portal/verify?token={magic_token}"

            html_content = f"""
            <html>
            <body style="font-family: Arial, sans-serif; max-width: 600px; margin: 0 auto;">
                <h2 style="color: #2563eb;">Access Your Application Status</h2>
                <p>Hi {candidate['first_name']},</p>
                <p>Click the button below to access your application status portal:</p>

                <p style="text-align: center; margin: 30px 0;">
                    <a href="{portal_link}"
                       style="background-color: #2563eb; color: white; padding: 14px 28px;
                              text-decoration: none; border-radius: 6px; font-weight: bold;">
                        Access Portal
                    </a>
                </p>

                <p><small>This link expires in 24 hours. If you didn't request this, please ignore this email.</small></p>

                <p>Best regards,<br>The Recruiting Team</p>
            </body>
            </html>
            """

            message = EmailMessage(
                to=[EmailRecipient(email=candidate["email"], name=f"{candidate['first_name']} {candidate['last_name']}")],
                subject="Access Your Application Status",
                html_content=html_content,
                email_type=EmailType.APPLICATION_STATUS_UPDATE,
            )

            await email_service.send_email(message)
            logger.info(f"Sent portal access link to {request.email}")

    # Always return same message to prevent email enumeration
    return PortalAccessResponse()


@router.post("/verify", response_model=PortalSession)
async def verify_magic_link(
    request: PortalMagicLinkVerify,
):
    """
    Verify a magic link token and create a session.

    Returns a session token that can be used for subsequent requests.
    """
    client = get_supabase_client()

    # Find magic link
    magic_link = await client.select(
        "candidate_portal_magic_links",
        "*",
        filters={"token": request.token, "is_used": False},
        single=True,
    )

    if not magic_link:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Invalid or expired access link",
        )

    # Check expiration
    expires_at = datetime.fromisoformat(magic_link["expires_at"].replace("Z", "+00:00"))
    if expires_at < datetime.utcnow().replace(tzinfo=expires_at.tzinfo):
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Access link has expired. Please request a new one.",
        )

    # Mark as used
    await client.update(
        "candidate_portal_magic_links",
        {"is_used": True, "used_at": datetime.utcnow().isoformat()},
        filters={"id": magic_link["id"]},
    )

    # Get candidate info
    candidate = await client.select(
        "candidates",
        "id, first_name, last_name, email",
        filters={"id": magic_link["candidate_id"]},
        single=True,
    )

    if not candidate:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Candidate not found",
        )

    # Create session
    session_token = secrets.token_urlsafe(32)
    session_expires = datetime.utcnow() + timedelta(hours=4)

    await client.insert("candidate_portal_sessions", {
        "tenant_id": magic_link["tenant_id"],
        "candidate_id": str(candidate["id"]),
        "session_token": session_token,
        "expires_at": session_expires.isoformat(),
    })

    return PortalSession(
        session_token=session_token,
        candidate_id=candidate["id"],
        candidate_name=f"{candidate['first_name']} {candidate['last_name']}",
        candidate_email=candidate["email"],
        expires_at=session_expires,
    )


# =============================================================================
# Application Status
# =============================================================================


@router.get("/applications", response_model=ApplicationListPublic)
async def list_candidate_applications(
    session: dict = Depends(get_candidate_session),
):
    """
    Get all applications for the authenticated candidate.

    Returns simplified public-facing application information.
    """
    client = get_supabase_client()

    # Get all applications for this candidate
    applications = await client.select(
        "applications",
        "*",
        filters={"candidate_id": session["candidate_id"]},
        return_empty_on_404=True,
    ) or []

    result = []
    for app in applications:
        # Get job details
        job = await client.select(
            "job_requisitions",
            "title, department, location",
            filters={"id": app["requisition_id"]},
            single=True,
        )

        # Get upcoming interviews
        interviews = await client.select(
            "interview_schedules",
            "*",
            filters={
                "application_id": str(app["id"]),
                "status": "scheduled",
            },
            return_empty_on_404=True,
        ) or []

        upcoming_interviews = [
            InterviewInfoPublic(
                id=i["id"],
                interview_type=i.get("interview_type", "interview"),
                title=i.get("title", "Interview"),
                scheduled_at=datetime.fromisoformat(i["scheduled_at"].replace("Z", "+00:00")) if i.get("scheduled_at") else None,
                duration_minutes=i.get("duration_minutes", 60),
                location=i.get("location"),
                video_link=i.get("video_link"),
                status=i.get("status", "scheduled"),
                can_reschedule=True,
            )
            for i in interviews
        ]

        current_status = _map_internal_to_public_status(app.get("status", "new"), app.get("stage_name"))

        # Build status timeline
        timeline = [
            ApplicationStatusUpdate(
                status="received",
                title="Application Received",
                description="We received your application and it's being reviewed.",
                timestamp=datetime.fromisoformat(app["created_at"].replace("Z", "+00:00")),
                is_current=(current_status == ApplicationStatusPublic.RECEIVED),
            )
        ]

        if current_status not in [ApplicationStatusPublic.RECEIVED, ApplicationStatusPublic.WITHDRAWN]:
            timeline.append(ApplicationStatusUpdate(
                status="under_review",
                title="Under Review",
                description="Your application is being reviewed by our team.",
                timestamp=datetime.fromisoformat(app.get("updated_at", app["created_at"]).replace("Z", "+00:00")),
                is_current=(current_status == ApplicationStatusPublic.UNDER_REVIEW),
            ))

        status_messages = {
            ApplicationStatusPublic.RECEIVED: "Your application has been received and is in queue for review.",
            ApplicationStatusPublic.UNDER_REVIEW: "Our team is reviewing your application.",
            ApplicationStatusPublic.INTERVIEW_SCHEDULED: "Great news! You have an interview scheduled.",
            ApplicationStatusPublic.INTERVIEWS_COMPLETE: "Thank you for completing your interviews. We're evaluating candidates.",
            ApplicationStatusPublic.DECISION_PENDING: "We're finalizing our decision. You'll hear from us soon.",
            ApplicationStatusPublic.OFFER_EXTENDED: "Congratulations! An offer has been extended to you.",
            ApplicationStatusPublic.HIRED: "Welcome to the team!",
            ApplicationStatusPublic.NOT_SELECTED: "Thank you for your interest. We've decided to move forward with other candidates.",
            ApplicationStatusPublic.WITHDRAWN: "This application has been withdrawn.",
        }

        result.append(ApplicationDetailPublic(
            id=app["id"],
            position_title=job.get("title", "Position") if job else "Position",
            department=job.get("department") if job else None,
            location=job.get("location") if job else None,
            applied_at=datetime.fromisoformat(app["created_at"].replace("Z", "+00:00")),
            current_status=current_status,
            status_message=status_messages.get(current_status, "Your application is being processed."),
            status_timeline=timeline,
            upcoming_interviews=upcoming_interviews,
            documents_requested=[],
            can_withdraw=(current_status not in [
                ApplicationStatusPublic.HIRED,
                ApplicationStatusPublic.NOT_SELECTED,
                ApplicationStatusPublic.WITHDRAWN,
            ]),
        ))

    return ApplicationListPublic(
        applications=result,
        total=len(result),
    )


@router.get("/applications/{application_id}", response_model=ApplicationDetailPublic)
async def get_application_detail(
    application_id: UUID,
    session: dict = Depends(get_candidate_session),
):
    """Get detailed status for a specific application."""
    client = get_supabase_client()

    application = await client.select(
        "applications",
        "*",
        filters={
            "id": str(application_id),
            "candidate_id": session["candidate_id"],
        },
        single=True,
    )

    if not application:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Application not found",
        )

    # Get job details
    job = await client.select(
        "job_requisitions",
        "title, department, location",
        filters={"id": application["requisition_id"]},
        single=True,
    )

    current_status = _map_internal_to_public_status(application.get("status", "new"))

    return ApplicationDetailPublic(
        id=application["id"],
        position_title=job.get("title", "Position") if job else "Position",
        department=job.get("department") if job else None,
        location=job.get("location") if job else None,
        applied_at=datetime.fromisoformat(application["created_at"].replace("Z", "+00:00")),
        current_status=current_status,
        status_message="Your application is being processed.",
        status_timeline=[],
        upcoming_interviews=[],
        documents_requested=[],
        can_withdraw=True,
    )


# =============================================================================
# Document Upload
# =============================================================================


@router.post("/documents/upload", response_model=DocumentUploadResponse)
async def request_document_upload(
    request: DocumentUploadRequest,
    session: dict = Depends(get_candidate_session),
):
    """
    Request a signed URL to upload a document.

    Returns a pre-signed URL for direct upload to storage.
    """
    client = get_supabase_client()

    # Verify application belongs to candidate
    application = await client.select(
        "applications",
        "id",
        filters={
            "id": str(request.application_id),
            "candidate_id": session["candidate_id"],
        },
        single=True,
    )

    if not application:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Application not found",
        )

    # Generate document ID and upload URL
    doc_id = secrets.token_hex(16)
    expires_at = datetime.utcnow() + timedelta(hours=1)

    # Create document record
    await client.insert("candidate_documents", {
        "id": doc_id,
        "tenant_id": session["tenant_id"],
        "candidate_id": session["candidate_id"],
        "application_id": str(request.application_id),
        "document_type": request.document_type.value,
        "filename": request.filename,
        "content_type": request.content_type,
        "description": request.description,
        "status": "pending_upload",
    })

    # In production, this would return a real signed URL
    # For now, return a placeholder
    upload_url = f"/api/v1/recruiting/portal/documents/{doc_id}/upload"

    return DocumentUploadResponse(
        upload_url=upload_url,
        document_id=UUID(doc_id),
        expires_at=expires_at,
    )


@router.get("/documents", response_model=List[CandidateDocument])
async def list_candidate_documents(
    application_id: Optional[UUID] = Query(None),
    session: dict = Depends(get_candidate_session),
):
    """List documents uploaded by the candidate."""
    client = get_supabase_client()

    filters = {"candidate_id": session["candidate_id"]}
    if application_id:
        filters["application_id"] = str(application_id)

    documents = await client.select(
        "candidate_documents",
        "*",
        filters=filters,
        return_empty_on_404=True,
    ) or []

    return [
        CandidateDocument(
            id=doc["id"],
            application_id=doc["application_id"],
            document_type=DocumentType(doc["document_type"]),
            filename=doc["filename"],
            file_url=doc.get("file_url", ""),
            uploaded_at=datetime.fromisoformat(doc["created_at"].replace("Z", "+00:00")),
            description=doc.get("description"),
        )
        for doc in documents
    ]


# =============================================================================
# EEO Self-Identification
# =============================================================================


@router.get("/eeo/options", response_model=EEOFormOptions)
async def get_eeo_form_options():
    """Get EEO self-identification form options."""
    return EEOFormOptions(
        gender_options=[
            {"value": "male", "label": "Male"},
            {"value": "female", "label": "Female"},
            {"value": "non_binary", "label": "Non-Binary"},
            {"value": "prefer_not_to_say", "label": "Prefer not to say"},
        ],
        ethnicity_options=[
            {"value": "hispanic_latino", "label": "Hispanic or Latino"},
            {"value": "white", "label": "White (Not Hispanic or Latino)"},
            {"value": "black", "label": "Black or African American (Not Hispanic or Latino)"},
            {"value": "asian", "label": "Asian (Not Hispanic or Latino)"},
            {"value": "native_american", "label": "American Indian or Alaska Native (Not Hispanic or Latino)"},
            {"value": "pacific_islander", "label": "Native Hawaiian or Pacific Islander (Not Hispanic or Latino)"},
            {"value": "two_or_more", "label": "Two or More Races (Not Hispanic or Latino)"},
            {"value": "prefer_not_to_say", "label": "Prefer not to say"},
        ],
        veteran_status_options=[
            {"value": "veteran", "label": "I am a protected veteran"},
            {"value": "not_veteran", "label": "I am not a protected veteran"},
            {"value": "prefer_not_to_say", "label": "Prefer not to say"},
        ],
        disability_status_options=[
            {"value": "yes", "label": "Yes, I have a disability (or previously had a disability)"},
            {"value": "no", "label": "No, I do not have a disability"},
            {"value": "prefer_not_to_say", "label": "Prefer not to say"},
        ],
    )


@router.post("/eeo/submit", response_model=EEOSubmissionResponse)
async def submit_eeo_self_identification(
    data: EEOSelfIdentification,
    session: dict = Depends(get_candidate_session),
):
    """
    Submit voluntary EEO self-identification.

    This data is stored separately from the application for privacy
    and is used only for aggregate reporting.
    """
    client = get_supabase_client()

    # Verify application belongs to candidate
    application = await client.select(
        "applications",
        "id",
        filters={
            "id": str(data.application_id),
            "candidate_id": session["candidate_id"],
        },
        single=True,
    )

    if not application:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Application not found",
        )

    # Check if already submitted
    existing = await client.select(
        "eeo_responses",
        "id",
        filters={"application_id": str(data.application_id)},
        single=True,
    )

    if existing:
        # Update existing
        await client.update(
            "eeo_responses",
            {
                "gender": data.gender,
                "ethnicity": data.ethnicity,
                "veteran_status": data.veteran_status,
                "disability_status": data.disability_status,
            },
            filters={"id": existing["id"]},
        )
    else:
        # Create new
        await client.insert("eeo_responses", {
            "tenant_id": session["tenant_id"],
            "application_id": str(data.application_id),
            "gender": data.gender,
            "ethnicity": data.ethnicity,
            "veteran_status": data.veteran_status,
            "disability_status": data.disability_status,
        })

    logger.info(f"EEO response submitted for application {data.application_id}")

    return EEOSubmissionResponse(success=True)


# =============================================================================
# Interview Actions
# =============================================================================


@router.post("/interviews/{interview_id}/confirm")
async def confirm_interview(
    interview_id: UUID,
    confirmation: InterviewConfirmation,
    session: dict = Depends(get_candidate_session),
):
    """Confirm or decline an interview."""
    client = get_supabase_client()

    # Get interview and verify it's for this candidate's application
    interview = await client.select(
        "interview_schedules",
        "*",
        filters={"id": str(interview_id)},
        single=True,
    )

    if not interview:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Interview not found",
        )

    # Verify application belongs to candidate
    application = await client.select(
        "applications",
        "candidate_id",
        filters={"id": interview["application_id"]},
        single=True,
    )

    if not application or str(application["candidate_id"]) != session["candidate_id"]:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="Not authorized to access this interview",
        )

    # Update status
    new_status = "confirmed" if confirmation.confirmed else "declined"
    await client.update(
        "interview_schedules",
        {
            "status": new_status,
            "notes": f"Candidate {'confirmed' if confirmation.confirmed else 'declined'}. {confirmation.notes or ''}".strip(),
        },
        filters={"id": str(interview_id)},
    )

    return {"message": f"Interview {new_status}"}


@router.post("/interviews/{interview_id}/reschedule", response_model=InterviewRescheduleResponse)
async def request_interview_reschedule(
    interview_id: UUID,
    request: InterviewRescheduleRequest,
    session: dict = Depends(get_candidate_session),
):
    """Request to reschedule an interview."""
    client = get_supabase_client()

    # Verify interview access (similar to confirm)
    interview = await client.select(
        "interview_schedules",
        "*",
        filters={"id": str(interview_id)},
        single=True,
    )

    if not interview:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Interview not found",
        )

    application = await client.select(
        "applications",
        "candidate_id",
        filters={"id": interview["application_id"]},
        single=True,
    )

    if not application or str(application["candidate_id"]) != session["candidate_id"]:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="Not authorized",
        )

    # Create reschedule request
    preferred_dates_str = None
    if request.preferred_dates:
        preferred_dates_str = ",".join(d.isoformat() for d in request.preferred_dates)

    reschedule_record = await client.insert("interview_reschedule_requests", {
        "tenant_id": session["tenant_id"],
        "interview_id": str(interview_id),
        "requested_by_candidate": True,
        "reason": request.reason,
        "preferred_dates": preferred_dates_str,
        "status": "submitted",
    })

    # Update interview status
    await client.update(
        "interview_schedules",
        {"status": "reschedule_requested"},
        filters={"id": str(interview_id)},
    )

    return InterviewRescheduleResponse(
        request_id=reschedule_record["id"],
        status="submitted",
        message="Your reschedule request has been submitted. A recruiter will contact you with new available times.",
    )


# =============================================================================
# Withdrawal
# =============================================================================


@router.post("/applications/{application_id}/withdraw", response_model=WithdrawalResponse)
async def withdraw_application(
    application_id: UUID,
    request: WithdrawalRequest,
    session: dict = Depends(get_candidate_session),
):
    """Withdraw an application."""
    client = get_supabase_client()

    # Verify application belongs to candidate
    application = await client.select(
        "applications",
        "*",
        filters={
            "id": str(application_id),
            "candidate_id": session["candidate_id"],
        },
        single=True,
    )

    if not application:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Application not found",
        )

    # Check if can be withdrawn
    non_withdrawable = ["hired", "withdrawn"]
    if application.get("status", "").lower() in non_withdrawable:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="This application cannot be withdrawn",
        )

    # Update status
    await client.update(
        "applications",
        {
            "status": "withdrawn",
            "withdrawn_at": datetime.utcnow().isoformat(),
            "withdrawal_reason": request.reason,
        },
        filters={"id": str(application_id)},
    )

    logger.info(f"Application {application_id} withdrawn by candidate")

    return WithdrawalResponse(success=True)


# =============================================================================
# Profile
# =============================================================================


@router.get("/profile", response_model=CandidateProfileResponse)
async def get_candidate_profile(
    session: dict = Depends(get_candidate_session),
):
    """Get candidate profile information."""
    client = get_supabase_client()

    candidate = await client.select(
        "candidates",
        "*",
        filters={"id": session["candidate_id"]},
        single=True,
    )

    if not candidate:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Candidate not found",
        )

    # Count active applications
    applications = await client.select(
        "applications",
        "id",
        filters={
            "candidate_id": session["candidate_id"],
        },
        return_empty_on_404=True,
    ) or []

    active_count = len([
        a for a in applications
        if a.get("status", "").lower() not in ["withdrawn", "hired", "rejected"]
    ])

    return CandidateProfileResponse(
        id=candidate["id"],
        first_name=candidate["first_name"],
        last_name=candidate["last_name"],
        email=candidate["email"],
        phone=candidate.get("phone"),
        linkedin_url=candidate.get("linkedin_url"),
        preferred_location=candidate.get("preferred_location"),
        willing_to_relocate=candidate.get("willing_to_relocate"),
        active_applications_count=active_count,
    )


@router.patch("/profile", response_model=CandidateProfileResponse)
async def update_candidate_profile(
    update: CandidateProfileUpdate,
    session: dict = Depends(get_candidate_session),
):
    """Update candidate profile information."""
    client = get_supabase_client()

    update_data = update.model_dump(exclude_unset=True)

    if update_data:
        await client.update(
            "candidates",
            update_data,
            filters={"id": session["candidate_id"]},
        )

    return await get_candidate_profile(session)
