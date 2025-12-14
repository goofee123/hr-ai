"""Compensation Cycles router - using Supabase REST API."""

import json
from datetime import datetime, timezone
from typing import Optional
from uuid import UUID

from fastapi import APIRouter, Depends, HTTPException, Query, status

from app.core.permissions import Permission, require_permission, require_any_permission
from app.core.security import TokenData, get_current_user
from app.core.supabase_client import get_supabase_client
from app.compensation.schemas import (
    CompCycleCreate,
    CompCycleUpdate,
    CompCycleResponse,
    CompCycleListResponse,
    CycleStatusUpdate,
    CycleLaunchRequest,
    CycleStatus,
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


@router.get("", response_model=PaginatedResponse[CompCycleListResponse])
async def list_cycles(
    page: int = Query(1, ge=1),
    page_size: int = Query(20, ge=1, le=100),
    status: Optional[str] = None,
    fiscal_year: Optional[int] = None,
    current_user: TokenData = Depends(require_any_permission(
        Permission.COMPENSATION_VIEW, Permission.COMPENSATION_MANAGE
    )),
):
    """List compensation cycles with filters and pagination."""
    client = get_supabase_client()

    # Build filters
    filters = {"tenant_id": str(current_user.tenant_id)}
    if status:
        filters["status"] = status
    if fiscal_year:
        filters["year"] = str(fiscal_year)

    # Get all cycles
    cycles = await client.select("comp_cycles", "*", filters=filters) or []

    # Get total count before pagination
    total = len(cycles)

    # Sort by created_at descending
    cycles.sort(key=lambda x: x.get("created_at", ""), reverse=True)

    # Apply pagination
    offset = (page - 1) * page_size
    cycles = cycles[offset:offset + page_size]

    # Get employee and scenario counts for each cycle
    items = []
    for cycle in cycles:
        cycle = parse_jsonb_fields(cycle, ["department_ids"])

        # Get employee count from active dataset version
        employee_count = 0
        try:
            versions = await client.select(
                "comp_dataset_versions",
                "id",
                filters={"cycle_id": cycle["id"], "is_active": "true"},
            ) or []
            if versions:
                snapshots = await client.select(
                    "comp_employee_snapshots",
                    "id",
                    filters={"dataset_version_id": versions[0]["id"]},
                ) or []
                employee_count = len(snapshots)
        except Exception:
            # If is_active column doesn't exist or table missing, skip
            employee_count = 0

        # Get scenario count
        scenario_count = 0
        try:
            scenarios = await client.select(
                "comp_scenarios",
                "id",
                filters={"cycle_id": cycle["id"]},
            ) or []
            scenario_count = len(scenarios)
        except Exception:
            pass

        response = CompCycleListResponse.model_validate(cycle)
        response.employee_count = employee_count
        response.scenario_count = scenario_count
        items.append(response)

    return PaginatedResponse.create(
        items=items,
        total=total,
        page=page,
        page_size=page_size,
    )


@router.post("", response_model=CompCycleResponse, status_code=status.HTTP_201_CREATED)
async def create_cycle(
    cycle_data: CompCycleCreate,
    current_user: TokenData = Depends(require_permission(Permission.COMPENSATION_MANAGE)),
):
    """Create a new compensation cycle."""
    client = get_supabase_client()

    # Prepare cycle data - matching actual DB schema
    cycle_dict = {
        "tenant_id": str(current_user.tenant_id),
        "name": cycle_data.name,
        "year": cycle_data.fiscal_year,  # DB column is 'year' not 'fiscal_year'
        "cycle_type": cycle_data.cycle_type,
        "effective_date": cycle_data.effective_date.isoformat(),
        "planning_start_date": cycle_data.planning_start_date.isoformat() if cycle_data.planning_start_date else None,
        "manager_input_start": cycle_data.manager_input_start.isoformat() if cycle_data.manager_input_start else None,
        "manager_input_deadline": cycle_data.manager_input_deadline.isoformat() if cycle_data.manager_input_deadline else None,
        "hr_review_deadline": cycle_data.hr_review_deadline.isoformat() if cycle_data.hr_review_deadline else None,
        "total_budget_amount": float(cycle_data.total_budget_amount) if cycle_data.total_budget_amount else None,
        "status": CycleStatus.DRAFT,
        "created_by": str(current_user.user_id),
    }

    # Create cycle
    cycle = await client.insert("comp_cycles", cycle_dict)
    cycle = parse_jsonb_fields(cycle, ["department_ids"])

    return CompCycleResponse.model_validate(cycle)


@router.get("/{cycle_id}", response_model=CompCycleResponse)
async def get_cycle(
    cycle_id: UUID,
    current_user: TokenData = Depends(require_permission(Permission.COMPENSATION_VIEW)),
):
    """Get a compensation cycle by ID."""
    client = get_supabase_client()

    cycle = await client.select(
        "comp_cycles",
        "*",
        filters={"id": str(cycle_id), "tenant_id": str(current_user.tenant_id)},
        single=True,
    )

    if not cycle:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Compensation cycle not found",
        )

    cycle = parse_jsonb_fields(cycle, ["department_ids"])

    return CompCycleResponse.model_validate(cycle)


