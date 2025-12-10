"""Resume Parsing Task - Background job for LLM-based resume extraction."""

import logging
import base64
import json
from datetime import datetime, timezone
from typing import Dict, Any, Optional, List
from uuid import UUID

import httpx

from app.config import get_settings

logger = logging.getLogger(__name__)
settings = get_settings()


def _get_headers() -> Dict[str, str]:
    """Get headers for Supabase REST API calls."""
    return {
        "apikey": settings.supabase_service_role_key,
        "Authorization": f"Bearer {settings.supabase_service_role_key}",
        "Content-Type": "application/json",
        "Prefer": "return=representation",
    }


# LLM Prompt for resume extraction - Enhanced with temporal context
RESUME_EXTRACTION_PROMPT = """Extract the following information from this resume in JSON format.
Today's date is {current_date}.

{{
  "personal": {{
    "full_name": "",
    "email": "",
    "phone": "",
    "location": "",
    "linkedin_url": ""
  }},
  "summary": "",
  "current_level": "",  // "intern", "entry", "mid", "senior", "lead", "manager", "director", "executive"
  "experience": [
    {{
      "company": "",
      "title": "",
      "level": "",  // "intern", "entry", "mid", "senior", "lead", "manager", "director", "executive"
      "start_date": "",  // YYYY-MM format
      "end_date": "",    // YYYY-MM format or "present"
      "is_current": false,
      "duration_months": 0,  // calculated duration
      "description": "",
      "key_technologies": [],  // specific tools/technologies used in this role
      "achievements": []
    }}
  ],
  "education": [
    {{
      "institution": "",
      "degree": "",
      "field": "",
      "graduation_date": "",
      "gpa": null
    }}
  ],
  "skills": {{
    "current": [],      // skills actively used in last 2 years
    "proficient": [],   // skills with significant experience
    "familiar": [],     // skills mentioned but limited experience
    "outdated": []      // skills from old roles, not used recently
  }},
  "certifications": [
    {{
      "name": "",
      "issuer": "",
      "date": "",
      "is_current": true  // false if expired or very old
    }}
  ],
  "languages": [],
  "career_progression": {{
    "trajectory": "",  // "ascending", "lateral", "mixed", "early_career"
    "years_at_current_level": 0,
    "total_years_experience": 0,
    "years_relevant_experience": 0  // non-intern, professional experience only
  }},
  "derived_insights": {{
    "most_recent_title": "",
    "most_recent_company": "",
    "primary_industry": "",
    "career_stability": "",  // "stable", "frequent_changes", "contractor", "mixed"
    "employment_gaps": []    // any gaps > 6 months
  }}
}}

CRITICAL INSTRUCTIONS:
1. Calculate experience EXCLUDING internships when determining seniority
2. Mark skills as "outdated" if only used in roles >3 years ago
3. A person who was an "Intern" in 2021 but is now a "Software Engineer" in 2024 is NOT an intern
4. current_level should reflect their MOST RECENT role, not historical roles
5. years_relevant_experience should exclude internships and student jobs
6. For skills categorization: if a skill appears only in old roles (>3 years), mark it "outdated"
7. Identify career_progression trajectory based on title changes over time

Resume text:
{resume_text}
"""


def _categorize_skill_recency(experience: List[Dict], skill: str, cutoff_years: int = 3) -> str:
    """Determine if a skill is current, proficient, familiar, or outdated based on when it was used."""
    from datetime import datetime

    cutoff_date = datetime.now().year - cutoff_years
    skill_lower = skill.lower()

    most_recent_use = None
    total_months_used = 0

    for exp in experience:
        # Check if skill mentioned in this role
        exp_skills = [s.lower() for s in exp.get("key_technologies", [])]
        description_lower = exp.get("description", "").lower()

        if skill_lower in exp_skills or skill_lower in description_lower:
            # Parse end date
            end_date_str = exp.get("end_date", "")
            if end_date_str == "present" or exp.get("is_current"):
                end_year = datetime.now().year
            elif end_date_str:
                try:
                    end_year = int(end_date_str.split("-")[0])
                except:
                    end_year = datetime.now().year
            else:
                end_year = datetime.now().year

            if most_recent_use is None or end_year > most_recent_use:
                most_recent_use = end_year

            total_months_used += exp.get("duration_months", 0)

    if most_recent_use is None:
        return "familiar"  # Mentioned but not tied to specific role

    if most_recent_use < cutoff_date:
        return "outdated"
    elif total_months_used >= 24:  # 2+ years of use
        return "current" if most_recent_use >= datetime.now().year - 1 else "proficient"
    elif total_months_used >= 6:
        return "proficient"
    else:
        return "familiar"


