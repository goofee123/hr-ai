"""Recruiter tasks router using Supabase REST API."""

from datetime import datetime, timezone
from typing import Optional
from uuid import UUID

from fastapi import APIRouter, Depends, HTTPException, Query, status

from app.core.permissions import Permission, require_permission
from app.core.security import TokenData
from app.core.supabase_client import get_supabase_client
from app.recruiting.schemas.task import (
    TaskComplete,
    TaskCreate,
    TaskResponse,
    TaskUpdate,
    TaskWithContext,
)
from app.shared.schemas.common import PaginatedResponse

router = APIRouter()


@router.get("/", response_model=PaginatedResponse[TaskWithContext])
async def list_tasks(
    page: int = Query(1, ge=1),
    page_size: int = Query(20, ge=1, le=100),
    assigned_to: Optional[UUID] = None,
    status: Optional[str] = None,
    task_type: Optional[str] = None,
    priority: Optional[str] = None,
    requisition_id: Optional[UUID] = None,
    candidate_id: Optional[UUID] = None,
    overdue_only: bool = False,
    my_tasks: bool = False,
    current_user: TokenData = Depends(require_permission(Permission.TASKS_VIEW)),
):
    """List tasks with filters."""
    client = get_supabase_client()

    # Build filters
    filters = {"tenant_id": str(current_user.tenant_id)}

    if my_tasks or assigned_to == current_user.user_id:
        filters["assigned_to"] = str(current_user.user_id)
    elif assigned_to:
        filters["assigned_to"] = str(assigned_to)

    if status:
        filters["status"] = status
    if task_type:
        filters["task_type"] = task_type
    if priority:
        filters["priority"] = priority
    if requisition_id:
        filters["requisition_id"] = str(requisition_id)
    if candidate_id:
        filters["candidate_id"] = str(candidate_id)

    # Get all tasks for counting
    all_tasks = await client.query(
        "recruiter_tasks",
        "id",
        filters=filters,
    )
    total = len(all_tasks)

    # Get paginated tasks
    offset = (page - 1) * page_size
    tasks = await client.query(
        "recruiter_tasks",
        "*",
        filters=filters,
        order="due_date",
        limit=page_size,
        offset=offset,
    )

    # Filter overdue if needed
    if overdue_only:
        today = datetime.now(timezone.utc).date().isoformat()
        tasks = [
            t for t in tasks
            if t.get("due_date") and t["due_date"] < today and t.get("status") != "completed"
        ]
        total = len(tasks)

    # Get related data for context
    candidate_ids = list({t.get("candidate_id") for t in tasks if t.get("candidate_id")})
    requisition_ids = list({t.get("requisition_id") for t in tasks if t.get("requisition_id")})

    # Fetch candidates
    candidates_map = {}
    if candidate_ids:
        candidates = await client.query(
            "candidates",
            "id,first_name,last_name",
            filters={"id": f"in.({','.join(candidate_ids)})"},
        )
        for c in candidates:
            candidates_map[c["id"]] = f"{c.get('first_name', '')} {c.get('last_name', '')}".strip()

    # Fetch requisitions
    requisitions_map = {}
    if requisition_ids:
        requisitions = await client.query(
            "job_requisitions",
            "id,external_title",
            filters={"id": f"in.({','.join(requisition_ids)})"},
        )
        for r in requisitions:
            requisitions_map[r["id"]] = r.get("external_title", "")

    # Build response with context
    items = []
    for task in tasks:
        items.append(
            TaskWithContext(
                id=UUID(task["id"]),
                tenant_id=UUID(task["tenant_id"]),
                task_type=task.get("task_type", "general"),
                title=task["title"],
                description=task.get("description"),
                due_date=datetime.fromisoformat(task["due_date"].replace("Z", "+00:00")).date() if task.get("due_date") else None,
                priority=task.get("priority", "medium"),
                application_id=UUID(task["application_id"]) if task.get("application_id") else None,
                requisition_id=UUID(task["requisition_id"]) if task.get("requisition_id") else None,
                candidate_id=UUID(task["candidate_id"]) if task.get("candidate_id") else None,
                assigned_to=UUID(task["assigned_to"]) if task.get("assigned_to") else None,
                status=task.get("status", "pending"),
                completed_at=datetime.fromisoformat(task["completed_at"].replace("Z", "+00:00")) if task.get("completed_at") else None,
                completed_by=UUID(task["completed_by"]) if task.get("completed_by") else None,
                reminder_sent=task.get("reminder_sent", False),
                created_by=UUID(task["created_by"]) if task.get("created_by") else None,
                created_at=datetime.fromisoformat(task["created_at"].replace("Z", "+00:00")),
                updated_at=datetime.fromisoformat(task["updated_at"].replace("Z", "+00:00")) if task.get("updated_at") else None,
                candidate_name=candidates_map.get(task.get("candidate_id")),
                requisition_title=requisitions_map.get(task.get("requisition_id")),
                assigned_to_name=None,
            )
        )

    return PaginatedResponse.create(
        items=items,
        total=total,
        page=page,
        page_size=page_size,
    )


