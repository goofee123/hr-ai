"""Compensation Data Import router - using Supabase REST API."""

import json
import csv
import io
from datetime import datetime, timezone
from typing import Optional
from uuid import UUID

from fastapi import APIRouter, Depends, HTTPException, UploadFile, File, Query, status

from app.core.permissions import Permission, require_permission
from app.core.security import TokenData, get_current_user
from app.core.supabase_client import get_supabase_client
from app.compensation.schemas import (
    DatasetVersionCreate,
    DatasetVersionResponse,
    EmployeeSnapshotCreate,
    EmployeeSnapshotResponse,
    ImportValidationResult,
    ImportRequest,
)
from app.shared.schemas.common import PaginatedResponse

router = APIRouter()


# Column mapping from Dayforce/BH Excel to our schema
COLUMN_MAPPING = {
    # Identity
    "Emp ID#": "employee_id",
    "Employee ID": "employee_id",
    "First Name": "first_name",
    "Last Name": "last_name",
    "Email": "email",
    # Organization
    "Business Unit": "business_unit",
    "Department": "department",
    "Sub Department": "sub_department",
    "Sub-Department": "sub_department",
    "Manager Name": "manager_name",
    "Manager Employee ID": "manager_employee_id",
    "Job Title": "job_title",
    "Title": "job_title",
    # Employment
    "Hire Date": "hire_date",
    "Last Increase Date": "last_increase_date",
    "Employment Type": "employment_type",
    "TYPE": "employment_type",
    "Schedule": "schedule",
    "Weekly Hours": "weekly_hours",
    "WEEK H": "weekly_hours",
    "Location": "location",
    "Country": "country",
    # Current Compensation
    "Current Hourly": "current_hourly_rate",
    "Hourly Rate": "current_hourly_rate",
    "Current Weekly": "current_weekly",
    "Current Annual": "current_annual",
    "Annual Salary": "current_annual",
    # Pay Structure
    "Pay Grade": "pay_grade",
    "Grade": "pay_grade",
    "Band Min": "band_minimum",
    "Band Minimum": "band_minimum",
    "MidPoint": "band_midpoint",
    "Band Midpoint": "band_midpoint",
    "Band Max": "band_maximum",
    "Band Maximum": "band_maximum",
    "Compa Ratio": "current_compa_ratio",
    "Current Compa Ratio": "current_compa_ratio",
    # Performance
    "Performance Score": "performance_score",
    "Jan 25 PR": "performance_score",
    "Performance Rating": "performance_rating",
    # Historical Rates
    "01-01-24 Rate": "prior_year_rate",
    "Prior Year Rate": "prior_year_rate",
    "2024 Inc %": "prior_year_increase_pct",
    "Prior Year Inc %": "prior_year_increase_pct",
    "01-01-25 Rate": "current_year_rate",
    "Current Year Rate": "current_year_rate",
    "2025 Inc %": "current_year_increase_pct",
    "Current Year Inc %": "current_year_increase_pct",
    # Bonus Eligibility
    "GBP": "gbp_eligible",
    "GBP Eligible": "gbp_eligible",
    "Cap Bonus Eligible": "cap_bonus_eligible",
    "Cap Bonus": "cap_bonus_eligible",
    # Prior Bonus
    "2024 Q1 $": "prior_year_bonus",
    "Prior Year Bonus": "prior_year_bonus",
    "2024 $": "ytd_total",
    "YTD Total": "ytd_total",
}


def parse_value(value: str, field_type: str):
    """Parse string value to appropriate type."""
    if not value or value.strip() == "":
        return None

    value = value.strip()

    if field_type == "decimal":
        # Remove currency symbols and commas
        cleaned = value.replace("$", "").replace(",", "").replace("%", "").strip()
        try:
            return float(cleaned)
        except (ValueError, TypeError):
            return None

    elif field_type == "date":
        # Try common date formats
        for fmt in ["%Y-%m-%d", "%m/%d/%Y", "%m-%d-%Y", "%d/%m/%Y"]:
            try:
                return datetime.strptime(value, fmt).date().isoformat()
            except ValueError:
                continue
        return None

    elif field_type == "boolean":
        return value.lower() in ("true", "yes", "1", "y", "x")

    elif field_type == "integer":
        try:
            return int(float(value))
        except (ValueError, TypeError):
            return None

    return value


