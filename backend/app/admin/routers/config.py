"""Admin configuration router - using Supabase REST API."""

from typing import List, Dict, Any
from uuid import UUID
import json

from fastapi import APIRouter, Depends, HTTPException, status

from app.core.permissions import Permission, require_permission
from app.core.security import TokenData
from app.core.supabase_client import get_supabase_client
from app.admin.schemas import (
    PipelineTemplateCreate,
    PipelineTemplateUpdate,
    PipelineTemplateResponse,
    DispositionReasonCreate,
    DispositionReasonUpdate,
    DispositionReasonResponse,
    ApplicationSourceCreate,
    ApplicationSourceUpdate,
    ApplicationSourceResponse,
    SLAConfigurationCreate,
    SLAConfigurationUpdate,
    SLAConfigurationResponse,
)

router = APIRouter()


def parse_jsonb_fields(data: Dict[str, Any], fields: List[str]) -> Dict[str, Any]:
    """Parse JSONB fields that might come as strings from Supabase REST API."""
    for field in fields:
        if field in data and isinstance(data[field], str):
            try:
                data[field] = json.loads(data[field])
            except (json.JSONDecodeError, TypeError):
                pass
    return data


# ====================================================================
# PIPELINE TEMPLATES
# ====================================================================


@router.get("/pipeline-templates", response_model=List[PipelineTemplateResponse])
async def list_pipeline_templates(
    current_user: TokenData = Depends(require_permission(Permission.ADMIN_PIPELINE_TEMPLATES)),
):
    """List all pipeline templates for the tenant."""
    client = get_supabase_client()

    templates = await client.select(
        "pipeline_templates",
        "*",
        filters={"tenant_id": str(current_user.tenant_id)},
        return_empty_on_404=True,
    ) or []

    # Parse JSONB fields and sort by name
    templates = [parse_jsonb_fields(t, ["stages"]) for t in templates]
    templates.sort(key=lambda x: x.get("name", ""))

    return [PipelineTemplateResponse.model_validate(t) for t in templates]


@router.post("/pipeline-templates", response_model=PipelineTemplateResponse, status_code=status.HTTP_201_CREATED)
async def create_pipeline_template(
    template_data: PipelineTemplateCreate,
    current_user: TokenData = Depends(require_permission(Permission.ADMIN_PIPELINE_TEMPLATES)),
):
    """Create a new pipeline template."""
    client = get_supabase_client()

    # Check for duplicate name
    existing = await client.select(
        "pipeline_templates",
        "id",
        filters={
            "tenant_id": str(current_user.tenant_id),
            "name": template_data.name,
        },
        single=True,
    )

    if existing:
        raise HTTPException(
            status_code=status.HTTP_409_CONFLICT,
            detail="Pipeline template with this name already exists",
        )

    # If marking as default, unset other defaults
    if template_data.is_default:
        existing_default = await client.select(
            "pipeline_templates",
            "id",
            filters={
                "tenant_id": str(current_user.tenant_id),
                "is_default": "true",
            },
        ) or []
        for existing_t in existing_default:
            await client.update(
                "pipeline_templates",
                {"is_default": False},
                filters={"id": existing_t["id"]},
            )

    # Convert stages to JSON-serializable format
    stages_json = [stage.model_dump() for stage in template_data.stages]

    template_dict = {
        "tenant_id": str(current_user.tenant_id),
        "name": template_data.name,
        "description": template_data.description,
        "is_default": template_data.is_default,
        "stages": json.dumps(stages_json),
        "created_by": str(current_user.user_id),
    }

    template = await client.insert("pipeline_templates", template_dict)

    # Parse stages back from JSON string if needed
    if isinstance(template.get("stages"), str):
        template["stages"] = json.loads(template["stages"])

    return PipelineTemplateResponse.model_validate(template)


@router.get("/pipeline-templates/{template_id}", response_model=PipelineTemplateResponse)
async def get_pipeline_template(
    template_id: UUID,
    current_user: TokenData = Depends(require_permission(Permission.ADMIN_PIPELINE_TEMPLATES)),
):
    """Get a pipeline template by ID."""
    client = get_supabase_client()

    template = await client.select(
        "pipeline_templates",
        "*",
        filters={
            "id": str(template_id),
            "tenant_id": str(current_user.tenant_id),
        },
        single=True,
    )

    if not template:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Pipeline template not found",
        )

    return PipelineTemplateResponse.model_validate(template)


