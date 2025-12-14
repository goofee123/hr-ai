"""Employee Compensation Snapshot schemas."""

from datetime import date, datetime
from decimal import Decimal
from typing import Optional, Any, Dict
from uuid import UUID

from pydantic import BaseModel, Field


class DatasetVersionCreate(BaseModel):
    """Schema for creating a dataset version."""
    cycle_id: UUID
    source: str = Field(default="manual")
    source_file_name: Optional[str] = None
    notes: Optional[str] = None


class DatasetVersionResponse(BaseModel):
    """Schema for dataset version response."""
    id: UUID
    tenant_id: UUID
    cycle_id: Optional[UUID] = None
    version_number: int
    source: Optional[str] = None
    source_file_name: Optional[str] = None
    imported_by: Optional[UUID] = None
    imported_at: datetime
    row_count: Optional[int] = None
    error_count: int = 0
    status: str
    is_active: bool
    notes: Optional[str] = None
    created_at: datetime

    class Config:
        from_attributes = True


class EmployeeSnapshotCreate(BaseModel):
    """Schema for creating an employee snapshot (via import)."""
    dataset_version_id: UUID
    employee_id: str = Field(..., max_length=50)
    first_name: Optional[str] = None
    last_name: Optional[str] = None
    email: Optional[str] = None
    business_unit: Optional[str] = None
    department: Optional[str] = None
    sub_department: Optional[str] = None
    manager_name: Optional[str] = None
    manager_employee_id: Optional[str] = None
    job_title: Optional[str] = None
    hire_date: Optional[date] = None
    last_increase_date: Optional[date] = None
    employment_type: Optional[str] = None
    schedule: Optional[str] = None
    weekly_hours: Optional[Decimal] = Field(default=40)
    location: Optional[str] = None
    country: Optional[str] = None
    current_hourly_rate: Optional[Decimal] = None
    current_weekly: Optional[Decimal] = None
    current_annual: Optional[Decimal] = None
    pay_grade: Optional[str] = None
    band_minimum: Optional[Decimal] = None
    band_midpoint: Optional[Decimal] = None
    band_maximum: Optional[Decimal] = None
    current_compa_ratio: Optional[Decimal] = None
    performance_score: Optional[Decimal] = None
    performance_rating: Optional[str] = None
    prior_year_rate: Optional[Decimal] = None
    prior_year_increase_pct: Optional[Decimal] = None
    current_year_rate: Optional[Decimal] = None
    current_year_increase_pct: Optional[Decimal] = None
    gbp_eligible: bool = False
    cap_bonus_eligible: bool = False
    prior_year_bonus: Optional[Decimal] = None
    ytd_total: Optional[Decimal] = None
    historical_data: Optional[Dict[str, Any]] = None
    extra_attributes: Optional[Dict[str, Any]] = None


class EmployeeSnapshotResponse(BaseModel):
    """Schema for employee snapshot response."""
    id: UUID
    tenant_id: UUID
    dataset_version_id: UUID
    employee_id: str
    first_name: Optional[str] = None
    last_name: Optional[str] = None
    email: Optional[str] = None
    business_unit: Optional[str] = None
    department: Optional[str] = None
    sub_department: Optional[str] = None
    manager_name: Optional[str] = None
    manager_employee_id: Optional[str] = None
    job_title: Optional[str] = None
    hire_date: Optional[date] = None
    last_increase_date: Optional[date] = None
    employment_type: Optional[str] = None
    schedule: Optional[str] = None
    weekly_hours: Optional[Decimal] = None
    location: Optional[str] = None
    country: Optional[str] = None
    current_hourly_rate: Optional[Decimal] = None
    current_weekly: Optional[Decimal] = None
    current_annual: Optional[Decimal] = None
    pay_grade: Optional[str] = None
    band_minimum: Optional[Decimal] = None
    band_midpoint: Optional[Decimal] = None
    band_maximum: Optional[Decimal] = None
    current_compa_ratio: Optional[Decimal] = None
    performance_score: Optional[Decimal] = None
    performance_rating: Optional[str] = None
    prior_year_rate: Optional[Decimal] = None
    prior_year_increase_pct: Optional[Decimal] = None
    current_year_rate: Optional[Decimal] = None
    current_year_increase_pct: Optional[Decimal] = None
    gbp_eligible: bool = False
    cap_bonus_eligible: bool = False
    prior_year_bonus: Optional[Decimal] = None
    ytd_total: Optional[Decimal] = None
    historical_data: Optional[Dict[str, Any]] = None
    extra_attributes: Optional[Dict[str, Any]] = None
    created_at: datetime

    class Config:
        from_attributes = True


class EmployeeSnapshotListResponse(BaseModel):
    """Schema for listing employee snapshots (reduced fields)."""
    id: UUID
    employee_id: str
    first_name: Optional[str] = None
    last_name: Optional[str] = None
    department: Optional[str] = None
    job_title: Optional[str] = None
    current_annual: Optional[Decimal] = None
    current_compa_ratio: Optional[Decimal] = None
    performance_score: Optional[Decimal] = None
    pay_grade: Optional[str] = None

    class Config:
        from_attributes = True


class ImportValidationResult(BaseModel):
    """Schema for import validation result."""
    valid: bool
    row_count: int
    error_count: int
    errors: list[dict] = []
    warnings: list[dict] = []
    column_mapping: Optional[dict] = None


class ImportRequest(BaseModel):
    """Schema for initiating an import."""
    cycle_id: UUID
    source: str = Field(default="dayforce_import")
    file_name: str
    column_mapping: Optional[Dict[str, str]] = None
