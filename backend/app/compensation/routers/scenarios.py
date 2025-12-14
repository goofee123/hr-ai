"""Compensation Scenarios router - using Supabase REST API."""

import json
from datetime import datetime, timezone
from decimal import Decimal
from typing import Optional, List
from uuid import UUID

from fastapi import APIRouter, Depends, HTTPException, Query, status

from app.core.permissions import Permission, require_permission
from app.core.security import TokenData, get_current_user
from app.core.supabase_client import get_supabase_client
from app.compensation.schemas import (
    ScenarioCreate,
    ScenarioUpdate,
    ScenarioResponse,
    ScenarioSummary,
    ScenarioResultResponse,
    ScenarioCompareRequest,
    ScenarioCompareResponse,
    CalculateScenarioRequest,
    ScenarioStatus,
)
from app.compensation.services.rules_engine import get_rules_engine
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


@router.get("", response_model=list[ScenarioResponse])
async def list_scenarios(
    cycle_id: UUID,
    current_user: TokenData = Depends(require_permission(Permission.COMPENSATION_VIEW)),
):
    """List scenarios for a cycle."""
    client = get_supabase_client()

    # Verify cycle exists
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


@router.post("", response_model=ScenarioResponse, status_code=status.HTTP_201_CREATED)
async def create_scenario(
    scenario_data: ScenarioCreate,
    current_user: TokenData = Depends(require_permission(Permission.COMPENSATION_MANAGE)),
):
    """Create a new scenario."""
    client = get_supabase_client()

    # Verify cycle exists
    cycle = await client.select(
        "comp_cycles",
        "*",
        filters={"id": str(scenario_data.cycle_id), "tenant_id": str(current_user.tenant_id)},
        single=True,
    )

    if not cycle:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Compensation cycle not found",
        )

    # Verify rule set exists if provided
    if scenario_data.rule_set_id:
        rule_set = await client.select(
            "comp_rule_sets",
            "id",
            filters={"id": str(scenario_data.rule_set_id), "tenant_id": str(current_user.tenant_id)},
            single=True,
        )
        if not rule_set:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail="Rule set not found",
            )

    scenario_dict = {
        "tenant_id": str(current_user.tenant_id),
        "cycle_id": str(scenario_data.cycle_id),
        "name": scenario_data.name,
        "description": scenario_data.description,
        "rule_set_id": str(scenario_data.rule_set_id) if scenario_data.rule_set_id else None,
        "base_merit_percent": float(scenario_data.base_merit_percent) if scenario_data.base_merit_percent else None,
        "base_bonus_percent": float(scenario_data.base_bonus_percent) if scenario_data.base_bonus_percent else None,
        "budget_target_percent": float(scenario_data.budget_target_percent) if scenario_data.budget_target_percent else None,
        "goal_description": scenario_data.goal_description,
        "status": ScenarioStatus.DRAFT,
        "created_by": str(current_user.user_id),
    }

    scenario = await client.insert("comp_scenarios", scenario_dict)

    return ScenarioResponse.model_validate(scenario)


@router.get("/{scenario_id}", response_model=ScenarioResponse)
async def get_scenario(
    scenario_id: UUID,
    current_user: TokenData = Depends(require_permission(Permission.COMPENSATION_VIEW)),
):
    """Get a scenario by ID."""
    client = get_supabase_client()

    scenario = await client.select(
        "comp_scenarios",
        "*",
        filters={"id": str(scenario_id), "tenant_id": str(current_user.tenant_id)},
        single=True,
    )

    if not scenario:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Scenario not found",
        )

    return ScenarioResponse.model_validate(scenario)