@router.post("/", response_model=TaskResponse, status_code=status.HTTP_201_CREATED)
async def create_task(
    task_data: TaskCreate,
    current_user: TokenData = Depends(require_permission(Permission.TASKS_CREATE)),
):
    """Create a new task."""
    client = get_supabase_client()

    # Validate related entities exist
    if task_data.candidate_id:
        candidate = await client.select(
            "candidates",
            "id",
            filters={
                "id": str(task_data.candidate_id),
                "tenant_id": str(current_user.tenant_id),
            },
            single=True,
        )
        if not candidate:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail="Candidate not found",
            )

    if task_data.requisition_id:
        requisition = await client.select(
            "job_requisitions",
            "id",
            filters={
                "id": str(task_data.requisition_id),
                "tenant_id": str(current_user.tenant_id),
            },
            single=True,
        )
        if not requisition:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail="Job requisition not found",
            )

    if task_data.application_id:
        application = await client.select(
            "applications",
            "id",
            filters={
                "id": str(task_data.application_id),
                "tenant_id": str(current_user.tenant_id),
            },
            single=True,
        )
        if not application:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail="Application not found",
            )

    # Create task
    task_record = {
        "tenant_id": str(current_user.tenant_id),
        "task_type": task_data.task_type,
        "title": task_data.title,
        "description": task_data.description,
        "due_date": task_data.due_date.isoformat() if task_data.due_date else None,
        "priority": task_data.priority,
        "application_id": str(task_data.application_id) if task_data.application_id else None,
        "requisition_id": str(task_data.requisition_id) if task_data.requisition_id else None,
        "candidate_id": str(task_data.candidate_id) if task_data.candidate_id else None,
        "assigned_to": str(task_data.assigned_to) if task_data.assigned_to else str(current_user.user_id),
        "status": "pending",
        "created_by": str(current_user.user_id),
    }

    task = await client.insert("recruiter_tasks", task_record)

    return TaskResponse(
        id=UUID(task["id"]),
        tenant_id=UUID(task["tenant_id"]),
        task_type=task.get("task_type", "general"),
        title=task["title"],
        description=task.get("description"),
        due_date=datetime.fromisoformat(task["due_date"].replace("Z", "+00:00")).date() if task.get("due_date") else None,
        priority=task.get("priority", "medium"),
        application_id=UUID(task["application_id"]) if task.get("application_id") else None,
        requisition_id=UUID(task["requisition_id"]) if task.get("requisition_id") else None,
        candidate_id=UUID(task["candidate_id"]) if task.get("candidate_id") else None,
        assigned_to=UUID(task["assigned_to"]) if task.get("assigned_to") else None,
        status=task.get("status", "pending"),
        completed_at=datetime.fromisoformat(task["completed_at"].replace("Z", "+00:00")) if task.get("completed_at") else None,
        completed_by=UUID(task["completed_by"]) if task.get("completed_by") else None,
        reminder_sent=task.get("reminder_sent", False),
        created_by=UUID(task["created_by"]) if task.get("created_by") else None,
        created_at=datetime.fromisoformat(task["created_at"].replace("Z", "+00:00")),
        updated_at=datetime.fromisoformat(task["updated_at"].replace("Z", "+00:00")) if task.get("updated_at") else None,
    )


