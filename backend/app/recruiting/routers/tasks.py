"""Recruiter tasks router."""

from datetime import datetime, timezone
from typing import Optional
from uuid import UUID

from fastapi import APIRouter, Depends, HTTPException, Query, status
from sqlalchemy import func, or_, select
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.orm import selectinload

from app.core.database import get_db
from app.core.permissions import Permission, require_permission
from app.core.security import TokenData
from app.core.tenant import get_tenant_id
from app.recruiting.models.candidate import Application, Candidate
from app.recruiting.models.job import JobRequisition
from app.recruiting.models.task import RecruiterTask
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
    db: AsyncSession = Depends(get_db),
    tenant_id: UUID = Depends(get_tenant_id),
    current_user: TokenData = Depends(require_permission(Permission.TASKS_VIEW)),
):
    """List tasks with filters."""
    # Base query
    query = select(RecruiterTask).where(RecruiterTask.tenant_id == tenant_id)

    # Apply filters
    if my_tasks or assigned_to == current_user.user_id:
        query = query.where(RecruiterTask.assigned_to == current_user.user_id)
    elif assigned_to:
        query = query.where(RecruiterTask.assigned_to == assigned_to)

    if status:
        query = query.where(RecruiterTask.status == status)
    if task_type:
        query = query.where(RecruiterTask.task_type == task_type)
    if priority:
        query = query.where(RecruiterTask.priority == priority)
    if requisition_id:
        query = query.where(RecruiterTask.requisition_id == requisition_id)
    if candidate_id:
        query = query.where(RecruiterTask.candidate_id == candidate_id)
    if overdue_only:
        today = datetime.now(timezone.utc).date()
        query = query.where(
            RecruiterTask.due_date < today,
            RecruiterTask.status != "completed",
        )

    # Get total count
    count_query = select(func.count()).select_from(query.subquery())
    total = (await db.execute(count_query)).scalar() or 0

    # Apply pagination and ordering
    offset = (page - 1) * page_size
    query = (
        query
        .offset(offset)
        .limit(page_size)
        .order_by(
            RecruiterTask.status.asc(),  # pending first
            RecruiterTask.due_date.asc().nullslast(),
            RecruiterTask.priority.desc(),
        )
    )

    result = await db.execute(query)
    tasks = result.scalars().all()

    # Get related data for context
    task_ids = [t.id for t in tasks]
    candidate_ids = [t.candidate_id for t in tasks if t.candidate_id]
    requisition_ids = [t.requisition_id for t in tasks if t.requisition_id]

    # Fetch candidates
    candidates_map = {}
    if candidate_ids:
        result = await db.execute(
            select(Candidate).where(Candidate.id.in_(candidate_ids))
        )
        for c in result.scalars().all():
            candidates_map[c.id] = f"{c.first_name} {c.last_name}"

    # Fetch requisitions
    requisitions_map = {}
    if requisition_ids:
        result = await db.execute(
            select(JobRequisition).where(JobRequisition.id.in_(requisition_ids))
        )
        for r in result.scalars().all():
            requisitions_map[r.id] = r.external_title

    # Build response with context
    items = []
    for task in tasks:
        response = TaskWithContext(
            id=task.id,
            tenant_id=task.tenant_id,
            task_type=task.task_type,
            title=task.title,
            description=task.description,
            due_date=task.due_date,
            priority=task.priority,
            application_id=task.application_id,
            requisition_id=task.requisition_id,
            candidate_id=task.candidate_id,
            assigned_to=task.assigned_to,
            status=task.status,
            completed_at=task.completed_at,
            completed_by=task.completed_by,
            reminder_sent=task.reminder_sent,
            created_by=task.created_by,
            created_at=task.created_at,
            updated_at=task.updated_at,
            candidate_name=candidates_map.get(task.candidate_id) if task.candidate_id else None,
            requisition_title=requisitions_map.get(task.requisition_id) if task.requisition_id else None,
            assigned_to_name=None,  # Would need user lookup
        )
        items.append(response)

    return PaginatedResponse.create(
        items=items,
        total=total,
        page=page,
        page_size=page_size,
    )


