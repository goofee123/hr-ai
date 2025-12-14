"""Scenario Modeling schemas."""

from datetime import datetime
from decimal import Decimal
from typing import Optional, Any, Dict, List
from uuid import UUID

from pydantic import BaseModel, Field


class ScenarioStatus:
    DRAFT = "draft"
    CALCULATING = "calculating"
    CALCULATED = "calculated"
    SELECTED = "selected"
    ARCHIVED = "archived"


class ScenarioCreate(BaseModel):
    """Schema for creating a scenario."""
    cycle_id: UUID
    name: str = Field(..., min_length=1, max_length=100)
    description: Optional[str] = None
    rule_set_id: Optional[UUID] = None
    base_merit_percent: Optional[Decimal] = Field(None, ge=0, le=100)
    base_bonus_percent: Optional[Decimal] = Field(None, ge=0, le=100)
    budget_target_percent: Optional[Decimal] = Field(None, ge=0, le=100)
    goal_description: Optional[str] = None


class ScenarioUpdate(BaseModel):
    """Schema for updating a scenario."""
    name: Optional[str] = Field(None, min_length=1, max_length=100)
    description: Optional[str] = None
    rule_set_id: Optional[UUID] = None
    base_merit_percent: Optional[Decimal] = Field(None, ge=0, le=100)
    base_bonus_percent: Optional[Decimal] = Field(None, ge=0, le=100)
    budget_target_percent: Optional[Decimal] = Field(None, ge=0, le=100)
    goal_description: Optional[str] = None


class ScenarioResponse(BaseModel):
    """Schema for scenario response."""
    id: UUID
    tenant_id: UUID
    cycle_id: UUID
    name: str
    description: Optional[str] = None
    rule_set_id: Optional[UUID] = None
    base_merit_percent: Optional[Decimal] = None
    base_bonus_percent: Optional[Decimal] = None
    budget_target_percent: Optional[Decimal] = None
    goal_description: Optional[str] = None
    status: str
    calculated_at: Optional[datetime] = None
    total_current_payroll: Optional[Decimal] = None
    total_recommended_increase: Optional[Decimal] = None
    overall_increase_percent: Optional[Decimal] = None
    employees_affected: Optional[int] = None
    is_selected: bool
    selected_by: Optional[UUID] = None
    selected_at: Optional[datetime] = None
    created_by: Optional[UUID] = None
    created_at: datetime
    updated_at: datetime

    class Config:
        from_attributes = True


class ScenarioSummary(BaseModel):
    """Schema for scenario summary/comparison view."""
    id: UUID
    name: str
    status: str
    is_selected: bool
    total_current_payroll: Optional[Decimal] = None
    total_recommended_increase: Optional[Decimal] = None
    overall_increase_percent: Optional[Decimal] = None
    employees_affected: Optional[int] = None
    avg_raise_percent: Optional[Decimal] = None
    flagged_for_review: int = 0


class ScenarioResultCreate(BaseModel):
    """Schema for creating a scenario result (internal use)."""
    scenario_id: UUID
    employee_snapshot_id: UUID
    recommended_raise_percent: Optional[Decimal] = None
    recommended_raise_amount: Optional[Decimal] = None
    recommended_new_salary: Optional[Decimal] = None
    recommended_new_hourly: Optional[Decimal] = None
    recommended_bonus_percent: Optional[Decimal] = None
    recommended_bonus_amount: Optional[Decimal] = None
    proposed_compa_ratio: Optional[Decimal] = None
    total_increase_percent: Optional[Decimal] = None
    total_increase_amount: Optional[Decimal] = None
    promotion_flag: bool = False
    cap_bonus_flag: bool = False
    needs_review_flag: bool = False
    excluded_flag: bool = False
    applied_rules: List[Dict[str, Any]] = []
    rule_notes: Optional[str] = None


class ScenarioResultResponse(BaseModel):
    """Schema for scenario result response."""
    id: UUID
    scenario_id: UUID
    employee_snapshot_id: UUID
    recommended_raise_percent: Optional[Decimal] = None
    recommended_raise_amount: Optional[Decimal] = None
    recommended_new_salary: Optional[Decimal] = None
    recommended_new_hourly: Optional[Decimal] = None
    recommended_bonus_percent: Optional[Decimal] = None
    recommended_bonus_amount: Optional[Decimal] = None
    proposed_compa_ratio: Optional[Decimal] = None
    total_increase_percent: Optional[Decimal] = None
    total_increase_amount: Optional[Decimal] = None
    promotion_flag: bool
    cap_bonus_flag: bool
    needs_review_flag: bool
    excluded_flag: bool
    applied_rules: List[Dict[str, Any]]
    rule_notes: Optional[str] = None
    created_at: datetime

    class Config:
        from_attributes = True


class ScenarioCompareRequest(BaseModel):
    """Schema for comparing multiple scenarios."""
    scenario_ids: List[UUID] = Field(..., min_length=2, max_length=5)


class ScenarioCompareResponse(BaseModel):
    """Schema for scenario comparison result."""
    scenarios: List[ScenarioSummary]
    comparison_metrics: Dict[str, Any]


class CalculateScenarioRequest(BaseModel):
    """Schema for triggering scenario calculation."""
    recalculate: bool = Field(default=False, description="Force recalculation even if already calculated")
