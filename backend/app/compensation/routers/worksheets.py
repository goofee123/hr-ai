"""Compensation Worksheets router - using Supabase REST API."""

import json
from datetime import datetime, timezone
from typing import Optional
from uuid import UUID

from fastapi import APIRouter, Depends, HTTPException, Query, status

from app.core.permissions import Permission, require_permission, require_any_permission
from app.core.security import TokenData, get_current_user
from app.core.supabase_client import get_supabase_client
from app.compensation.schemas import (
    WorksheetStatus,
    WorksheetEntryUpdate,
    WorksheetEntryResponse,
    WorksheetEntryListResponse,
    BulkWorksheetUpdate,
    WorksheetSubmitRequest,
    WorksheetTotals,
    WorksheetReviewRequest,
    BulkReviewRequest,
)
from app.shared.schemas.common import PaginatedResponse

router = APIRouter()


def parse_jsonb_fields(data: dict, fields: list) -> dict:
    """Parse JSONB fields that may come as strings from Supabase REST API."""
    result = data.copy()
    for field in fields:
        if field in result and isinstance(result[field], str):
            try:
                result[field] = json.loads(result[field])
            except (json.JSONDecodeError, TypeError):
                pass
    return result


def _build_entry_response(entry: dict, employee: dict) -> WorksheetEntryListResponse:
    """Build worksheet entry response with employee data."""
    return WorksheetEntryListResponse(
        id=entry["id"],
        cycle_id=entry["cycle_id"],
        scenario_id=entry.get("scenario_id"),
        employee_snapshot_id=entry["employee_snapshot_id"],
        # Employee info
        employee_id=employee.get("employee_id"),
        first_name=employee.get("first_name"),
        last_name=employee.get("last_name"),
        job_title=employee.get("job_title"),
        department=employee.get("department"),
        manager_name=employee.get("manager_name"),
        hire_date=employee.get("hire_date"),
        performance_score=employee.get("performance_score"),
        # Current compensation
        current_annual=employee.get("current_annual"),
        current_hourly_rate=employee.get("current_hourly_rate"),
        current_compa_ratio=employee.get("current_compa_ratio"),
        band_minimum=employee.get("band_minimum"),
        band_midpoint=employee.get("band_midpoint"),
        band_maximum=employee.get("band_maximum"),
        pay_grade=employee.get("pay_grade"),
        # System proposed
        system_raise_percent=entry.get("system_raise_percent"),
        system_raise_amount=entry.get("system_raise_amount"),
        system_new_salary=entry.get("system_new_salary"),
        system_bonus_percent=entry.get("system_bonus_percent"),
        system_bonus_amount=entry.get("system_bonus_amount"),
        # Manager input
        manager_raise_percent=entry.get("manager_raise_percent"),
        manager_raise_amount=entry.get("manager_raise_amount"),
        manager_new_salary=entry.get("manager_new_salary"),
        manager_bonus_percent=entry.get("manager_bonus_percent"),
        manager_bonus_amount=entry.get("manager_bonus_amount"),
        manager_promotion_flag=entry.get("manager_promotion_flag", False),
        manager_justification=entry.get("manager_justification"),
        manager_exception_flag=entry.get("manager_exception_flag", False),
        # Deltas
        delta_raise_percent=entry.get("delta_raise_percent"),
        delta_bonus_amount=entry.get("delta_bonus_amount"),
        # Status
        status=entry.get("status", "pending"),
        highlight_color=entry.get("highlight_color"),
        submitted_at=entry.get("submitted_at"),
        reviewed_at=entry.get("reviewed_at"),
        review_notes=entry.get("review_notes"),
    )


