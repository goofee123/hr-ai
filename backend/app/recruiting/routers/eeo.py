"""EEO (Equal Employment Opportunity) compliance router."""

from datetime import datetime, timezone, timedelta
from typing import Optional
from uuid import UUID

from fastapi import APIRouter, Depends, HTTPException, Query, status

from app.core.permissions import Permission, require_permission
from app.core.security import TokenData
from app.core.tenant import get_tenant_id
from app.core.supabase_client import get_supabase_client
from app.recruiting.schemas.eeo import (
    EEOResponseCreate,
    EEOResponseResponse,
    EEOFormOptions,
    EEOSummaryReport,
    EEOCategorySummary,
    EEOSummaryByCategory,
    AdverseImpactReport,
    AdverseImpactAnalysis,
    AuditLogEntry,
    AuditLogResponse,
)

router = APIRouter()


# EEO Form Options (for frontend)
@router.get("/form-options", response_model=EEOFormOptions)
async def get_eeo_form_options():
    """Get available options for EEO self-identification form."""
    return EEOFormOptions()


# EEO Response Collection
@router.post("/responses", response_model=EEOResponseResponse, status_code=status.HTTP_201_CREATED)
async def submit_eeo_response(
    data: EEOResponseCreate,
    tenant_id: UUID = Depends(get_tenant_id),
):
    """
    Submit EEO self-identification response.

    This endpoint can be called by candidates (public) or recruiters.
    EEO data is stored separately and never shown during candidate evaluation.
    """
    client = get_supabase_client()

    # Verify application exists
    app = await client.select(
        "applications",
        "id, tenant_id",
        filters={"id": str(data.application_id)},
        single=True,
    )

    if not app:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Application not found",
        )

    # Check if EEO response already exists
    existing = await client.select(
        "eeo_responses",
        "id",
        filters={"application_id": str(data.application_id)},
        single=True,
    )

    if existing:
        # Update existing response
        updated = await client.update(
            "eeo_responses",
            {
                "gender": data.gender,
                "ethnicity": data.ethnicity,
                "veteran_status": data.veteran_status,
                "disability_status": data.disability_status,
                "collected_at": datetime.now(timezone.utc).isoformat(),
            },
            filters={"id": existing["id"]},
        )
        response_data = updated
    else:
        # Create new response
        response_data = await client.insert(
            "eeo_responses",
            {
                "tenant_id": str(tenant_id),
                "application_id": str(data.application_id),
                "gender": data.gender,
                "ethnicity": data.ethnicity,
                "veteran_status": data.veteran_status,
                "disability_status": data.disability_status,
            },
        )

    return EEOResponseResponse(
        id=UUID(response_data["id"]),
        application_id=UUID(response_data["application_id"]),
        gender=response_data.get("gender"),
        ethnicity=response_data.get("ethnicity"),
        veteran_status=response_data.get("veteran_status"),
        disability_status=response_data.get("disability_status"),
        collected_at=datetime.fromisoformat(response_data["collected_at"].replace("Z", "+00:00")),
    )


@router.get("/responses/{application_id}", response_model=EEOResponseResponse)
async def get_eeo_response(
    application_id: UUID,
    tenant_id: UUID = Depends(get_tenant_id),
    _: TokenData = Depends(require_permission(Permission.EEO_VIEW)),  # Only HR admin can view
):
    """
    Get EEO response for a specific application.

    Restricted to HR admins only - EEO data should not be visible during normal recruiting workflow.
    """
    client = get_supabase_client()

    response = await client.select(
        "eeo_responses",
        "*",
        filters={"application_id": str(application_id), "tenant_id": str(tenant_id)},
        single=True,
    )

    if not response:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="EEO response not found",
        )

    return EEOResponseResponse(
        id=UUID(response["id"]),
        application_id=UUID(response["application_id"]),
        gender=response.get("gender"),
        ethnicity=response.get("ethnicity"),
        veteran_status=response.get("veteran_status"),
        disability_status=response.get("disability_status"),
        collected_at=datetime.fromisoformat(response["collected_at"].replace("Z", "+00:00")),
    )


