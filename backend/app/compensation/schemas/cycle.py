"""Compensation Cycle schemas - matching actual DB schema."""

from datetime import date, datetime
from decimal import Decimal
from typing import Optional
from uuid import UUID

from pydantic import BaseModel, Field


class CycleStatus:
    DRAFT = "draft"
    MODELING = "modeling"
    MANAGER_REVIEW = "manager_review"
    EXECUTIVE_REVIEW = "executive_review"
    COMP_QA = "comp_qa"
    APPROVED = "approved"
    EXPORTED = "exported"
    ARCHIVED = "archived"


class CycleType:
    ANNUAL = "annual"
    MID_YEAR = "mid_year"
    OFF_CYCLE = "off_cycle"


class CompCycleCreate(BaseModel):
    """Schema for creating a compensation cycle - matches DB schema."""
    name: str = Field(..., min_length=1, max_length=100)
    fiscal_year: int = Field(..., ge=2020, le=2100)
    cycle_type: str = Field(default=CycleType.ANNUAL)
    effective_date: date
    planning_start_date: Optional[date] = None
    manager_input_start: Optional[date] = None
    manager_input_deadline: Optional[date] = None
    hr_review_deadline: Optional[date] = None
    total_budget_amount: Optional[Decimal] = None


class CompCycleUpdate(BaseModel):
    """Schema for updating a compensation cycle."""
    name: Optional[str] = Field(None, min_length=1, max_length=100)
    cycle_type: Optional[str] = None
    effective_date: Optional[date] = None
    planning_start_date: Optional[date] = None
    manager_input_start: Optional[date] = None
    manager_input_deadline: Optional[date] = None
    hr_review_deadline: Optional[date] = None
    total_budget_amount: Optional[Decimal] = None
    status: Optional[str] = None


class CompCycleResponse(BaseModel):
    """Schema for compensation cycle response - matches DB schema."""
    id: UUID
    tenant_id: UUID
    name: str
    fiscal_year: int = Field(alias="year")  # DB column is 'year'
    cycle_type: str
    effective_date: date
    planning_start_date: Optional[date] = None
    manager_input_start: Optional[date] = None
    manager_input_deadline: Optional[date] = None
    hr_review_deadline: Optional[date] = None
    status: str
    total_budget_amount: Optional[Decimal] = None
    allocated_amount: Optional[Decimal] = None
    remaining_amount: Optional[Decimal] = None
    selected_scenario_id: Optional[UUID] = None
    last_export_at: Optional[datetime] = None
    export_batch_id: Optional[str] = None
    created_by: Optional[UUID] = None
    created_at: datetime
    updated_at: datetime

    class Config:
        from_attributes = True
        populate_by_name = True


class CompCycleListResponse(BaseModel):
    """Schema for listing compensation cycles."""
    id: UUID
    name: str
    fiscal_year: int = Field(alias="year")  # DB column is 'year'
    cycle_type: str
    status: str
    effective_date: date
    total_budget_amount: Optional[Decimal] = None
    created_at: datetime
    # Computed fields
    employee_count: int = 0
    scenario_count: int = 0

    class Config:
        from_attributes = True
        populate_by_name = True


class CycleStatusUpdate(BaseModel):
    """Schema for updating cycle status."""
    status: str = Field(..., description="New status for the cycle")
    notes: Optional[str] = None


class CycleLaunchRequest(BaseModel):
    """Schema for launching a cycle to manager review."""
    scenario_id: UUID = Field(..., description="Selected scenario to use for manager worksheets")
    notify_managers: bool = Field(default=True, description="Send email notifications to managers")
