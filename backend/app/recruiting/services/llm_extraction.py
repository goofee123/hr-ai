"""LLM-based resume parsing service using OpenAI."""

import json
import os
from typing import Optional

from openai import AsyncOpenAI

# Resume extraction prompt
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


class LLMExtractionService:
    """Service for extracting structured data from resumes using LLM."""

    def __init__(self, api_key: Optional[str] = None):
        self.api_key = api_key or os.getenv("OPENAI_API_KEY")
        if self.api_key:
            self.client = AsyncOpenAI(api_key=self.api_key)
        else:
            self.client = None

    async def parse_resume(self, resume_text: str) -> dict:
        """Parse resume text using OpenAI GPT-4.

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
                model="gpt-4o-mini",  # Use cost-effective model
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
                "model": "gpt-4o-mini",
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

        from datetime import datetime

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


# Singleton instance
_llm_service: Optional[LLMExtractionService] = None


def get_llm_service() -> LLMExtractionService:
    """Get or create the LLM extraction service singleton."""
    global _llm_service
    if _llm_service is None:
        _llm_service = LLMExtractionService()
    return _llm_service