@router.get("/{task_id}", response_model=TaskWithContext)
async def get_task(
    task_id: UUID,
    current_user: TokenData = Depends(require_permission(Permission.TASKS_VIEW)),
):
    """Get a task by ID."""
    client = get_supabase_client()

    task = await client.select(
        "recruiter_tasks",
        "*",
        filters={
            "id": str(task_id),
            "tenant_id": str(current_user.tenant_id),
        },
        single=True,
    )

    if not task:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Task not found",
        )

    # Get context
    candidate_name = None
    if task.get("candidate_id"):
        candidate = await client.select(
            "candidates",
            "first_name,last_name",
            filters={"id": task["candidate_id"]},
            single=True,
        )
        if candidate:
            candidate_name = f"{candidate.get('first_name', '')} {candidate.get('last_name', '')}".strip()

    requisition_title = None
    if task.get("requisition_id"):
        requisition = await client.select(
            "job_requisitions",
            "external_title",
            filters={"id": task["requisition_id"]},
            single=True,
        )
        if requisition:
            requisition_title = requisition.get("external_title")

    return TaskWithContext(
        id=UUID(task["id"]),
        tenant_id=UUID(task["tenant_id"]),
        task_type=task.get("task_type", "general"),
        title=task["title"],
        description=task.get("description"),
        due_date=datetime.fromisoformat(task["due_date"].replace("Z", "+00:00")).date() if task.get("due_date") else None,
        priority=task.get("priority", "medium"),
        application_id=UUID(task["application_id"]) if task.get("application_id") else None,
        requisition_id=UUID(task["requisition_id"]) if task.get("requisition_id") else None,
        candidate_id=UUID(task["candidate_id"]) if task.get("candidate_id") else None,
        assigned_to=UUID(task["assigned_to"]) if task.get("assigned_to") else None,
        status=task.get("status", "pending"),
        completed_at=datetime.fromisoformat(task["completed_at"].replace("Z", "+00:00")) if task.get("completed_at") else None,
        completed_by=UUID(task["completed_by"]) if task.get("completed_by") else None,
        reminder_sent=task.get("reminder_sent", False),
        created_by=UUID(task["created_by"]) if task.get("created_by") else None,
        created_at=datetime.fromisoformat(task["created_at"].replace("Z", "+00:00")),
        updated_at=datetime.fromisoformat(task["updated_at"].replace("Z", "+00:00")) if task.get("updated_at") else None,
        candidate_name=candidate_name,
        requisition_title=requisition_title,
        assigned_to_name=None,
    )


@router.patch("/{task_id}", response_model=TaskResponse)
async def update_task(
    task_id: UUID,
    task_data: TaskUpdate,
    current_user: TokenData = Depends(require_permission(Permission.TASKS_EDIT)),
):
    """Update a task."""
    client = get_supabase_client()

    # Verify task exists
    task = await client.select(
        "recruiter_tasks",
        "*",
        filters={
            "id": str(task_id),
            "tenant_id": str(current_user.tenant_id),
        },
        single=True,
    )

    if not task:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Task not found",
        )

    # Apply updates
    update_data = task_data.model_dump(exclude_unset=True)

    # Convert UUIDs to strings
    for key in ["application_id", "requisition_id", "candidate_id", "assigned_to"]:
        if key in update_data and update_data[key] is not None:
            update_data[key] = str(update_data[key])

    # Convert date to string
    if "due_date" in update_data and update_data["due_date"] is not None:
        update_data["due_date"] = update_data["due_date"].isoformat()

    if update_data:
        updated = await client.update(
            "recruiter_tasks",
            update_data,
            filters={"id": str(task_id)},
        )
        task = updated if updated else task

    return TaskResponse(
        id=UUID(task["id"]),
        tenant_id=UUID(task["tenant_id"]),
        task_type=task.get("task_type", "general"),
        title=task["title"],
        description=task.get("description"),
        due_date=datetime.fromisoformat(task["due_date"].replace("Z", "+00:00")).date() if task.get("due_date") else None,
        priority=task.get("priority", "medium"),
        application_id=UUID(task["application_id"]) if task.get("application_id") else None,
        requisition_id=UUID(task["requisition_id"]) if task.get("requisition_id") else None,
        candidate_id=UUID(task["candidate_id"]) if task.get("candidate_id") else None,
        assigned_to=UUID(task["assigned_to"]) if task.get("assigned_to") else None,
        status=task.get("status", "pending"),
        completed_at=datetime.fromisoformat(task["completed_at"].replace("Z", "+00:00")) if task.get("completed_at") else None,
        completed_by=UUID(task["completed_by"]) if task.get("completed_by") else None,
        reminder_sent=task.get("reminder_sent", False),
        created_by=UUID(task["created_by"]) if task.get("created_by") else None,
        created_at=datetime.fromisoformat(task["created_at"].replace("Z", "+00:00")),
        updated_at=datetime.fromisoformat(task["updated_at"].replace("Z", "+00:00")) if task.get("updated_at") else None,
    )