# Field types for parsing
FIELD_TYPES = {
    "employee_id": "string",
    "first_name": "string",
    "last_name": "string",
    "email": "string",
    "business_unit": "string",
    "department": "string",
    "sub_department": "string",
    "manager_name": "string",
    "manager_employee_id": "string",
    "job_title": "string",
    "hire_date": "date",
    "last_increase_date": "date",
    "employment_type": "string",
    "schedule": "string",
    "weekly_hours": "decimal",
    "location": "string",
    "country": "string",
    "current_hourly_rate": "decimal",
    "current_weekly": "decimal",
    "current_annual": "decimal",
    "pay_grade": "string",
    "band_minimum": "decimal",
    "band_midpoint": "decimal",
    "band_maximum": "decimal",
    "current_compa_ratio": "decimal",
    "performance_score": "decimal",
    "performance_rating": "string",
    "prior_year_rate": "decimal",
    "prior_year_increase_pct": "decimal",
    "current_year_rate": "decimal",
    "current_year_increase_pct": "decimal",
    "gbp_eligible": "boolean",
    "cap_bonus_eligible": "boolean",
    "prior_year_bonus": "decimal",
    "ytd_total": "decimal",
}


@router.post("/validate", response_model=ImportValidationResult)
async def validate_import(
    file: UploadFile = File(...),
    current_user: TokenData = Depends(require_permission(Permission.COMPENSATION_MANAGE)),
):
    """Validate an import file before committing."""
    # Read file content
    content = await file.read()

    try:
        # Decode and parse CSV
        text = content.decode("utf-8-sig")  # Handle BOM
        reader = csv.DictReader(io.StringIO(text))

        rows = list(reader)
        headers = reader.fieldnames or []

        # Map headers
        mapped_headers = {}
        unmapped_headers = []

        for header in headers:
            if header in COLUMN_MAPPING:
                mapped_headers[header] = COLUMN_MAPPING[header]
            else:
                unmapped_headers.append(header)

        # Validate rows
        errors = []
        warnings = []
        valid_rows = 0

        for i, row in enumerate(rows, start=2):  # Start at 2 (1-indexed + header)
            row_errors = []

            # Check required fields
            emp_id = None
            for header in ["Emp ID#", "Employee ID"]:
                if header in row and row[header]:
                    emp_id = row[header]
                    break

            if not emp_id:
                row_errors.append("Missing Employee ID")

            # Validate data types
            for header, value in row.items():
                if header in COLUMN_MAPPING and value:
                    field = COLUMN_MAPPING[header]
                    field_type = FIELD_TYPES.get(field, "string")
                    parsed = parse_value(value, field_type)

                    if parsed is None and value.strip():
                        warnings.append(f"Row {i}: Could not parse '{value}' for {header}")

            if row_errors:
                errors.append({"row": i, "errors": row_errors})
            else:
                valid_rows += 1

        return ImportValidationResult(
            is_valid=len(errors) == 0,
            total_rows=len(rows),
            valid_rows=valid_rows,
            error_count=len(errors),
            warning_count=len(warnings),
            errors=errors[:50] if errors else None,  # Limit to first 50 errors
            warnings=warnings[:50] if warnings else None,
            mapped_columns=list(mapped_headers.keys()),
            unmapped_columns=unmapped_headers,
        )

    except Exception as e:
        raise HTTPException(
            status_code=400,
            detail=f"Failed to parse file: {str(e)}"
        )


