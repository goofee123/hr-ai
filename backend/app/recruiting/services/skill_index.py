"""Skill Index Service - Recency-Aware Skill Tracking.

This service implements a temporal, semantic, and context-aware skill tracking system.

Key Concepts:
1. Skill Recency - How recently was the skill used? (decay over time)
2. Skill Depth - How many years of experience? How many roles used it?
3. Skill Context - Was it mentioned in education, a job, or just listed?
4. Skill Freshness Weight - Higher weight for skills used in recent roles

This avoids the "keyword soup" problem where a skill mentioned once 10 years ago
is treated the same as a current daily-use technology.
"""

import logging
import math
from dataclasses import dataclass, field
from datetime import datetime, date
from enum import Enum
from typing import Any, Dict, List, Optional, Tuple
from uuid import UUID

from app.core.supabase_client import get_supabase_client

logger = logging.getLogger(__name__)


class SkillSource(Enum):
    """Where the skill was mentioned."""
    CURRENT_JOB = "current_job"        # Highest confidence - actively using
    RECENT_JOB = "recent_job"          # Last 3 years
    PAST_JOB = "past_job"              # 3-7 years ago
    LEGACY_JOB = "legacy_job"          # 7+ years ago
    EDUCATION = "education"            # Academic only - lower weight
    CERTIFICATION = "certification"    # Has certification
    LISTED_ONLY = "listed_only"        # Just listed in skills section, not job-backed


class SkillConfidence(Enum):
    """How confident we are in the skill assessment."""
    VERIFIED = "verified"              # Multiple jobs, recent use
    STRONG = "strong"                  # At least one job with multiple mentions
    MODERATE = "moderate"              # Mentioned in job(s) but not emphasized
    WEAK = "weak"                      # Listed but no job context
    STALE = "stale"                    # Not used in 5+ years


@dataclass
class SkillRecord:
    """A single skill with recency and depth metadata."""
    skill_name: str
    normalized_name: str               # Lowercase, standardized (e.g., "ReactJS" -> "react")
    last_used_date: Optional[date]     # Most recent use
    first_used_date: Optional[date]    # Earliest use
    years_experience: float            # Total years using this skill
    job_count: int                     # Number of jobs that used this skill
    source: SkillSource                # Where it's primarily from
    confidence: SkillConfidence        # How confident we are
    recency_weight: float              # 0.0 to 1.0 - decays over time
    depth_weight: float                # 0.0 to 1.0 - based on years + job count
    final_weight: float                # Combined score for matching
    source_details: List[str] = field(default_factory=list)  # Company names where used


@dataclass
class CandidateSkillProfile:
    """Complete skill profile for a candidate."""
    candidate_id: UUID
    skills: List[SkillRecord]
    profile_updated_at: datetime
    resume_version: int
    current_level: str                 # intern, entry, mid, senior, lead, etc.
    total_experience_years: float
    current_skills: List[str]          # Skills from current/latest role
    trending_up: List[str]             # Skills gaining depth
    stale_skills: List[str]            # Skills not used recently


class SkillNormalizer:
    """Normalize skill names to canonical forms."""

    # Common aliases and variations
    SKILL_ALIASES = {
        # JavaScript variations
        "javascript": ["js", "ecmascript", "es6", "es2015", "es2020"],
        "typescript": ["ts"],
        "react": ["reactjs", "react.js", "react js"],
        "vue": ["vuejs", "vue.js", "vue 3"],
        "angular": ["angularjs", "angular.js", "angular 2", "angular 14"],
        "node": ["nodejs", "node.js", "node js"],
        "express": ["expressjs", "express.js"],

        # Python variations
        "python": ["python3", "python 3", "py"],
        "django": ["django framework"],
        "flask": ["flask framework"],
        "fastapi": ["fast api", "fast-api"],

        # Data Science
        "machine learning": ["ml", "machine-learning"],
        "deep learning": ["dl", "deep-learning"],
        "natural language processing": ["nlp"],
        "computer vision": ["cv", "image recognition"],
        "tensorflow": ["tf", "tensorflow 2"],
        "pytorch": ["torch"],

        # Cloud
        "amazon web services": ["aws", "amazon aws"],
        "google cloud platform": ["gcp", "google cloud"],
        "microsoft azure": ["azure", "ms azure"],
        "kubernetes": ["k8s", "kube"],
        "docker": ["docker containers", "containerization"],

        # Databases
        "postgresql": ["postgres", "psql"],
        "mongodb": ["mongo"],
        "mysql": ["my sql"],
        "redis": ["redis cache"],
        "elasticsearch": ["elastic", "elastic search", "es"],

        # DevOps
        "continuous integration": ["ci", "ci/cd", "cicd"],
        "infrastructure as code": ["iac"],
        "terraform": ["tf", "hashicorp terraform"],

        # Languages
        "c++": ["cpp", "cplusplus"],
        "c#": ["csharp", "c sharp"],
        "golang": ["go", "go lang"],
        "ruby on rails": ["rails", "ror"],

        # Soft skills
        "project management": ["pm", "project mgmt"],
        "agile methodology": ["agile", "scrum", "kanban"],
    }

    # Build reverse lookup
    _REVERSE_ALIASES: Dict[str, str] = {}
    for canonical, aliases in SKILL_ALIASES.items():
        _REVERSE_ALIASES[canonical.lower()] = canonical
        for alias in aliases:
            _REVERSE_ALIASES[alias.lower()] = canonical

    @classmethod
    def normalize(cls, skill: str) -> str:
        """Normalize a skill name to its canonical form."""
        skill_lower = skill.lower().strip()

        # Check direct alias match
        if skill_lower in cls._REVERSE_ALIASES:
            return cls._REVERSE_ALIASES[skill_lower]

        # Return lowercased original if no alias found
        return skill_lower


