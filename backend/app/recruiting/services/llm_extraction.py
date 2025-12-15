"""LLM-based resume parsing service using OpenAI with model versioning and confidence scoring.

This service extracts structured facts from resumes with:
- Model/prompt versioning for reproducibility and debugging
- Confidence scores for each extracted fact
- Integration with observations system for provenance tracking
"""

import json
import os
import time
from dataclasses import dataclass
from datetime import datetime
from typing import Any, Optional
from uuid import UUID

from openai import AsyncOpenAI

# =============================================================================
# VERSION TRACKING
# =============================================================================

# Prompt versioning - increment when changing prompts
PROMPT_VERSION = "v2.1"  # Current extraction prompt version

# Model configuration
DEFAULT_MODEL = "gpt-4o-mini"
MODEL_VERSION = "2024-07-18"  # Model checkpoint date

# =============================================================================
# CONFIDENCE-AWARE EXTRACTION PROMPT
# =============================================================================

RESUME_EXTRACTION_PROMPT_V2 = """Extract structured facts from this resume with confidence scores.

For each extracted piece of information, provide a confidence score (0.0-1.0):
- 1.0: Explicitly stated, unambiguous (e.g., "Email: john@example.com")
- 0.95: Very clear, standard format (e.g., phone number in header)
- 0.80-0.94: Clearly implied (e.g., current title from "Currently at" section)
- 0.65-0.79: Inferred from context (e.g., years experience from date math)
- <0.65: Uncertain, may need verification (e.g., partial or ambiguous data)

Return ONLY valid JSON with this structure:

{
  "facts": [
    {"field": "full_name", "value": "John Doe", "confidence": 0.98},
    {"field": "email", "value": "john@example.com", "confidence": 1.0},
    {"field": "phone", "value": "+1-555-123-4567", "confidence": 0.95},
    {"field": "location", "value": "San Francisco, CA", "confidence": 0.85},
    {"field": "linkedin_url", "value": "linkedin.com/in/johndoe", "confidence": 0.98},
    {"field": "current_title", "value": "Senior Software Engineer", "confidence": 0.92},
    {"field": "current_company", "value": "Google", "confidence": 0.95},
    {"field": "years_experience", "value": "8", "confidence": 0.75},
    {"field": "skill", "value": "Python", "confidence": 0.90},
    {"field": "skill", "value": "Machine Learning", "confidence": 0.85},
    {"field": "education_degree", "value": "BS Computer Science", "confidence": 0.88},
    {"field": "education_institution", "value": "Stanford University", "confidence": 0.90},
    {"field": "certification", "value": "AWS Solutions Architect", "confidence": 0.92}
  ],
  "summary": "Professional summary text extracted from resume",
  "experience": [
    {
      "company": "Company Name",
      "title": "Job Title",
      "start_date": "2020-01",
      "end_date": "Present",
      "is_current": true,
      "description": "Role description",
      "confidence": 0.88
    }
  ],
  "education": [
    {
      "institution": "University Name",
      "degree": "Bachelor of Science",
      "field": "Computer Science",
      "graduation_date": "2015",
      "confidence": 0.85
    }
  ]
}

IMPORTANT:
- Extract ALL skills mentioned (each as separate fact with field="skill")
- Be conservative with confidence - if something is implied but not explicit, lower the score
- For years_experience, calculate from work history if not explicitly stated (lower confidence)
- Use null for missing values, don't guess

Resume text:
{resume_text}
"""

# Legacy prompt (kept for backwards compatibility)
RESUME_EXTRACTION_PROMPT = """Extract structured information from this resume text.
Return ONLY valid JSON with the following structure (use null for missing fields):

{
  "personal": {
    "full_name": "string or null",
    "email": "string or null",
    "phone": "string or null",
    "location": "city, state/country or null",
    "linkedin_url": "string or null"
  },
  "summary": "professional summary text or null",
  "experience": [
    {
      "company": "company name",
      "title": "job title",
      "start_date": "YYYY-MM or null",
      "end_date": "YYYY-MM or 'Present'",
      "is_current": true/false,
      "description": "role description",
      "achievements": ["achievement 1", "achievement 2"]
    }
  ],
  "education": [
    {
      "institution": "school name",
      "degree": "degree type",
      "field": "field of study",
      "graduation_date": "YYYY or null",
      "gpa": "GPA or null"
    }
  ],
  "skills": ["skill1", "skill2", "skill3"],
  "certifications": [
    {
      "name": "certification name",
      "issuer": "issuing organization",
      "date": "YYYY-MM or null"
    }
  ],
  "languages": ["English", "Spanish"],
  "total_years_experience": number or null
}

Resume text:
{resume_text}
"""