@router.post("/employees", response_model=DatasetVersionResponse)
async def import_employees(
    cycle_id: UUID,
    file: UploadFile = File(...),
    source: str = Query("manual_upload", description="Import source"),
    current_user: TokenData = Depends(require_permission(Permission.COMPENSATION_MANAGE)),
):
    """Import employee compensation data from CSV."""
    client = get_supabase_client()

    # Verify cycle exists
    cycle = await client.select(
        "comp_cycles",
        "*",
        filters={"id": str(cycle_id), "tenant_id": str(current_user.tenant_id)},
        single=True,
    )

    if not cycle:
        raise HTTPException(status_code=404, detail="Compensation cycle not found")

    # Read file content
    content = await file.read()

    try:
        text = content.decode("utf-8-sig")
        reader = csv.DictReader(io.StringIO(text))
        rows = list(reader)

        # Get next version number
        existing_versions = await client.select(
            "comp_dataset_versions",
            "version_number",
            filters={"cycle_id": str(cycle_id)},
        ) or []

        next_version = 1
        if existing_versions:
            max_version = max(v["version_number"] for v in existing_versions)
            next_version = max_version + 1

        # Create dataset version
        version_data = {
            "tenant_id": str(current_user.tenant_id),
            "cycle_id": str(cycle_id),
            "version_number": next_version,
            "source": source,
            "source_file_name": file.filename,
            "imported_by": str(current_user.user_id),
            "row_count": len(rows),
            "status": "imported",
            "is_active": False,
        }

        version = await client.insert("comp_dataset_versions", version_data)
        version_id = version["id"]

        # Import employee snapshots
        imported_count = 0
        error_count = 0

        for row in rows:
            try:
                # Map columns
                snapshot_data = {
                    "tenant_id": str(current_user.tenant_id),
                    "dataset_version_id": version_id,
                }

                extra_attributes = {}

                for header, value in row.items():
                    if header in COLUMN_MAPPING:
                        field = COLUMN_MAPPING[header]
                        field_type = FIELD_TYPES.get(field, "string")
                        parsed = parse_value(value, field_type)

                        if parsed is not None:
                            snapshot_data[field] = parsed
                    elif value:
                        # Store unmapped columns in extra_attributes
                        extra_attributes[header] = value

                if extra_attributes:
                    snapshot_data["extra_attributes"] = json.dumps(extra_attributes)

                # Calculate compa ratio if not provided
                if "current_compa_ratio" not in snapshot_data:
                    if snapshot_data.get("current_annual") and snapshot_data.get("band_midpoint"):
                        current = float(snapshot_data["current_annual"])
                        midpoint = float(snapshot_data["band_midpoint"])
                        if midpoint > 0:
                            snapshot_data["current_compa_ratio"] = current / midpoint

                await client.insert("comp_employee_snapshots", snapshot_data)
                imported_count += 1

            except Exception as e:
                error_count += 1

        # Update version with counts
        await client.update(
            "comp_dataset_versions",
            {
                "row_count": imported_count,
                "error_count": error_count,
                "status": "validated" if error_count == 0 else "imported",
            },
            filters={"id": version_id},
        )

        # Refresh version
        version = await client.select(
            "comp_dataset_versions",
            "*",
            filters={"id": version_id},
            single=True,
        )

        return DatasetVersionResponse.model_validate(version)

    except Exception as e:
        raise HTTPException(
            status_code=400,
            detail=f"Import failed: {str(e)}"
        )


@router.get("/versions", response_model=list[DatasetVersionResponse])
async def list_dataset_versions(
    cycle_id: UUID,
    current_user: TokenData = Depends(require_permission(Permission.COMPENSATION_VIEW)),
):
    """List all dataset versions for a cycle."""
    client = get_supabase_client()

    versions = await client.select(
        "comp_dataset_versions",
        "*",
        filters={"cycle_id": str(cycle_id), "tenant_id": str(current_user.tenant_id)},
    ) or []

    # Sort by version number descending
    versions.sort(key=lambda x: x.get("version_number", 0), reverse=True)

    return [DatasetVersionResponse.model_validate(v) for v in versions]


@router.post("/versions/{version_id}/activate", response_model=DatasetVersionResponse)
async def activate_dataset_version(
    version_id: UUID,
    current_user: TokenData = Depends(require_permission(Permission.COMPENSATION_MANAGE)),
):
    """Activate a dataset version (deactivates others)."""
    client = get_supabase_client()

    # Get version
    version = await client.select(
        "comp_dataset_versions",
        "*",
        filters={"id": str(version_id), "tenant_id": str(current_user.tenant_id)},
        single=True,
    )

    if not version:
        raise HTTPException(status_code=404, detail="Dataset version not found")

    if version["status"] not in ["validated", "imported", "active"]:
        raise HTTPException(
            status_code=400,
            detail=f"Cannot activate version with status {version['status']}"
        )

    cycle_id = version["cycle_id"]

    # Deactivate other versions
    other_versions = await client.select(
        "comp_dataset_versions",
        "id",
        filters={"cycle_id": cycle_id, "is_active": "true"},
    ) or []

    for v in other_versions:
        if v["id"] != str(version_id):
            await client.update(
                "comp_dataset_versions",
                {"is_active": False},
                filters={"id": v["id"]},
            )

    # Activate this version
    version = await client.update(
        "comp_dataset_versions",
        {"is_active": True, "status": "active"},
        filters={"id": str(version_id)},
    )

    return DatasetVersionResponse.model_validate(version)


