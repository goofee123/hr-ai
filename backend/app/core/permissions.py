"""Role-Based Access Control (RBAC) permissions."""

from enum import Enum
from functools import wraps
from typing import Callable, List

from fastapi import Depends, HTTPException, status

from app.core.security import TokenData, get_current_user


class UserRole(str, Enum):
    """User roles in the system."""

    SUPER_ADMIN = "super_admin"
    HR_ADMIN = "hr_admin"
    RECRUITER = "recruiter"
    HIRING_MANAGER = "hiring_manager"
    COMPENSATION_ANALYST = "compensation_analyst"
    EXECUTIVE = "executive"
    PAYROLL = "payroll"
    EMPLOYEE = "employee"


class Permission(str, Enum):
    """Available permissions in the system."""

    # Recruiting - Jobs
    JOBS_VIEW = "jobs:view"
    JOBS_CREATE = "jobs:create"
    JOBS_EDIT = "jobs:edit"
    JOBS_DELETE = "jobs:delete"
    JOBS_CHANGE_STATUS = "jobs:change_status"

    # Recruiting - Candidates
    CANDIDATES_VIEW = "candidates:view"
    CANDIDATES_CREATE = "candidates:create"
    CANDIDATES_EDIT = "candidates:edit"
    CANDIDATES_DELETE = "candidates:delete"
    CANDIDATES_ADVANCE = "candidates:advance"

    # Recruiting - Applications
    APPLICATIONS_VIEW = "applications:view"
    APPLICATIONS_CREATE = "applications:create"
    APPLICATIONS_EDIT = "applications:edit"
    APPLICATIONS_MOVE_STAGE = "applications:move_stage"
    APPLICATIONS_REJECT = "applications:reject"

    # Recruiting - Tasks
    TASKS_VIEW = "tasks:view"
    TASKS_CREATE = "tasks:create"
    TASKS_EDIT = "tasks:edit"
    TASKS_DELETE = "tasks:delete"
    TASKS_ASSIGN = "tasks:assign"
    TASKS_COMPLETE = "tasks:complete"

    # Recruiting - Workload
    WORKLOAD_VIEW = "workload:view"
    WORKLOAD_ASSIGN = "workload:assign"

    # Compensation - Cycles
    CYCLES_VIEW = "cycles:view"
    CYCLES_CREATE = "cycles:create"
    CYCLES_EDIT = "cycles:edit"
    CYCLES_LAUNCH = "cycles:launch"

    # Compensation - Scenarios
    SCENARIOS_VIEW = "scenarios:view"
    SCENARIOS_CREATE = "scenarios:create"
    SCENARIOS_SELECT = "scenarios:select"

    # Compensation - Rules
    RULES_VIEW = "rules:view"
    RULES_CREATE = "rules:create"
    RULES_EDIT = "rules:edit"
    RULES_DELETE = "rules:delete"

    # Compensation - Worksheet
    WORKSHEET_VIEW_ALL = "worksheet:view_all"
    WORKSHEET_VIEW_OWN = "worksheet:view_own"
    WORKSHEET_EDIT = "worksheet:edit"
    WORKSHEET_APPROVE = "worksheet:approve"

    # Compensation - Export
    EXPORT_PAYROLL = "export:payroll"

    # Admin
    ADMIN_USERS = "admin:users"
    ADMIN_ORG_STRUCTURE = "admin:org_structure"
    ADMIN_CONFIG = "admin:config"
    ADMIN_PIPELINE_TEMPLATES = "admin:pipeline_templates"
    ADMIN_DISPOSITION_REASONS = "admin:disposition_reasons"
    ADMIN_APPLICATION_SOURCES = "admin:application_sources"
    ADMIN_SLA_SETTINGS = "admin:sla_settings"

    # EEO Compliance (restricted to HR Admin only)
    EEO_VIEW = "eeo:view"
    EEO_REPORTS = "eeo:reports"
    EEO_EXPORT = "eeo:export"
    EEO_AUDIT = "eeo:audit"

    # General Recruiting Permissions (for interview scheduling, etc.)
    RECRUITING_READ = "recruiting:read"
    RECRUITING_WRITE = "recruiting:write"
    RECRUITING_REPORTS = "recruiting:reports"

    # Interview-specific permissions
    INTERVIEWS_VIEW = "interviews:view"
    INTERVIEWS_SCHEDULE = "interviews:schedule"
    INTERVIEWS_MANAGE = "interviews:manage"