@router.get("", response_model=PaginatedResponse[WorksheetEntryListResponse])
async def list_worksheet_entries(
    cycle_id: UUID,
    page: int = Query(1, ge=1),
    page_size: int = Query(50, ge=1, le=200),
    department: Optional[str] = None,
    manager_id: Optional[str] = None,
    status_filter: Optional[str] = None,
    search: Optional[str] = None,
    current_user: TokenData = Depends(require_any_permission(
        Permission.COMPENSATION_VIEW, Permission.COMPENSATION_MANAGE
    )),
):
    """List worksheet entries for a cycle with filters."""
    client = get_supabase_client()

    # Get worksheet entries
    filters = {
        "tenant_id": str(current_user.tenant_id),
        "cycle_id": str(cycle_id),
    }
    if status_filter:
        filters["status"] = status_filter

    entries = await client.select("comp_worksheet_entries", "*", filters=filters) or []

    # Get all employee snapshots for this cycle to join with
    # First get the active dataset version
    cycle = await client.select(
        "comp_cycles",
        "*",
        filters={"id": str(cycle_id), "tenant_id": str(current_user.tenant_id)},
        single=True,
    )
    if not cycle:
        raise HTTPException(status_code=404, detail="Cycle not found")

    # Get active dataset version
    versions = await client.select(
        "comp_dataset_versions",
        "id",
        filters={"cycle_id": str(cycle_id), "is_active": "true"},
    ) or []

    if not versions:
        return PaginatedResponse.create(items=[], total=0, page=page, page_size=page_size)

    # Get employee snapshots
    employee_ids = [e["employee_snapshot_id"] for e in entries]
    employees_map = {}
    if employee_ids:
        for emp_id in employee_ids:
            emp = await client.select(
                "comp_employee_snapshots",
                "*",
                filters={"id": emp_id},
                single=True,
            )
            if emp:
                employees_map[emp_id] = emp

    # Build response with joined data
    items = []
    for entry in entries:
        employee = employees_map.get(entry["employee_snapshot_id"], {})

        # Apply filters
        if department and employee.get("department") != department:
            continue
        if manager_id and employee.get("manager_employee_id") != manager_id:
            continue
        if search:
            search_lower = search.lower()
            full_name = f"{employee.get('first_name', '')} {employee.get('last_name', '')}".lower()
            if search_lower not in full_name and search_lower not in employee.get("employee_id", "").lower():
                continue

        items.append(_build_entry_response(entry, employee))

    total = len(items)

    # Sort by department, then last name
    items.sort(key=lambda x: (x.department or "", x.last_name or ""))

    # Apply pagination
    offset = (page - 1) * page_size
    items = items[offset:offset + page_size]

    return PaginatedResponse.create(
        items=items,
        total=total,
        page=page,
        page_size=page_size,
    )


@router.get("/my-team", response_model=PaginatedResponse[WorksheetEntryListResponse])
async def get_my_team_worksheet(
    cycle_id: UUID,
    page: int = Query(1, ge=1),
    page_size: int = Query(50, ge=1, le=200),
    current_user: TokenData = Depends(get_current_user),
):
    """Get worksheet entries for the current user's direct reports."""
    client = get_supabase_client()

    # Get user's employee ID (would be linked via user profile in real system)
    user = await client.select(
        "users",
        "employee_id",
        filters={"id": str(current_user.user_id)},
        single=True,
    )

    if not user or not user.get("employee_id"):
        return PaginatedResponse.create(items=[], total=0, page=page, page_size=page_size)

    manager_employee_id = user["employee_id"]

    # Get active dataset version
    versions = await client.select(
        "comp_dataset_versions",
        "id",
        filters={"cycle_id": str(cycle_id), "is_active": "true"},
    ) or []

    if not versions:
        return PaginatedResponse.create(items=[], total=0, page=page, page_size=page_size)

    dataset_version_id = versions[0]["id"]

    # Get employees who report to this manager
    employees = await client.select(
        "comp_employee_snapshots",
        "*",
        filters={
            "dataset_version_id": dataset_version_id,
            "manager_employee_id": manager_employee_id,
        },
    ) or []

    if not employees:
        return PaginatedResponse.create(items=[], total=0, page=page, page_size=page_size)

    # Get worksheet entries for these employees
    employee_ids = [e["id"] for e in employees]
    employees_map = {e["id"]: e for e in employees}

    entries = await client.select(
        "comp_worksheet_entries",
        "*",
        filters={"cycle_id": str(cycle_id)},
    ) or []

    # Filter to only direct reports
    items = []
    for entry in entries:
        if entry["employee_snapshot_id"] in employees_map:
            employee = employees_map[entry["employee_snapshot_id"]]
            items.append(_build_entry_response(entry, employee))

    total = len(items)

    # Sort by last name
    items.sort(key=lambda x: x.last_name or "")

    # Apply pagination
    offset = (page - 1) * page_size
    items = items[offset:offset + page_size]

    return PaginatedResponse.create(
        items=items,
        total=total,
        page=page,
        page_size=page_size,
    )


