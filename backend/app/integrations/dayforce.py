"""Dayforce HCM Integration Service.

This service syncs job openings and employee data between Dayforce and our system.
"""

import os
from datetime import datetime, timezone
from typing import Optional
from uuid import UUID

import httpx

from app.config import get_settings


settings = get_settings()


class DayforceClient:
    """Client for Dayforce HCM API."""

    def __init__(
        self,
        base_url: Optional[str] = None,
        client_namespace: Optional[str] = None,
        username: Optional[str] = None,
        password: Optional[str] = None,
    ):
        self.base_url = base_url or os.getenv("DAYFORCE_BASE_URL", "https://api.dayforce.com")
        self.client_namespace = client_namespace or os.getenv("DAYFORCE_CLIENT_NAMESPACE", "")
        self.username = username or os.getenv("DAYFORCE_USERNAME", "")
        self.password = password or os.getenv("DAYFORCE_PASSWORD", "")
        self._token: Optional[str] = None
        self._token_expires: Optional[datetime] = None

    def _get_auth_headers(self) -> dict:
        """Get authentication headers for Dayforce API."""
        return {
            "Content-Type": "application/json",
            "Accept": "application/json",
        }

    async def authenticate(self) -> bool:
        """Authenticate with Dayforce API.

        Returns:
            True if authentication successful
        """
        if not self.username or not self.password:
            return False

        try:
            async with httpx.AsyncClient() as client:
                response = await client.post(
                    f"{self.base_url}/{self.client_namespace}/V1/Token",
                    headers=self._get_auth_headers(),
                    json={
                        "username": self.username,
                        "password": self.password,
                    },
                    timeout=30,
                )

                if response.status_code == 200:
                    data = response.json()
                    self._token = data.get("access_token")
                    return True

                return False

        except Exception as e:
            print(f"Dayforce authentication error: {e}")
            return False

    async def get_job_postings(self, status: str = "Open") -> list[dict]:
        """Fetch job postings from Dayforce.

        Args:
            status: Filter by posting status (Open, Closed, Draft)

        Returns:
            List of job posting dictionaries
        """
        if not self._token and not await self.authenticate():
            return []

        try:
            async with httpx.AsyncClient() as client:
                response = await client.get(
                    f"{self.base_url}/{self.client_namespace}/V1/JobPostings",
                    headers={
                        **self._get_auth_headers(),
                        "Authorization": f"Bearer {self._token}",
                    },
                    params={"status": status},
                    timeout=60,
                )

                if response.status_code == 200:
                    data = response.json()
                    return data.get("Data", [])

                return []

        except Exception as e:
            print(f"Error fetching Dayforce job postings: {e}")
            return []

    async def get_employees(self, department: Optional[str] = None) -> list[dict]:
        """Fetch employees from Dayforce.

        Args:
            department: Optional department filter

        Returns:
            List of employee dictionaries
        """
        if not self._token and not await self.authenticate():
            return []

        try:
            async with httpx.AsyncClient() as client:
                params = {}
                if department:
                    params["department"] = department

                response = await client.get(
                    f"{self.base_url}/{self.client_namespace}/V1/Employees",
                    headers={
                        **self._get_auth_headers(),
                        "Authorization": f"Bearer {self._token}",
                    },
                    params=params,
                    timeout=60,
                )

                if response.status_code == 200:
                    data = response.json()
                    return data.get("Data", [])

                return []

        except Exception as e:
            print(f"Error fetching Dayforce employees: {e}")
            return []

    async def get_organization_structure(self) -> dict:
        """Fetch organization structure (departments, locations).

        Returns:
            Organization structure dictionary
        """
        if not self._token and not await self.authenticate():
            return {}

        try:
            async with httpx.AsyncClient() as client:
                response = await client.get(
                    f"{self.base_url}/{self.client_namespace}/V1/OrgUnits",
                    headers={
                        **self._get_auth_headers(),
                        "Authorization": f"Bearer {self._token}",
                    },
                    timeout=30,
                )

                if response.status_code == 200:
                    return response.json()

                return {}

        except Exception as e:
            print(f"Error fetching Dayforce org structure: {e}")
            return {}


