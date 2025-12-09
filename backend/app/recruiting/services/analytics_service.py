"""Analytics service for recruiting reports and dashboards."""

from datetime import datetime, timedelta, timezone
from typing import Optional
from uuid import UUID

import httpx

from app.config import get_settings


settings = get_settings()


class AnalyticsService:
    """Service for generating recruiting analytics and reports."""

    def __init__(self):
        self.supabase_url = settings.supabase_url
        self.supabase_key = settings.supabase_service_role_key

    def _get_headers(self):
        """Get headers for Supabase REST API calls."""
        return {
            "apikey": self.supabase_key,
            "Authorization": f"Bearer {self.supabase_key}",
            "Content-Type": "application/json",
            "Prefer": "return=representation",
        }

    async def get_recruiter_performance(
        self,
        tenant_id: UUID,
        recruiter_id: Optional[UUID] = None,
        start_date: Optional[str] = None,
        end_date: Optional[str] = None,
    ) -> dict:
        """Get recruiter performance metrics.

        Args:
            tenant_id: Tenant ID
            recruiter_id: Optional specific recruiter ID
            start_date: Optional start date filter (ISO format)
            end_date: Optional end date filter (ISO format)

        Returns:
            Performance metrics dictionary
        """
        if not start_date:
            start_date = (datetime.now(timezone.utc) - timedelta(days=90)).isoformat()
        if not end_date:
            end_date = datetime.now(timezone.utc).isoformat()

        async with httpx.AsyncClient() as client:
            # Get recruiters with their assignments
            params = {
                "tenant_id": f"eq.{tenant_id}",
                "select": "id,recruiter_id,requisition_id,assigned_at,completed_at,status",
            }

            if recruiter_id:
                params["recruiter_id"] = f"eq.{recruiter_id}"

            assignments_response = await client.get(
                f"{self.supabase_url}/rest/v1/recruiter_assignments",
                headers=self._get_headers(),
                params=params,
                timeout=30,
            )

            assignments = assignments_response.json() if assignments_response.status_code == 200 else []

            # Get applications processed by recruiters
            app_params = {
                "tenant_id": f"eq.{tenant_id}",
                "select": "id,assigned_to,status,current_stage,created_at,updated_at",
            }

            apps_response = await client.get(
                f"{self.supabase_url}/rest/v1/applications",
                headers=self._get_headers(),
                params=app_params,
                timeout=30,
            )

            applications = apps_response.json() if apps_response.status_code == 200 else []

            # Get offers created
            offers_params = {
                "tenant_id": f"eq.{tenant_id}",
                "select": "id,created_by,status,created_at",
            }

            offers_response = await client.get(
                f"{self.supabase_url}/rest/v1/offers",
                headers=self._get_headers(),
                params=offers_params,
                timeout=30,
            )

            offers = offers_response.json() if offers_response.status_code == 200 else []

            # Calculate metrics per recruiter
            recruiters = {}

            for assignment in assignments:
                rid = assignment.get("recruiter_id")
                if not rid:
                    continue

                if rid not in recruiters:
                    recruiters[rid] = {
                        "recruiter_id": rid,
                        "jobs_assigned": 0,
                        "jobs_completed": 0,
                        "avg_time_to_fill_days": 0,
                        "total_fill_days": 0,
                    }

                recruiters[rid]["jobs_assigned"] += 1

                if assignment.get("status") == "completed":
                    recruiters[rid]["jobs_completed"] += 1
                    if assignment.get("assigned_at") and assignment.get("completed_at"):
                        try:
                            assigned = datetime.fromisoformat(assignment["assigned_at"].replace("Z", "+00:00"))
                            completed = datetime.fromisoformat(assignment["completed_at"].replace("Z", "+00:00"))
                            days = (completed - assigned).days
                            recruiters[rid]["total_fill_days"] += days
                        except:
                            pass

            # Calculate averages and add application stats
            for rid, metrics in recruiters.items():
                if metrics["jobs_completed"] > 0:
                    metrics["avg_time_to_fill_days"] = round(
                        metrics["total_fill_days"] / metrics["jobs_completed"], 1
                    )
                del metrics["total_fill_days"]

                # Count applications assigned to this recruiter
                assigned_apps = [a for a in applications if a.get("assigned_to") == rid]
                metrics["applications_processed"] = len(assigned_apps)
                metrics["applications_hired"] = len([
                    a for a in assigned_apps if a.get("status") == "hired"
                ])
                metrics["applications_rejected"] = len([
                    a for a in assigned_apps if a.get("status") == "rejected"
                ])

                # Count offers created
                recruiter_offers = [o for o in offers if o.get("created_by") == rid]
                metrics["offers_extended"] = len(recruiter_offers)
                metrics["offers_accepted"] = len([
                    o for o in recruiter_offers if o.get("status") == "accepted"
                ])

                if metrics["offers_extended"] > 0:
                    metrics["offer_acceptance_rate"] = round(
                        (metrics["offers_accepted"] / metrics["offers_extended"]) * 100, 1
                    )
                else:
                    metrics["offer_acceptance_rate"] = 0.0

            return {
                "period": {
                    "start": start_date,
                    "end": end_date,
                },
                "recruiters": list(recruiters.values()),
                "summary": {
                    "total_recruiters": len(recruiters),
                    "total_jobs_assigned": sum(r["jobs_assigned"] for r in recruiters.values()),
                    "total_jobs_completed": sum(r["jobs_completed"] for r in recruiters.values()),
                    "total_applications": len(applications),
                    "total_hires": sum(r["applications_hired"] for r in recruiters.values()),
                },
            }

    async def get_time_to_fill_report(
        self,
        tenant_id: UUID,
        start_date: Optional[str] = None,
        end_date: Optional[str] = None,
        department: Optional[str] = None,
    ) -> dict:
        """Get time-to-fill analytics.

        Args:
            tenant_id: Tenant ID
            start_date: Optional start date filter
            end_date: Optional end date filter
            department: Optional department filter

        Returns:
            Time-to-fill metrics
        """
        async with httpx.AsyncClient() as client:
            params = {
                "tenant_id": f"eq.{tenant_id}",
                "status": "in.(filled,closed)",
                "select": "id,title,department,status,job_opened_at,filled_at,created_at,updated_at",
            }

            if department:
                params["department"] = f"eq.{department}"

            response = await client.get(
                f"{self.supabase_url}/rest/v1/job_requisitions",
                headers=self._get_headers(),
                params=params,
                timeout=30,
            )

            jobs = response.json() if response.status_code == 200 else []

            # Calculate time-to-fill for each job
            fill_times = []
            by_department = {}

            for job in jobs:
                opened = job.get("job_opened_at") or job.get("created_at")
                filled = job.get("filled_at") or job.get("updated_at")

                if opened and filled:
                    try:
                        opened_dt = datetime.fromisoformat(opened.replace("Z", "+00:00"))
                        filled_dt = datetime.fromisoformat(filled.replace("Z", "+00:00"))
                        days = (filled_dt - opened_dt).days

                        fill_times.append({
                            "job_id": job["id"],
                            "title": job.get("title"),
                            "department": job.get("department"),
                            "days_to_fill": days,
                        })

                        dept = job.get("department") or "Unknown"
                        if dept not in by_department:
                            by_department[dept] = []
                        by_department[dept].append(days)
                    except:
                        pass

            # Calculate overall metrics
            all_days = [f["days_to_fill"] for f in fill_times]

            overall = {
                "avg_days": round(sum(all_days) / len(all_days), 1) if all_days else 0,
                "min_days": min(all_days) if all_days else 0,
                "max_days": max(all_days) if all_days else 0,
                "median_days": sorted(all_days)[len(all_days) // 2] if all_days else 0,
                "total_jobs_filled": len(fill_times),
            }

            # Calculate by department
            dept_metrics = []
            for dept, days in by_department.items():
                dept_metrics.append({
                    "department": dept,
                    "avg_days": round(sum(days) / len(days), 1),
                    "jobs_filled": len(days),
                })

            return {
                "overall": overall,
                "by_department": sorted(dept_metrics, key=lambda x: x["avg_days"]),
                "details": fill_times[:100],  # Limit details
            }

    async def get_source_effectiveness_report(
        self,
        tenant_id: UUID,
        start_date: Optional[str] = None,
        end_date: Optional[str] = None,
    ) -> dict:
        """Get application source effectiveness metrics.

        Args:
            tenant_id: Tenant ID
            start_date: Optional start date filter
            end_date: Optional end date filter

        Returns:
            Source effectiveness metrics
        """
        async with httpx.AsyncClient() as client:
            # Get application sources
            sources_response = await client.get(
                f"{self.supabase_url}/rest/v1/application_sources",
                headers=self._get_headers(),
                params={
                    "tenant_id": f"eq.{tenant_id}",
                    "is_active": "eq.true",
                    "select": "id,name,source_type",
                },
                timeout=15,
            )

            sources = sources_response.json() if sources_response.status_code == 200 else []
            source_map = {s["id"]: s for s in sources}

            # Get applications with source data
            apps_response = await client.get(
                f"{self.supabase_url}/rest/v1/applications",
                headers=self._get_headers(),
                params={
                    "tenant_id": f"eq.{tenant_id}",
                    "select": "id,source_id,status,current_stage,created_at",
                },
                timeout=30,
            )

            applications = apps_response.json() if apps_response.status_code == 200 else []

            # Group by source
            by_source = {}
            for app in applications:
                source_id = app.get("source_id")
                source_name = source_map.get(source_id, {}).get("name", "Direct/Unknown")

                if source_name not in by_source:
                    by_source[source_name] = {
                        "source": source_name,
                        "total_applications": 0,
                        "hired": 0,
                        "rejected": 0,
                        "in_progress": 0,
                    }

                by_source[source_name]["total_applications"] += 1

                status = app.get("status", "")
                if status == "hired":
                    by_source[source_name]["hired"] += 1
                elif status == "rejected":
                    by_source[source_name]["rejected"] += 1
                else:
                    by_source[source_name]["in_progress"] += 1

            # Calculate conversion rates
            source_metrics = []
            for name, data in by_source.items():
                if data["total_applications"] > 0:
                    data["conversion_rate"] = round(
                        (data["hired"] / data["total_applications"]) * 100, 1
                    )
                else:
                    data["conversion_rate"] = 0.0
                source_metrics.append(data)

            # Sort by conversion rate
            source_metrics.sort(key=lambda x: x["conversion_rate"], reverse=True)

            total_apps = sum(s["total_applications"] for s in source_metrics)
            total_hires = sum(s["hired"] for s in source_metrics)

            return {
                "sources": source_metrics,
                "summary": {
                    "total_sources": len(source_metrics),
                    "total_applications": total_apps,
                    "total_hires": total_hires,
                    "overall_conversion_rate": round(
                        (total_hires / total_apps * 100) if total_apps > 0 else 0, 1
                    ),
                },
            }

    async def get_pipeline_funnel_report(
        self,
        tenant_id: UUID,
        requisition_id: Optional[UUID] = None,
    ) -> dict:
        """Get pipeline funnel analytics.

        Args:
            tenant_id: Tenant ID
            requisition_id: Optional job requisition filter

        Returns:
            Pipeline funnel metrics
        """
        async with httpx.AsyncClient() as client:
            # Get pipeline templates for stage names
            templates_response = await client.get(
                f"{self.supabase_url}/rest/v1/pipeline_templates",
                headers=self._get_headers(),
                params={
                    "tenant_id": f"eq.{tenant_id}",
                    "is_default": "eq.true",
                    "select": "stages",
                },
                timeout=15,
            )

            default_stages = ["applied", "screening", "interview", "offer", "hired"]
            if templates_response.status_code == 200 and templates_response.json():
                template = templates_response.json()[0]
                stages_data = template.get("stages", [])
                if stages_data and isinstance(stages_data, list):
                    extracted = []
                    for s in stages_data:
                        if isinstance(s, dict):
                            extracted.append(s.get("name", "unknown"))
                        elif isinstance(s, str):
                            extracted.append(s)
                    if extracted:
                        default_stages = extracted

            # Get applications
            params = {
                "tenant_id": f"eq.{tenant_id}",
                "select": "id,current_stage,status,created_at",
            }

            if requisition_id:
                params["requisition_id"] = f"eq.{requisition_id}"

            apps_response = await client.get(
                f"{self.supabase_url}/rest/v1/applications",
                headers=self._get_headers(),
                params=params,
                timeout=30,
            )

            applications = apps_response.json() if apps_response.status_code == 200 else []

            # Count by stage
            stage_counts = {}
            for stage in default_stages:
                stage_counts[stage] = 0
            stage_counts["rejected"] = 0

            for app in applications:
                stage = app.get("current_stage", "applied")
                if stage in stage_counts:
                    stage_counts[stage] += 1
                elif app.get("status") == "rejected":
                    stage_counts["rejected"] += 1
                else:
                    # Unknown stage
                    if stage not in stage_counts:
                        stage_counts[stage] = 0
                    stage_counts[stage] += 1

            # Build funnel
            total = len(applications)
            funnel = []
            cumulative = total

            for stage in default_stages:
                count = stage_counts.get(stage, 0)
                funnel.append({
                    "stage": stage,
                    "count": count,
                    "percentage_of_total": round((count / total * 100) if total > 0 else 0, 1),
                })

            return {
                "funnel": funnel,
                "total_applications": total,
                "rejected_count": stage_counts.get("rejected", 0),
                "conversion_rates": {
                    "applied_to_screening": round(
                        (stage_counts.get("screening", 0) / stage_counts.get("applied", 1) * 100)
                        if stage_counts.get("applied", 0) > 0 else 0, 1
                    ),
                    "screening_to_interview": round(
                        (stage_counts.get("interview", 0) / max(stage_counts.get("screening", 1), 1) * 100), 1
                    ),
                    "interview_to_offer": round(
                        (stage_counts.get("offer", 0) / max(stage_counts.get("interview", 1), 1) * 100), 1
                    ),
                    "offer_to_hired": round(
                        (stage_counts.get("hired", 0) / max(stage_counts.get("offer", 1), 1) * 100), 1
                    ),
                },
            }

    async def get_dashboard_summary(
        self,
        tenant_id: UUID,
    ) -> dict:
        """Get dashboard summary metrics.

        Args:
            tenant_id: Tenant ID

        Returns:
            Dashboard summary data
        """
        async with httpx.AsyncClient() as client:
            # Get counts with Prefer: count=exact header
            headers_with_count = {**self._get_headers(), "Prefer": "count=exact"}

            # Open jobs
            jobs_response = await client.get(
                f"{self.supabase_url}/rest/v1/job_requisitions",
                headers=headers_with_count,
                params={
                    "tenant_id": f"eq.{tenant_id}",
                    "status": "eq.open",
                    "select": "id",
                },
                timeout=15,
            )

            open_jobs = 0
            if "content-range" in jobs_response.headers:
                range_header = jobs_response.headers["content-range"]
                if "/" in range_header:
                    open_jobs = int(range_header.split("/")[1])

            # Active candidates (not rejected/hired)
            candidates_response = await client.get(
                f"{self.supabase_url}/rest/v1/applications",
                headers=headers_with_count,
                params={
                    "tenant_id": f"eq.{tenant_id}",
                    "status": "not.in.(rejected,hired,withdrawn)",
                    "select": "id",
                },
                timeout=15,
            )

            active_candidates = 0
            if "content-range" in candidates_response.headers:
                range_header = candidates_response.headers["content-range"]
                if "/" in range_header:
                    active_candidates = int(range_header.split("/")[1])

            # Hires this month
            month_start = datetime.now(timezone.utc).replace(
                day=1, hour=0, minute=0, second=0, microsecond=0
            ).isoformat()

            hires_response = await client.get(
                f"{self.supabase_url}/rest/v1/applications",
                headers=headers_with_count,
                params={
                    "tenant_id": f"eq.{tenant_id}",
                    "status": "eq.hired",
                    "hired_at": f"gte.{month_start}",
                    "select": "id",
                },
                timeout=15,
            )

            hires_this_month = 0
            if "content-range" in hires_response.headers:
                range_header = hires_response.headers["content-range"]
                if "/" in range_header:
                    hires_this_month = int(range_header.split("/")[1])

            # Pending offers
            offers_response = await client.get(
                f"{self.supabase_url}/rest/v1/offers",
                headers=headers_with_count,
                params={
                    "tenant_id": f"eq.{tenant_id}",
                    "status": "in.(pending_approval,approved,sent)",
                    "select": "id",
                },
                timeout=15,
            )

            pending_offers = 0
            if "content-range" in offers_response.headers:
                range_header = offers_response.headers["content-range"]
                if "/" in range_header:
                    pending_offers = int(range_header.split("/")[1])

            # SLA alerts (at risk)
            alerts_response = await client.get(
                f"{self.supabase_url}/rest/v1/sla_alerts",
                headers=headers_with_count,
                params={
                    "tenant_id": f"eq.{tenant_id}",
                    "acknowledged_at": "is.null",
                    "select": "id",
                },
                timeout=15,
            )

            sla_alerts = 0
            if "content-range" in alerts_response.headers:
                range_header = alerts_response.headers["content-range"]
                if "/" in range_header:
                    sla_alerts = int(range_header.split("/")[1])

            return {
                "summary": {
                    "open_jobs": open_jobs,
                    "active_candidates": active_candidates,
                    "hires_this_month": hires_this_month,
                    "pending_offers": pending_offers,
                    "sla_alerts": sla_alerts,
                },
                "generated_at": datetime.now(timezone.utc).isoformat(),
            }


# Singleton instance
_analytics_service: Optional[AnalyticsService] = None


def get_analytics_service() -> AnalyticsService:
    """Get or create the analytics service singleton."""
    global _analytics_service
    if _analytics_service is None:
        _analytics_service = AnalyticsService()
    return _analytics_service