# =============================================================================
# DATA CLASSES
# =============================================================================

@dataclass
class ExtractedFact:
    """A single fact extracted from a document with provenance."""
    field: str
    value: str
    confidence: float
    extraction_method: str = "llm"
    model_name: Optional[str] = None
    model_version: Optional[str] = None
    prompt_version: Optional[str] = None


@dataclass
class ExtractionResult:
    """Complete result of LLM extraction with provenance."""
    facts: list[ExtractedFact]
    parsed_data: dict[str, Any]  # Legacy format for backwards compatibility
    model_name: str
    model_version: str
    prompt_version: str
    extraction_time_ms: int
    text_length: int
    was_truncated: bool
    error: Optional[str] = None


class LLMExtractionService:
    """Service for extracting structured data from resumes using LLM.

    Features:
    - Model/prompt versioning for reproducibility
    - Confidence scores for extracted facts
    - Integration with observations system
    - Backwards-compatible with legacy API
    """

    def __init__(self, api_key: Optional[str] = None, model: str = DEFAULT_MODEL):
        self.api_key = api_key or os.getenv("OPENAI_API_KEY")
        self.model = model
        self.model_version = MODEL_VERSION
        self.prompt_version = PROMPT_VERSION
        if self.api_key:
            self.client = AsyncOpenAI(api_key=self.api_key)
        else:
            self.client = None

    async def extract_with_confidence(
        self,
        resume_text: str,
        source_document_id: Optional[UUID] = None,
    ) -> ExtractionResult:
        """Extract structured facts from resume with confidence scores.

        This is the recommended method for new integrations.
        Returns facts with provenance for storing as observations.

        Args:
            resume_text: Plain text extracted from a resume
            source_document_id: UUID of the source document (resume)

        Returns:
            ExtractionResult with facts, confidence scores, and provenance
        """
        start_time = time.time()
        max_chars = 15000
        was_truncated = len(resume_text) > max_chars

        if not self.client:
            return ExtractionResult(
                facts=[],
                parsed_data={"error": "OpenAI API key not configured"},
                model_name=self.model,
                model_version=self.model_version,
                prompt_version=self.prompt_version,
                extraction_time_ms=0,
                text_length=len(resume_text) if resume_text else 0,
                was_truncated=was_truncated,
                error="OpenAI API key not configured",
            )

        if not resume_text or len(resume_text.strip()) < 50:
            return ExtractionResult(
                facts=[],
                parsed_data={"error": "Resume text too short or empty"},
                model_name=self.model,
                model_version=self.model_version,
                prompt_version=self.prompt_version,
                extraction_time_ms=0,
                text_length=len(resume_text) if resume_text else 0,
                was_truncated=False,
                error="Resume text too short or empty",
            )

        try:
            truncated_text = resume_text[:max_chars]
            if was_truncated:
                truncated_text += "\n\n[Text truncated...]"

            prompt = RESUME_EXTRACTION_PROMPT_V2.format(resume_text=truncated_text)

            response = await self.client.chat.completions.create(
                model=self.model,
                messages=[
                    {
                        "role": "system",
                        "content": "You are an expert resume parser. Extract structured information with confidence scores. Always return valid JSON.",
                    },
                    {"role": "user", "content": prompt},
                ],
                temperature=0.1,
                max_tokens=3000,
            )

            content = response.choices[0].message.content
            extraction_time_ms = int((time.time() - start_time) * 1000)

            # Parse JSON response
            if "```json" in content:
                content = content.split("```json")[1].split("```")[0]
            elif "```" in content:
                content = content.split("```")[1].split("```")[0]

            parsed_data = json.loads(content.strip())

            # Convert to ExtractedFact objects
            facts = []
            for fact_dict in parsed_data.get("facts", []):
                fact = ExtractedFact(
                    field=fact_dict.get("field", ""),
                    value=str(fact_dict.get("value", "")),
                    confidence=float(fact_dict.get("confidence", 0.5)),
                    extraction_method="llm",
                    model_name=self.model,
                    model_version=self.model_version,
                    prompt_version=self.prompt_version,
                )
                facts.append(fact)

            # Add provenance to parsed_data for backwards compatibility
            parsed_data["_extraction_metadata"] = {
                "model": self.model,
                "model_version": self.model_version,
                "prompt_version": self.prompt_version,
                "text_length": len(resume_text),
                "was_truncated": was_truncated,
                "extraction_time_ms": extraction_time_ms,
                "fact_count": len(facts),
            }

            return ExtractionResult(
                facts=facts,
                parsed_data=parsed_data,
                model_name=self.model,
                model_version=self.model_version,
                prompt_version=self.prompt_version,
                extraction_time_ms=extraction_time_ms,
                text_length=len(resume_text),
                was_truncated=was_truncated,
            )

        except json.JSONDecodeError as e:
            extraction_time_ms = int((time.time() - start_time) * 1000)
            return ExtractionResult(
                facts=[],
                parsed_data={"error": f"Failed to parse LLM response: {str(e)}"},
                model_name=self.model,
                model_version=self.model_version,
                prompt_version=self.prompt_version,
                extraction_time_ms=extraction_time_ms,
                text_length=len(resume_text),
                was_truncated=was_truncated,
                error=f"JSON parse error: {str(e)}",
            )
        except Exception as e:
            extraction_time_ms = int((time.time() - start_time) * 1000)
            return ExtractionResult(
                facts=[],
                parsed_data={"error": f"LLM extraction failed: {str(e)}"},
                model_name=self.model,
                model_version=self.model_version,
                prompt_version=self.prompt_version,
                extraction_time_ms=extraction_time_ms,
                text_length=len(resume_text),
                was_truncated=was_truncated,
                error=str(e),
            )

    def facts_to_observation_creates(
        self,
        extraction_result: ExtractionResult,
        source_document_id: Optional[UUID] = None,
    ) -> list[dict]:
        """Convert ExtractedFacts to ObservationCreate-compatible dicts.

        Use this to store extracted facts as observations with full provenance.

        Args:
            extraction_result: Result from extract_with_confidence()
            source_document_id: UUID of the source resume

        Returns:
            List of dicts ready for ObservationCreate schema
        """
        observations = []
        for fact in extraction_result.facts:
            # Determine value_type based on field
            value_type = "string"
            if fact.field in ["years_experience"]:
                value_type = "number"
            elif fact.field in ["skill", "certification"]:
                value_type = "string"  # Each skill is stored as separate observation

            obs = {
                "field_name": fact.field,
                "field_value": fact.value,
                "value_type": value_type,
                "confidence": fact.confidence,
                "extraction_method": "llm",
                "source_document_id": str(source_document_id) if source_document_id else None,
                # Model provenance stored in observations table
                # will be added by observation_service
            }
            observations.append(obs)

        return observations

    async def parse_resume(self, resume_text: str) -> dict:
        """Parse resume text using OpenAI GPT-4.

        LEGACY METHOD - Use extract_with_confidence() for new integrations.

        Args:
            resume_text: Plain text extracted from a resume

        Returns:
            Structured resume data as a dictionary
        """
        if not self.client:
            return {
                "error": "OpenAI API key not configured",
                "raw_text": resume_text[:1000] if resume_text else None,
            }

        if not resume_text or len(resume_text.strip()) < 50:
            return {
                "error": "Resume text too short or empty",
                "raw_text": resume_text,
            }

        try:
            # Truncate very long resumes to avoid token limits
            max_chars = 15000
            truncated_text = resume_text[:max_chars]
            if len(resume_text) > max_chars:
                truncated_text += "\n\n[Text truncated...]"

            prompt = RESUME_EXTRACTION_PROMPT.format(resume_text=truncated_text)

            response = await self.client.chat.completions.create(
                model=self.model,
                messages=[
                    {
                        "role": "system",
                        "content": "You are a resume parser. Extract structured information from resumes. Always return valid JSON.",
                    },
                    {"role": "user", "content": prompt},
                ],
                temperature=0.1,
                max_tokens=2000,
            )

            content = response.choices[0].message.content

            # Try to parse the JSON response
            # Handle potential markdown code blocks
            if "```json" in content:
                content = content.split("```json")[1].split("```")[0]
            elif "```" in content:
                content = content.split("```")[1].split("```")[0]

            parsed_data = json.loads(content.strip())

            # Add metadata about the extraction
            parsed_data["_extraction_metadata"] = {
                "model": self.model,
                "model_version": self.model_version,
                "prompt_version": self.prompt_version,
                "text_length": len(resume_text),
                "was_truncated": len(resume_text) > max_chars,
            }

            return parsed_data

        except json.JSONDecodeError as e:
            return {
                "error": f"Failed to parse LLM response as JSON: {str(e)}",
                "raw_response": content if "content" in dir() else None,
            }
        except Exception as e:
            return {
                "error": f"LLM extraction failed: {str(e)}",
            }

    async def extract_skills(self, resume_text: str) -> list:
        """Extract just the skills from a resume.

        Args:
            resume_text: Plain text from resume

        Returns:
            List of extracted skills
        """
        parsed = await self.parse_resume(resume_text)
        return parsed.get("skills", [])

    async def extract_skills_with_confidence(self, resume_text: str) -> list[dict]:
        """Extract skills with confidence scores.

        Args:
            resume_text: Plain text from resume

        Returns:
            List of {skill, confidence} dicts
        """
        result = await self.extract_with_confidence(resume_text)
        skills = []
        for fact in result.facts:
            if fact.field == "skill":
                skills.append({
                    "skill": fact.value,
                    "confidence": fact.confidence,
                })
        return skills

    async def calculate_experience_years(self, parsed_data: dict) -> Optional[float]:
        """Calculate total years of experience from parsed resume data.

        Args:
            parsed_data: Parsed resume dictionary

        Returns:
            Total years of experience or None
        """
        if "total_years_experience" in parsed_data and parsed_data["total_years_experience"]:
            return parsed_data["total_years_experience"]

        # Try to calculate from experience entries
        experience = parsed_data.get("experience", [])
        if not experience:
            return None

        total_months = 0
        for exp in experience:
            start = exp.get("start_date")
            end = exp.get("end_date")

            if not start:
                continue

            try:
                # Parse start date
                if len(start) == 4:
                    start_date = datetime(int(start), 1, 1)
                else:
                    parts = start.split("-")
                    start_date = datetime(int(parts[0]), int(parts[1]) if len(parts) > 1 else 1, 1)

                # Parse end date
                if end and end.lower() != "present":
                    if len(end) == 4:
                        end_date = datetime(int(end), 12, 31)
                    else:
                        parts = end.split("-")
                        end_date = datetime(int(parts[0]), int(parts[1]) if len(parts) > 1 else 12, 28)
                else:
                    end_date = datetime.now()

                months = (end_date.year - start_date.year) * 12 + (end_date.month - start_date.month)
                total_months += max(0, months)

            except (ValueError, IndexError):
                continue

        if total_months > 0:
            return round(total_months / 12, 1)

        return None

    @staticmethod
    def get_confidence_label(confidence: float) -> str:
        """Get human-readable confidence label.

        Matches frontend confidence interpretation:
        - Explicit: 0.95+ (explicitly stated in document)
        - Very Likely: 0.80-0.94 (clearly implied or standard format)
        - Inferred: 0.65-0.79 (inferred from context)
        - Uncertain: <0.65 (may need verification)
        """
        if confidence >= 0.95:
            return "Explicit"
        elif confidence >= 0.80:
            return "Very Likely"
        elif confidence >= 0.65:
            return "Inferred"
        else:
            return "Uncertain"


# Singleton instance
_llm_service: Optional[LLMExtractionService] = None


def get_llm_service() -> LLMExtractionService:
    """Get or create the LLM extraction service singleton."""
    global _llm_service
    if _llm_service is None:
        _llm_service = LLMExtractionService()
    return _llm_service