@router.post("/", response_model=TaskResponse, status_code=status.HTTP_201_CREATED)
async def create_task(
    task_data: TaskCreate,
    db: AsyncSession = Depends(get_db),
    tenant_id: UUID = Depends(get_tenant_id),
    current_user: TokenData = Depends(require_permission(Permission.TASKS_CREATE)),
):
    """Create a new task."""
    # Validate related entities exist
    if task_data.candidate_id:
        result = await db.execute(
            select(Candidate).where(
                Candidate.id == task_data.candidate_id,
                Candidate.tenant_id == tenant_id,
            )
        )
        if not result.scalar_one_or_none():
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail="Candidate not found",
            )

    if task_data.requisition_id:
        result = await db.execute(
            select(JobRequisition).where(
                JobRequisition.id == task_data.requisition_id,
                JobRequisition.tenant_id == tenant_id,
            )
        )
        if not result.scalar_one_or_none():
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail="Job requisition not found",
            )

    if task_data.application_id:
        result = await db.execute(
            select(Application).where(
                Application.id == task_data.application_id,
                Application.tenant_id == tenant_id,
            )
        )
        if not result.scalar_one_or_none():
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail="Application not found",
            )

    # Create task
    task = RecruiterTask(
        tenant_id=tenant_id,
        task_type=task_data.task_type,
        title=task_data.title,
        description=task_data.description,
        due_date=task_data.due_date,
        priority=task_data.priority,
        application_id=task_data.application_id,
        requisition_id=task_data.requisition_id,
        candidate_id=task_data.candidate_id,
        assigned_to=task_data.assigned_to or current_user.user_id,
        status="pending",
        created_by=current_user.user_id,
    )

    db.add(task)
    await db.commit()
    await db.refresh(task)

    return TaskResponse.model_validate(task)


@router.get("/{task_id}", response_model=TaskWithContext)
async def get_task(
    task_id: UUID,
    db: AsyncSession = Depends(get_db),
    tenant_id: UUID = Depends(get_tenant_id),
    _: TokenData = Depends(require_permission(Permission.TASKS_VIEW)),
):
    """Get a task by ID."""
    result = await db.execute(
        select(RecruiterTask).where(
            RecruiterTask.id == task_id,
            RecruiterTask.tenant_id == tenant_id,
        )
    )
    task = result.scalar_one_or_none()

    if not task:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Task not found",
        )

    # Get context
    candidate_name = None
    if task.candidate_id:
        result = await db.execute(
            select(Candidate).where(Candidate.id == task.candidate_id)
        )
        candidate = result.scalar_one_or_none()
        if candidate:
            candidate_name = f"{candidate.first_name} {candidate.last_name}"

    requisition_title = None
    if task.requisition_id:
        result = await db.execute(
            select(JobRequisition).where(JobRequisition.id == task.requisition_id)
        )
        requisition = result.scalar_one_or_none()
        if requisition:
            requisition_title = requisition.external_title

    return TaskWithContext(
        id=task.id,
        tenant_id=task.tenant_id,
        task_type=task.task_type,
        title=task.title,
        description=task.description,
        due_date=task.due_date,
        priority=task.priority,
        application_id=task.application_id,
        requisition_id=task.requisition_id,
        candidate_id=task.candidate_id,
        assigned_to=task.assigned_to,
        status=task.status,
        completed_at=task.completed_at,
        completed_by=task.completed_by,
        reminder_sent=task.reminder_sent,
        created_by=task.created_by,
        created_at=task.created_at,
        updated_at=task.updated_at,
        candidate_name=candidate_name,
        requisition_title=requisition_title,
        assigned_to_name=None,
    )


@router.patch("/{task_id}", response_model=TaskResponse)
async def update_task(
    task_id: UUID,
    task_data: TaskUpdate,
    db: AsyncSession = Depends(get_db),
    tenant_id: UUID = Depends(get_tenant_id),
    _: TokenData = Depends(require_permission(Permission.TASKS_EDIT)),
):
    """Update a task."""
    result = await db.execute(
        select(RecruiterTask).where(
            RecruiterTask.id == task_id,
            RecruiterTask.tenant_id == tenant_id,
        )
    )
    task = result.scalar_one_or_none()

    if not task:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Task not found",
        )

    # Apply updates
    update_data = task_data.model_dump(exclude_unset=True)
    for field, value in update_data.items():
        setattr(task, field, value)

    await db.commit()
    await db.refresh(task)

    return TaskResponse.model_validate(task)


