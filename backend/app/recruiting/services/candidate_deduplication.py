"""Candidate Deduplication Service.

Enterprise-grade deduplication that handles:
1. Same email - exact match (primary identifier)
2. Same phone number - fuzzy match
3. Same name + LinkedIn - probabilistic match
4. Resume update scenarios - person reapplying years later
5. Name changes (marriage, etc.) - handled via email as anchor
6. Email address changes - handled via phone/LinkedIn as secondary anchors

Deduplication Strategy:
- Email is the GOLD STANDARD identifier
- Phone is SILVER (secondary, with normalization)
- LinkedIn URL is BRONZE (tertiary, with URL normalization)
- Name + Experience fingerprint is LAST RESORT (probabilistic)
"""

import logging
import re
from dataclasses import dataclass
from datetime import datetime
from enum import Enum
from typing import Any, Dict, List, Optional, Tuple
from uuid import UUID

from app.core.supabase_client import get_supabase_client

logger = logging.getLogger(__name__)


class MatchConfidence(Enum):
    """Match confidence levels."""
    EXACT = "exact"           # 100% certain - same email
    HIGH = "high"             # 95%+ - same phone or LinkedIn
    MEDIUM = "medium"         # 80%+ - same name + company history
    LOW = "low"               # 60%+ - similar name + overlapping skills
    NONE = "none"             # No match found


@dataclass
class DeduplicationResult:
    """Result of deduplication check."""
    is_duplicate: bool
    existing_candidate_id: Optional[UUID]
    confidence: MatchConfidence
    match_reasons: List[str]
    suggested_action: str  # 'create_new', 'update_existing', 'merge_required', 'review_required'
    profile_changes: Optional[Dict[str, Any]] = None  # What changed if updating


@dataclass
class CandidateFingerprint:
    """Unique identifier components for a candidate."""
    email: Optional[str]
    phone_normalized: Optional[str]
    linkedin_normalized: Optional[str]
    name_normalized: str
    experience_fingerprint: Optional[str]  # Hash of company names + titles


