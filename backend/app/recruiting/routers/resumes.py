"""Resume upload and management endpoints."""

import uuid
from datetime import datetime, timezone
from typing import List, Optional
from uuid import UUID

import httpx
from fastapi import APIRouter, Depends, File, HTTPException, UploadFile, status

from app.config import get_settings
from app.core.security import TokenData
from app.core.permissions import Permission, require_permission
from app.core.supabase_client import get_supabase_client
from app.recruiting.schemas.resume import (
    ResumeUploadResponse,
    ResumeResponse,
    ResumeListItem,
    ResumeParseRequest,
    SetPrimaryResumeRequest,
)
from app.recruiting.services.text_extraction import extract_text
from app.recruiting.services.llm_extraction import get_llm_service

router = APIRouter()
settings = get_settings()

# Supabase storage settings
SUPABASE_URL = settings.supabase_url
SUPABASE_KEY = settings.supabase_service_role_key
STORAGE_BUCKET = "resumes"

# Allowed file types
ALLOWED_MIME_TYPES = {
    "application/pdf": ".pdf",
    "application/vnd.openxmlformats-officedocument.wordprocessingml.document": ".docx",
    "application/msword": ".doc",
}
MAX_FILE_SIZE = 10 * 1024 * 1024  # 10 MB


async def upload_to_storage(file_content: bytes, file_path: str, mime_type: str) -> str:
    """Upload a file to Supabase Storage.

    Returns the file path in storage.
    """
    async with httpx.AsyncClient() as http_client:
        headers = {
            "Authorization": f"Bearer {SUPABASE_KEY}",
            "apikey": SUPABASE_KEY,
            "Content-Type": mime_type,
        }

        response = await http_client.post(
            f"{SUPABASE_URL}/storage/v1/object/{STORAGE_BUCKET}/{file_path}",
            headers=headers,
            content=file_content,
            timeout=60.0,
        )

        if response.status_code not in (200, 201):
            # Try to create bucket if it doesn't exist
            if "not found" in response.text.lower():
                # Create bucket
                bucket_response = await http_client.post(
                    f"{SUPABASE_URL}/storage/v1/bucket",
                    headers={
                        "Authorization": f"Bearer {SUPABASE_KEY}",
                        "apikey": SUPABASE_KEY,
                        "Content-Type": "application/json",
                    },
                    json={
                        "id": STORAGE_BUCKET,
                        "name": STORAGE_BUCKET,
                        "public": False,
                    },
                    timeout=30.0,
                )
                if bucket_response.status_code in (200, 201):
                    # Retry upload
                    response = await http_client.post(
                        f"{SUPABASE_URL}/storage/v1/object/{STORAGE_BUCKET}/{file_path}",
                        headers=headers,
                        content=file_content,
                        timeout=60.0,
                    )
                    if response.status_code in (200, 201):
                        return file_path

            raise HTTPException(
                status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
                detail=f"Failed to upload file to storage: {response.text}",
            )

        return file_path


async def get_download_url(file_path: str) -> str:
    """Get a signed download URL for a file."""
    async with httpx.AsyncClient() as http_client:
        headers = {
            "Authorization": f"Bearer {SUPABASE_KEY}",
            "apikey": SUPABASE_KEY,
            "Content-Type": "application/json",
        }

        response = await http_client.post(
            f"{SUPABASE_URL}/storage/v1/object/sign/{STORAGE_BUCKET}/{file_path}",
            headers=headers,
            json={"expiresIn": 3600},  # 1 hour
            timeout=30.0,
        )

        if response.status_code != 200:
            raise HTTPException(
                status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
                detail=f"Failed to generate download URL: {response.text}",
            )

        data = response.json()
        return f"{SUPABASE_URL}/storage/v1{data['signedURL']}"


