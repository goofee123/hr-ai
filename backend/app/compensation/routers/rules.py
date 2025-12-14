"""Compensation Rules router - using Supabase REST API."""

import json
from datetime import datetime, timezone
from typing import Optional
from uuid import UUID

from fastapi import APIRouter, Depends, HTTPException, Query, status

from app.core.permissions import Permission, require_permission
from app.core.security import TokenData, get_current_user
from app.core.supabase_client import get_supabase_client
from app.compensation.schemas import (
    RuleSetCreate,
    RuleSetUpdate,
    RuleSetResponse,
    RuleCreate,
    RuleUpdate,
    RuleResponse,
    RuleTestRequest,
    RuleTestResult,
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


# ============================================================================
# RULE SETS
# ============================================================================

@router.get("/sets", response_model=PaginatedResponse[RuleSetResponse])
async def list_rule_sets(
    page: int = Query(1, ge=1),
    page_size: int = Query(20, ge=1, le=100),
    is_active: Optional[bool] = None,
    current_user: TokenData = Depends(require_permission(Permission.COMPENSATION_VIEW)),
):
    """List rule sets."""
    client = get_supabase_client()

    filters = {"tenant_id": str(current_user.tenant_id)}
    if is_active is not None:
        filters["is_active"] = str(is_active).lower()

    rule_sets = await client.select("comp_rule_sets", "*", filters=filters) or []

    total = len(rule_sets)
    rule_sets.sort(key=lambda x: x.get("created_at", ""), reverse=True)

    offset = (page - 1) * page_size
    rule_sets = rule_sets[offset:offset + page_size]

    # Get rule counts
    items = []
    for rs in rule_sets:
        rules = await client.select(
            "comp_rules",
            "id",
            filters={"rule_set_id": rs["id"]},
        ) or []
        response = RuleSetResponse.model_validate(rs)
        response.rule_count = len(rules)
        items.append(response)

    return PaginatedResponse.create(
        items=items,
        total=total,
        page=page,
        page_size=page_size,
    )


@router.post("/sets", response_model=RuleSetResponse, status_code=status.HTTP_201_CREATED)
async def create_rule_set(
    rule_set_data: RuleSetCreate,
    current_user: TokenData = Depends(require_permission(Permission.COMPENSATION_MANAGE)),
):
    """Create a new rule set."""
    client = get_supabase_client()

    rule_set_dict = {
        "tenant_id": str(current_user.tenant_id),
        "name": rule_set_data.name,
        "description": rule_set_data.description,
        "is_active": rule_set_data.is_active,
        "is_default": rule_set_data.is_default,
        "created_by": str(current_user.user_id),
    }

    # If marking as default, unset other defaults
    if rule_set_data.is_default:
        existing_defaults = await client.select(
            "comp_rule_sets",
            "id",
            filters={"tenant_id": str(current_user.tenant_id), "is_default": "true"},
        ) or []
        for rs in existing_defaults:
            await client.update(
                "comp_rule_sets",
                {"is_default": False},
                filters={"id": rs["id"]},
            )

    rule_set = await client.insert("comp_rule_sets", rule_set_dict)
    response = RuleSetResponse.model_validate(rule_set)
    response.rule_count = 0
    return response


@router.get("/sets/{rule_set_id}", response_model=RuleSetResponse)
async def get_rule_set(
    rule_set_id: UUID,
    current_user: TokenData = Depends(require_permission(Permission.COMPENSATION_VIEW)),
):
    """Get a rule set by ID."""
    client = get_supabase_client()

    rule_set = await client.select(
        "comp_rule_sets",
        "*",
        filters={"id": str(rule_set_id), "tenant_id": str(current_user.tenant_id)},
        single=True,
    )

    if not rule_set:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Rule set not found",
        )

    # Get rule count
    rules = await client.select(
        "comp_rules",
        "id",
        filters={"rule_set_id": str(rule_set_id)},
    ) or []

    response = RuleSetResponse.model_validate(rule_set)
    response.rule_count = len(rules)
    return response


