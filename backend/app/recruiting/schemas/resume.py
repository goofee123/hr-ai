"""Resume schemas."""

from datetime import datetime
from typing import Optional
from uuid import UUID

from pydantic import BaseModel, Field


class ResumeUploadResponse(BaseModel):
    """Response after uploading a resume."""

    id: UUID
    candidate_id: UUID
    file_name: str
    file_path: str
    file_size_bytes: int
    mime_type: str
    version_number: int
    is_primary: bool
    parsing_status: str
    uploaded_at: datetime

    class Config:
        from_attributes = True


class ResumeResponse(BaseModel):
    """Full resume response with parsed data."""

    id: UUID
    candidate_id: UUID
    file_name: str
    file_path: str
    file_size_bytes: Optional[int]
    mime_type: Optional[str]
    version_number: int
    is_primary: bool
    parsing_status: str
    parsed_data: dict
    uploaded_at: datetime
    created_at: datetime
    updated_at: Optional[datetime]

    class Config:
        from_attributes = True


class ResumeListItem(BaseModel):
    """Resume item for list views."""

    id: UUID
    file_name: str
    file_size_bytes: Optional[int]
    mime_type: Optional[str]
    version_number: int
    is_primary: bool
    parsing_status: str
    uploaded_at: datetime


class ParsedResumeData(BaseModel):
    """Structured resume data extracted by LLM."""

    personal: Optional[dict] = None
    summary: Optional[str] = None
    experience: Optional[list] = None
    education: Optional[list] = None
    skills: Optional[list] = None
    certifications: Optional[list] = None
    languages: Optional[list] = None
    total_years_experience: Optional[float] = None


class ResumeParseRequest(BaseModel):
    """Request to re-parse a resume."""

    force: bool = Field(
        False,
        description="Force re-parsing even if already parsed",
    )


class SetPrimaryResumeRequest(BaseModel):
    """Request to set a resume as primary."""

    resume_id: UUID = Field(..., description="Resume ID to set as primary")