@router.patch("/{scenario_id}", response_model=ScenarioResponse)
async def update_scenario(
    scenario_id: UUID,
    scenario_data: ScenarioUpdate,
    current_user: TokenData = Depends(require_permission(Permission.COMPENSATION_MANAGE)),
):
    """Update a scenario."""
    client = get_supabase_client()

    scenario = await client.select(
        "comp_scenarios",
        "*",
        filters={"id": str(scenario_id), "tenant_id": str(current_user.tenant_id)},
        single=True,
    )

    if not scenario:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Scenario not found",
        )

    update_data = scenario_data.model_dump(exclude_unset=True)

    # Convert decimals
    for key in ["base_merit_percent", "base_bonus_percent", "budget_target_percent"]:
        if key in update_data and update_data[key]:
            update_data[key] = float(update_data[key])

    if "rule_set_id" in update_data and update_data["rule_set_id"]:
        update_data["rule_set_id"] = str(update_data["rule_set_id"])

    if update_data:
        update_data["updated_at"] = datetime.now(timezone.utc).isoformat()
        scenario = await client.update(
            "comp_scenarios",
            update_data,
            filters={"id": str(scenario_id)},
        )

    return ScenarioResponse.model_validate(scenario)


@router.post("/{scenario_id}/calculate", response_model=ScenarioResponse)
async def calculate_scenario(
    scenario_id: UUID,
    request: CalculateScenarioRequest,
    current_user: TokenData = Depends(require_permission(Permission.COMPENSATION_MANAGE)),
):
    """Calculate/recalculate scenario results for all employees."""
    client = get_supabase_client()

    scenario = await client.select(
        "comp_scenarios",
        "*",
        filters={"id": str(scenario_id), "tenant_id": str(current_user.tenant_id)},
        single=True,
    )

    if not scenario:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Scenario not found",
        )

    # Check if already calculated and not forcing recalculation
    if scenario["status"] == ScenarioStatus.CALCULATED and not request.recalculate:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Scenario already calculated. Set recalculate=true to force recalculation.",
        )

    # Update status to calculating
    await client.update(
        "comp_scenarios",
        {"status": ScenarioStatus.CALCULATING},
        filters={"id": str(scenario_id)},
    )

    # Get cycle and active dataset
    cycle = await client.select(
        "comp_cycles",
        "*",
        filters={"id": scenario["cycle_id"]},
        single=True,
    )

    dataset_version = await client.select(
        "comp_dataset_versions",
        "*",
        filters={"cycle_id": scenario["cycle_id"], "is_active": "true"},
        single=True,
    )

    if not dataset_version:
        await client.update(
            "comp_scenarios",
            {"status": ScenarioStatus.DRAFT},
            filters={"id": str(scenario_id)},
        )
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="No active dataset version for this cycle. Import employee data first.",
        )

    # Get employees
    employees = await client.select(
        "comp_employee_snapshots",
        "*",
        filters={"dataset_version_id": dataset_version["id"]},
    ) or []

    # Get rules if rule set specified
    rules = []
    if scenario.get("rule_set_id"):
        rules = await client.select(
            "comp_rules",
            "*",
            filters={"rule_set_id": scenario["rule_set_id"], "is_active": "true"},
        ) or []
        # Parse JSONB
        for rule in rules:
            rule = parse_jsonb_fields(rule, ["conditions", "actions"])

    # Delete existing results if recalculating
    if request.recalculate:
        existing_results = await client.select(
            "comp_scenario_results",
            "id",
            filters={"scenario_id": str(scenario_id)},
        ) or []
        for result in existing_results:
            await client.delete("comp_scenario_results", filters={"id": result["id"]})

    # Process each employee through rules engine
    engine = get_rules_engine()
    total_current_payroll = Decimal("0")
    total_recommended_increase = Decimal("0")
    employees_affected = 0

    base_merit = Decimal(str(scenario.get("base_merit_percent") or 0))
    base_bonus = Decimal(str(scenario.get("base_bonus_percent") or 0))

    for emp in employees:
        emp = parse_jsonb_fields(emp, ["historical_data", "extra_attributes"])

        result = engine.process_employee(
            employee=emp,
            rules=rules,
            base_merit_percent=base_merit,
            base_bonus_percent=base_bonus,
        )

        # Prepare result for storage
        result_dict = {
            "tenant_id": str(current_user.tenant_id),
            "scenario_id": str(scenario_id),
            "employee_snapshot_id": emp["id"],
            "recommended_raise_percent": float(result["recommended_raise_percent"]),
            "recommended_raise_amount": float(result["recommended_raise_amount"]),
            "recommended_new_salary": float(result["recommended_new_salary"]),
            "recommended_new_hourly": float(result.get("recommended_new_hourly") or 0),
            "recommended_bonus_percent": float(result["recommended_bonus_percent"]),
            "recommended_bonus_amount": float(result["recommended_bonus_amount"]),
            "proposed_compa_ratio": float(result.get("proposed_compa_ratio") or 0),
            "total_increase_percent": float(result["total_increase_percent"]),
            "total_increase_amount": float(result["total_increase_amount"]),
            "promotion_flag": result["promotion_flag"],
            "cap_bonus_flag": result["cap_bonus_flag"],
            "needs_review_flag": result["needs_review_flag"],
            "excluded_flag": result["excluded_flag"],
            "applied_rules": json.dumps(result["applied_rules"]),
            "rule_notes": result.get("rule_notes") or "",
        }

        await client.insert("comp_scenario_results", result_dict)

        # Update totals
        current_annual = Decimal(str(emp.get("current_annual") or 0))
        total_current_payroll += current_annual

        if not result["excluded_flag"]:
            total_recommended_increase += result["total_increase_amount"]
            if result["total_increase_amount"] > 0:
                employees_affected += 1

    # Calculate overall percentage
    overall_percent = Decimal("0")
    if total_current_payroll > 0:
        overall_percent = (total_recommended_increase / total_current_payroll) * 100

    # Update scenario with aggregated results
    now = datetime.now(timezone.utc).isoformat()
    scenario = await client.update(
        "comp_scenarios",
        {
            "status": ScenarioStatus.CALCULATED,
            "calculated_at": now,
            "total_current_payroll": float(total_current_payroll),
            "total_recommended_increase": float(total_recommended_increase),
            "overall_increase_percent": float(overall_percent),
            "employees_affected": employees_affected,
            "updated_at": now,
        },
        filters={"id": str(scenario_id)},
    )

    return ScenarioResponse.model_validate(scenario)