@router.patch("/pipeline-templates/{template_id}", response_model=PipelineTemplateResponse)
async def update_pipeline_template(
    template_id: UUID,
    template_data: PipelineTemplateUpdate,
    current_user: TokenData = Depends(require_permission(Permission.ADMIN_PIPELINE_TEMPLATES)),
):
    """Update a pipeline template."""
    client = get_supabase_client()

    # Check template exists
    template = await client.select(
        "pipeline_templates",
        "*",
        filters={
            "id": str(template_id),
            "tenant_id": str(current_user.tenant_id),
        },
        single=True,
    )

    if not template:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Pipeline template not found",
        )

    # Check for name conflict if changing name
    if template_data.name and template_data.name != template["name"]:
        existing = await client.select(
            "pipeline_templates",
            "id",
            filters={
                "tenant_id": str(current_user.tenant_id),
                "name": template_data.name,
            },
            single=True,
        )
        if existing and existing["id"] != str(template_id):
            raise HTTPException(
                status_code=status.HTTP_409_CONFLICT,
                detail="Another template with this name already exists",
            )

    # Handle default flag
    if template_data.is_default:
        existing_default = await client.select(
            "pipeline_templates",
            "id",
            filters={
                "tenant_id": str(current_user.tenant_id),
                "is_default": "true",
            },
        ) or []
        for existing_t in existing_default:
            if existing_t["id"] != str(template_id):
                await client.update(
                    "pipeline_templates",
                    {"is_default": False},
                    filters={"id": existing_t["id"]},
                )

    # Build update data
    update_data = template_data.model_dump(exclude_unset=True)
    if "stages" in update_data and update_data["stages"] is not None:
        update_data["stages"] = json.dumps([s.model_dump() if hasattr(s, 'model_dump') else s for s in update_data["stages"]])

    if update_data:
        template = await client.update(
            "pipeline_templates",
            update_data,
            filters={"id": str(template_id)},
        )

    return PipelineTemplateResponse.model_validate(template)


@router.delete("/pipeline-templates/{template_id}", status_code=status.HTTP_204_NO_CONTENT)
async def delete_pipeline_template(
    template_id: UUID,
    current_user: TokenData = Depends(require_permission(Permission.ADMIN_PIPELINE_TEMPLATES)),
):
    """Delete a pipeline template."""
    client = get_supabase_client()

    # Check template exists
    template = await client.select(
        "pipeline_templates",
        "id",
        filters={
            "id": str(template_id),
            "tenant_id": str(current_user.tenant_id),
        },
        single=True,
    )

    if not template:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Pipeline template not found",
        )

    await client.delete("pipeline_templates", filters={"id": str(template_id)})

    return None


# ====================================================================
# DISPOSITION REASONS
# ====================================================================


@router.get("/disposition-reasons", response_model=List[DispositionReasonResponse])
async def list_disposition_reasons(
    active_only: bool = False,
    current_user: TokenData = Depends(require_permission(Permission.ADMIN_DISPOSITION_REASONS)),
):
    """List all disposition reasons for the tenant."""
    client = get_supabase_client()

    filters = {"tenant_id": str(current_user.tenant_id)}
    if active_only:
        filters["is_active"] = "true"

    reasons = await client.select("disposition_reasons", "*", filters=filters, return_empty_on_404=True) or []

    # Sort by sort_order
    reasons.sort(key=lambda x: x.get("sort_order", 0))

    return [DispositionReasonResponse.model_validate(r) for r in reasons]


@router.post("/disposition-reasons", response_model=DispositionReasonResponse, status_code=status.HTTP_201_CREATED)
async def create_disposition_reason(
    reason_data: DispositionReasonCreate,
    current_user: TokenData = Depends(require_permission(Permission.ADMIN_DISPOSITION_REASONS)),
):
    """Create a new disposition reason."""
    client = get_supabase_client()

    # Check for duplicate code
    existing = await client.select(
        "disposition_reasons",
        "id",
        filters={
            "tenant_id": str(current_user.tenant_id),
            "code": reason_data.code,
        },
        single=True,
    )

    if existing:
        raise HTTPException(
            status_code=status.HTTP_409_CONFLICT,
            detail="Disposition reason with this code already exists",
        )

    reason_dict = {
        "tenant_id": str(current_user.tenant_id),
        **reason_data.model_dump(),
    }

    reason = await client.insert("disposition_reasons", reason_dict)

    return DispositionReasonResponse.model_validate(reason)