# Role to permissions mapping
ROLE_PERMISSIONS: dict[UserRole, set[Permission]] = {
    UserRole.SUPER_ADMIN: set(Permission),  # All permissions
    UserRole.HR_ADMIN: {
        # Recruiting
        Permission.JOBS_VIEW,
        Permission.JOBS_CREATE,
        Permission.JOBS_EDIT,
        Permission.JOBS_DELETE,
        Permission.JOBS_CHANGE_STATUS,
        Permission.CANDIDATES_VIEW,
        Permission.CANDIDATES_CREATE,
        Permission.CANDIDATES_EDIT,
        Permission.CANDIDATES_DELETE,
        Permission.CANDIDATES_ADVANCE,
        Permission.APPLICATIONS_VIEW,
        Permission.APPLICATIONS_CREATE,
        Permission.APPLICATIONS_EDIT,
        Permission.APPLICATIONS_MOVE_STAGE,
        Permission.APPLICATIONS_REJECT,
        Permission.TASKS_VIEW,
        Permission.TASKS_CREATE,
        Permission.TASKS_EDIT,
        Permission.TASKS_DELETE,
        Permission.TASKS_ASSIGN,
        Permission.TASKS_COMPLETE,
        Permission.WORKLOAD_VIEW,
        Permission.WORKLOAD_ASSIGN,
        # General Recruiting
        Permission.RECRUITING_READ,
        Permission.RECRUITING_WRITE,
        Permission.RECRUITING_REPORTS,
        # Interview Scheduling
        Permission.INTERVIEWS_VIEW,
        Permission.INTERVIEWS_SCHEDULE,
        Permission.INTERVIEWS_MANAGE,
        # Compensation
        Permission.CYCLES_VIEW,
        Permission.CYCLES_CREATE,
        Permission.CYCLES_EDIT,
        Permission.CYCLES_LAUNCH,
        Permission.SCENARIOS_VIEW,
        Permission.SCENARIOS_CREATE,
        Permission.RULES_VIEW,
        Permission.RULES_CREATE,
        Permission.RULES_EDIT,
        Permission.RULES_DELETE,
        Permission.WORKSHEET_VIEW_ALL,
        Permission.WORKSHEET_APPROVE,
        Permission.EXPORT_PAYROLL,
        # Admin
        Permission.ADMIN_USERS,
        Permission.ADMIN_ORG_STRUCTURE,
        Permission.ADMIN_CONFIG,
        Permission.ADMIN_PIPELINE_TEMPLATES,
        Permission.ADMIN_DISPOSITION_REASONS,
        Permission.ADMIN_APPLICATION_SOURCES,
        Permission.ADMIN_SLA_SETTINGS,
        # EEO Compliance
        Permission.EEO_VIEW,
        Permission.EEO_REPORTS,
        Permission.EEO_EXPORT,
        Permission.EEO_AUDIT,
    },
    UserRole.RECRUITER: {
        Permission.JOBS_VIEW,
        Permission.CANDIDATES_VIEW,
        Permission.CANDIDATES_CREATE,
        Permission.CANDIDATES_EDIT,
        Permission.CANDIDATES_ADVANCE,
        Permission.APPLICATIONS_VIEW,
        Permission.APPLICATIONS_CREATE,
        Permission.APPLICATIONS_EDIT,
        Permission.APPLICATIONS_MOVE_STAGE,
        Permission.APPLICATIONS_REJECT,
        Permission.TASKS_VIEW,
        Permission.TASKS_CREATE,
        Permission.TASKS_EDIT,
        Permission.TASKS_DELETE,
        Permission.TASKS_COMPLETE,
        # General Recruiting
        Permission.RECRUITING_READ,
        Permission.RECRUITING_WRITE,
        Permission.RECRUITING_REPORTS,
        # Interview Scheduling
        Permission.INTERVIEWS_VIEW,
        Permission.INTERVIEWS_SCHEDULE,
        Permission.INTERVIEWS_MANAGE,
    },
    UserRole.HIRING_MANAGER: {
        Permission.JOBS_VIEW,
        Permission.JOBS_CREATE,
        Permission.JOBS_EDIT,
        Permission.CANDIDATES_VIEW,
        Permission.CANDIDATES_ADVANCE,
        Permission.APPLICATIONS_VIEW,
        Permission.TASKS_VIEW,
        Permission.WORKSHEET_VIEW_OWN,
        Permission.WORKSHEET_EDIT,
        # Recruiting read (for interviews)
        Permission.RECRUITING_READ,
        Permission.INTERVIEWS_VIEW,
    },
    UserRole.COMPENSATION_ANALYST: {
        Permission.CYCLES_VIEW,
        Permission.SCENARIOS_VIEW,
        Permission.SCENARIOS_CREATE,
        Permission.RULES_VIEW,
        Permission.WORKSHEET_VIEW_ALL,
    },
    UserRole.EXECUTIVE: {
        Permission.JOBS_VIEW,
        Permission.CYCLES_VIEW,
        Permission.SCENARIOS_VIEW,
        Permission.SCENARIOS_SELECT,
        Permission.WORKSHEET_VIEW_ALL,
    },
    UserRole.PAYROLL: {
        Permission.CYCLES_VIEW,
        Permission.EXPORT_PAYROLL,
    },
    UserRole.EMPLOYEE: set(),  # No special permissions
}