@router.get("/{scenario_id}/results", response_model=PaginatedResponse[ScenarioResultResponse])
async def get_scenario_results(
    scenario_id: UUID,
    page: int = Query(1, ge=1),
    page_size: int = Query(50, ge=1, le=200),
    department: Optional[str] = None,
    needs_review: Optional[bool] = None,
    current_user: TokenData = Depends(require_permission(Permission.COMPENSATION_VIEW)),
):
    """Get scenario results with pagination."""
    client = get_supabase_client()

    # Verify scenario exists
    scenario = await client.select(
        "comp_scenarios",
        "id",
        filters={"id": str(scenario_id), "tenant_id": str(current_user.tenant_id)},
        single=True,
    )

    if not scenario:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Scenario not found",
        )

    results = await client.select(
        "comp_scenario_results",
        "*",
        filters={"scenario_id": str(scenario_id)},
    ) or []

    # Filter by flags
    if needs_review is not None:
        results = [r for r in results if r.get("needs_review_flag") == needs_review]

    total = len(results)

    # Apply pagination
    offset = (page - 1) * page_size
    results = results[offset:offset + page_size]

    items = []
    for r in results:
        r = parse_jsonb_fields(r, ["applied_rules"])
        items.append(ScenarioResultResponse.model_validate(r))

    return PaginatedResponse.create(
        items=items,
        total=total,
        page=page,
        page_size=page_size,
    )