def _calculate_relevant_experience(experience: List[Dict]) -> float:
    """Calculate years of relevant (non-intern) experience."""
    from datetime import datetime

    total_months = 0
    intern_keywords = ["intern", "internship", "co-op", "student", "trainee"]

    for exp in experience:
        title_lower = exp.get("title", "").lower()

        # Skip intern/student roles
        if any(kw in title_lower for kw in intern_keywords):
            continue

        duration = exp.get("duration_months", 0)
        if duration == 0:
            # Try to calculate from dates
            start = exp.get("start_date", "")
            end = exp.get("end_date", "")
            if start:
                try:
                    start_parts = start.split("-")
                    start_year = int(start_parts[0])
                    start_month = int(start_parts[1]) if len(start_parts) > 1 else 1

                    if end == "present" or exp.get("is_current"):
                        end_year = datetime.now().year
                        end_month = datetime.now().month
                    elif end:
                        end_parts = end.split("-")
                        end_year = int(end_parts[0])
                        end_month = int(end_parts[1]) if len(end_parts) > 1 else 12
                    else:
                        continue

                    duration = (end_year - start_year) * 12 + (end_month - start_month)
                except:
                    continue

        total_months += max(0, duration)

    return round(total_months / 12, 1)


def _determine_current_level(experience: List[Dict]) -> str:
    """Determine candidate's current career level from most recent role."""
    if not experience:
        return "entry"

    # Sort by end date (most recent first)
    def get_sort_key(exp):
        end = exp.get("end_date", "")
        if end == "present" or exp.get("is_current"):
            return "9999-99"
        return end or "0000-00"

    sorted_exp = sorted(experience, key=get_sort_key, reverse=True)

    # Get most recent role
    recent = sorted_exp[0]
    title = recent.get("title", "").lower()

    # Level detection patterns
    level_patterns = {
        "executive": ["ceo", "cto", "cfo", "coo", "chief", "president", "vp ", "vice president"],
        "director": ["director", "head of"],
        "manager": ["manager", "team lead", "tech lead", "engineering lead"],
        "lead": ["lead", "principal", "staff"],
        "senior": ["senior", "sr.", "sr "],
        "mid": ["ii", "iii", "2", "3"],
        "entry": ["junior", "jr.", "jr ", "associate", "i"],
        "intern": ["intern", "internship", "co-op", "trainee", "student"],
    }

    for level, patterns in level_patterns.items():
        if any(p in title for p in patterns):
            return level

    # Default based on years of experience
    years = _calculate_relevant_experience(experience)
    if years >= 10:
        return "senior"
    elif years >= 5:
        return "mid"
    elif years >= 2:
        return "entry"
    else:
        return "entry"


async def parse_resume(ctx: Dict[str, Any], resume_id: str, tenant_id: str) -> Dict[str, Any]:
    """
    Background task to parse a resume using LLM extraction.

    Args:
        ctx: ARQ context
        resume_id: UUID of the resume record
        tenant_id: UUID of the tenant

    Returns:
        Dict with parsed data and status
    """
    logger.info(f"Starting resume parsing for resume_id={resume_id}")

    result = {
        "resume_id": resume_id,
        "status": "pending",
        "parsed_at": None,
        "parsed_data": None,
        "error": None,
    }

    async with httpx.AsyncClient() as client:
        try:
            # 1. Fetch resume record
            resume = await _get_resume(client, resume_id, tenant_id)
            if not resume:
                result["status"] = "failed"
                result["error"] = "Resume not found"
                return result

            # 2. Get resume text (from storage or text field)
            resume_text = await _extract_text(client, resume)
            if not resume_text:
                result["status"] = "failed"
                result["error"] = "Could not extract text from resume"
                return result

            # 3. Parse with LLM
            parsed_data = await _parse_with_llm(resume_text)
            if not parsed_data:
                result["status"] = "failed"
                result["error"] = "LLM parsing failed"
                return result

            # 4. Build skill index with recency weights
            skill_index_data = await _build_skill_index(parsed_data)
            parsed_data["skill_index"] = skill_index_data

            # 5. Update resume record with parsed data
            await _update_resume_parsed_data(client, resume_id, parsed_data)

            # 6. Update candidate record with extracted info
            if resume.get("candidate_id"):
                await _update_candidate_from_parsed(
                    client, resume["candidate_id"], parsed_data
                )

            result["status"] = "completed"
            result["parsed_at"] = datetime.now(timezone.utc).isoformat()
            result["parsed_data"] = parsed_data

            logger.info(f"Resume parsing completed for resume_id={resume_id}")

        except Exception as e:
            logger.error(f"Resume parsing failed for resume_id={resume_id}: {str(e)}")
            result["status"] = "failed"
            result["error"] = str(e)

    return result


