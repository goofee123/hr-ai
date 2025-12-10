"""Compliance audit logging middleware for OFCCP/EEO compliance."""

import json
from datetime import datetime, timezone
from typing import Callable, Optional
from uuid import UUID, uuid4

from fastapi import Request, Response
from starlette.middleware.base import BaseHTTPMiddleware
from starlette.types import ASGIApp

from app.core.supabase_client import get_supabase_client


# Actions that require audit logging for compliance
AUDITABLE_ACTIONS = {
    # Application lifecycle
    "POST:/api/v1/recruiting/applications": "application_create",
    "PATCH:/api/v1/recruiting/applications/{id}": "application_update",
    "POST:/api/v1/recruiting/applications/{id}/advance": "stage_advance",
    "POST:/api/v1/recruiting/applications/{id}/reject": "application_reject",
    # Candidate actions
    "POST:/api/v1/recruiting/candidates": "candidate_create",
    "PATCH:/api/v1/recruiting/candidates/{id}": "candidate_update",
    "DELETE:/api/v1/recruiting/candidates/{id}": "candidate_delete",
    # Offer actions
    "POST:/api/v1/recruiting/offers": "offer_create",
    "PATCH:/api/v1/recruiting/offers/{id}": "offer_update",
    "POST:/api/v1/recruiting/offers/{id}/extend": "offer_extend",
    "POST:/api/v1/recruiting/offers/{id}/rescind": "offer_rescind",
    # Bulk operations
    "POST:/api/v1/recruiting/bulk/stage-change": "bulk_stage_change",
    "POST:/api/v1/recruiting/bulk/reject": "bulk_reject",
    # EEO data
    "POST:/api/v1/recruiting/eeo/responses": "eeo_response_submit",
    "GET:/api/v1/recruiting/eeo/reports/summary": "eeo_report_access",
    "GET:/api/v1/recruiting/eeo/reports/adverse-impact": "adverse_impact_report_access",
    "GET:/api/v1/recruiting/eeo/reports/ofccp-export": "ofccp_export",
}


class AuditLogMiddleware(BaseHTTPMiddleware):
    """Middleware to log compliance-relevant actions."""

    def __init__(self, app: ASGIApp):
        super().__init__(app)

    async def dispatch(self, request: Request, call_next: Callable) -> Response:
        """Process request and log auditable actions."""
        # Get action type if this is an auditable request
        action_type = self._get_action_type(request)

        # Process the request
        response = await call_next(request)

        # Log if this was an auditable action and it succeeded
        if action_type and 200 <= response.status_code < 300:
            await self._log_audit_action(request, response, action_type)

        return response

    def _get_action_type(self, request: Request) -> Optional[str]:
        """Determine if this request should be audited."""
        method = request.method
        path = request.url.path

        # Direct match
        key = f"{method}:{path}"
        if key in AUDITABLE_ACTIONS:
            return AUDITABLE_ACTIONS[key]

        # Pattern matching for paths with IDs
        for pattern, action in AUDITABLE_ACTIONS.items():
            pattern_method, pattern_path = pattern.split(":", 1)
            if method != pattern_method:
                continue

            # Check if pattern matches (simple UUID pattern matching)
            if "{id}" in pattern_path:
                pattern_parts = pattern_path.split("/")
                path_parts = path.split("/")
                if len(pattern_parts) == len(path_parts):
                    matches = True
                    for pp, actual in zip(pattern_parts, path_parts):
                        if pp == "{id}":
                            # Check if it looks like a UUID
                            try:
                                UUID(actual)
                            except ValueError:
                                matches = False
                                break
                        elif pp != actual:
                            matches = False
                            break
                    if matches:
                        return action

        return None

    async def _log_audit_action(
        self, request: Request, response: Response, action_type: str
    ) -> None:
        """Log the action to the compliance audit table."""
        try:
            # Extract user info from request state (set by auth middleware)
            user_id = getattr(request.state, "user_id", None)
            tenant_id = getattr(request.state, "tenant_id", None)

            if not tenant_id:
                # Try to get from path or query params
                tenant_id = request.query_params.get("tenant_id")

            # Extract entity info from path
            entity_type, entity_id = self._extract_entity_info(request.url.path)

            # Build action data
            action_data = {
                "method": request.method,
                "path": request.url.path,
                "query_params": dict(request.query_params),
                "status_code": response.status_code,
            }

            # Get IP and user agent
            ip_address = self._get_client_ip(request)
            user_agent = request.headers.get("user-agent", "")

            # Log to database
            client = get_supabase_client()
            await client.insert(
                "compliance_audit_log",
                {
                    "id": str(uuid4()),
                    "tenant_id": str(tenant_id) if tenant_id else None,
                    "action_type": action_type,
                    "entity_type": entity_type,
                    "entity_id": str(entity_id) if entity_id else None,
                    "user_id": str(user_id) if user_id else None,
                    "action_data": action_data,
                    "ip_address": ip_address,
                    "user_agent": user_agent[:500] if user_agent else None,
                    "created_at": datetime.now(timezone.utc).isoformat(),
                },
            )
        except Exception as e:
            # Log error but don't fail the request
            print(f"Audit log error: {e}")

    def _extract_entity_info(self, path: str) -> tuple[Optional[str], Optional[UUID]]:
        """Extract entity type and ID from path."""
        parts = path.strip("/").split("/")

        # Common patterns:
        # /api/v1/recruiting/applications/{id}
        # /api/v1/recruiting/candidates/{id}
        # /api/v1/recruiting/offers/{id}

        entity_type = None
        entity_id = None

        for i, part in enumerate(parts):
            # Check if this part is a UUID
            try:
                potential_id = UUID(part)
                # The previous part is likely the entity type
                if i > 0:
                    entity_type = parts[i - 1]
                    # Singularize common plurals
                    if entity_type.endswith("s"):
                        entity_type = entity_type[:-1]
                    entity_id = potential_id
                break
            except ValueError:
                continue

        return entity_type, entity_id

    def _get_client_ip(self, request: Request) -> str:
        """Get client IP address, handling proxies."""
        # Check X-Forwarded-For header first (for proxies/load balancers)
        forwarded = request.headers.get("x-forwarded-for")
        if forwarded:
            # Take the first IP (original client)
            return forwarded.split(",")[0].strip()

        # Check X-Real-IP header
        real_ip = request.headers.get("x-real-ip")
        if real_ip:
            return real_ip

        # Fall back to direct client
        if request.client:
            return request.client.host

        return "unknown"