def get_role_permissions(role: UserRole) -> set[Permission]:
    """Get all permissions for a given role."""
    return ROLE_PERMISSIONS.get(role, set())


def has_permission(role: str, permission: Permission) -> bool:
    """Check if a role has a specific permission."""
    try:
        user_role = UserRole(role)
        return permission in get_role_permissions(user_role)
    except ValueError:
        return False


def has_any_permission(role: str, permissions: List[Permission]) -> bool:
    """Check if a role has any of the specified permissions."""
    return any(has_permission(role, p) for p in permissions)


def has_all_permissions(role: str, permissions: List[Permission]) -> bool:
    """Check if a role has all of the specified permissions."""
    return all(has_permission(role, p) for p in permissions)


class PermissionChecker:
    """Dependency class for checking permissions."""

    def __init__(self, required_permissions: List[Permission], require_all: bool = True):
        self.required_permissions = required_permissions
        self.require_all = require_all

    async def __call__(self, current_user: TokenData = Depends(get_current_user)) -> TokenData:
        """Check if the current user has the required permissions."""
        if self.require_all:
            has_access = has_all_permissions(current_user.role, self.required_permissions)
        else:
            has_access = has_any_permission(current_user.role, self.required_permissions)

        if not has_access:
            raise HTTPException(
                status_code=status.HTTP_403_FORBIDDEN,
                detail="Insufficient permissions",
            )

        return current_user


def require_permission(permission: Permission):
    """Dependency factory for requiring a single permission."""
    return PermissionChecker([permission])


def require_any_permission(*permissions: Permission):
    """Dependency factory for requiring any of the specified permissions."""
    return PermissionChecker(list(permissions), require_all=False)


def require_all_permissions(*permissions: Permission):
    """Dependency factory for requiring all specified permissions."""
    return PermissionChecker(list(permissions), require_all=True)