@router.get("/disposition-reasons/{reason_id}", response_model=DispositionReasonResponse)
async def get_disposition_reason(
    reason_id: UUID,
    current_user: TokenData = Depends(require_permission(Permission.ADMIN_DISPOSITION_REASONS)),
):
    """Get a disposition reason by ID."""
    client = get_supabase_client()

    reason = await client.select(
        "disposition_reasons",
        "*",
        filters={
            "id": str(reason_id),
            "tenant_id": str(current_user.tenant_id),
        },
        single=True,
    )

    if not reason:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Disposition reason not found",
        )

    return DispositionReasonResponse.model_validate(reason)


@router.patch("/disposition-reasons/{reason_id}", response_model=DispositionReasonResponse)
async def update_disposition_reason(
    reason_id: UUID,
    reason_data: DispositionReasonUpdate,
    current_user: TokenData = Depends(require_permission(Permission.ADMIN_DISPOSITION_REASONS)),
):
    """Update a disposition reason."""
    client = get_supabase_client()

    # Check reason exists
    reason = await client.select(
        "disposition_reasons",
        "*",
        filters={
            "id": str(reason_id),
            "tenant_id": str(current_user.tenant_id),
        },
        single=True,
    )

    if not reason:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Disposition reason not found",
        )

    # Check for code conflict if changing code
    if reason_data.code and reason_data.code != reason["code"]:
        existing = await client.select(
            "disposition_reasons",
            "id",
            filters={
                "tenant_id": str(current_user.tenant_id),
                "code": reason_data.code,
            },
            single=True,
        )
        if existing and existing["id"] != str(reason_id):
            raise HTTPException(
                status_code=status.HTTP_409_CONFLICT,
                detail="Another reason with this code already exists",
            )

    update_data = reason_data.model_dump(exclude_unset=True)
    if update_data:
        reason = await client.update(
            "disposition_reasons",
            update_data,
            filters={"id": str(reason_id)},
        )

    return DispositionReasonResponse.model_validate(reason)


@router.delete("/disposition-reasons/{reason_id}", status_code=status.HTTP_204_NO_CONTENT)
async def delete_disposition_reason(
    reason_id: UUID,
    current_user: TokenData = Depends(require_permission(Permission.ADMIN_DISPOSITION_REASONS)),
):
    """Delete a disposition reason."""
    client = get_supabase_client()

    # Check reason exists
    reason = await client.select(
        "disposition_reasons",
        "id",
        filters={
            "id": str(reason_id),
            "tenant_id": str(current_user.tenant_id),
        },
        single=True,
    )

    if not reason:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Disposition reason not found",
        )

    await client.delete("disposition_reasons", filters={"id": str(reason_id)})

    return None


# ====================================================================
# APPLICATION SOURCES
# ====================================================================


@router.get("/application-sources", response_model=List[ApplicationSourceResponse])
async def list_application_sources(
    active_only: bool = False,
    current_user: TokenData = Depends(require_permission(Permission.ADMIN_APPLICATION_SOURCES)),
):
    """List all application sources for the tenant."""
    client = get_supabase_client()

    filters = {"tenant_id": str(current_user.tenant_id)}
    if active_only:
        filters["is_active"] = "true"

    sources = await client.select("application_sources", "*", filters=filters, return_empty_on_404=True) or []

    # Parse JSONB fields and sort by name
    sources = [parse_jsonb_fields(s, ["integration_config"]) for s in sources]
    sources.sort(key=lambda x: x.get("name", ""))

    return [ApplicationSourceResponse.model_validate(s) for s in sources]