@router.patch("/{cycle_id}", response_model=CompCycleResponse)
async def update_cycle(
    cycle_id: UUID,
    cycle_data: CompCycleUpdate,
    current_user: TokenData = Depends(require_permission(Permission.COMPENSATION_MANAGE)),
):
    """Update a compensation cycle."""
    client = get_supabase_client()

    # Check cycle exists
    cycle = await client.select(
        "comp_cycles",
        "*",
        filters={"id": str(cycle_id), "tenant_id": str(current_user.tenant_id)},
        single=True,
    )

    if not cycle:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Compensation cycle not found",
        )

    # Apply updates
    update_data = cycle_data.model_dump(exclude_unset=True)
    if update_data:
        # Convert dates to ISO strings - matching actual DB column names
        for key in ["effective_date", "planning_start_date", "manager_input_start",
                    "manager_input_deadline", "hr_review_deadline"]:
            if key in update_data and update_data[key]:
                update_data[key] = update_data[key].isoformat()

        # Convert decimal
        if "total_budget_amount" in update_data and update_data["total_budget_amount"]:
            update_data["total_budget_amount"] = float(update_data["total_budget_amount"])

        update_data["updated_at"] = datetime.now(timezone.utc).isoformat()

        cycle = await client.update(
            "comp_cycles",
            update_data,
            filters={"id": str(cycle_id)},
        )

    cycle = parse_jsonb_fields(cycle, ["department_ids"])

    return CompCycleResponse.model_validate(cycle)


@router.post("/{cycle_id}/status", response_model=CompCycleResponse)
async def update_cycle_status(
    cycle_id: UUID,
    status_update: CycleStatusUpdate,
    current_user: TokenData = Depends(require_permission(Permission.COMPENSATION_MANAGE)),
):
    """Update compensation cycle status."""
    client = get_supabase_client()

    # Get current cycle
    cycle = await client.select(
        "comp_cycles",
        "*",
        filters={"id": str(cycle_id), "tenant_id": str(current_user.tenant_id)},
        single=True,
    )

    if not cycle:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Compensation cycle not found",
        )

    # Validate status transition
    valid_transitions = {
        CycleStatus.DRAFT: [CycleStatus.MODELING, CycleStatus.ARCHIVED],
        CycleStatus.MODELING: [CycleStatus.MANAGER_REVIEW, CycleStatus.DRAFT],
        CycleStatus.MANAGER_REVIEW: [CycleStatus.EXECUTIVE_REVIEW, CycleStatus.MODELING],
        CycleStatus.EXECUTIVE_REVIEW: [CycleStatus.COMP_QA, CycleStatus.MANAGER_REVIEW],
        CycleStatus.COMP_QA: [CycleStatus.APPROVED, CycleStatus.EXECUTIVE_REVIEW],
        CycleStatus.APPROVED: [CycleStatus.EXPORTED],
        CycleStatus.EXPORTED: [CycleStatus.ARCHIVED],
    }

    current_status = cycle["status"]
    new_status = status_update.status

    if new_status not in valid_transitions.get(current_status, []):
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=f"Invalid status transition from {current_status} to {new_status}",
        )

    # Prepare update
    now = datetime.now(timezone.utc).isoformat()
    update_data = {
        "status": new_status,
        "updated_at": now,
    }

    cycle = await client.update(
        "comp_cycles",
        update_data,
        filters={"id": str(cycle_id)},
    )

    cycle = parse_jsonb_fields(cycle, ["department_ids"])

    return CompCycleResponse.model_validate(cycle)


@router.post("/{cycle_id}/launch", response_model=CompCycleResponse)
async def launch_cycle(
    cycle_id: UUID,
    launch_request: CycleLaunchRequest,
    current_user: TokenData = Depends(require_permission(Permission.COMPENSATION_MANAGE)),
):
    """Launch a cycle to manager review phase.

    This:
    1. Selects the specified scenario
    2. Creates worksheet entries for all employees based on scenario results
    3. Transitions cycle to manager_review status
    """
    client = get_supabase_client()

    # Get cycle
    cycle = await client.select(
        "comp_cycles",
        "*",
        filters={"id": str(cycle_id), "tenant_id": str(current_user.tenant_id)},
        single=True,
    )

    if not cycle:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Compensation cycle not found",
        )

    if cycle["status"] != CycleStatus.MODELING:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Cycle must be in modeling status to launch",
        )

    # Verify scenario exists and belongs to this cycle
    scenario = await client.select(
        "comp_scenarios",
        "*",
        filters={"id": str(launch_request.scenario_id), "cycle_id": str(cycle_id)},
        single=True,
    )

    if not scenario:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Scenario not found or does not belong to this cycle",
        )

    if scenario["status"] != "calculated":
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Scenario must be calculated before launching",
        )

    # Mark scenario as selected
    now = datetime.now(timezone.utc).isoformat()
    await client.update(
        "comp_scenarios",
        {
            "is_selected": True,
            "selected_by": str(current_user.user_id),
            "selected_at": now,
        },
        filters={"id": str(launch_request.scenario_id)},
    )

    # Get scenario results
    results = await client.select(
        "comp_scenario_results",
        "*",
        filters={"scenario_id": str(launch_request.scenario_id)},
    ) or []

    # Create worksheet entries
    for result in results:
        worksheet_entry = {
            "tenant_id": str(current_user.tenant_id),
            "cycle_id": str(cycle_id),
            "scenario_id": str(launch_request.scenario_id),
            "employee_snapshot_id": result["employee_snapshot_id"],
            "system_raise_percent": result.get("recommended_raise_percent"),
            "system_raise_amount": result.get("recommended_raise_amount"),
            "system_new_salary": result.get("recommended_new_salary"),
            "system_bonus_percent": result.get("recommended_bonus_percent"),
            "system_bonus_amount": result.get("recommended_bonus_amount"),
            "status": "pending",
        }
        await client.insert("comp_worksheet_entries", worksheet_entry)

    # Update cycle status
    cycle = await client.update(
        "comp_cycles",
        {
            "status": CycleStatus.MANAGER_REVIEW,
            "updated_at": now,
        },
        filters={"id": str(cycle_id)},
    )

    cycle = parse_jsonb_fields(cycle, ["department_ids"])

    return CompCycleResponse.model_validate(cycle)