async def _get_resume(
    client: httpx.AsyncClient, resume_id: str, tenant_id: str
) -> Optional[Dict[str, Any]]:
    """Fetch resume record from database."""
    try:
        response = await client.get(
            f"{settings.supabase_url}/rest/v1/resumes",
            headers=_get_headers(),
            params={
                "id": f"eq.{resume_id}",
                "tenant_id": f"eq.{tenant_id}",
                "select": "*",
            },
            timeout=30,
        )

        if response.status_code == 200 and response.json():
            return response.json()[0]
        return None
    except Exception as e:
        logger.error(f"Error fetching resume: {str(e)}")
        return None


async def _extract_text(
    client: httpx.AsyncClient, resume: Dict[str, Any]
) -> Optional[str]:
    """Extract text from resume file or use stored text."""
    # If text already extracted, use it
    if resume.get("extracted_text"):
        return resume["extracted_text"]

    # If file path available, download and extract
    file_path = resume.get("file_path")
    if not file_path:
        return None

    try:
        # Download file from Supabase storage
        storage_url = f"{settings.supabase_url}/storage/v1/object/{file_path}"
        response = await client.get(
            storage_url,
            headers={
                "apikey": settings.supabase_service_role_key,
                "Authorization": f"Bearer {settings.supabase_service_role_key}",
            },
            timeout=60,
        )

        if response.status_code != 200:
            logger.warning(f"Failed to download resume file: {response.status_code}")
            return None

        # Determine file type and extract text
        content_type = response.headers.get("content-type", "")
        file_content = response.content

        if "pdf" in content_type.lower() or file_path.lower().endswith(".pdf"):
            return await _extract_pdf_text(file_content)
        elif "word" in content_type.lower() or file_path.lower().endswith((".doc", ".docx")):
            return await _extract_docx_text(file_content)
        else:
            # Try to decode as plain text
            try:
                return file_content.decode("utf-8")
            except UnicodeDecodeError:
                return None

    except Exception as e:
        logger.error(f"Error extracting text: {str(e)}")
        return None


async def _extract_pdf_text(content: bytes) -> Optional[str]:
    """Extract text from PDF bytes using PyPDF2."""
    try:
        import io
        from PyPDF2 import PdfReader

        pdf_file = io.BytesIO(content)
        reader = PdfReader(pdf_file)

        text_parts = []
        for page in reader.pages:
            text = page.extract_text()
            if text:
                text_parts.append(text)

        return "\n".join(text_parts) if text_parts else None
    except ImportError:
        logger.warning("PyPDF2 not installed, cannot extract PDF text")
        return None
    except Exception as e:
        logger.error(f"PDF extraction error: {str(e)}")
        return None


async def _extract_docx_text(content: bytes) -> Optional[str]:
    """Extract text from DOCX bytes using python-docx."""
    try:
        import io
        from docx import Document

        docx_file = io.BytesIO(content)
        doc = Document(docx_file)

        text_parts = []
        for para in doc.paragraphs:
            if para.text.strip():
                text_parts.append(para.text)

        return "\n".join(text_parts) if text_parts else None
    except ImportError:
        logger.warning("python-docx not installed, cannot extract DOCX text")
        return None
    except Exception as e:
        logger.error(f"DOCX extraction error: {str(e)}")
        return None