@router.get("/employees", response_model=PaginatedResponse[EmployeeSnapshotResponse])
async def list_employee_snapshots(
    version_id: UUID,
    page: int = Query(1, ge=1),
    page_size: int = Query(50, ge=1, le=200),
    department: Optional[str] = None,
    search: Optional[str] = None,
    current_user: TokenData = Depends(require_permission(Permission.COMPENSATION_VIEW)),
):
    """List employee snapshots for a dataset version."""
    client = get_supabase_client()

    # Verify version exists and user has access
    version = await client.select(
        "comp_dataset_versions",
        "*",
        filters={"id": str(version_id), "tenant_id": str(current_user.tenant_id)},
        single=True,
    )

    if not version:
        raise HTTPException(status_code=404, detail="Dataset version not found")

    # Get employees
    filters = {"dataset_version_id": str(version_id)}
    if department:
        filters["department"] = department

    employees = await client.select(
        "comp_employee_snapshots",
        "*",
        filters=filters,
    ) or []

    # Apply search filter
    if search:
        search_lower = search.lower()
        employees = [
            e for e in employees
            if search_lower in f"{e.get('first_name', '')} {e.get('last_name', '')}".lower()
            or search_lower in e.get("employee_id", "").lower()
        ]

    total = len(employees)

    # Sort by department, last name
    employees.sort(key=lambda x: (x.get("department") or "", x.get("last_name") or ""))

    # Paginate
    offset = (page - 1) * page_size
    employees = employees[offset:offset + page_size]

    # Parse JSONB
    items = []
    for emp in employees:
        emp = {k: v for k, v in emp.items()}
        if "extra_attributes" in emp and isinstance(emp["extra_attributes"], str):
            try:
                emp["extra_attributes"] = json.loads(emp["extra_attributes"])
            except:
                pass
        if "historical_data" in emp and isinstance(emp["historical_data"], str):
            try:
                emp["historical_data"] = json.loads(emp["historical_data"])
            except:
                pass
        items.append(EmployeeSnapshotResponse.model_validate(emp))

    return PaginatedResponse.create(
        items=items,
        total=total,
        page=page,
        page_size=page_size,
    )


@router.get("/departments", response_model=list[str])
async def list_departments(
    version_id: UUID,
    current_user: TokenData = Depends(require_permission(Permission.COMPENSATION_VIEW)),
):
    """Get distinct departments from a dataset version."""
    client = get_supabase_client()

    # Verify version exists
    version = await client.select(
        "comp_dataset_versions",
        "id",
        filters={"id": str(version_id), "tenant_id": str(current_user.tenant_id)},
        single=True,
    )

    if not version:
        raise HTTPException(status_code=404, detail="Dataset version not found")

    employees = await client.select(
        "comp_employee_snapshots",
        "department",
        filters={"dataset_version_id": str(version_id)},
    ) or []

    departments = sorted(set(
        e["department"] for e in employees
        if e.get("department")
    ))

    return departments


@router.delete("/versions/{version_id}", status_code=status.HTTP_204_NO_CONTENT)
async def delete_dataset_version(
    version_id: UUID,
    current_user: TokenData = Depends(require_permission(Permission.COMPENSATION_MANAGE)),
):
    """Delete a dataset version and its employees."""
    client = get_supabase_client()

    version = await client.select(
        "comp_dataset_versions",
        "*",
        filters={"id": str(version_id), "tenant_id": str(current_user.tenant_id)},
        single=True,
    )

    if not version:
        raise HTTPException(status_code=404, detail="Dataset version not found")

    if version["is_active"]:
        raise HTTPException(
            status_code=400,
            detail="Cannot delete active dataset version"
        )

    # Delete employee snapshots first
    employees = await client.select(
        "comp_employee_snapshots",
        "id",
        filters={"dataset_version_id": str(version_id)},
    ) or []

    for emp in employees:
        await client.delete("comp_employee_snapshots", filters={"id": emp["id"]})

    # Delete version
    await client.delete("comp_dataset_versions", filters={"id": str(version_id)})

    return None