@router.post("/{task_id}/complete", response_model=TaskResponse)
async def complete_task(
    task_id: UUID,
    completion: TaskComplete,
    current_user: TokenData = Depends(require_permission(Permission.TASKS_COMPLETE)),
):
    """Mark a task as completed."""
    client = get_supabase_client()

    task = await client.select(
        "recruiter_tasks",
        "*",
        filters={
            "id": str(task_id),
            "tenant_id": str(current_user.tenant_id),
        },
        single=True,
    )

    if not task:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Task not found",
        )

    if task.get("status") == "completed":
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Task is already completed",
        )

    now = datetime.now(timezone.utc)

    update_data = {
        "status": "completed",
        "completed_at": now.isoformat(),
        "completed_by": str(current_user.user_id),
    }

    if completion.notes:
        current_desc = task.get("description") or ""
        update_data["description"] = f"{current_desc}\n\nCompletion notes: {completion.notes}".strip()

    updated = await client.update(
        "recruiter_tasks",
        update_data,
        filters={"id": str(task_id)},
    )

    task = updated if updated else task

    return TaskResponse(
        id=UUID(task["id"]),
        tenant_id=UUID(task["tenant_id"]),
        task_type=task.get("task_type", "general"),
        title=task["title"],
        description=task.get("description"),
        due_date=datetime.fromisoformat(task["due_date"].replace("Z", "+00:00")).date() if task.get("due_date") else None,
        priority=task.get("priority", "medium"),
        application_id=UUID(task["application_id"]) if task.get("application_id") else None,
        requisition_id=UUID(task["requisition_id"]) if task.get("requisition_id") else None,
        candidate_id=UUID(task["candidate_id"]) if task.get("candidate_id") else None,
        assigned_to=UUID(task["assigned_to"]) if task.get("assigned_to") else None,
        status=task.get("status", "completed"),
        completed_at=datetime.fromisoformat(task["completed_at"].replace("Z", "+00:00")) if task.get("completed_at") else None,
        completed_by=UUID(task["completed_by"]) if task.get("completed_by") else None,
        reminder_sent=task.get("reminder_sent", False),
        created_by=UUID(task["created_by"]) if task.get("created_by") else None,
        created_at=datetime.fromisoformat(task["created_at"].replace("Z", "+00:00")),
        updated_at=datetime.fromisoformat(task["updated_at"].replace("Z", "+00:00")) if task.get("updated_at") else None,
    )


@router.delete("/{task_id}", status_code=status.HTTP_204_NO_CONTENT)
async def delete_task(
    task_id: UUID,
    current_user: TokenData = Depends(require_permission(Permission.TASKS_DELETE)),
):
    """Delete a task."""
    client = get_supabase_client()

    task = await client.select(
        "recruiter_tasks",
        "id",
        filters={
            "id": str(task_id),
            "tenant_id": str(current_user.tenant_id),
        },
        single=True,
    )

    if not task:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Task not found",
        )

    await client.delete("recruiter_tasks", filters={"id": str(task_id)})

    return None


@router.get("/summary/workload")
async def get_workload_summary(
    current_user: TokenData = Depends(require_permission(Permission.TASKS_VIEW)),
):
    """Get task workload summary by assignee."""
    client = get_supabase_client()

    # Get all tasks for tenant
    tasks = await client.query(
        "recruiter_tasks",
        "assigned_to,status,due_date",
        filters={"tenant_id": str(current_user.tenant_id)},
    )

    today = datetime.now(timezone.utc).date().isoformat()

    # Build workload map
    workload = {}
    for task in tasks:
        user_id = task.get("assigned_to")
        if not user_id:
            continue

        if user_id not in workload:
            workload[user_id] = {"pending": 0, "in_progress": 0, "completed": 0, "overdue": 0}

        status = task.get("status", "pending")
        if status in workload[user_id]:
            workload[user_id][status] += 1

        # Check if overdue
        due_date = task.get("due_date")
        if due_date and due_date < today and status != "completed":
            workload[user_id]["overdue"] += 1

    return {
        "workload": [
            {
                "user_id": user_id,
                "pending": counts.get("pending", 0),
                "in_progress": counts.get("in_progress", 0),
                "completed": counts.get("completed", 0),
                "overdue": counts.get("overdue", 0),
            }
            for user_id, counts in workload.items()
        ]
    }


@router.get("/summary/by-type")
async def get_tasks_by_type(
    current_user: TokenData = Depends(require_permission(Permission.TASKS_VIEW)),
):
    """Get task counts by type."""
    client = get_supabase_client()

    tasks = await client.query(
        "recruiter_tasks",
        "task_type,status",
        filters={"tenant_id": str(current_user.tenant_id)},
    )

    by_type = {}
    for task in tasks:
        task_type = task.get("task_type", "general")
        status = task.get("status", "pending")

        if task_type not in by_type:
            by_type[task_type] = {"pending": 0, "in_progress": 0, "completed": 0}

        if status in by_type[task_type]:
            by_type[task_type][status] += 1

    return {"by_type": by_type}