async def _build_skill_index(parsed_data: Dict[str, Any]) -> Dict[str, Any]:
    """Build skill index with recency weights from parsed resume data.

    This creates a structured skill profile with:
    - Recency weights (skills decay over time)
    - Depth weights (years + job count)
    - Confidence levels (verified, strong, moderate, weak, stale)
    """
    try:
        from app.recruiting.services.skill_index import skill_index_service

        skill_records = skill_index_service.extract_skills_from_parsed_resume(parsed_data)

        # Convert to serializable format
        skills_indexed = []
        for record in skill_records:
            skills_indexed.append({
                "skill": record.skill_name,
                "normalized": record.normalized_name,
                "last_used": str(record.last_used_date) if record.last_used_date else None,
                "years_experience": record.years_experience,
                "job_count": record.job_count,
                "source": record.source.value,
                "confidence": record.confidence.value,
                "recency_weight": record.recency_weight,
                "depth_weight": record.depth_weight,
                "final_weight": record.final_weight,
            })

        # Get categorized skills
        current_skills = [s["skill"] for s in skills_indexed if s["source"] == "current_job"]
        stale_skills = [s["skill"] for s in skills_indexed if s["confidence"] == "stale"]
        top_skills = [s["skill"] for s in skills_indexed[:10]]  # Top 10 by weight

        return {
            "skills": skills_indexed,
            "summary": {
                "total_skills": len(skills_indexed),
                "current_skills": current_skills,
                "stale_skills": stale_skills,
                "top_skills": top_skills,
            },
            "indexed_at": datetime.now(timezone.utc).isoformat(),
        }

    except Exception as e:
        logger.error(f"Error building skill index: {str(e)}")
        return {
            "skills": [],
            "summary": {"total_skills": 0},
            "error": str(e),
        }


async def _parse_with_llm(resume_text: str) -> Optional[Dict[str, Any]]:
    """Parse resume text using OpenAI GPT-4."""
    openai_key = settings.openai_api_key if hasattr(settings, 'openai_api_key') else None

    if not openai_key:
        logger.warning("OpenAI API key not configured, using mock parsing")
        return _mock_parse(resume_text)

    try:
        async with httpx.AsyncClient() as client:
            # Format prompt with current date
            current_date = datetime.now().strftime("%Y-%m-%d")
            prompt = RESUME_EXTRACTION_PROMPT.format(
                current_date=current_date,
                resume_text=resume_text[:15000]
            )

            response = await client.post(
                "https://api.openai.com/v1/chat/completions",
                headers={
                    "Authorization": f"Bearer {openai_key}",
                    "Content-Type": "application/json",
                },
                json={
                    "model": "gpt-4-turbo-preview",
                    "messages": [
                        {
                            "role": "system",
                            "content": "You are a resume parsing assistant. Extract information accurately and return valid JSON only."
                        },
                        {"role": "user", "content": prompt}
                    ],
                    "temperature": 0.1,
                    "max_tokens": 4000,
                    "response_format": {"type": "json_object"}
                },
                timeout=120,
            )

            if response.status_code != 200:
                logger.error(f"OpenAI API error: {response.status_code} - {response.text}")
                return None

            result = response.json()
            content = result["choices"][0]["message"]["content"]
            return json.loads(content)

    except Exception as e:
        logger.error(f"LLM parsing error: {str(e)}")
        return None


def _mock_parse(resume_text: str) -> Dict[str, Any]:
    """Mock parsing for when OpenAI is not configured (development/testing)."""
    # Extract basic info using simple patterns
    import re

    email_match = re.search(r'[\w.+-]+@[\w-]+\.[\w.-]+', resume_text)
    phone_match = re.search(r'[\+\d][\d\s\-\(\)]{8,}', resume_text)

    # Simple skill extraction (common tech terms)
    common_skills = [
        "Python", "JavaScript", "TypeScript", "Java", "C++", "React", "Node.js",
        "AWS", "Docker", "Kubernetes", "SQL", "PostgreSQL", "MongoDB", "Git",
        "Machine Learning", "AI", "Data Analysis", "Project Management"
    ]
    found_skills = [s for s in common_skills if s.lower() in resume_text.lower()]

    return {
        "personal": {
            "full_name": "",  # Would need more sophisticated NER
            "email": email_match.group() if email_match else "",
            "phone": phone_match.group().strip() if phone_match else "",
            "location": "",
            "linkedin_url": ""
        },
        "summary": "",
        "experience": [],
        "education": [],
        "skills": found_skills,
        "certifications": [],
        "languages": [],
        "total_years_experience": 0,
        "_parsing_mode": "mock"
    }


async def _update_resume_parsed_data(
    client: httpx.AsyncClient, resume_id: str, parsed_data: Dict[str, Any]
) -> None:
    """Update resume record with parsed data."""
    try:
        now = datetime.now(timezone.utc).isoformat()

        response = await client.patch(
            f"{settings.supabase_url}/rest/v1/resumes",
            headers=_get_headers(),
            params={"id": f"eq.{resume_id}"},
            json={
                "parsed_data": parsed_data,
                "parsed_at": now,
                "updated_at": now,
            },
            timeout=30,
        )

        if response.status_code not in (200, 204):
            logger.warning(f"Failed to update resume parsed data: {response.status_code}")
    except Exception as e:
        logger.error(f"Error updating resume: {str(e)}")