@router.get("/totals", response_model=WorksheetTotals)
async def get_worksheet_totals(
    cycle_id: UUID,
    department: Optional[str] = None,
    current_user: TokenData = Depends(require_permission(Permission.COMPENSATION_VIEW)),
):
    """Get aggregated totals for worksheet entries."""
    client = get_supabase_client()

    # Get all entries
    entries = await client.select(
        "comp_worksheet_entries",
        "*",
        filters={"cycle_id": str(cycle_id), "tenant_id": str(current_user.tenant_id)},
    ) or []

    # Get employee data for department filtering
    employee_ids = [e["employee_snapshot_id"] for e in entries]
    employees_map = {}

    for emp_id in employee_ids:
        emp = await client.select(
            "comp_employee_snapshots",
            "*",
            filters={"id": emp_id},
            single=True,
        )
        if emp:
            employees_map[emp_id] = emp

    # Calculate totals
    total_current_payroll = 0
    total_system_increase = 0
    total_manager_increase = 0
    total_bonus_amount = 0
    employee_count = 0
    pending_count = 0
    submitted_count = 0
    approved_count = 0
    flagged_count = 0

    for entry in entries:
        employee = employees_map.get(entry["employee_snapshot_id"], {})

        # Department filter
        if department and employee.get("department") != department:
            continue

        employee_count += 1
        current_annual = float(employee.get("current_annual") or 0)
        total_current_payroll += current_annual

        # System increases
        system_amount = float(entry.get("system_raise_amount") or 0)
        total_system_increase += system_amount

        # Manager increases (use manager value if set, otherwise system)
        manager_amount = entry.get("manager_raise_amount")
        if manager_amount is not None:
            total_manager_increase += float(manager_amount)
        else:
            total_manager_increase += system_amount

        # Bonus
        bonus = entry.get("manager_bonus_amount") or entry.get("system_bonus_amount") or 0
        total_bonus_amount += float(bonus)

        # Status counts
        status = entry.get("status", "pending")
        if status == "pending":
            pending_count += 1
        elif status == "submitted":
            submitted_count += 1
        elif status == "approved":
            approved_count += 1
        elif status == "flagged":
            flagged_count += 1

    # Calculate percentages
    system_increase_percent = (total_system_increase / total_current_payroll * 100) if total_current_payroll > 0 else 0
    manager_increase_percent = (total_manager_increase / total_current_payroll * 100) if total_current_payroll > 0 else 0

    return WorksheetTotals(
        total_current_payroll=total_current_payroll,
        total_system_increase=total_system_increase,
        total_manager_increase=total_manager_increase,
        total_bonus_amount=total_bonus_amount,
        system_increase_percent=system_increase_percent,
        manager_increase_percent=manager_increase_percent,
        employee_count=employee_count,
        pending_count=pending_count,
        submitted_count=submitted_count,
        approved_count=approved_count,
        flagged_count=flagged_count,
    )


@router.get("/{entry_id}", response_model=WorksheetEntryResponse)
async def get_worksheet_entry(
    entry_id: UUID,
    current_user: TokenData = Depends(require_permission(Permission.COMPENSATION_VIEW)),
):
    """Get a specific worksheet entry."""
    client = get_supabase_client()

    entry = await client.select(
        "comp_worksheet_entries",
        "*",
        filters={"id": str(entry_id), "tenant_id": str(current_user.tenant_id)},
        single=True,
    )

    if not entry:
        raise HTTPException(status_code=404, detail="Worksheet entry not found")

    return WorksheetEntryResponse.model_validate(entry)