class DayforceSyncService:
    """Service for syncing data between Dayforce and our system."""

    def __init__(self):
        self.client = DayforceClient()
        self.supabase_url = settings.supabase_url
        self.supabase_key = settings.supabase_service_role_key

    def _get_headers(self) -> dict:
        """Get headers for Supabase REST API calls."""
        return {
            "apikey": self.supabase_key,
            "Authorization": f"Bearer {self.supabase_key}",
            "Content-Type": "application/json",
            "Prefer": "return=representation",
        }

    async def sync_job_openings(self, tenant_id: UUID) -> dict:
        """Sync job openings from Dayforce to our system.

        Args:
            tenant_id: Tenant ID to sync jobs for

        Returns:
            Sync result summary
        """
        result = {
            "synced": 0,
            "created": 0,
            "updated": 0,
            "errors": 0,
            "error_details": [],
        }

        try:
            # Fetch job postings from Dayforce
            postings = await self.client.get_job_postings(status="Open")

            if not postings:
                result["error_details"].append("No job postings returned from Dayforce")
                return result

            async with httpx.AsyncClient() as client:
                for posting in postings:
                    try:
                        dayforce_job_id = posting.get("JobPostingId") or posting.get("XRefCode")

                        if not dayforce_job_id:
                            result["errors"] += 1
                            continue

                        # Check if job already exists
                        existing_response = await client.get(
                            f"{self.supabase_url}/rest/v1/job_requisitions",
                            headers=self._get_headers(),
                            params={
                                "tenant_id": f"eq.{tenant_id}",
                                "dayforce_job_id": f"eq.{dayforce_job_id}",
                                "select": "id",
                            },
                            timeout=15,
                        )

                        job_data = self._transform_dayforce_job(posting, tenant_id)

                        if existing_response.status_code == 200 and existing_response.json():
                            # Update existing
                            existing_id = existing_response.json()[0]["id"]
                            update_response = await client.patch(
                                f"{self.supabase_url}/rest/v1/job_requisitions",
                                headers=self._get_headers(),
                                params={"id": f"eq.{existing_id}"},
                                json=job_data,
                                timeout=15,
                            )
                            if update_response.status_code in (200, 204):
                                result["updated"] += 1
                            else:
                                result["errors"] += 1
                        else:
                            # Create new
                            create_response = await client.post(
                                f"{self.supabase_url}/rest/v1/job_requisitions",
                                headers=self._get_headers(),
                                json=job_data,
                                timeout=15,
                            )
                            if create_response.status_code in (200, 201):
                                result["created"] += 1
                            else:
                                result["errors"] += 1
                                result["error_details"].append(
                                    f"Failed to create job {dayforce_job_id}: {create_response.text[:100]}"
                                )

                        result["synced"] += 1

                    except Exception as e:
                        result["errors"] += 1
                        result["error_details"].append(str(e))

        except Exception as e:
            result["error_details"].append(f"Sync failed: {str(e)}")

        return result

    def _transform_dayforce_job(self, posting: dict, tenant_id: UUID) -> dict:
        """Transform Dayforce job posting to our job requisition format.

        Args:
            posting: Dayforce job posting data
            tenant_id: Target tenant ID

        Returns:
            Transformed job requisition data
        """
        now = datetime.now(timezone.utc).isoformat()

        return {
            "tenant_id": str(tenant_id),
            "dayforce_job_id": posting.get("JobPostingId") or posting.get("XRefCode"),
            "title": posting.get("JobTitle") or posting.get("Title", "Untitled Position"),
            "department": posting.get("Department", {}).get("ShortName") or posting.get("Department"),
            "location": posting.get("Location", {}).get("ShortName") or posting.get("Location"),
            "description": posting.get("Description") or posting.get("JobDescription", ""),
            "requirements": posting.get("Qualifications") or posting.get("Requirements", ""),
            "employment_type": self._map_employment_type(posting.get("EmploymentType")),
            "status": self._map_job_status(posting.get("Status")),
            "headcount": posting.get("NumberOfOpenings", 1),
            "compensation_band_min": posting.get("MinSalary"),
            "compensation_band_max": posting.get("MaxSalary"),
            "external_posting_url": posting.get("ApplyUrl"),
            "metadata": {
                "dayforce_sync": True,
                "dayforce_last_sync": now,
                "dayforce_raw": posting,
            },
            "updated_at": now,
        }

    def _map_employment_type(self, dayforce_type: Optional[str]) -> str:
        """Map Dayforce employment type to our format."""
        mapping = {
            "Full-Time": "full_time",
            "Part-Time": "part_time",
            "Contract": "contract",
            "Temporary": "temporary",
            "Intern": "intern",
        }
        return mapping.get(dayforce_type, "full_time")

    def _map_job_status(self, dayforce_status: Optional[str]) -> str:
        """Map Dayforce job status to our format."""
        mapping = {
            "Open": "open",
            "Closed": "closed",
            "Draft": "draft",
            "Filled": "filled",
            "On Hold": "on_hold",
        }
        return mapping.get(dayforce_status, "open")

    async def sync_employees(self, tenant_id: UUID) -> dict:
        """Sync employees from Dayforce for referral lookups.

        Args:
            tenant_id: Tenant ID

        Returns:
            Sync result summary
        """
        result = {
            "synced": 0,
            "created": 0,
            "updated": 0,
            "errors": 0,
        }

        try:
            employees = await self.client.get_employees()

            if not employees:
                return result

            async with httpx.AsyncClient() as client:
                for emp in employees:
                    try:
                        dayforce_emp_id = emp.get("EmployeeId") or emp.get("XRefCode")

                        if not dayforce_emp_id:
                            result["errors"] += 1
                            continue

                        emp_data = {
                            "tenant_id": str(tenant_id),
                            "dayforce_employee_id": dayforce_emp_id,
                            "email": emp.get("Email") or emp.get("WorkEmail"),
                            "first_name": emp.get("FirstName"),
                            "last_name": emp.get("LastName"),
                            "department": emp.get("Department", {}).get("ShortName") or emp.get("Department"),
                            "title": emp.get("JobTitle") or emp.get("Position"),
                            "is_active": emp.get("Status") == "Active",
                            "metadata": {
                                "dayforce_sync": True,
                                "dayforce_last_sync": datetime.now(timezone.utc).isoformat(),
                            },
                        }

                        # Check if exists
                        existing_response = await client.get(
                            f"{self.supabase_url}/rest/v1/employees",
                            headers=self._get_headers(),
                            params={
                                "tenant_id": f"eq.{tenant_id}",
                                "dayforce_employee_id": f"eq.{dayforce_emp_id}",
                                "select": "id",
                            },
                            timeout=15,
                        )

                        if existing_response.status_code == 200 and existing_response.json():
                            existing_id = existing_response.json()[0]["id"]
                            await client.patch(
                                f"{self.supabase_url}/rest/v1/employees",
                                headers=self._get_headers(),
                                params={"id": f"eq.{existing_id}"},
                                json=emp_data,
                                timeout=15,
                            )
                            result["updated"] += 1
                        else:
                            await client.post(
                                f"{self.supabase_url}/rest/v1/employees",
                                headers=self._get_headers(),
                                json=emp_data,
                                timeout=15,
                            )
                            result["created"] += 1

                        result["synced"] += 1

                    except Exception as e:
                        result["errors"] += 1

        except Exception as e:
            print(f"Employee sync error: {e}")

        return result

    async def get_sync_status(self, tenant_id: UUID) -> dict:
        """Get the status of Dayforce sync for a tenant.

        Args:
            tenant_id: Tenant ID

        Returns:
            Sync status information
        """
        try:
            async with httpx.AsyncClient() as client:
                # Get count of Dayforce-synced jobs
                jobs_response = await client.get(
                    f"{self.supabase_url}/rest/v1/job_requisitions",
                    headers={**self._get_headers(), "Prefer": "count=exact"},
                    params={
                        "tenant_id": f"eq.{tenant_id}",
                        "dayforce_job_id": "not.is.null",
                        "select": "id",
                    },
                    timeout=15,
                )

                jobs_count = 0
                if "content-range" in jobs_response.headers:
                    range_header = jobs_response.headers["content-range"]
                    if "/" in range_header:
                        jobs_count = int(range_header.split("/")[1])

                # Get last sync time from metadata
                last_sync_response = await client.get(
                    f"{self.supabase_url}/rest/v1/job_requisitions",
                    headers=self._get_headers(),
                    params={
                        "tenant_id": f"eq.{tenant_id}",
                        "dayforce_job_id": "not.is.null",
                        "select": "metadata",
                        "order": "updated_at.desc",
                        "limit": "1",
                    },
                    timeout=15,
                )

                last_sync = None
                if last_sync_response.status_code == 200:
                    data = last_sync_response.json()
                    if data and data[0].get("metadata"):
                        last_sync = data[0]["metadata"].get("dayforce_last_sync")

                return {
                    "connected": bool(self.client.username and self.client.password),
                    "jobs_synced": jobs_count,
                    "last_sync": last_sync,
                    "dayforce_url": self.client.base_url,
                    "client_namespace": self.client.client_namespace,
                }

        except Exception as e:
            return {
                "connected": False,
                "error": str(e),
            }


# Singleton instance
_dayforce_sync_service: Optional[DayforceSyncService] = None


def get_dayforce_sync_service() -> DayforceSyncService:
    """Get or create the Dayforce sync service singleton."""
    global _dayforce_sync_service
    if _dayforce_sync_service is None:
        _dayforce_sync_service = DayforceSyncService()
    return _dayforce_sync_service