@router.post("/compare", response_model=ScenarioCompareResponse)
async def compare_scenarios(
    request: ScenarioCompareRequest,
    current_user: TokenData = Depends(require_permission(Permission.COMPENSATION_VIEW)),
):
    """Compare multiple scenarios side by side."""
    client = get_supabase_client()

    summaries = []
    for scenario_id in request.scenario_ids:
        scenario = await client.select(
            "comp_scenarios",
            "*",
            filters={"id": str(scenario_id), "tenant_id": str(current_user.tenant_id)},
            single=True,
        )

        if not scenario:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail=f"Scenario {scenario_id} not found",
            )

        # Get flagged count
        results = await client.select(
            "comp_scenario_results",
            "id, needs_review_flag, recommended_raise_percent",
            filters={"scenario_id": str(scenario_id)},
        ) or []

        flagged_count = sum(1 for r in results if r.get("needs_review_flag"))
        avg_raise = sum(Decimal(str(r.get("recommended_raise_percent") or 0)) for r in results) / len(results) if results else Decimal("0")

        summaries.append(ScenarioSummary(
            id=scenario["id"],
            name=scenario["name"],
            status=scenario["status"],
            is_selected=scenario.get("is_selected", False),
            total_current_payroll=scenario.get("total_current_payroll"),
            total_recommended_increase=scenario.get("total_recommended_increase"),
            overall_increase_percent=scenario.get("overall_increase_percent"),
            employees_affected=scenario.get("employees_affected"),
            avg_raise_percent=avg_raise,
            flagged_for_review=flagged_count,
        ))

    # Calculate comparison metrics
    metrics = {
        "scenarios_compared": len(summaries),
        "min_increase_percent": min(s.overall_increase_percent or 0 for s in summaries) if summaries else 0,
        "max_increase_percent": max(s.overall_increase_percent or 0 for s in summaries) if summaries else 0,
    }

    return ScenarioCompareResponse(
        scenarios=summaries,
        comparison_metrics=metrics,
    )


@router.post("/{scenario_id}/select", response_model=ScenarioResponse)
async def select_scenario(
    scenario_id: UUID,
    current_user: TokenData = Depends(require_permission(Permission.COMPENSATION_MANAGE)),
):
    """Select a scenario as the approved one for the cycle."""
    client = get_supabase_client()

    scenario = await client.select(
        "comp_scenarios",
        "*",
        filters={"id": str(scenario_id), "tenant_id": str(current_user.tenant_id)},
        single=True,
    )

    if not scenario:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Scenario not found",
        )

    if scenario["status"] != ScenarioStatus.CALCULATED:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Scenario must be calculated before selection",
        )

    # Deselect other scenarios for this cycle
    other_scenarios = await client.select(
        "comp_scenarios",
        "id",
        filters={"cycle_id": scenario["cycle_id"], "is_selected": "true"},
    ) or []

    for other in other_scenarios:
        await client.update(
            "comp_scenarios",
            {"is_selected": False},
            filters={"id": other["id"]},
        )

    # Select this scenario
    now = datetime.now(timezone.utc).isoformat()
    scenario = await client.update(
        "comp_scenarios",
        {
            "is_selected": True,
            "selected_by": str(current_user.user_id),
            "selected_at": now,
            "status": ScenarioStatus.SELECTED,
            "updated_at": now,
        },
        filters={"id": str(scenario_id)},
    )

    return ScenarioResponse.model_validate(scenario)


@router.delete("/{scenario_id}", status_code=status.HTTP_204_NO_CONTENT)
async def delete_scenario(
    scenario_id: UUID,
    current_user: TokenData = Depends(require_permission(Permission.COMPENSATION_MANAGE)),
):
    """Delete a scenario and its results."""
    client = get_supabase_client()

    scenario = await client.select(
        "comp_scenarios",
        "*",
        filters={"id": str(scenario_id), "tenant_id": str(current_user.tenant_id)},
        single=True,
    )

    if not scenario:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Scenario not found",
        )

    if scenario.get("is_selected"):
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Cannot delete selected scenario",
        )

    # Delete results first
    results = await client.select(
        "comp_scenario_results",
        "id",
        filters={"scenario_id": str(scenario_id)},
    ) or []

    for result in results:
        await client.delete("comp_scenario_results", filters={"id": result["id"]})

    # Delete scenario
    await client.delete("comp_scenarios", filters={"id": str(scenario_id)})

    return None
