"""Manager Worksheet schemas."""

from datetime import datetime
from decimal import Decimal
from typing import Optional, Any, Dict, List
from uuid import UUID

from pydantic import BaseModel, Field


class WorksheetStatus:
    PENDING = "pending"
    SUBMITTED = "submitted"
    APPROVED = "approved"
    REJECTED = "rejected"
    FLAGGED = "flagged"


class HighlightColor:
    LIGHT_GREEN = "light_green"  # Getting an increase
    DARK_GREEN = "dark_green"    # Getting cap bonus in lieu of increase
    BEIGE = "beige"              # Becoming salaried (hourly to salary)
    RED = "red"                  # No increase (poor performance or recent hire)


class WorksheetEntryUpdate(BaseModel):
    """Schema for manager updating a worksheet entry."""
    manager_raise_percent: Optional[Decimal] = Field(None, ge=0, le=100)
    manager_raise_amount: Optional[Decimal] = None
    manager_new_salary: Optional[Decimal] = None
    manager_bonus_percent: Optional[Decimal] = Field(None, ge=0, le=100)
    manager_bonus_amount: Optional[Decimal] = None
    manager_promotion_flag: Optional[bool] = None
    manager_justification: Optional[str] = None
    manager_exception_flag: Optional[bool] = None


class WorksheetEntryResponse(BaseModel):
    """Schema for worksheet entry response."""
    id: UUID
    tenant_id: UUID
    cycle_id: UUID
    scenario_id: Optional[UUID] = None
    employee_snapshot_id: UUID

    # Employee info (from snapshot join)
    employee_id: Optional[str] = None
    first_name: Optional[str] = None
    last_name: Optional[str] = None
    department: Optional[str] = None
    job_title: Optional[str] = None
    current_annual: Optional[Decimal] = None
    current_compa_ratio: Optional[Decimal] = None
    performance_score: Optional[Decimal] = None

    # System proposed values
    system_raise_percent: Optional[Decimal] = None
    system_raise_amount: Optional[Decimal] = None
    system_new_salary: Optional[Decimal] = None
    system_bonus_percent: Optional[Decimal] = None
    system_bonus_amount: Optional[Decimal] = None

    # Manager input
    manager_raise_percent: Optional[Decimal] = None
    manager_raise_amount: Optional[Decimal] = None
    manager_new_salary: Optional[Decimal] = None
    manager_bonus_percent: Optional[Decimal] = None
    manager_bonus_amount: Optional[Decimal] = None
    manager_promotion_flag: bool = False
    manager_justification: Optional[str] = None
    manager_exception_flag: bool = False

    # Calculated deltas
    delta_raise_percent: Optional[Decimal] = None
    delta_bonus_amount: Optional[Decimal] = None

    # Workflow
    status: str
    submitted_by: Optional[UUID] = None
    submitted_at: Optional[datetime] = None
    reviewed_by: Optional[UUID] = None
    reviewed_at: Optional[datetime] = None
    review_notes: Optional[str] = None
    approved_by: Optional[UUID] = None
    approved_at: Optional[datetime] = None
    approval_notes: Optional[str] = None

    # Display
    highlight_color: Optional[str] = None

    created_at: datetime
    updated_at: datetime

    class Config:
        from_attributes = True


class WorksheetEntryListResponse(BaseModel):
    """Schema for listing worksheet entries (AG Grid compatible)."""
    id: UUID
    employee_id: str
    first_name: Optional[str] = None
    last_name: Optional[str] = None
    department: Optional[str] = None
    sub_department: Optional[str] = None
    manager_name: Optional[str] = None
    job_title: Optional[str] = None
    hire_date: Optional[str] = None
    last_increase_date: Optional[str] = None
    employment_type: Optional[str] = None
    weekly_hours: Optional[Decimal] = None

    # Current comp
    current_hourly_rate: Optional[Decimal] = None
    current_weekly: Optional[Decimal] = None
    current_annual: Optional[Decimal] = None
    current_compa_ratio: Optional[Decimal] = None
    pay_grade: Optional[str] = None
    band_midpoint: Optional[Decimal] = None

    # Performance
    performance_score: Optional[Decimal] = None

    # Historical
    prior_year_rate: Optional[Decimal] = None
    prior_year_increase_pct: Optional[Decimal] = None
    current_year_rate: Optional[Decimal] = None

    # System proposed
    system_raise_percent: Optional[Decimal] = None
    system_raise_amount: Optional[Decimal] = None
    system_new_salary: Optional[Decimal] = None
    system_bonus_percent: Optional[Decimal] = None
    system_bonus_amount: Optional[Decimal] = None

    # Manager input
    manager_raise_percent: Optional[Decimal] = None
    manager_raise_amount: Optional[Decimal] = None
    manager_new_salary: Optional[Decimal] = None
    manager_bonus_percent: Optional[Decimal] = None
    manager_bonus_amount: Optional[Decimal] = None
    manager_promotion_flag: bool = False
    manager_justification: Optional[str] = None

    # Workflow
    status: str
    highlight_color: Optional[str] = None

    # Bonus eligibility
    gbp_eligible: bool = False
    cap_bonus_eligible: bool = False

    class Config:
        from_attributes = True


class BulkWorksheetUpdate(BaseModel):
    """Schema for bulk updating worksheet entries."""
    entry_ids: List[UUID]
    updates: WorksheetEntryUpdate


class WorksheetSubmitRequest(BaseModel):
    """Schema for submitting worksheet entries for approval."""
    entry_ids: Optional[List[UUID]] = None  # If None, submit all pending
    notes: Optional[str] = None


class WorksheetTotals(BaseModel):
    """Schema for worksheet totals/rollup."""
    total_employees: int
    total_current_payroll: Decimal
    total_recommended_increase: Decimal
    overall_increase_percent: Decimal

    # By status
    pending_count: int
    submitted_count: int
    approved_count: int
    flagged_count: int

    # By department
    department_breakdown: Optional[List[Dict[str, Any]]] = None


class WorksheetReviewRequest(BaseModel):
    """Schema for reviewing a worksheet entry."""
    action: str = Field(..., description="approve, reject, or flag")
    notes: Optional[str] = None


class BulkReviewRequest(BaseModel):
    """Schema for bulk reviewing worksheet entries."""
    entry_ids: List[UUID]
    action: str = Field(..., description="approve, reject, or flag")
    notes: Optional[str] = None
