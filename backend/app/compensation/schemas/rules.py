"""Rules Engine schemas."""

from datetime import date, datetime
from typing import Optional, Any, Dict, List
from uuid import UUID

from pydantic import BaseModel, Field


class RuleOperator:
    """Supported rule operators."""
    EQ = "EQ"
    NEQ = "NEQ"
    GT = "GT"
    GTE = "GTE"
    LT = "LT"
    LTE = "LTE"
    IN = "IN"
    NOT_IN = "NOT_IN"
    BETWEEN = "BETWEEN"
    CONTAINS = "CONTAINS"
    IS_NULL = "IS_NULL"
    IS_NOT_NULL = "IS_NOT_NULL"


class RuleActionType:
    """Supported rule action types."""
    SET_MERIT_PERCENT = "SET_MERIT_PERCENT"
    SET_MERIT_AMOUNT = "SET_MERIT_AMOUNT"
    SET_BONUS_PERCENT = "SET_BONUS_PERCENT"
    SET_BONUS_AMOUNT = "SET_BONUS_AMOUNT"
    SET_MINIMUM_SALARY = "SET_MINIMUM_SALARY"
    CAP_TO_BAND_MAX = "CAP_TO_BAND_MAX"
    CAP_BONUS = "CAP_BONUS"
    FLAG_FOR_REVIEW = "FLAG_FOR_REVIEW"
    REQUIRE_JUSTIFICATION = "REQUIRE_JUSTIFICATION"
    SET_PROMOTION_FLAG = "SET_PROMOTION_FLAG"
    EXCLUDE = "EXCLUDE"


class RuleType:
    """Rule types."""
    MERIT = "merit"
    BONUS = "bonus"
    PROMOTION = "promotion"
    MINIMUM_SALARY = "minimum_salary"
    CAP = "cap"
    ELIGIBILITY = "eligibility"


class RuleCondition(BaseModel):
    """Schema for a single rule condition."""
    field: str = Field(..., description="Employee field to evaluate")
    operator: str = Field(..., description="Comparison operator (EQ, GT, GTE, LT, LTE, IN, BETWEEN, etc.)")
    value: Any = Field(..., description="Value to compare against")


class RuleConditionGroup(BaseModel):
    """Schema for a group of conditions with logic (AND/OR)."""
    logic: str = Field(default="AND", description="Logic operator: AND or OR")
    conditions: List[Any] = Field(..., description="List of conditions or nested condition groups")


class RuleAction(BaseModel):
    """Schema for a rule action."""
    action_type: str = Field(..., description="Type of action to perform")
    value: Optional[Any] = None
    value_field: Optional[str] = None
    value_formula: Optional[str] = None
    min_value: Optional[float] = None
    max_value: Optional[float] = None
    apply_to: Optional[str] = None
    notes: Optional[str] = None


class RuleSetCreate(BaseModel):
    """Schema for creating a rule set."""
    name: str = Field(..., min_length=1, max_length=100)
    description: Optional[str] = None
    is_active: bool = True
    is_default: bool = False


class RuleSetUpdate(BaseModel):
    """Schema for updating a rule set."""
    name: Optional[str] = Field(None, min_length=1, max_length=100)
    description: Optional[str] = None
    is_active: Optional[bool] = None
    is_default: Optional[bool] = None


class RuleSetResponse(BaseModel):
    """Schema for rule set response."""
    id: UUID
    tenant_id: UUID
    name: str
    description: Optional[str] = None
    is_active: bool
    is_default: bool
    version: int
    created_by: Optional[UUID] = None
    created_at: datetime
    updated_at: datetime
    # Computed
    rule_count: int = 0

    class Config:
        from_attributes = True


class RuleCreate(BaseModel):
    """Schema for creating a rule."""
    rule_set_id: UUID
    name: str = Field(..., min_length=1, max_length=100)
    description: Optional[str] = None
    priority: int = Field(default=100, ge=1, le=1000)
    is_active: bool = True
    rule_type: str = Field(..., description="Rule type: merit, bonus, promotion, minimum_salary, cap, eligibility")
    conditions: Dict[str, Any] = Field(..., description="JSONB conditions with nested logic")
    actions: Dict[str, Any] = Field(..., description="JSONB actions to perform when conditions match")
    effective_date: Optional[date] = None
    expiry_date: Optional[date] = None


class RuleUpdate(BaseModel):
    """Schema for updating a rule."""
    name: Optional[str] = Field(None, min_length=1, max_length=100)
    description: Optional[str] = None
    priority: Optional[int] = Field(None, ge=1, le=1000)
    is_active: Optional[bool] = None
    rule_type: Optional[str] = None
    conditions: Optional[Dict[str, Any]] = None
    actions: Optional[Dict[str, Any]] = None
    effective_date: Optional[date] = None
    expiry_date: Optional[date] = None


class RuleResponse(BaseModel):
    """Schema for rule response."""
    id: UUID
    tenant_id: UUID
    rule_set_id: UUID
    name: str
    description: Optional[str] = None
    priority: int
    is_active: bool
    rule_type: str
    conditions: Dict[str, Any]
    actions: Dict[str, Any]
    effective_date: Optional[date] = None
    expiry_date: Optional[date] = None
    created_by: Optional[UUID] = None
    created_at: datetime
    updated_at: datetime

    class Config:
        from_attributes = True


class RuleTestRequest(BaseModel):
    """Schema for testing a rule against sample data."""
    rule_id: Optional[UUID] = None
    conditions: Optional[Dict[str, Any]] = None
    actions: Optional[Dict[str, Any]] = None
    test_employee: Dict[str, Any] = Field(..., description="Sample employee data to test against")


class RuleTestResult(BaseModel):
    """Schema for rule test result."""
    matched: bool
    conditions_evaluated: List[Dict[str, Any]]
    actions_applied: List[Dict[str, Any]]
    result: Dict[str, Any]