@router.patch("/{entry_id}", response_model=WorksheetEntryResponse)
async def update_worksheet_entry(
    entry_id: UUID,
    update_data: WorksheetEntryUpdate,
    current_user: TokenData = Depends(require_permission(Permission.COMPENSATION_MANAGE)),
):
    """Update a worksheet entry (manager input)."""
    client = get_supabase_client()

    # Get current entry
    entry = await client.select(
        "comp_worksheet_entries",
        "*",
        filters={"id": str(entry_id), "tenant_id": str(current_user.tenant_id)},
        single=True,
    )

    if not entry:
        raise HTTPException(status_code=404, detail="Worksheet entry not found")

    # Check status allows updates
    if entry["status"] in ["approved", "rejected"]:
        raise HTTPException(
            status_code=400,
            detail="Cannot update entry that has been approved or rejected"
        )

    # Prepare update
    update_dict = update_data.model_dump(exclude_unset=True)

    # Calculate deltas if manager values are being set
    if "manager_raise_percent" in update_dict:
        system_percent = entry.get("system_raise_percent") or 0
        manager_percent = update_dict["manager_raise_percent"] or 0
        update_dict["delta_raise_percent"] = float(manager_percent) - float(system_percent)

    if "manager_bonus_amount" in update_dict:
        system_bonus = entry.get("system_bonus_amount") or 0
        manager_bonus = update_dict["manager_bonus_amount"] or 0
        update_dict["delta_bonus_amount"] = float(manager_bonus) - float(system_bonus)

    # Calculate new salary if raise is provided
    if "manager_raise_percent" in update_dict and update_dict["manager_raise_percent"] is not None:
        employee = await client.select(
            "comp_employee_snapshots",
            "current_annual",
            filters={"id": entry["employee_snapshot_id"]},
            single=True,
        )
        if employee:
            current = float(employee.get("current_annual") or 0)
            new_salary = current * (1 + float(update_dict["manager_raise_percent"]) / 100)
            update_dict["manager_new_salary"] = new_salary
            update_dict["manager_raise_amount"] = new_salary - current

    if update_dict:
        update_dict["updated_at"] = datetime.now(timezone.utc).isoformat()

        entry = await client.update(
            "comp_worksheet_entries",
            update_dict,
            filters={"id": str(entry_id)},
        )

    # Log audit
    await client.insert("comp_audit_log", {
        "tenant_id": str(current_user.tenant_id),
        "entity_type": "worksheet_entry",
        "entity_id": str(entry_id),
        "action": "update",
        "user_id": str(current_user.user_id),
        "new_values": json.dumps(update_dict),
    })

    return WorksheetEntryResponse.model_validate(entry)


@router.post("/bulk-update", response_model=dict)
async def bulk_update_worksheet_entries(
    bulk_update: BulkWorksheetUpdate,
    current_user: TokenData = Depends(require_permission(Permission.COMPENSATION_MANAGE)),
):
    """Bulk update multiple worksheet entries."""
    client = get_supabase_client()

    updated_count = 0
    errors = []

    for entry_id in bulk_update.entry_ids:
        try:
            entry = await client.select(
                "comp_worksheet_entries",
                "*",
                filters={"id": str(entry_id), "tenant_id": str(current_user.tenant_id)},
                single=True,
            )

            if not entry:
                errors.append({"entry_id": str(entry_id), "error": "Not found"})
                continue

            if entry["status"] in ["approved", "rejected"]:
                errors.append({"entry_id": str(entry_id), "error": "Cannot update approved/rejected entry"})
                continue

            update_dict = {}
            if bulk_update.raise_percent is not None:
                update_dict["manager_raise_percent"] = bulk_update.raise_percent

                # Calculate amounts
                employee = await client.select(
                    "comp_employee_snapshots",
                    "current_annual",
                    filters={"id": entry["employee_snapshot_id"]},
                    single=True,
                )
                if employee:
                    current = float(employee.get("current_annual") or 0)
                    new_salary = current * (1 + float(bulk_update.raise_percent) / 100)
                    update_dict["manager_new_salary"] = new_salary
                    update_dict["manager_raise_amount"] = new_salary - current

                # Delta
                system_percent = entry.get("system_raise_percent") or 0
                update_dict["delta_raise_percent"] = float(bulk_update.raise_percent) - float(system_percent)

            if bulk_update.bonus_percent is not None:
                update_dict["manager_bonus_percent"] = bulk_update.bonus_percent

            if bulk_update.highlight_color is not None:
                update_dict["highlight_color"] = bulk_update.highlight_color

            if update_dict:
                update_dict["updated_at"] = datetime.now(timezone.utc).isoformat()
                await client.update(
                    "comp_worksheet_entries",
                    update_dict,
                    filters={"id": str(entry_id)},
                )
                updated_count += 1

        except Exception as e:
            errors.append({"entry_id": str(entry_id), "error": str(e)})

    return {
        "updated_count": updated_count,
        "error_count": len(errors),
        "errors": errors if errors else None,
    }