@router.delete("/{cycle_id}", status_code=status.HTTP_204_NO_CONTENT)
async def delete_cycle(
    cycle_id: UUID,
    current_user: TokenData = Depends(require_permission(Permission.COMPENSATION_MANAGE)),
):
    """Delete (archive) a compensation cycle."""
    client = get_supabase_client()

    # Check cycle exists
    cycle = await client.select(
        "comp_cycles",
        "*",
        filters={"id": str(cycle_id), "tenant_id": str(current_user.tenant_id)},
        single=True,
    )

    if not cycle:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Compensation cycle not found",
        )

    # Only allow deletion of draft cycles
    if cycle["status"] != CycleStatus.DRAFT:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Only draft cycles can be deleted",
        )

    # Soft delete by archiving
    now = datetime.now(timezone.utc).isoformat()
    await client.update(
        "comp_cycles",
        {"status": CycleStatus.ARCHIVED, "updated_at": now},
        filters={"id": str(cycle_id)},
    )

    return None


# =============================================================================
# NESTED SCENARIO ROUTES (for convenience - /cycles/{id}/scenarios)
# =============================================================================

from app.compensation.schemas import ScenarioCreate, ScenarioResponse


@router.get("/{cycle_id}/scenarios", response_model=list[ScenarioResponse])
async def list_cycle_scenarios(
    cycle_id: UUID,
    current_user: TokenData = Depends(require_any_permission(
        Permission.COMPENSATION_VIEW, Permission.COMPENSATION_MANAGE
    )),
):
    """List scenarios for a specific cycle."""
    client = get_supabase_client()

    # Verify cycle exists and belongs to tenant
    cycle = await client.select(
        "comp_cycles",
        "id",
        filters={"id": str(cycle_id), "tenant_id": str(current_user.tenant_id)},
        single=True,
    )

    if not cycle:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Compensation cycle not found",
        )

    scenarios = await client.select(
        "comp_scenarios",
        "*",
        filters={"cycle_id": str(cycle_id)},
    ) or []

    scenarios.sort(key=lambda x: x.get("created_at", ""), reverse=True)

    return [ScenarioResponse.model_validate(s) for s in scenarios]


@router.post("/{cycle_id}/scenarios", response_model=ScenarioResponse, status_code=status.HTTP_201_CREATED)
async def create_cycle_scenario(
    cycle_id: UUID,
    scenario_data: ScenarioCreate,
    current_user: TokenData = Depends(require_permission(Permission.COMPENSATION_MANAGE)),
):
    """Create a scenario for a specific cycle."""
    client = get_supabase_client()

    # Verify cycle exists and belongs to tenant
    cycle = await client.select(
        "comp_cycles",
        "*",
        filters={"id": str(cycle_id), "tenant_id": str(current_user.tenant_id)},
        single=True,
    )

    if not cycle:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Compensation cycle not found",
        )

    # Override cycle_id from path
    scenario_dict = {
        "tenant_id": str(current_user.tenant_id),
        "cycle_id": str(cycle_id),
        "name": scenario_data.name,
        "description": scenario_data.description,
        "rule_set_id": str(scenario_data.rule_set_id) if scenario_data.rule_set_id else None,
        "base_merit_percent": float(scenario_data.base_merit_percent) if scenario_data.base_merit_percent else None,
        "base_bonus_percent": float(scenario_data.base_bonus_percent) if scenario_data.base_bonus_percent else None,
        "budget_target_percent": float(scenario_data.budget_target_percent) if scenario_data.budget_target_percent else None,
        "goal_description": scenario_data.goal_description,
        "status": "draft",
        "created_by": str(current_user.user_id),
    }

    scenario = await client.insert("comp_scenarios", scenario_dict)

    return ScenarioResponse.model_validate(scenario)