@router.post("/{task_id}/complete", response_model=TaskResponse)
async def complete_task(
    task_id: UUID,
    completion: TaskComplete,
    db: AsyncSession = Depends(get_db),
    tenant_id: UUID = Depends(get_tenant_id),
    current_user: TokenData = Depends(require_permission(Permission.TASKS_COMPLETE)),
):
    """Mark a task as completed."""
    result = await db.execute(
        select(RecruiterTask).where(
            RecruiterTask.id == task_id,
            RecruiterTask.tenant_id == tenant_id,
        )
    )
    task = result.scalar_one_or_none()

    if not task:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Task not found",
        )

    if task.status == "completed":
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Task is already completed",
        )

    now = datetime.now(timezone.utc)

    task.status = "completed"
    task.completed_at = now
    task.completed_by = current_user.user_id

    if completion.notes:
        task.description = f"{task.description or ''}\n\nCompletion notes: {completion.notes}".strip()

    await db.commit()
    await db.refresh(task)

    return TaskResponse.model_validate(task)


@router.delete("/{task_id}", status_code=status.HTTP_204_NO_CONTENT)
async def delete_task(
    task_id: UUID,
    db: AsyncSession = Depends(get_db),
    tenant_id: UUID = Depends(get_tenant_id),
    _: TokenData = Depends(require_permission(Permission.TASKS_DELETE)),
):
    """Delete a task."""
    result = await db.execute(
        select(RecruiterTask).where(
            RecruiterTask.id == task_id,
            RecruiterTask.tenant_id == tenant_id,
        )
    )
    task = result.scalar_one_or_none()

    if not task:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Task not found",
        )

    await db.delete(task)
    await db.commit()

    return None


@router.get("/summary/workload")
async def get_workload_summary(
    db: AsyncSession = Depends(get_db),
    tenant_id: UUID = Depends(get_tenant_id),
    _: TokenData = Depends(require_permission(Permission.TASKS_VIEW)),
):
    """Get task workload summary by assignee."""
    # Get counts by assignee and status
    result = await db.execute(
        select(
            RecruiterTask.assigned_to,
            RecruiterTask.status,
            func.count(RecruiterTask.id).label("count"),
        )
        .where(RecruiterTask.tenant_id == tenant_id)
        .group_by(RecruiterTask.assigned_to, RecruiterTask.status)
    )

    # Build workload map
    workload: dict[UUID, dict[str, int]] = {}
    for row in result:
        if row.assigned_to not in workload:
            workload[row.assigned_to] = {"pending": 0, "in_progress": 0, "completed": 0}
        workload[row.assigned_to][row.status] = row.count

    # Get overdue counts
    today = datetime.now(timezone.utc).date()
    result = await db.execute(
        select(
            RecruiterTask.assigned_to,
            func.count(RecruiterTask.id).label("overdue_count"),
        )
        .where(
            RecruiterTask.tenant_id == tenant_id,
            RecruiterTask.due_date < today,
            RecruiterTask.status != "completed",
        )
        .group_by(RecruiterTask.assigned_to)
    )

    for row in result:
        if row.assigned_to in workload:
            workload[row.assigned_to]["overdue"] = row.overdue_count

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
    db: AsyncSession = Depends(get_db),
    tenant_id: UUID = Depends(get_tenant_id),
    _: TokenData = Depends(require_permission(Permission.TASKS_VIEW)),
):
    """Get task counts by type."""
    result = await db.execute(
        select(
            RecruiterTask.task_type,
            RecruiterTask.status,
            func.count(RecruiterTask.id).label("count"),
        )
        .where(RecruiterTask.tenant_id == tenant_id)
        .group_by(RecruiterTask.task_type, RecruiterTask.status)
    )

    by_type: dict[str, dict[str, int]] = {}
    for row in result:
        if row.task_type not in by_type:
            by_type[row.task_type] = {"pending": 0, "in_progress": 0, "completed": 0}
        by_type[row.task_type][row.status] = row.count

    return {"by_type": by_type}