@router.post("/submit", response_model=dict)
async def submit_worksheet_entries(
    submit_request: WorksheetSubmitRequest,
    current_user: TokenData = Depends(require_permission(Permission.COMPENSATION_MANAGE)),
):
    """Submit worksheet entries for review."""
    client = get_supabase_client()

    now = datetime.now(timezone.utc).isoformat()
    submitted_count = 0
    errors = []

    for entry_id in submit_request.entry_ids:
        try:
            entry = await client.select(
                "comp_worksheet_entries",
                "*",
                filters={"id": str(entry_id), "tenant_id": str(current_user.tenant_id)},
                single=True,
            )

            if not entry:
                errors.append({"entry_id": str(entry_id), "error": "Not found"})
                continue

            if entry["status"] != "pending":
                errors.append({"entry_id": str(entry_id), "error": f"Cannot submit entry with status {entry['status']}"})
                continue

            await client.update(
                "comp_worksheet_entries",
                {
                    "status": "submitted",
                    "submitted_by": str(current_user.user_id),
                    "submitted_at": now,
                    "updated_at": now,
                },
                filters={"id": str(entry_id)},
            )

            # Log audit
            await client.insert("comp_audit_log", {
                "tenant_id": str(current_user.tenant_id),
                "entity_type": "worksheet_entry",
                "entity_id": str(entry_id),
                "action": "submit",
                "user_id": str(current_user.user_id),
            })

            submitted_count += 1

        except Exception as e:
            errors.append({"entry_id": str(entry_id), "error": str(e)})

    return {
        "submitted_count": submitted_count,
        "error_count": len(errors),
        "errors": errors if errors else None,
    }


@router.post("/{entry_id}/review", response_model=WorksheetEntryResponse)
async def review_worksheet_entry(
    entry_id: UUID,
    review: WorksheetReviewRequest,
    current_user: TokenData = Depends(require_permission(Permission.COMPENSATION_MANAGE)),
):
    """Approve or reject a worksheet entry."""
    client = get_supabase_client()

    entry = await client.select(
        "comp_worksheet_entries",
        "*",
        filters={"id": str(entry_id), "tenant_id": str(current_user.tenant_id)},
        single=True,
    )

    if not entry:
        raise HTTPException(status_code=404, detail="Worksheet entry not found")

    if entry["status"] not in ["submitted", "flagged"]:
        raise HTTPException(
            status_code=400,
            detail=f"Cannot review entry with status {entry['status']}"
        )

    now = datetime.now(timezone.utc).isoformat()

    update_dict = {
        "status": review.decision,
        "reviewed_by": str(current_user.user_id),
        "reviewed_at": now,
        "review_notes": review.notes,
        "updated_at": now,
    }

    if review.decision == "approved":
        update_dict["approved_by"] = str(current_user.user_id)
        update_dict["approved_at"] = now
        update_dict["approval_notes"] = review.notes

    entry = await client.update(
        "comp_worksheet_entries",
        update_dict,
        filters={"id": str(entry_id)},
    )

    # Log audit
    await client.insert("comp_audit_log", {
        "tenant_id": str(current_user.tenant_id),
        "entity_type": "worksheet_entry",
        "entity_id": str(entry_id),
        "action": f"review_{review.decision}",
        "user_id": str(current_user.user_id),
        "new_values": json.dumps({"notes": review.notes}),
    })

    return WorksheetEntryResponse.model_validate(entry)


@router.post("/bulk-review", response_model=dict)
async def bulk_review_worksheet_entries(
    bulk_review: BulkReviewRequest,
    current_user: TokenData = Depends(require_permission(Permission.COMPENSATION_MANAGE)),
):
    """Bulk approve or reject worksheet entries."""
    client = get_supabase_client()

    now = datetime.now(timezone.utc).isoformat()
    reviewed_count = 0
    errors = []

    for entry_id in bulk_review.entry_ids:
        try:
            entry = await client.select(
                "comp_worksheet_entries",
                "*",
                filters={"id": str(entry_id), "tenant_id": str(current_user.tenant_id)},
                single=True,
            )

            if not entry:
                errors.append({"entry_id": str(entry_id), "error": "Not found"})
                continue

            if entry["status"] not in ["submitted", "flagged"]:
                errors.append({"entry_id": str(entry_id), "error": f"Cannot review entry with status {entry['status']}"})
                continue

            update_dict = {
                "status": bulk_review.decision,
                "reviewed_by": str(current_user.user_id),
                "reviewed_at": now,
                "review_notes": bulk_review.notes,
                "updated_at": now,
            }

            if bulk_review.decision == "approved":
                update_dict["approved_by"] = str(current_user.user_id)
                update_dict["approved_at"] = now

            await client.update(
                "comp_worksheet_entries",
                update_dict,
                filters={"id": str(entry_id)},
            )

            reviewed_count += 1

        except Exception as e:
            errors.append({"entry_id": str(entry_id), "error": str(e)})

    return {
        "reviewed_count": reviewed_count,
        "error_count": len(errors),
        "errors": errors if errors else None,
    }