@router.post(
    "/candidates/{candidate_id}/resumes",
    response_model=ResumeUploadResponse,
    status_code=status.HTTP_201_CREATED,
)
async def upload_resume(
    candidate_id: UUID,
    file: UploadFile = File(...),
    parse_immediately: bool = True,
    current_user: TokenData = Depends(require_permission(Permission.CANDIDATES_EDIT)),
):
    """Upload a resume for a candidate.

    The resume will be stored in Supabase Storage and optionally parsed using LLM.
    """
    client = get_supabase_client()

    # Verify candidate exists
    candidate = await client.select(
        "candidates",
        "id,tenant_id",
        filters={
            "id": str(candidate_id),
            "tenant_id": str(current_user.tenant_id),
        },
        single=True,
    )

    if not candidate:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Candidate not found",
        )

    # Validate file type
    content_type = file.content_type or "application/octet-stream"
    if content_type not in ALLOWED_MIME_TYPES:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=f"File type not allowed. Allowed types: PDF, DOCX, DOC",
        )

    # Read file content
    file_content = await file.read()
    file_size = len(file_content)

    if file_size > MAX_FILE_SIZE:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=f"File too large. Maximum size: {MAX_FILE_SIZE / 1024 / 1024} MB",
        )

    # Get version number (count existing resumes for this candidate)
    existing_resumes = await client.select(
        "resumes",
        "id",
        filters={"candidate_id": str(candidate_id)},
    ) or []
    version_number = len(existing_resumes) + 1

    # Generate unique file path
    file_ext = ALLOWED_MIME_TYPES.get(content_type, ".pdf")
    resume_id = str(uuid.uuid4())
    file_path = f"{current_user.tenant_id}/{candidate_id}/{resume_id}{file_ext}"

    # Upload to storage
    await upload_to_storage(file_content, file_path, content_type)

    # Determine if this should be primary
    is_primary = version_number == 1  # First resume is automatically primary

    # Create resume record
    now = datetime.now(timezone.utc)
    resume_data = {
        "id": resume_id,
        "tenant_id": str(current_user.tenant_id),
        "candidate_id": str(candidate_id),
        "file_name": file.filename or f"resume{file_ext}",
        "file_path": file_path,
        "file_size_bytes": file_size,
        "mime_type": content_type,
        "version_number": version_number,
        "is_primary": is_primary,
        "parsing_status": "pending",
        "parsed_data": {},
        "uploaded_at": now.isoformat(),
    }

    resume = await client.insert("resumes", resume_data)

    # Parse resume in background if requested
    if parse_immediately:
        # Extract text
        extracted_text, extraction_metadata = extract_text(file_content, content_type)

        if extracted_text:
            # Update parsing status to processing
            await client.update(
                "resumes",
                {"parsing_status": "processing"},
                filters={"id": resume_id},
            )

            # Parse with LLM
            llm_service = get_llm_service()
            parsed_data = await llm_service.parse_resume(extracted_text)

            # Add extraction metadata
            parsed_data["_extraction_metadata"] = extraction_metadata

            # Calculate experience years if not present
            if "total_years_experience" not in parsed_data or not parsed_data.get("total_years_experience"):
                years = await llm_service.calculate_experience_years(parsed_data)
                if years:
                    parsed_data["total_years_experience"] = years

            # Update resume with parsed data
            parsing_status = "completed" if "error" not in parsed_data else "failed"
            await client.update(
                "resumes",
                {
                    "parsing_status": parsing_status,
                    "parsed_data": parsed_data,
                },
                filters={"id": resume_id},
            )

            # Update candidate skills if parsed successfully
            if parsing_status == "completed" and parsed_data.get("skills"):
                await client.update(
                    "candidates",
                    {"skills": parsed_data["skills"]},
                    filters={"id": str(candidate_id)},
                )

            resume["parsing_status"] = parsing_status
        else:
            await client.update(
                "resumes",
                {
                    "parsing_status": "failed",
                    "parsed_data": extraction_metadata,
                },
                filters={"id": resume_id},
            )
            resume["parsing_status"] = "failed"

    return ResumeUploadResponse(
        id=resume["id"],
        candidate_id=candidate_id,
        file_name=resume["file_name"],
        file_path=resume["file_path"],
        file_size_bytes=file_size,
        mime_type=content_type,
        version_number=version_number,
        is_primary=is_primary,
        parsing_status=resume["parsing_status"],
        uploaded_at=now,
    )


@router.get("/candidates/{candidate_id}/resumes", response_model=List[ResumeListItem])
async def list_candidate_resumes(
    candidate_id: UUID,
    current_user: TokenData = Depends(require_permission(Permission.CANDIDATES_VIEW)),
):
    """List all resumes for a candidate."""
    client = get_supabase_client()

    # Verify candidate exists and belongs to tenant
    candidate = await client.select(
        "candidates",
        "id",
        filters={
            "id": str(candidate_id),
            "tenant_id": str(current_user.tenant_id),
        },
        single=True,
    )

    if not candidate:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Candidate not found",
        )

    resumes = await client.select(
        "resumes",
        "id,file_name,file_size_bytes,mime_type,version_number,is_primary,parsing_status,uploaded_at",
        filters={"candidate_id": str(candidate_id)},
    ) or []

    # Sort by version number descending (newest first)
    resumes.sort(key=lambda x: x.get("version_number", 0), reverse=True)

    return [
        ResumeListItem(
            id=r["id"],
            file_name=r["file_name"],
            file_size_bytes=r.get("file_size_bytes"),
            mime_type=r.get("mime_type"),
            version_number=r["version_number"],
            is_primary=r["is_primary"],
            parsing_status=r["parsing_status"],
            uploaded_at=datetime.fromisoformat(r["uploaded_at"].replace("Z", "+00:00")),
        )
        for r in resumes
    ]