# EEO Summary Report
@router.get("/reports/summary", response_model=EEOSummaryReport)
async def get_eeo_summary_report(
    start_date: Optional[datetime] = Query(None, description="Start of date range"),
    end_date: Optional[datetime] = Query(None, description="End of date range"),
    requisition_id: Optional[UUID] = Query(None, description="Filter by requisition"),
    tenant_id: UUID = Depends(get_tenant_id),
    _: TokenData = Depends(require_permission(Permission.EEO_REPORTS)),
):
    """
    Generate EEO summary report.

    Shows aggregate statistics - individual responses are never shown.
    Restricted to HR admins only.
    """
    client = get_supabase_client()

    # Build filters
    filters = {"tenant_id": str(tenant_id)}

    # Get all EEO responses (optionally filtered by date)
    query_params = {"tenant_id": f"eq.{tenant_id}"}

    if start_date:
        query_params["collected_at"] = f"gte.{start_date.isoformat()}"
    if end_date:
        query_params["collected_at"] = f"lte.{end_date.isoformat()}"

    # Get EEO responses
    eeo_responses = await client.query(
        "eeo_responses",
        "*, applications!eeo_responses_application_id_fkey(requisition_id)",
        filters=filters,
    )

    # Filter by requisition if specified
    if requisition_id:
        eeo_responses = [
            r for r in eeo_responses
            if r.get("applications", {}).get("requisition_id") == str(requisition_id)
        ]

    # Get total applications count
    app_filters = {"tenant_id": str(tenant_id)}
    if requisition_id:
        app_filters["requisition_id"] = str(requisition_id)

    applications = await client.query("applications", "id", filters=app_filters)
    total_applications = len(applications)
    total_responses = len(eeo_responses)

    # Calculate response rate
    response_rate = (total_responses / total_applications * 100) if total_applications > 0 else 0

    # Helper to build category summary
    def build_category_summary(field: str, options: list[dict]) -> EEOCategorySummary:
        counts = {}
        for opt in options:
            counts[opt["value"]] = 0

        for response in eeo_responses:
            value = response.get(field)
            if value and value in counts:
                counts[value] += 1

        breakdown = []
        for opt in options:
            count = counts.get(opt["value"], 0)
            percentage = (count / total_responses * 100) if total_responses > 0 else 0
            breakdown.append(EEOSummaryByCategory(
                value=opt["value"],
                label=opt["label"],
                count=count,
                percentage=round(percentage, 2),
            ))

        return EEOCategorySummary(
            category=field,
            total_responses=total_responses,
            breakdown=breakdown,
        )

    form_options = EEOFormOptions()

    return EEOSummaryReport(
        report_date=datetime.now(timezone.utc),
        date_range_start=start_date,
        date_range_end=end_date,
        total_applications=total_applications,
        total_eeo_responses=total_responses,
        response_rate=round(response_rate, 2),
        gender_summary=build_category_summary("gender", form_options.gender_options),
        ethnicity_summary=build_category_summary("ethnicity", form_options.ethnicity_options),
        veteran_summary=build_category_summary("veteran_status", form_options.veteran_status_options),
        disability_summary=build_category_summary("disability_status", form_options.disability_status_options),
    )