class SkillRecencyCalculator:
    """Calculate skill recency weights using decay function."""

    # Decay constants
    HALF_LIFE_YEARS = 3.0      # Skill loses half its weight every 3 years
    MIN_WEIGHT = 0.05          # Minimum weight for very old skills
    EDUCATION_PENALTY = 0.3    # Education-only skills get 30% weight
    LISTED_ONLY_PENALTY = 0.2  # Skills just listed get 20% weight

    @classmethod
    def calculate_recency_weight(
        cls,
        last_used: Optional[date],
        source: SkillSource,
        reference_date: Optional[date] = None,
    ) -> float:
        """Calculate recency weight using exponential decay.

        Formula: weight = max(MIN_WEIGHT, e^(-lambda * years_ago))
        where lambda = ln(2) / HALF_LIFE_YEARS
        """
        if reference_date is None:
            reference_date = date.today()

        # Base penalties for non-job sources
        if source == SkillSource.EDUCATION:
            return cls.EDUCATION_PENALTY
        if source == SkillSource.LISTED_ONLY:
            return cls.LISTED_ONLY_PENALTY

        # Current job is always 1.0
        if source == SkillSource.CURRENT_JOB:
            return 1.0

        if not last_used:
            return cls.LISTED_ONLY_PENALTY

        # Calculate years since last use
        years_ago = (reference_date - last_used).days / 365.25

        if years_ago <= 0:
            return 1.0

        # Exponential decay
        decay_rate = math.log(2) / cls.HALF_LIFE_YEARS
        weight = math.exp(-decay_rate * years_ago)

        return max(cls.MIN_WEIGHT, weight)

    @classmethod
    def calculate_depth_weight(
        cls,
        years_experience: float,
        job_count: int,
    ) -> float:
        """Calculate depth weight based on experience.

        Considers both total years and number of different roles.
        """
        # Years component: logarithmic growth, caps at ~10 years
        years_weight = min(1.0, math.log1p(years_experience) / math.log1p(10))

        # Job count component: having it in multiple roles = more confidence
        job_weight = min(1.0, job_count / 3.0)  # 3+ jobs = max weight

        # Combined: average with slight preference for years
        return (years_weight * 0.6 + job_weight * 0.4)