async def _update_candidate_from_parsed(
    client: httpx.AsyncClient, candidate_id: str, parsed_data: Dict[str, Any]
) -> None:
    """Update candidate record with extracted info."""
    try:
        personal = parsed_data.get("personal", {})
        skills = parsed_data.get("skills", [])
        experience = parsed_data.get("experience", [])

        # Get current company/title from most recent experience
        current_company = ""
        current_title = ""
        if experience:
            for exp in experience:
                if exp.get("is_current"):
                    current_company = exp.get("company", "")
                    current_title = exp.get("title", "")
                    break
            if not current_company and experience:
                current_company = experience[0].get("company", "")
                current_title = experience[0].get("title", "")

        update_data = {
            "parsed_data": parsed_data,
            "skills_extracted": skills[:50],  # Limit to 50 skills
            "experience_years": parsed_data.get("total_years_experience"),
            "current_company": current_company,
            "current_title": current_title,
            "updated_at": datetime.now(timezone.utc).isoformat(),
        }

        # Only update if we have data
        if personal.get("linkedin_url"):
            update_data["linkedin_url"] = personal["linkedin_url"]

        response = await client.patch(
            f"{settings.supabase_url}/rest/v1/candidates",
            headers=_get_headers(),
            params={"id": f"eq.{candidate_id}"},
            json=update_data,
            timeout=30,
        )

        if response.status_code not in (200, 204):
            logger.warning(f"Failed to update candidate: {response.status_code}")
    except Exception as e:
        logger.error(f"Error updating candidate: {str(e)}")


async def parse_cover_letter(
    ctx: Dict[str, Any], application_id: str, cover_letter_text: str, tenant_id: str
) -> Dict[str, Any]:
    """
    Background task to parse a cover letter using LLM extraction.

    Extracts key insights like:
    - Why candidate is interested
    - Key qualifications mentioned
    - Salary expectations (if mentioned)
    - Availability
    """
    logger.info(f"Starting cover letter parsing for application_id={application_id}")

    result = {
        "application_id": application_id,
        "status": "pending",
        "parsed_data": None,
        "error": None,
    }

    openai_key = settings.openai_api_key if hasattr(settings, 'openai_api_key') else None

    if not openai_key:
        result["status"] = "skipped"
        result["error"] = "OpenAI API key not configured"
        return result

    try:
        cover_letter_prompt = """Analyze this cover letter and extract insights in JSON format:
{
  "motivation": "",          // Why they want this role
  "key_qualifications": [],  // Top qualifications they highlight
  "relevant_experience": "", // Most relevant experience mentioned
  "salary_expectation": null,// If mentioned
  "availability": "",        // Start date or notice period if mentioned
  "referral": "",           // If they mention a referral
  "tone": "",               // professional, enthusiastic, casual, etc.
  "red_flags": [],          // Any concerning statements
  "strengths": []           // Key strengths they emphasize
}

Cover letter:
{cover_letter_text}
"""

        async with httpx.AsyncClient() as client:
            response = await client.post(
                "https://api.openai.com/v1/chat/completions",
                headers={
                    "Authorization": f"Bearer {openai_key}",
                    "Content-Type": "application/json",
                },
                json={
                    "model": "gpt-4-turbo-preview",
                    "messages": [
                        {
                            "role": "system",
                            "content": "You are analyzing cover letters to extract key insights. Return valid JSON only."
                        },
                        {
                            "role": "user",
                            "content": cover_letter_prompt.format(cover_letter_text=cover_letter_text[:5000])
                        }
                    ],
                    "temperature": 0.1,
                    "max_tokens": 1000,
                    "response_format": {"type": "json_object"}
                },
                timeout=60,
            )

            if response.status_code != 200:
                result["status"] = "failed"
                result["error"] = f"OpenAI API error: {response.status_code}"
                return result

            parsed = json.loads(response.json()["choices"][0]["message"]["content"])

            # Update application with parsed cover letter data
            await client.patch(
                f"{settings.supabase_url}/rest/v1/applications",
                headers=_get_headers(),
                params={"id": f"eq.{application_id}"},
                json={
                    "cover_letter_parsed": parsed,
                    "updated_at": datetime.now(timezone.utc).isoformat(),
                },
                timeout=30,
            )

            result["status"] = "completed"
            result["parsed_data"] = parsed

    except Exception as e:
        logger.error(f"Cover letter parsing failed: {str(e)}")
        result["status"] = "failed"
        result["error"] = str(e)

    return result