class CandidateDeduplicationService:
    """Service for detecting and handling duplicate candidates."""

    def __init__(self):
        self.client = get_supabase_client()

    @staticmethod
    def normalize_email(email: Optional[str]) -> Optional[str]:
        """Normalize email for comparison.

        Handles:
        - Case normalization
        - Gmail dot trick (john.doe@gmail.com == johndoe@gmail.com)
        - Plus addressing (john+newsletter@gmail.com == john@gmail.com)
        """
        if not email:
            return None

        email = email.lower().strip()

        # Handle Gmail-specific normalizations
        if "@gmail.com" in email or "@googlemail.com" in email:
            local, domain = email.split("@")
            # Remove dots from local part
            local = local.replace(".", "")
            # Remove plus addressing
            if "+" in local:
                local = local.split("+")[0]
            # Normalize googlemail to gmail
            domain = "gmail.com"
            email = f"{local}@{domain}"

        return email

    @staticmethod
    def normalize_phone(phone: Optional[str]) -> Optional[str]:
        """Normalize phone number for comparison.

        Strips all non-numeric characters, normalizes country code.
        Returns last 10 digits for US numbers.
        """
        if not phone:
            return None

        # Remove all non-numeric characters
        digits = re.sub(r'\D', '', phone)

        if not digits:
            return None

        # Handle US numbers - normalize to last 10 digits
        if len(digits) >= 10:
            # Remove leading 1 for US country code
            if len(digits) == 11 and digits.startswith('1'):
                digits = digits[1:]
            # Take last 10 digits
            return digits[-10:]

        return digits

    @staticmethod
    def normalize_linkedin(url: Optional[str]) -> Optional[str]:
        """Normalize LinkedIn URL.

        Extracts the profile slug from various URL formats:
        - https://www.linkedin.com/in/johndoe
        - https://linkedin.com/in/johndoe/
        - linkedin.com/in/johndoe
        """
        if not url:
            return None

        url = url.lower().strip()

        # Extract profile slug using regex
        patterns = [
            r'linkedin\.com/in/([a-zA-Z0-9\-_]+)',
            r'linkedin\.com/pub/([a-zA-Z0-9\-_/]+)',
        ]

        for pattern in patterns:
            match = re.search(pattern, url)
            if match:
                return match.group(1).rstrip('/')

        return None

    @staticmethod
    def normalize_name(first_name: str, last_name: str) -> str:
        """Normalize name for comparison.

        Handles:
        - Case normalization
        - Common nickname mappings (Will -> William, Bob -> Robert)
        - Removal of suffixes (Jr., III, etc.)
        """
        # Common nickname mappings
        nicknames = {
            'will': 'william',
            'bill': 'william',
            'bob': 'robert',
            'rob': 'robert',
            'bobby': 'robert',
            'dick': 'richard',
            'rich': 'richard',
            'rick': 'richard',
            'mike': 'michael',
            'mick': 'michael',
            'jim': 'james',
            'jimmy': 'james',
            'jamie': 'james',
            'joe': 'joseph',
            'joey': 'joseph',
            'dave': 'david',
            'dan': 'daniel',
            'danny': 'daniel',
            'tom': 'thomas',
            'tommy': 'thomas',
            'tony': 'anthony',
            'ed': 'edward',
            'eddie': 'edward',
            'ted': 'edward',
            'teddy': 'edward',
            'chris': 'christopher',
            'matt': 'matthew',
            'nick': 'nicholas',
            'alex': 'alexander',
            'jen': 'jennifer',
            'jenny': 'jennifer',
            'kate': 'katherine',
            'katie': 'katherine',
            'kathy': 'katherine',
            'liz': 'elizabeth',
            'beth': 'elizabeth',
            'betty': 'elizabeth',
            'sue': 'susan',
            'suzy': 'susan',
            'meg': 'margaret',
            'maggie': 'margaret',
            'peggy': 'margaret',
            'sam': 'samuel',
            'sammy': 'samuel',
            'samantha': 'samantha',  # Keep as is
            'pat': 'patricia',
            'patty': 'patricia',
            'jo': 'josephine',
        }

        # Suffixes to remove
        suffixes = ['jr', 'jr.', 'sr', 'sr.', 'ii', 'iii', 'iv', 'v', 'esq', 'esq.', 'phd', 'md', 'dds']

        first = first_name.lower().strip()
        last = last_name.lower().strip()

        # Normalize nickname
        first = nicknames.get(first, first)

        # Remove suffixes from last name
        last_parts = last.split()
        last_parts = [p for p in last_parts if p.lower() not in suffixes]
        last = ' '.join(last_parts)

        return f"{first}|{last}"

    @staticmethod
    def create_experience_fingerprint(experience: List[Dict]) -> Optional[str]:
        """Create a fingerprint from work experience.

        Used as a last-resort matching when email/phone differ.
        """
        if not experience:
            return None

        # Extract company names and titles, normalize
        fingerprint_parts = []
        for exp in experience[:5]:  # Top 5 most recent
            company = exp.get('company', '').lower().strip()
            title = exp.get('title', '').lower().strip()
            if company:
                # Remove common suffixes
                company = re.sub(r'\s+(inc|llc|ltd|corp|corporation|company|co)\.?$', '', company)
                fingerprint_parts.append(f"{company}:{title}")

        if not fingerprint_parts:
            return None

        # Sort for consistent ordering
        fingerprint_parts.sort()
        return '|'.join(fingerprint_parts)

    async def find_duplicates(
        self,
        tenant_id: UUID,
        email: Optional[str],
        phone: Optional[str] = None,
        linkedin_url: Optional[str] = None,
        first_name: str = "",
        last_name: str = "",
        parsed_experience: Optional[List[Dict]] = None,
        exclude_candidate_id: Optional[UUID] = None,
    ) -> DeduplicationResult:
        """Find potential duplicate candidates.

        Returns the best match if found, with confidence level and suggested action.
        """
        matches: List[Tuple[Dict, MatchConfidence, List[str]]] = []

        # Normalize inputs
        email_norm = self.normalize_email(email)
        phone_norm = self.normalize_phone(phone)
        linkedin_norm = self.normalize_linkedin(linkedin_url)
        name_norm = self.normalize_name(first_name, last_name)
        exp_fingerprint = self.create_experience_fingerprint(parsed_experience or [])

        # Get all candidates for this tenant
        candidates = await self.client.select(
            "candidates",
            "*",
            filters={"tenant_id": str(tenant_id)},
        ) or []

        for candidate in candidates:
            # Skip if this is the candidate we're updating
            if exclude_candidate_id and candidate["id"] == str(exclude_candidate_id):
                continue

            match_reasons = []
            highest_confidence = MatchConfidence.NONE

            # Check 1: Email match (EXACT confidence)
            if email_norm:
                candidate_email_norm = self.normalize_email(candidate.get("email"))
                if candidate_email_norm == email_norm:
                    match_reasons.append(f"Email match: {email}")
                    highest_confidence = MatchConfidence.EXACT

            # Check 2: Phone match (HIGH confidence)
            if phone_norm and highest_confidence != MatchConfidence.EXACT:
                candidate_phone_norm = self.normalize_phone(candidate.get("phone"))
                if candidate_phone_norm and candidate_phone_norm == phone_norm:
                    match_reasons.append(f"Phone match: {phone}")
                    if highest_confidence.value not in [MatchConfidence.EXACT.value]:
                        highest_confidence = MatchConfidence.HIGH

            # Check 3: LinkedIn match (HIGH confidence)
            if linkedin_norm and highest_confidence not in [MatchConfidence.EXACT]:
                candidate_linkedin_norm = self.normalize_linkedin(candidate.get("linkedin_url"))
                if candidate_linkedin_norm and candidate_linkedin_norm == linkedin_norm:
                    match_reasons.append(f"LinkedIn match: {linkedin_url}")
                    if highest_confidence not in [MatchConfidence.EXACT, MatchConfidence.HIGH]:
                        highest_confidence = MatchConfidence.HIGH

            # Check 4: Name + Experience fingerprint (MEDIUM confidence)
            if highest_confidence == MatchConfidence.NONE and exp_fingerprint:
                candidate_name_norm = self.normalize_name(
                    candidate.get("first_name", ""),
                    candidate.get("last_name", "")
                )

                # Get candidate's resume and check experience
                resumes = await self.client.select(
                    "resumes",
                    "parsed_data",
                    filters={"candidate_id": candidate["id"], "is_primary": True},
                    single=True,
                ) or {}

                if resumes and candidate_name_norm == name_norm:
                    parsed_data = resumes.get("parsed_data", {})
                    candidate_exp = parsed_data.get("experience", [])
                    candidate_exp_fingerprint = self.create_experience_fingerprint(candidate_exp)

                    if candidate_exp_fingerprint and exp_fingerprint:
                        # Check for overlapping companies
                        incoming_companies = set(exp_fingerprint.split('|'))
                        existing_companies = set(candidate_exp_fingerprint.split('|'))
                        overlap = incoming_companies & existing_companies

                        if len(overlap) >= 2:  # At least 2 companies match
                            match_reasons.append(f"Name + work history match: {len(overlap)} overlapping companies")
                            highest_confidence = MatchConfidence.MEDIUM

            # Check 5: Name-only match with same source (LOW confidence)
            if highest_confidence == MatchConfidence.NONE:
                candidate_name_norm = self.normalize_name(
                    candidate.get("first_name", ""),
                    candidate.get("last_name", "")
                )
                if candidate_name_norm == name_norm:
                    match_reasons.append(f"Name match (requires review): {first_name} {last_name}")
                    highest_confidence = MatchConfidence.LOW

            if highest_confidence != MatchConfidence.NONE:
                matches.append((candidate, highest_confidence, match_reasons))

        if not matches:
            return DeduplicationResult(
                is_duplicate=False,
                existing_candidate_id=None,
                confidence=MatchConfidence.NONE,
                match_reasons=[],
                suggested_action="create_new",
            )

        # Sort by confidence (best first)
        confidence_order = {
            MatchConfidence.EXACT: 0,
            MatchConfidence.HIGH: 1,
            MatchConfidence.MEDIUM: 2,
            MatchConfidence.LOW: 3,
        }
        matches.sort(key=lambda x: confidence_order.get(x[1], 999))

        best_match = matches[0]
        candidate, confidence, reasons = best_match

        # Determine suggested action based on confidence
        if confidence == MatchConfidence.EXACT:
            suggested_action = "update_existing"
        elif confidence == MatchConfidence.HIGH:
            suggested_action = "update_existing"
        elif confidence == MatchConfidence.MEDIUM:
            suggested_action = "review_required"
        else:
            suggested_action = "review_required"

        return DeduplicationResult(
            is_duplicate=True,
            existing_candidate_id=UUID(candidate["id"]),
            confidence=confidence,
            match_reasons=reasons,
            suggested_action=suggested_action,
        )

    async def detect_profile_changes(
        self,
        existing_candidate: Dict,
        new_data: Dict,
        existing_parsed_data: Optional[Dict] = None,
        new_parsed_data: Optional[Dict] = None,
    ) -> Dict[str, Any]:
        """Detect what changed between old and new profile data.

        Returns a structured diff for review or auto-merge.
        """
        changes = {
            "contact_info": {},
            "career_progression": {},
            "skills_added": [],
            "skills_removed": [],
            "experience_added": [],
            "is_significant_update": False,
        }

        # Check contact info changes
        for field in ["first_name", "last_name", "phone", "linkedin_url", "location"]:
            old_value = existing_candidate.get(field)
            new_value = new_data.get(field)
            if new_value and old_value != new_value:
                changes["contact_info"][field] = {
                    "old": old_value,
                    "new": new_value,
                }

        # Check skills changes
        old_skills = set(existing_candidate.get("skills") or [])
        new_skills = set(new_data.get("skills") or [])

        changes["skills_added"] = list(new_skills - old_skills)
        changes["skills_removed"] = list(old_skills - new_skills)

        # Check experience additions (from parsed data)
        if existing_parsed_data and new_parsed_data:
            old_exp = existing_parsed_data.get("experience", [])
            new_exp = new_parsed_data.get("experience", [])

            # Find new jobs not in old experience
            old_companies = {(e.get("company", "").lower(), e.get("title", "").lower()) for e in old_exp}

            for exp in new_exp:
                key = (exp.get("company", "").lower(), exp.get("title", "").lower())
                if key not in old_companies and exp.get("company"):
                    changes["experience_added"].append({
                        "company": exp.get("company"),
                        "title": exp.get("title"),
                        "start_date": exp.get("start_date"),
                        "end_date": exp.get("end_date"),
                    })

            # Check for career level progression
            old_level = existing_parsed_data.get("current_level", "unknown")
            new_level = new_parsed_data.get("current_level", "unknown")

            level_order = ["intern", "entry", "mid", "senior", "lead", "manager", "director", "executive"]
            old_idx = level_order.index(old_level) if old_level in level_order else -1
            new_idx = level_order.index(new_level) if new_level in level_order else -1

            if new_idx > old_idx and old_idx >= 0:
                changes["career_progression"] = {
                    "old_level": old_level,
                    "new_level": new_level,
                    "progression": "promoted",
                }

        # Determine if this is a significant update
        if (
            len(changes["skills_added"]) >= 3 or
            len(changes["experience_added"]) >= 1 or
            changes.get("career_progression", {}).get("progression") == "promoted" or
            "email" in changes["contact_info"]
        ):
            changes["is_significant_update"] = True

        return changes

    async def merge_candidate_profiles(
        self,
        tenant_id: UUID,
        existing_candidate_id: UUID,
        new_candidate_data: Dict,
        new_resume_data: Optional[Dict] = None,
        merge_strategy: str = "prefer_new",  # 'prefer_new', 'prefer_existing', 'smart_merge'
    ) -> Dict[str, Any]:
        """Merge a new submission into an existing candidate profile.

        Strategies:
        - prefer_new: Always use new data where provided
        - prefer_existing: Only fill in blanks with new data
        - smart_merge: Use heuristics (newer dates win, aggregate skills, etc.)
        """
        # Get existing candidate
        existing = await self.client.select(
            "candidates",
            "*",
            filters={"id": str(existing_candidate_id), "tenant_id": str(tenant_id)},
            single=True,
        )

        if not existing:
            raise ValueError(f"Candidate {existing_candidate_id} not found")

        merged_data = dict(existing)

        if merge_strategy == "prefer_new":
            # Update all fields where new data is provided
            for key, value in new_candidate_data.items():
                if value is not None and key not in ["id", "tenant_id", "created_at"]:
                    merged_data[key] = value

        elif merge_strategy == "prefer_existing":
            # Only fill in blank fields
            for key, value in new_candidate_data.items():
                if value is not None and not existing.get(key) and key not in ["id", "tenant_id", "created_at"]:
                    merged_data[key] = value

        elif merge_strategy == "smart_merge":
            # Contact info: prefer new (more likely to be current)
            for field in ["phone", "linkedin_url", "location"]:
                if new_candidate_data.get(field):
                    merged_data[field] = new_candidate_data[field]

            # Skills: aggregate (union of both)
            old_skills = set(existing.get("skills") or [])
            new_skills = set(new_candidate_data.get("skills") or [])
            merged_data["skills"] = list(old_skills | new_skills)

            # Tags: aggregate
            old_tags = set(existing.get("tags") or [])
            new_tags = set(new_candidate_data.get("tags") or [])
            merged_data["tags"] = list(old_tags | new_tags)

            # Name: prefer existing unless explicitly different
            # (protects against parsing errors)
            if not existing.get("first_name") or not existing.get("last_name"):
                merged_data["first_name"] = new_candidate_data.get("first_name", merged_data.get("first_name"))
                merged_data["last_name"] = new_candidate_data.get("last_name", merged_data.get("last_name"))

        # Remove metadata fields before update
        update_data = {k: v for k, v in merged_data.items()
                      if k not in ["id", "tenant_id", "created_at", "updated_at"]}

        # Update candidate
        updated = await self.client.update(
            "candidates",
            update_data,
            filters={"id": str(existing_candidate_id)},
        )

        result = {
            "candidate_id": str(existing_candidate_id),
            "action": "merged",
            "merge_strategy": merge_strategy,
            "updated": True,
        }

        # If new resume data provided, add as new version
        if new_resume_data:
            # Get current resume count
            resumes = await self.client.select(
                "resumes",
                "version_number",
                filters={"candidate_id": str(existing_candidate_id)},
            ) or []

            max_version = max([r.get("version_number", 0) for r in resumes], default=0)

            # Unset is_primary on old resumes
            for resume in resumes:
                if resume.get("is_primary"):
                    await self.client.update(
                        "resumes",
                        {"is_primary": False},
                        filters={"candidate_id": str(existing_candidate_id), "is_primary": True},
                    )
                    break

            # Insert new resume
            new_resume = {
                "tenant_id": str(tenant_id),
                "candidate_id": str(existing_candidate_id),
                "version_number": max_version + 1,
                "is_primary": True,
                **new_resume_data,
            }

            resume = await self.client.insert("resumes", new_resume)
            result["new_resume_id"] = resume["id"]
            result["resume_version"] = max_version + 1

        return result

    async def get_duplicate_candidates_for_review(
        self,
        tenant_id: UUID,
        page: int = 1,
        page_size: int = 20,
    ) -> Dict[str, Any]:
        """Get list of potential duplicate candidate pairs for manual review.

        Useful for data cleanup and deduplication maintenance.
        """
        candidates = await self.client.select(
            "candidates",
            "*",
            filters={"tenant_id": str(tenant_id)},
        ) or []

        duplicate_groups = []
        seen_ids = set()

        for i, candidate in enumerate(candidates):
            if candidate["id"] in seen_ids:
                continue

            # Find potential duplicates for this candidate
            for other in candidates[i + 1:]:
                if other["id"] in seen_ids:
                    continue

                # Check for potential match
                match_score = 0
                match_reasons = []

                # Same normalized phone
                if self.normalize_phone(candidate.get("phone")) == self.normalize_phone(other.get("phone")):
                    if candidate.get("phone"):
                        match_score += 30
                        match_reasons.append("Same phone")

                # Same name
                if self.normalize_name(
                    candidate.get("first_name", ""),
                    candidate.get("last_name", "")
                ) == self.normalize_name(
                    other.get("first_name", ""),
                    other.get("last_name", "")
                ):
                    match_score += 25
                    match_reasons.append("Same name")

                # Same LinkedIn
                if self.normalize_linkedin(candidate.get("linkedin_url")) == self.normalize_linkedin(other.get("linkedin_url")):
                    if candidate.get("linkedin_url"):
                        match_score += 35
                        match_reasons.append("Same LinkedIn")

                # Overlapping skills
                skills_a = set(candidate.get("skills") or [])
                skills_b = set(other.get("skills") or [])
                if skills_a and skills_b:
                    overlap = len(skills_a & skills_b) / max(len(skills_a), len(skills_b))
                    if overlap > 0.7:
                        match_score += 10
                        match_reasons.append(f"70%+ skill overlap")

                if match_score >= 50:
                    duplicate_groups.append({
                        "candidate_a": {
                            "id": candidate["id"],
                            "name": f"{candidate.get('first_name')} {candidate.get('last_name')}",
                            "email": candidate.get("email"),
                            "phone": candidate.get("phone"),
                        },
                        "candidate_b": {
                            "id": other["id"],
                            "name": f"{other.get('first_name')} {other.get('last_name')}",
                            "email": other.get("email"),
                            "phone": other.get("phone"),
                        },
                        "match_score": match_score,
                        "match_reasons": match_reasons,
                    })
                    seen_ids.add(other["id"])

        # Paginate results
        total = len(duplicate_groups)
        offset = (page - 1) * page_size
        duplicate_groups = duplicate_groups[offset:offset + page_size]

        return {
            "items": duplicate_groups,
            "total": total,
            "page": page,
            "page_size": page_size,
        }


# Singleton instance
candidate_deduplication_service = CandidateDeduplicationService()