@router.get("/candidates/{candidate_id}/resumes/{resume_id}", response_model=ResumeResponse)
async def get_resume(
    candidate_id: UUID,
    resume_id: UUID,
    current_user: TokenData = Depends(require_permission(Permission.CANDIDATES_VIEW)),
):
    """Get a specific resume with parsed data."""
    client = get_supabase_client()

    resume = await client.select(
        "resumes",
        "*",
        filters={
            "id": str(resume_id),
            "candidate_id": str(candidate_id),
        },
        single=True,
    )

    if not resume:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Resume not found",
        )

    # Verify tenant access via candidate
    candidate = await client.select(
        "candidates",
        "tenant_id",
        filters={"id": str(candidate_id)},
        single=True,
    )

    if not candidate or candidate.get("tenant_id") != str(current_user.tenant_id):
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Resume not found",
        )

    return ResumeResponse(
        id=resume["id"],
        candidate_id=resume["candidate_id"],
        file_name=resume["file_name"],
        file_path=resume["file_path"],
        file_size_bytes=resume.get("file_size_bytes"),
        mime_type=resume.get("mime_type"),
        version_number=resume["version_number"],
        is_primary=resume["is_primary"],
        parsing_status=resume["parsing_status"],
        parsed_data=resume.get("parsed_data") or {},
        uploaded_at=datetime.fromisoformat(resume["uploaded_at"].replace("Z", "+00:00")),
        created_at=datetime.fromisoformat(resume["created_at"].replace("Z", "+00:00")),
        updated_at=(
            datetime.fromisoformat(resume["updated_at"].replace("Z", "+00:00"))
            if resume.get("updated_at")
            else None
        ),
    )


@router.get("/candidates/{candidate_id}/resumes/{resume_id}/download")
async def download_resume(
    candidate_id: UUID,
    resume_id: UUID,
    current_user: TokenData = Depends(require_permission(Permission.CANDIDATES_VIEW)),
):
    """Get a signed download URL for a resume."""
    client = get_supabase_client()

    resume = await client.select(
        "resumes",
        "file_path,file_name",
        filters={
            "id": str(resume_id),
            "candidate_id": str(candidate_id),
        },
        single=True,
    )

    if not resume:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Resume not found",
        )

    # Verify tenant access
    candidate = await client.select(
        "candidates",
        "tenant_id",
        filters={"id": str(candidate_id)},
        single=True,
    )

    if not candidate or candidate.get("tenant_id") != str(current_user.tenant_id):
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Resume not found",
        )

    download_url = await get_download_url(resume["file_path"])

    return {
        "download_url": download_url,
        "file_name": resume["file_name"],
        "expires_in_seconds": 3600,
    }


@router.post("/candidates/{candidate_id}/resumes/{resume_id}/parse")
async def reparse_resume(
    candidate_id: UUID,
    resume_id: UUID,
    request: ResumeParseRequest = ResumeParseRequest(),
    current_user: TokenData = Depends(require_permission(Permission.CANDIDATES_EDIT)),
):
    """Re-parse a resume using LLM."""
    client = get_supabase_client()

    resume = await client.select(
        "resumes",
        "*",
        filters={
            "id": str(resume_id),
            "candidate_id": str(candidate_id),
        },
        single=True,
    )

    if not resume:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Resume not found",
        )

    # Verify tenant
    candidate = await client.select(
        "candidates",
        "tenant_id",
        filters={"id": str(candidate_id)},
        single=True,
    )

    if not candidate or candidate.get("tenant_id") != str(current_user.tenant_id):
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Resume not found",
        )

    # Check if already parsed (unless force)
    if resume["parsing_status"] == "completed" and not request.force:
        return {
            "message": "Resume already parsed",
            "parsing_status": resume["parsing_status"],
            "parsed_data": resume.get("parsed_data"),
        }

    # Download file from storage
    async with httpx.AsyncClient() as http_client:
        headers = {
            "Authorization": f"Bearer {SUPABASE_KEY}",
            "apikey": SUPABASE_KEY,
        }

        response = await http_client.get(
            f"{SUPABASE_URL}/storage/v1/object/{STORAGE_BUCKET}/{resume['file_path']}",
            headers=headers,
            timeout=60.0,
        )

        if response.status_code != 200:
            raise HTTPException(
                status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
                detail="Failed to download resume from storage",
            )

        file_content = response.content

    # Update status to processing
    await client.update(
        "resumes",
        {"parsing_status": "processing"},
        filters={"id": str(resume_id)},
    )

    # Extract text
    extracted_text, extraction_metadata = extract_text(
        file_content, resume.get("mime_type", "application/pdf")
    )

    if not extracted_text:
        await client.update(
            "resumes",
            {
                "parsing_status": "failed",
                "parsed_data": extraction_metadata,
            },
            filters={"id": str(resume_id)},
        )
        raise HTTPException(
            status_code=status.HTTP_422_UNPROCESSABLE_ENTITY,
            detail="Failed to extract text from resume",
        )

    # Parse with LLM
    llm_service = get_llm_service()
    parsed_data = await llm_service.parse_resume(extracted_text)
    parsed_data["_extraction_metadata"] = extraction_metadata

    # Calculate experience years
    if "total_years_experience" not in parsed_data or not parsed_data.get("total_years_experience"):
        years = await llm_service.calculate_experience_years(parsed_data)
        if years:
            parsed_data["total_years_experience"] = years

    parsing_status = "completed" if "error" not in parsed_data else "failed"

    await client.update(
        "resumes",
        {
            "parsing_status": parsing_status,
            "parsed_data": parsed_data,
        },
        filters={"id": str(resume_id)},
    )

    # Update candidate skills if parsed successfully
    if parsing_status == "completed" and parsed_data.get("skills"):
        await client.update(
            "candidates",
            {"skills": parsed_data["skills"]},
            filters={"id": str(candidate_id)},
        )

    return {
        "message": "Resume parsed successfully" if parsing_status == "completed" else "Parsing failed",
        "parsing_status": parsing_status,
        "parsed_data": parsed_data,
    }