@router.post("/application-sources", response_model=ApplicationSourceResponse, status_code=status.HTTP_201_CREATED)
async def create_application_source(
    source_data: ApplicationSourceCreate,
    current_user: TokenData = Depends(require_permission(Permission.ADMIN_APPLICATION_SOURCES)),
):
    """Create a new application source."""
    client = get_supabase_client()

    # Check for duplicate name
    existing = await client.select(
        "application_sources",
        "id",
        filters={
            "tenant_id": str(current_user.tenant_id),
            "name": source_data.name,
        },
        single=True,
    )

    if existing:
        raise HTTPException(
            status_code=status.HTTP_409_CONFLICT,
            detail="Application source with this name already exists",
        )

    source_dict = {
        "tenant_id": str(current_user.tenant_id),
        "name": source_data.name,
        "source_type": source_data.source_type,
        "integration_config": json.dumps(source_data.integration_config or {}),
        "is_active": source_data.is_active,
    }

    source = await client.insert("application_sources", source_dict)

    # Parse integration_config if it's a string
    if isinstance(source.get("integration_config"), str):
        source["integration_config"] = json.loads(source["integration_config"])

    return ApplicationSourceResponse.model_validate(source)


@router.get("/application-sources/{source_id}", response_model=ApplicationSourceResponse)
async def get_application_source(
    source_id: UUID,
    current_user: TokenData = Depends(require_permission(Permission.ADMIN_APPLICATION_SOURCES)),
):
    """Get an application source by ID."""
    client = get_supabase_client()

    source = await client.select(
        "application_sources",
        "*",
        filters={
            "id": str(source_id),
            "tenant_id": str(current_user.tenant_id),
        },
        single=True,
    )

    if not source:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Application source not found",
        )

    return ApplicationSourceResponse.model_validate(source)


@router.patch("/application-sources/{source_id}", response_model=ApplicationSourceResponse)
async def update_application_source(
    source_id: UUID,
    source_data: ApplicationSourceUpdate,
    current_user: TokenData = Depends(require_permission(Permission.ADMIN_APPLICATION_SOURCES)),
):
    """Update an application source."""
    client = get_supabase_client()

    # Check source exists
    source = await client.select(
        "application_sources",
        "*",
        filters={
            "id": str(source_id),
            "tenant_id": str(current_user.tenant_id),
        },
        single=True,
    )

    if not source:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Application source not found",
        )

    # Check for name conflict if changing name
    if source_data.name and source_data.name != source["name"]:
        existing = await client.select(
            "application_sources",
            "id",
            filters={
                "tenant_id": str(current_user.tenant_id),
                "name": source_data.name,
            },
            single=True,
        )
        if existing and existing["id"] != str(source_id):
            raise HTTPException(
                status_code=status.HTTP_409_CONFLICT,
                detail="Another source with this name already exists",
            )

    update_data = source_data.model_dump(exclude_unset=True)
    if "integration_config" in update_data and update_data["integration_config"] is not None:
        update_data["integration_config"] = json.dumps(update_data["integration_config"])

    if update_data:
        source = await client.update(
            "application_sources",
            update_data,
            filters={"id": str(source_id)},
        )

    return ApplicationSourceResponse.model_validate(source)


@router.delete("/application-sources/{source_id}", status_code=status.HTTP_204_NO_CONTENT)
async def delete_application_source(
    source_id: UUID,
    current_user: TokenData = Depends(require_permission(Permission.ADMIN_APPLICATION_SOURCES)),
):
    """Delete an application source."""
    client = get_supabase_client()

    # Check source exists
    source = await client.select(
        "application_sources",
        "id",
        filters={
            "id": str(source_id),
            "tenant_id": str(current_user.tenant_id),
        },
        single=True,
    )

    if not source:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Application source not found",
        )

    await client.delete("application_sources", filters={"id": str(source_id)})

    return None


# ====================================================================
# SLA CONFIGURATIONS
# ====================================================================


@router.get("/sla-configurations", response_model=List[SLAConfigurationResponse])
async def list_sla_configurations(
    active_only: bool = False,
    current_user: TokenData = Depends(require_permission(Permission.ADMIN_SLA_SETTINGS)),
):
    """List all SLA configurations for the tenant."""
    client = get_supabase_client()

    filters = {"tenant_id": str(current_user.tenant_id)}
    if active_only:
        filters["is_active"] = "true"

    configs = await client.select("sla_configurations", "*", filters=filters, return_empty_on_404=True) or []

    # Sort by job_type then name
    configs.sort(key=lambda x: (x.get("job_type", ""), x.get("name", "")))

    return [SLAConfigurationResponse.model_validate(c) for c in configs]