@router.patch("/sets/{rule_set_id}", response_model=RuleSetResponse)
async def update_rule_set(
    rule_set_id: UUID,
    rule_set_data: RuleSetUpdate,
    current_user: TokenData = Depends(require_permission(Permission.COMPENSATION_MANAGE)),
):
    """Update a rule set."""
    client = get_supabase_client()

    rule_set = await client.select(
        "comp_rule_sets",
        "*",
        filters={"id": str(rule_set_id), "tenant_id": str(current_user.tenant_id)},
        single=True,
    )

    if not rule_set:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Rule set not found",
        )

    update_data = rule_set_data.model_dump(exclude_unset=True)

    # If marking as default, unset other defaults
    if update_data.get("is_default"):
        existing_defaults = await client.select(
            "comp_rule_sets",
            "id",
            filters={"tenant_id": str(current_user.tenant_id), "is_default": "true"},
        ) or []
        for rs in existing_defaults:
            if rs["id"] != str(rule_set_id):
                await client.update(
                    "comp_rule_sets",
                    {"is_default": False},
                    filters={"id": rs["id"]},
                )

    if update_data:
        update_data["updated_at"] = datetime.now(timezone.utc).isoformat()
        rule_set = await client.update(
            "comp_rule_sets",
            update_data,
            filters={"id": str(rule_set_id)},
        )

    rules = await client.select(
        "comp_rules",
        "id",
        filters={"rule_set_id": str(rule_set_id)},
    ) or []

    response = RuleSetResponse.model_validate(rule_set)
    response.rule_count = len(rules)
    return response


@router.delete("/sets/{rule_set_id}", status_code=status.HTTP_204_NO_CONTENT)
async def delete_rule_set(
    rule_set_id: UUID,
    current_user: TokenData = Depends(require_permission(Permission.COMPENSATION_MANAGE)),
):
    """Delete a rule set and all its rules."""
    client = get_supabase_client()

    rule_set = await client.select(
        "comp_rule_sets",
        "*",
        filters={"id": str(rule_set_id), "tenant_id": str(current_user.tenant_id)},
        single=True,
    )

    if not rule_set:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Rule set not found",
        )

    # Check if in use by any scenarios
    scenarios = await client.select(
        "comp_scenarios",
        "id",
        filters={"rule_set_id": str(rule_set_id)},
    ) or []

    if scenarios:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Cannot delete rule set that is in use by scenarios",
        )

    # Delete all rules first
    rules = await client.select(
        "comp_rules",
        "id",
        filters={"rule_set_id": str(rule_set_id)},
    ) or []

    for rule in rules:
        await client.delete("comp_rules", filters={"id": rule["id"]})

    # Delete rule set
    await client.delete("comp_rule_sets", filters={"id": str(rule_set_id)})

    return None


# ============================================================================
# RULES
# ============================================================================

@router.get("/sets/{rule_set_id}/rules", response_model=list[RuleResponse])
async def list_rules(
    rule_set_id: UUID,
    current_user: TokenData = Depends(require_permission(Permission.COMPENSATION_VIEW)),
):
    """List all rules in a rule set."""
    client = get_supabase_client()

    # Verify rule set exists
    rule_set = await client.select(
        "comp_rule_sets",
        "id",
        filters={"id": str(rule_set_id), "tenant_id": str(current_user.tenant_id)},
        single=True,
    )

    if not rule_set:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Rule set not found",
        )

    rules = await client.select(
        "comp_rules",
        "*",
        filters={"rule_set_id": str(rule_set_id)},
    ) or []

    # Sort by priority
    rules.sort(key=lambda x: x.get("priority", 100))

    result = []
    for rule in rules:
        rule = parse_jsonb_fields(rule, ["conditions", "actions"])
        result.append(RuleResponse.model_validate(rule))

    return result


@router.post("", response_model=RuleResponse, status_code=status.HTTP_201_CREATED)
async def create_rule(
    rule_data: RuleCreate,
    current_user: TokenData = Depends(require_permission(Permission.COMPENSATION_MANAGE)),
):
    """Create a new rule."""
    client = get_supabase_client()

    # Verify rule set exists
    rule_set = await client.select(
        "comp_rule_sets",
        "id",
        filters={"id": str(rule_data.rule_set_id), "tenant_id": str(current_user.tenant_id)},
        single=True,
    )

    if not rule_set:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Rule set not found",
        )

    rule_dict = {
        "tenant_id": str(current_user.tenant_id),
        "rule_set_id": str(rule_data.rule_set_id),
        "name": rule_data.name,
        "description": rule_data.description,
        "priority": rule_data.priority,
        "is_active": rule_data.is_active,
        "rule_type": rule_data.rule_type,
        "conditions": json.dumps(rule_data.conditions),
        "actions": json.dumps(rule_data.actions),
        "effective_date": rule_data.effective_date.isoformat() if rule_data.effective_date else None,
        "expiry_date": rule_data.expiry_date.isoformat() if rule_data.expiry_date else None,
        "created_by": str(current_user.user_id),
    }

    rule = await client.insert("comp_rules", rule_dict)
    rule = parse_jsonb_fields(rule, ["conditions", "actions"])

    return RuleResponse.model_validate(rule)