# Adverse Impact Analysis
@router.get("/reports/adverse-impact", response_model=AdverseImpactReport)
async def get_adverse_impact_report(
    start_date: Optional[datetime] = Query(None),
    end_date: Optional[datetime] = Query(None),
    requisition_id: Optional[UUID] = Query(None),
    tenant_id: UUID = Depends(get_tenant_id),
    _: TokenData = Depends(require_permission(Permission.EEO_REPORTS)),
):
    """
    Generate adverse impact analysis report using the 4/5ths rule.

    The 4/5ths (80%) rule: If the selection rate for any group is less than
    80% of the selection rate of the group with the highest selection rate,
    there may be adverse impact.
    """
    client = get_supabase_client()

    # Get applications with EEO data and stage history
    filters = {"tenant_id": str(tenant_id)}
    if requisition_id:
        filters["requisition_id"] = str(requisition_id)

    # Get applications with their EEO responses
    applications = await client.query(
        "applications",
        "id, current_stage, status, eeo_responses(*)",
        filters=filters,
    )

    # Define key stages for analysis
    stage_transitions = [
        ("Applied", "Phone Screen"),
        ("Phone Screen", "Interview"),
        ("Interview", "Offer"),
        ("Offer", "Hired"),
    ]

    analyses = []
    warnings = []

    # Analyze by ethnicity (most common for OFCCP)
    ethnicity_options = EEOFormOptions().ethnicity_options

    for stage_from, stage_to in stage_transitions:
        # Count applicants and selections by ethnicity
        group_data = {}
        for opt in ethnicity_options:
            if opt["value"] == "prefer_not_to_say":
                continue
            group_data[opt["value"]] = {
                "label": opt["label"],
                "applicants": 0,
                "selected": 0,
            }

        for app in applications:
            eeo = app.get("eeo_responses")
            if not eeo or isinstance(eeo, list) and len(eeo) == 0:
                continue

            if isinstance(eeo, list):
                eeo = eeo[0]

            ethnicity = eeo.get("ethnicity")
            if not ethnicity or ethnicity == "prefer_not_to_say":
                continue

            if ethnicity not in group_data:
                continue

            # Check if applicant was at stage_from
            # (simplified - in production, check stage history)
            current_stage = app.get("current_stage", "Applied")
            status = app.get("status", "active")

            # Count as applicant for this transition
            group_data[ethnicity]["applicants"] += 1

            # Count as selected if they advanced past stage_to
            # (simplified logic - check if current stage is beyond stage_to)
            stage_order = ["Applied", "Phone Screen", "Interview", "Offer", "Hired"]
            if stage_to in stage_order:
                to_idx = stage_order.index(stage_to)
                if current_stage in stage_order:
                    current_idx = stage_order.index(current_stage)
                    if current_idx >= to_idx:
                        group_data[ethnicity]["selected"] += 1

        # Calculate selection rates
        rates = {}
        for group_key, data in group_data.items():
            if data["applicants"] > 0:
                rates[group_key] = {
                    "rate": data["selected"] / data["applicants"],
                    "applicants": data["applicants"],
                    "selected": data["selected"],
                    "label": data["label"],
                }

        if not rates:
            continue

        # Find reference group (highest selection rate)
        reference_group = max(rates.items(), key=lambda x: x[1]["rate"])
        reference_key = reference_group[0]
        reference_rate = reference_group[1]["rate"]

        if reference_rate == 0:
            continue

        # Calculate adverse impact for each group
        for group_key, data in rates.items():
            if group_key == reference_key:
                continue

            impact_ratio = data["rate"] / reference_rate if reference_rate > 0 else 0
            four_fifths_pass = impact_ratio >= 0.8

            analysis = AdverseImpactAnalysis(
                stage_from=stage_from,
                stage_to=stage_to,
                group_name=data["label"],
                group_applicants=data["applicants"],
                group_selected=data["selected"],
                group_selection_rate=round(data["rate"] * 100, 2),
                reference_group=rates[reference_key]["label"],
                reference_selection_rate=round(reference_rate * 100, 2),
                impact_ratio=round(impact_ratio, 3),
                four_fifths_rule_pass=four_fifths_pass,
            )
            analyses.append(analysis)

            if not four_fifths_pass and data["applicants"] >= 5:  # Minimum sample size
                warnings.append(
                    f"Potential adverse impact detected: {data['label']} has {round(impact_ratio * 100, 1)}% "
                    f"of the selection rate of {rates[reference_key]['label']} for {stage_from} → {stage_to}"
                )

    return AdverseImpactReport(
        report_date=datetime.now(timezone.utc),
        date_range_start=start_date,
        date_range_end=end_date,
        requisition_id=requisition_id,
        analyses=analyses,
        warnings=warnings,
    )