class SkillIndexService:
    """Service for building and querying skill indexes."""

    def __init__(self):
        self.client = get_supabase_client()
        self.normalizer = SkillNormalizer()
        self.recency_calc = SkillRecencyCalculator()

    def extract_skills_from_parsed_resume(
        self,
        parsed_data: Dict[str, Any],
        resume_date: Optional[date] = None,
    ) -> List[SkillRecord]:
        """Extract skills with recency info from parsed resume data.

        Expected parsed_data structure:
        {
            "experience": [
                {
                    "company": "...",
                    "title": "...",
                    "start_date": "2022-01",
                    "end_date": "2024-06" or null for current,
                    "technologies_used": ["Python", "FastAPI", ...],
                    "responsibilities": "..."
                }
            ],
            "education": [...],
            "certifications": [...],
            "skills": {
                "current": [...],
                "proficient": [...],
                "familiar": [...],
                "outdated": [...]
            },
            "current_level": "senior"
        }
        """
        reference_date = resume_date or date.today()
        skill_data: Dict[str, Dict] = {}  # normalized_name -> accumulated data

        # 1. Extract skills from each job experience
        for exp in parsed_data.get("experience", []):
            start_date = self._parse_date(exp.get("start_date"))
            end_date = self._parse_date(exp.get("end_date"))
            is_current = end_date is None or end_date >= reference_date

            # Calculate years in this role
            if start_date:
                end = end_date or reference_date
                years_in_role = max(0, (end - start_date).days / 365.25)
            else:
                years_in_role = 0

            # Determine source type
            if is_current:
                source = SkillSource.CURRENT_JOB
            elif end_date and (reference_date - end_date).days <= 3 * 365:
                source = SkillSource.RECENT_JOB
            elif end_date and (reference_date - end_date).days <= 7 * 365:
                source = SkillSource.PAST_JOB
            else:
                source = SkillSource.LEGACY_JOB

            # Get technologies used in this role
            technologies = exp.get("technologies_used", [])

            # Also extract skills from responsibilities text
            responsibilities = exp.get("responsibilities", "") or ""
            extracted_skills = self._extract_skills_from_text(responsibilities)
            technologies.extend(extracted_skills)

            # Process each skill
            for skill in technologies:
                normalized = self.normalizer.normalize(skill)

                if normalized not in skill_data:
                    skill_data[normalized] = {
                        "original_names": set(),
                        "last_used": None,
                        "first_used": None,
                        "total_years": 0,
                        "jobs": set(),
                        "best_source": source,
                        "source_details": [],
                    }

                data = skill_data[normalized]
                data["original_names"].add(skill)
                data["jobs"].add(exp.get("company", "Unknown"))
                data["source_details"].append(exp.get("company", "Unknown"))
                data["total_years"] += years_in_role

                # Track dates
                if end_date:
                    if not data["last_used"] or end_date > data["last_used"]:
                        data["last_used"] = end_date
                elif is_current:
                    data["last_used"] = reference_date

                if start_date:
                    if not data["first_used"] or start_date < data["first_used"]:
                        data["first_used"] = start_date

                # Upgrade source if current job
                if source == SkillSource.CURRENT_JOB:
                    data["best_source"] = SkillSource.CURRENT_JOB
                elif source.value < data["best_source"].value:
                    data["best_source"] = source

        # 2. Add skills from skills section (with lower weight if not job-backed)
        skills_section = parsed_data.get("skills", {})
        if isinstance(skills_section, list):
            # Flat list format
            for skill in skills_section:
                normalized = self.normalizer.normalize(skill)
                if normalized not in skill_data:
                    skill_data[normalized] = {
                        "original_names": {skill},
                        "last_used": None,
                        "first_used": None,
                        "total_years": 0,
                        "jobs": set(),
                        "best_source": SkillSource.LISTED_ONLY,
                        "source_details": [],
                    }
        elif isinstance(skills_section, dict):
            # Categorized format
            for category, skills in skills_section.items():
                for skill in (skills or []):
                    normalized = self.normalizer.normalize(skill)
                    if normalized not in skill_data:
                        # Determine source based on category
                        if category == "current":
                            source = SkillSource.CURRENT_JOB
                        elif category == "proficient":
                            source = SkillSource.RECENT_JOB
                        elif category == "familiar":
                            source = SkillSource.PAST_JOB
                        else:  # outdated
                            source = SkillSource.LEGACY_JOB

                        skill_data[normalized] = {
                            "original_names": {skill},
                            "last_used": None,
                            "first_used": None,
                            "total_years": 0,
                            "jobs": set(),
                            "best_source": source,
                            "source_details": [],
                        }

        # 3. Add certifications as skills
        for cert in parsed_data.get("certifications", []):
            cert_name = cert.get("name", "") if isinstance(cert, dict) else cert
            if cert_name:
                normalized = self.normalizer.normalize(cert_name)
                if normalized not in skill_data:
                    skill_data[normalized] = {
                        "original_names": {cert_name},
                        "last_used": None,
                        "first_used": None,
                        "total_years": 0,
                        "jobs": set(),
                        "best_source": SkillSource.CERTIFICATION,
                        "source_details": ["Certification"],
                    }

        # 4. Build SkillRecord objects with weights
        records = []
        for normalized, data in skill_data.items():
            recency_weight = self.recency_calc.calculate_recency_weight(
                data["last_used"],
                data["best_source"],
                reference_date,
            )

            depth_weight = self.recency_calc.calculate_depth_weight(
                data["total_years"],
                len(data["jobs"]),
            )

            # Final weight: geometric mean of recency and depth
            final_weight = math.sqrt(recency_weight * depth_weight) if depth_weight > 0 else recency_weight * 0.5

            # Determine confidence
            if data["best_source"] == SkillSource.CURRENT_JOB and len(data["jobs"]) >= 2:
                confidence = SkillConfidence.VERIFIED
            elif len(data["jobs"]) >= 1 and recency_weight > 0.5:
                confidence = SkillConfidence.STRONG
            elif len(data["jobs"]) >= 1:
                confidence = SkillConfidence.MODERATE
            elif recency_weight < 0.2:
                confidence = SkillConfidence.STALE
            else:
                confidence = SkillConfidence.WEAK

            records.append(SkillRecord(
                skill_name=list(data["original_names"])[0],
                normalized_name=normalized,
                last_used_date=data["last_used"],
                first_used_date=data["first_used"],
                years_experience=data["total_years"],
                job_count=len(data["jobs"]),
                source=data["best_source"],
                confidence=confidence,
                recency_weight=round(recency_weight, 3),
                depth_weight=round(depth_weight, 3),
                final_weight=round(final_weight, 3),
                source_details=data["source_details"][:5],  # Top 5 companies
            ))

        # Sort by final weight descending
        records.sort(key=lambda x: x.final_weight, reverse=True)

        return records

    def build_candidate_skill_profile(
        self,
        candidate_id: UUID,
        parsed_data: Dict[str, Any],
        resume_version: int = 1,
    ) -> CandidateSkillProfile:
        """Build a complete skill profile for a candidate."""
        skills = self.extract_skills_from_parsed_resume(parsed_data)

        # Categorize skills
        current_skills = [
            s.normalized_name for s in skills
            if s.source == SkillSource.CURRENT_JOB
        ]

        stale_skills = [
            s.normalized_name for s in skills
            if s.confidence == SkillConfidence.STALE
        ]

        # Trending up = multiple jobs + recent use
        trending_up = [
            s.normalized_name for s in skills
            if s.job_count >= 2 and s.recency_weight > 0.7
        ]

        # Calculate total experience
        experience = parsed_data.get("experience", [])
        total_years = 0
        for exp in experience:
            # Skip internships for total experience calculation
            title = (exp.get("title") or "").lower()
            if "intern" in title:
                continue

            start = self._parse_date(exp.get("start_date"))
            end = self._parse_date(exp.get("end_date")) or date.today()
            if start:
                total_years += max(0, (end - start).days / 365.25)

        return CandidateSkillProfile(
            candidate_id=candidate_id,
            skills=skills,
            profile_updated_at=datetime.now(),
            resume_version=resume_version,
            current_level=parsed_data.get("current_level", "unknown"),
            total_experience_years=round(total_years, 1),
            current_skills=current_skills,
            trending_up=trending_up,
            stale_skills=stale_skills,
        )

    def _parse_date(self, date_str: Optional[str]) -> Optional[date]:
        """Parse a date string in various formats."""
        if not date_str:
            return None

        formats = [
            "%Y-%m-%d",
            "%Y-%m",
            "%m/%Y",
            "%Y",
        ]

        for fmt in formats:
            try:
                return datetime.strptime(date_str, fmt).date()
            except ValueError:
                continue

        return None

    def _extract_skills_from_text(self, text: str) -> List[str]:
        """Extract potential skills from free text.

        This is a simple keyword extraction - in production you'd want
        NER or a more sophisticated approach.
        """
        # Common tech keywords to look for
        keywords = {
            "python", "java", "javascript", "typescript", "react", "angular", "vue",
            "node", "django", "flask", "spring", "aws", "azure", "gcp", "docker",
            "kubernetes", "terraform", "sql", "postgresql", "mongodb", "redis",
            "elasticsearch", "kafka", "rabbitmq", "graphql", "rest", "api",
            "microservices", "machine learning", "deep learning", "pytorch",
            "tensorflow", "pandas", "numpy", "scikit-learn", "spark", "hadoop",
        }

        text_lower = text.lower()
        found = []

        for keyword in keywords:
            if keyword in text_lower:
                found.append(keyword)

        return found

    def calculate_job_match_score(
        self,
        candidate_profile: CandidateSkillProfile,
        job_requirements: List[str],
        job_nice_to_haves: Optional[List[str]] = None,
        require_recent: bool = True,
    ) -> Tuple[float, Dict[str, Any]]:
        """Calculate match score between candidate skills and job requirements.

        Args:
            candidate_profile: Candidate's skill profile
            job_requirements: Required skills for the job
            job_nice_to_haves: Optional nice-to-have skills
            require_recent: If True, penalize stale skills even if present

        Returns:
            (score, breakdown) where score is 0.0-1.0 and breakdown shows details
        """
        # Build candidate skill lookup
        candidate_skills = {s.normalized_name: s for s in candidate_profile.skills}

        # Analyze required skills
        required_matches = []
        required_missing = []
        required_stale = []

        for req in job_requirements:
            req_normalized = self.normalizer.normalize(req)
            if req_normalized in candidate_skills:
                skill = candidate_skills[req_normalized]
                if require_recent and skill.confidence == SkillConfidence.STALE:
                    required_stale.append({
                        "skill": req,
                        "last_used": str(skill.last_used_date) if skill.last_used_date else "unknown",
                        "weight": skill.final_weight,
                    })
                else:
                    required_matches.append({
                        "skill": req,
                        "years_experience": skill.years_experience,
                        "recency_weight": skill.recency_weight,
                        "confidence": skill.confidence.value,
                    })
            else:
                required_missing.append(req)

        # Analyze nice-to-have skills
        nice_matches = []
        if job_nice_to_haves:
            for nice in job_nice_to_haves:
                nice_normalized = self.normalizer.normalize(nice)
                if nice_normalized in candidate_skills:
                    skill = candidate_skills[nice_normalized]
                    nice_matches.append({
                        "skill": nice,
                        "weight": skill.final_weight,
                    })

        # Calculate scores
        required_count = len(job_requirements)
        if required_count == 0:
            required_score = 1.0
        else:
            # Weight matches by their recency
            weighted_matches = sum(
                candidate_skills[self.normalizer.normalize(m["skill"])].final_weight
                for m in required_matches
            )
            # Stale skills get partial credit
            stale_credit = len(required_stale) * 0.3
            required_score = (weighted_matches + stale_credit) / required_count

        nice_count = len(job_nice_to_haves or [])
        if nice_count == 0:
            nice_score = 0
        else:
            nice_score = sum(m["weight"] for m in nice_matches) / nice_count

        # Combined score: 80% required, 20% nice-to-have
        final_score = required_score * 0.8 + nice_score * 0.2

        breakdown = {
            "final_score": round(final_score, 3),
            "required_score": round(required_score, 3),
            "nice_to_have_score": round(nice_score, 3),
            "required_skills": {
                "matched": required_matches,
                "missing": required_missing,
                "stale": required_stale,
            },
            "nice_to_have_matched": nice_matches,
            "candidate_level": candidate_profile.current_level,
            "total_experience_years": candidate_profile.total_experience_years,
            "current_skills": candidate_profile.current_skills[:10],
        }

        return final_score, breakdown

    def get_top_skill_recommendations(
        self,
        candidate_profile: CandidateSkillProfile,
        limit: int = 5,
    ) -> List[Dict[str, Any]]:
        """Get top recommended skills to highlight for a candidate.

        Returns skills that are:
        1. Current and verified
        2. Have high depth
        3. Are in demand (common in job postings)
        """
        # In-demand skills (would come from job market analysis in production)
        in_demand = {
            "python", "javascript", "typescript", "react", "node",
            "aws", "kubernetes", "docker", "sql", "postgresql",
            "machine learning", "deep learning", "fastapi", "golang",
        }

        recommendations = []

        for skill in candidate_profile.skills[:20]:  # Top 20 by weight
            is_in_demand = skill.normalized_name in in_demand

            if skill.final_weight >= 0.5 and (is_in_demand or skill.job_count >= 2):
                recommendations.append({
                    "skill": skill.skill_name,
                    "normalized": skill.normalized_name,
                    "years": skill.years_experience,
                    "recency": skill.recency_weight,
                    "confidence": skill.confidence.value,
                    "is_in_demand": is_in_demand,
                    "companies_used": skill.source_details[:3],
                })

            if len(recommendations) >= limit:
                break

        return recommendations


# Singleton instance
skill_index_service = SkillIndexService()