@router.get("/{rule_id}", response_model=RuleResponse)
async def get_rule(
    rule_id: UUID,
    current_user: TokenData = Depends(require_permission(Permission.COMPENSATION_VIEW)),
):
    """Get a rule by ID."""
    client = get_supabase_client()

    rule = await client.select(
        "comp_rules",
        "*",
        filters={"id": str(rule_id), "tenant_id": str(current_user.tenant_id)},
        single=True,
    )

    if not rule:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Rule not found",
        )

    rule = parse_jsonb_fields(rule, ["conditions", "actions"])

    return RuleResponse.model_validate(rule)


@router.patch("/{rule_id}", response_model=RuleResponse)
async def update_rule(
    rule_id: UUID,
    rule_data: RuleUpdate,
    current_user: TokenData = Depends(require_permission(Permission.COMPENSATION_MANAGE)),
):
    """Update a rule."""
    client = get_supabase_client()

    rule = await client.select(
        "comp_rules",
        "*",
        filters={"id": str(rule_id), "tenant_id": str(current_user.tenant_id)},
        single=True,
    )

    if not rule:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Rule not found",
        )

    update_data = rule_data.model_dump(exclude_unset=True)

    if "conditions" in update_data:
        update_data["conditions"] = json.dumps(update_data["conditions"])
    if "actions" in update_data:
        update_data["actions"] = json.dumps(update_data["actions"])
    if "effective_date" in update_data and update_data["effective_date"]:
        update_data["effective_date"] = update_data["effective_date"].isoformat()
    if "expiry_date" in update_data and update_data["expiry_date"]:
        update_data["expiry_date"] = update_data["expiry_date"].isoformat()

    if update_data:
        update_data["updated_at"] = datetime.now(timezone.utc).isoformat()
        rule = await client.update(
            "comp_rules",
            update_data,
            filters={"id": str(rule_id)},
        )

    rule = parse_jsonb_fields(rule, ["conditions", "actions"])

    return RuleResponse.model_validate(rule)


@router.delete("/{rule_id}", status_code=status.HTTP_204_NO_CONTENT)
async def delete_rule(
    rule_id: UUID,
    current_user: TokenData = Depends(require_permission(Permission.COMPENSATION_MANAGE)),
):
    """Delete a rule."""
    client = get_supabase_client()

    rule = await client.select(
        "comp_rules",
        "*",
        filters={"id": str(rule_id), "tenant_id": str(current_user.tenant_id)},
        single=True,
    )

    if not rule:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Rule not found",
        )

    await client.delete("comp_rules", filters={"id": str(rule_id)})

    return None


@router.post("/test", response_model=RuleTestResult)
async def test_rule(
    test_request: RuleTestRequest,
    current_user: TokenData = Depends(require_permission(Permission.COMPENSATION_MANAGE)),
):
    """Test a rule against sample employee data."""
    client = get_supabase_client()

    conditions = test_request.conditions
    actions = test_request.actions

    # If rule_id provided, load the rule
    if test_request.rule_id:
        rule = await client.select(
            "comp_rules",
            "*",
            filters={"id": str(test_request.rule_id), "tenant_id": str(current_user.tenant_id)},
            single=True,
        )

        if not rule:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail="Rule not found",
            )

        rule = parse_jsonb_fields(rule, ["conditions", "actions"])
        conditions = rule["conditions"]
        actions = rule["actions"]

    if not conditions or not actions:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Either rule_id or both conditions and actions must be provided",
        )

    engine = get_rules_engine()
    result = engine.test_rule(conditions, actions, test_request.test_employee)

    # Convert decimals to strings for JSON serialization
    serializable_result = {}
    for key, value in result["result"].items():
        if hasattr(value, "__float__"):
            serializable_result[key] = float(value)
        else:
            serializable_result[key] = value

    return RuleTestResult(
        matched=result["matched"],
        conditions_evaluated=result["conditions_evaluated"],
        actions_applied=result["actions_applied"],
        result=serializable_result,
    )