# Audit Log Endpoints
@router.get("/audit-log", response_model=AuditLogResponse)
async def get_audit_log(
    page: int = Query(1, ge=1),
    page_size: int = Query(50, ge=1, le=100),
    entity_type: Optional[str] = Query(None),
    entity_id: Optional[UUID] = Query(None),
    user_id: Optional[UUID] = Query(None),
    action_type: Optional[str] = Query(None),
    start_date: Optional[datetime] = Query(None),
    end_date: Optional[datetime] = Query(None),
    tenant_id: UUID = Depends(get_tenant_id),
    _: TokenData = Depends(require_permission(Permission.EEO_AUDIT)),
):
    """
    Query compliance audit log.

    All recruiting actions are logged for OFCCP compliance.
    """
    client = get_supabase_client()

    filters = {"tenant_id": str(tenant_id)}

    if entity_type:
        filters["entity_type"] = entity_type
    if entity_id:
        filters["entity_id"] = str(entity_id)
    if user_id:
        filters["user_id"] = str(user_id)
    if action_type:
        filters["action_type"] = action_type

    # Get total count
    all_logs = await client.query("compliance_audit_log", "id", filters=filters)
    total = len(all_logs)

    # Get paginated results
    offset = (page - 1) * page_size
    logs = await client.query(
        "compliance_audit_log",
        "*",
        filters=filters,
        order="created_at",
        order_desc=True,
        limit=page_size,
        offset=offset,
    )

    items = [
        AuditLogEntry(
            id=UUID(log["id"]),
            tenant_id=UUID(log["tenant_id"]),
            action_type=log["action_type"],
            entity_type=log["entity_type"],
            entity_id=UUID(log["entity_id"]),
            user_id=UUID(log["user_id"]),
            action_data=log.get("action_data", {}),
            ip_address=log.get("ip_address"),
            user_agent=log.get("user_agent"),
            created_at=datetime.fromisoformat(log["created_at"].replace("Z", "+00:00")),
        )
        for log in logs
    ]

    total_pages = (total + page_size - 1) // page_size

    return AuditLogResponse(
        items=items,
        total=total,
        page=page,
        page_size=page_size,
        total_pages=total_pages,
    )


# OFCCP Export
@router.get("/reports/ofccp-export")
async def export_ofccp_data(
    start_date: datetime = Query(...),
    end_date: datetime = Query(...),
    requisition_id: Optional[UUID] = Query(None),
    tenant_id: UUID = Depends(get_tenant_id),
    _: TokenData = Depends(require_permission(Permission.EEO_EXPORT)),
):
    """
    Export data in OFCCP-compliant format.

    Returns applicant flow data for federal contractor compliance reporting.
    """
    client = get_supabase_client()

    filters = {"tenant_id": str(tenant_id)}
    if requisition_id:
        filters["requisition_id"] = str(requisition_id)

    # Get applications with EEO data
    applications = await client.query(
        "applications",
        """
        id, applied_at, current_stage, status, disposition_reason_id,
        candidates!applications_candidate_id_fkey(first_name, last_name),
        job_requisitions!applications_requisition_id_fkey(requisition_number, external_title),
        eeo_responses(gender, ethnicity, veteran_status, disability_status)
        """,
        filters=filters,
    )

    # Format for OFCCP export
    export_data = []
    for app in applications:
        candidate = app.get("candidates") or {}
        job = app.get("job_requisitions") or {}
        eeo = app.get("eeo_responses") or {}

        if isinstance(eeo, list):
            eeo = eeo[0] if eeo else {}

        applied_at = app.get("applied_at")
        if applied_at:
            try:
                applied_dt = datetime.fromisoformat(applied_at.replace("Z", "+00:00"))
                if not (start_date <= applied_dt <= end_date):
                    continue
            except (ValueError, TypeError):
                pass

        export_data.append({
            "application_id": app["id"],
            "applied_date": app.get("applied_at"),
            "candidate_name": f"{candidate.get('first_name', '')} {candidate.get('last_name', '')}".strip(),
            "requisition_number": job.get("requisition_number"),
            "job_title": job.get("external_title"),
            "current_stage": app.get("current_stage"),
            "status": app.get("status"),
            "gender": eeo.get("gender"),
            "ethnicity": eeo.get("ethnicity"),
            "veteran_status": eeo.get("veteran_status"),
            "disability_status": eeo.get("disability_status"),
        })

    return {
        "export_date": datetime.now(timezone.utc).isoformat(),
        "date_range": {
            "start": start_date.isoformat(),
            "end": end_date.isoformat(),
        },
        "total_records": len(export_data),
        "data": export_data,
    }