@router.post("/candidates/{candidate_id}/resumes/set-primary")
async def set_primary_resume(
    candidate_id: UUID,
    request: SetPrimaryResumeRequest,
    current_user: TokenData = Depends(require_permission(Permission.CANDIDATES_EDIT)),
):
    """Set a resume as the primary resume for a candidate."""
    client = get_supabase_client()

    # Verify resume exists
    resume = await client.select(
        "resumes",
        "id",
        filters={
            "id": str(request.resume_id),
            "candidate_id": str(candidate_id),
        },
        single=True,
    )

    if not resume:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Resume not found",
        )

    # Verify tenant
    candidate = await client.select(
        "candidates",
        "tenant_id",
        filters={"id": str(candidate_id)},
        single=True,
    )

    if not candidate or candidate.get("tenant_id") != str(current_user.tenant_id):
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Resume not found",
        )

    # Unset all other resumes as primary
    all_resumes = await client.select(
        "resumes",
        "id",
        filters={"candidate_id": str(candidate_id)},
    ) or []

    for r in all_resumes:
        if r["id"] != str(request.resume_id):
            await client.update(
                "resumes",
                {"is_primary": False},
                filters={"id": r["id"]},
            )

    # Set the requested resume as primary
    await client.update(
        "resumes",
        {"is_primary": True},
        filters={"id": str(request.resume_id)},
    )

    return {"message": "Primary resume updated", "resume_id": str(request.resume_id)}


@router.delete("/candidates/{candidate_id}/resumes/{resume_id}", status_code=status.HTTP_204_NO_CONTENT)
async def delete_resume(
    candidate_id: UUID,
    resume_id: UUID,
    current_user: TokenData = Depends(require_permission(Permission.CANDIDATES_EDIT)),
):
    """Delete a resume."""
    client = get_supabase_client()

    resume = await client.select(
        "resumes",
        "file_path,is_primary",
        filters={
            "id": str(resume_id),
            "candidate_id": str(candidate_id),
        },
        single=True,
    )

    if not resume:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Resume not found",
        )

    # Verify tenant
    candidate = await client.select(
        "candidates",
        "tenant_id",
        filters={"id": str(candidate_id)},
        single=True,
    )

    if not candidate or candidate.get("tenant_id") != str(current_user.tenant_id):
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Resume not found",
        )

    # Delete from storage
    async with httpx.AsyncClient() as http_client:
        headers = {
            "Authorization": f"Bearer {SUPABASE_KEY}",
            "apikey": SUPABASE_KEY,
        }

        await http_client.delete(
            f"{SUPABASE_URL}/storage/v1/object/{STORAGE_BUCKET}/{resume['file_path']}",
            headers=headers,
            timeout=30.0,
        )

    # Delete from database
    await client.delete("resumes", filters={"id": str(resume_id)})

    # If this was primary, set another resume as primary
    if resume["is_primary"]:
        other_resumes = await client.select(
            "resumes",
            "id",
            filters={"candidate_id": str(candidate_id)},
        ) or []

        if other_resumes:
            await client.update(
                "resumes",
                {"is_primary": True},
                filters={"id": other_resumes[0]["id"]},
            )

    return None