@router.post("/sla-configurations", response_model=SLAConfigurationResponse, status_code=status.HTTP_201_CREATED)
async def create_sla_configuration(
    config_data: SLAConfigurationCreate,
    current_user: TokenData = Depends(require_permission(Permission.ADMIN_SLA_SETTINGS)),
):
    """Create a new SLA configuration."""
    client = get_supabase_client()

    # Check for duplicate name
    existing = await client.select(
        "sla_configurations",
        "id",
        filters={
            "tenant_id": str(current_user.tenant_id),
            "name": config_data.name,
        },
        single=True,
    )

    if existing:
        raise HTTPException(
            status_code=status.HTTP_409_CONFLICT,
            detail="SLA configuration with this name already exists",
        )

    # If marking as default, unset other defaults
    if config_data.is_default:
        existing_default = await client.select(
            "sla_configurations",
            "id",
            filters={
                "tenant_id": str(current_user.tenant_id),
                "is_default": "true",
            },
        ) or []
        for existing_c in existing_default:
            await client.update(
                "sla_configurations",
                {"is_default": False},
                filters={"id": existing_c["id"]},
            )

    config_dict = {
        "tenant_id": str(current_user.tenant_id),
        **config_data.model_dump(),
    }

    config = await client.insert("sla_configurations", config_dict)

    return SLAConfigurationResponse.model_validate(config)


@router.get("/sla-configurations/{config_id}", response_model=SLAConfigurationResponse)
async def get_sla_configuration(
    config_id: UUID,
    current_user: TokenData = Depends(require_permission(Permission.ADMIN_SLA_SETTINGS)),
):
    """Get an SLA configuration by ID."""
    client = get_supabase_client()

    config = await client.select(
        "sla_configurations",
        "*",
        filters={
            "id": str(config_id),
            "tenant_id": str(current_user.tenant_id),
        },
        single=True,
    )

    if not config:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="SLA configuration not found",
        )

    return SLAConfigurationResponse.model_validate(config)


@router.patch("/sla-configurations/{config_id}", response_model=SLAConfigurationResponse)
async def update_sla_configuration(
    config_id: UUID,
    config_data: SLAConfigurationUpdate,
    current_user: TokenData = Depends(require_permission(Permission.ADMIN_SLA_SETTINGS)),
):
    """Update an SLA configuration."""
    client = get_supabase_client()

    # Check config exists
    config = await client.select(
        "sla_configurations",
        "*",
        filters={
            "id": str(config_id),
            "tenant_id": str(current_user.tenant_id),
        },
        single=True,
    )

    if not config:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="SLA configuration not found",
        )

    # Check for name conflict if changing name
    if config_data.name and config_data.name != config["name"]:
        existing = await client.select(
            "sla_configurations",
            "id",
            filters={
                "tenant_id": str(current_user.tenant_id),
                "name": config_data.name,
            },
            single=True,
        )
        if existing and existing["id"] != str(config_id):
            raise HTTPException(
                status_code=status.HTTP_409_CONFLICT,
                detail="Another configuration with this name already exists",
            )

    # Handle default flag
    if config_data.is_default:
        existing_default = await client.select(
            "sla_configurations",
            "id",
            filters={
                "tenant_id": str(current_user.tenant_id),
                "is_default": "true",
            },
        ) or []
        for existing_c in existing_default:
            if existing_c["id"] != str(config_id):
                await client.update(
                    "sla_configurations",
                    {"is_default": False},
                    filters={"id": existing_c["id"]},
                )

    update_data = config_data.model_dump(exclude_unset=True)
    if update_data:
        config = await client.update(
            "sla_configurations",
            update_data,
            filters={"id": str(config_id)},
        )

    return SLAConfigurationResponse.model_validate(config)


@router.delete("/sla-configurations/{config_id}", status_code=status.HTTP_204_NO_CONTENT)
async def delete_sla_configuration(
    config_id: UUID,
    current_user: TokenData = Depends(require_permission(Permission.ADMIN_SLA_SETTINGS)),
):
    """Delete an SLA configuration."""
    client = get_supabase_client()

    # Check config exists
    config = await client.select(
        "sla_configurations",
        "id",
        filters={
            "id": str(config_id),
            "tenant_id": str(current_user.tenant_id),
        },
        single=True,
    )

    if not config:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="SLA configuration not found",
        )

    await client.delete("sla_configurations", filters={"id": str(config_id)})

    return None