# Utility function for manual audit logging from within routes
async def log_audit_event(
    tenant_id: UUID,
    user_id: UUID,
    action_type: str,
    entity_type: str,
    entity_id: UUID,
    action_data: dict,
    ip_address: Optional[str] = None,
    user_agent: Optional[str] = None,
) -> None:
    """Manually log an audit event (for use within routes)."""
    try:
        client = get_supabase_client()
        await client.insert(
            "compliance_audit_log",
            {
                "id": str(uuid4()),
                "tenant_id": str(tenant_id),
                "action_type": action_type,
                "entity_type": entity_type,
                "entity_id": str(entity_id),
                "user_id": str(user_id),
                "action_data": action_data,
                "ip_address": ip_address,
                "user_agent": user_agent[:500] if user_agent else None,
                "created_at": datetime.now(timezone.utc).isoformat(),
            },
        )
    except Exception as e:
        print(f"Manual audit log error: {e}")


# Action type constants for manual logging
class AuditAction:
    """Constants for audit action types."""

    # Application lifecycle
    APPLICATION_CREATE = "application_create"
    APPLICATION_UPDATE = "application_update"
    STAGE_ADVANCE = "stage_advance"
    APPLICATION_REJECT = "application_reject"
    APPLICATION_WITHDRAW = "application_withdraw"

    # Candidate actions
    CANDIDATE_CREATE = "candidate_create"
    CANDIDATE_UPDATE = "candidate_update"
    CANDIDATE_DELETE = "candidate_delete"
    CANDIDATE_MERGE = "candidate_merge"

    # Offer actions
    OFFER_CREATE = "offer_create"
    OFFER_UPDATE = "offer_update"
    OFFER_EXTEND = "offer_extend"
    OFFER_ACCEPT = "offer_accept"
    OFFER_DECLINE = "offer_decline"
    OFFER_RESCIND = "offer_rescind"

    # Interview actions
    INTERVIEW_SCHEDULE = "interview_schedule"
    INTERVIEW_COMPLETE = "interview_complete"
    INTERVIEW_CANCEL = "interview_cancel"
    SCORECARD_SUBMIT = "scorecard_submit"

    # EEO/Compliance
    EEO_RESPONSE_SUBMIT = "eeo_response_submit"
    EEO_REPORT_ACCESS = "eeo_report_access"
    ADVERSE_IMPACT_ACCESS = "adverse_impact_report_access"
    OFCCP_EXPORT = "ofccp_export"

    # Bulk operations
    BULK_STAGE_CHANGE = "bulk_stage_change"
    BULK_REJECT = "bulk_reject"
    BULK_EMAIL = "bulk_email"

    # Data access
    CANDIDATE_DATA_EXPORT = "candidate_data_export"
    APPLICANT_DATA_EXPORT = "applicant_data_export"
