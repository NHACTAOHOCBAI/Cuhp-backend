"""Todo list endpoints backed by the Eisenhower time-management matrix.

Tasks are a rolling backlog owned by a single user. Each task lives in one of
four quadrants ("do" / "schedule" / "delegate" / "eliminate") and carries an
optional due date used for the "Hôm nay / Tuần này / Tất cả" scope filters.

Ordering inside a quadrant is materialised in `TodoTask.position`; the
drag-and-drop endpoint renumbers a quadrant densely on every move so the
frontend never has to reason about gaps or ties.
"""

import uuid
from datetime import date, datetime, timedelta
from typing import List, Optional

from fastapi import APIRouter, Depends, HTTPException, Query
from sqlalchemy.orm import Session

from app import models
from app.api.deps import get_current_user
from app.core.database import get_db
from app.schemas.todo import (
    QUADRANT_LABELS,
    QUADRANTS,
    DailyCompletion,
    QuadrantStat,
    TodoListResponse,
    TodoStatsResponse,
    TodoTaskCreate,
    TodoTaskMoveRequest,
    TodoTaskResponse,
    TodoTaskUpdate,
)

router = APIRouter()


# --- Helpers ---
def _get_owned_task(db: Session, task_id: str, user_id: str) -> models.TodoTask:
    """Fetch a task or raise 404. Never leaks another user's rows."""
    task = (
        db.query(models.TodoTask)
        .filter(
            models.TodoTask.id == task_id,
            models.TodoTask.user_id == user_id,
        )
        .first()
    )
    if not task:
        raise HTTPException(status_code=404, detail="Không tìm thấy công việc này.")
    return task


def _next_position(db: Session, user_id: str, quadrant: str) -> int:
    """Position for a card appended to the bottom of a quadrant."""
    count = (
        db.query(models.TodoTask)
        .filter(
            models.TodoTask.user_id == user_id,
            models.TodoTask.quadrant == quadrant,
        )
        .count()
    )
    return count


def _renumber_quadrant(db: Session, user_id: str, quadrant: str) -> None:
    """Rewrite positions in a quadrant to a dense 0..n-1 sequence."""
    tasks = (
        db.query(models.TodoTask)
        .filter(
            models.TodoTask.user_id == user_id,
            models.TodoTask.quadrant == quadrant,
        )
        .order_by(
            models.TodoTask.position.asc(),
            models.TodoTask.created_at.asc(),
        )
        .all()
    )
    for index, task in enumerate(tasks):
        task.position = index


def _end_of_week(today: date) -> date:
    """Sunday of the current week (Monday-based week, matching VN convention)."""
    return today + timedelta(days=6 - today.weekday())


# --- Task CRUD ---
@router.get("/tasks", response_model=TodoListResponse)
def get_tasks(
    scope: str = Query("all", pattern="^(today|week|all)$"),
    quadrant: Optional[str] = Query(None),
    q: Optional[str] = Query(None),
    show_completed: bool = Query(False),
    db: Session = Depends(get_db),
    current_user: models.User = Depends(get_current_user),
):
    """List the current user's tasks for the matrix view.

    - `scope=today` keeps tasks due today or already overdue.
    - `scope=week` keeps tasks due on or before the end of this week (overdue
      tasks stay visible so they are never silently dropped).
    - `scope=all` keeps everything, including tasks with no due date.

    When `show_completed` is false the response still includes tasks completed
    today, so ticking a checkbox gives visible feedback instead of making the
    card disappear instantly.
    """
    today = date.today()
    query = db.query(models.TodoTask).filter(
        models.TodoTask.user_id == current_user.id
    )

    if quadrant is not None:
        if quadrant not in QUADRANTS:
            raise HTTPException(status_code=400, detail="Góc phần tư không hợp lệ.")
        query = query.filter(models.TodoTask.quadrant == quadrant)

    if scope == "today":
        query = query.filter(models.TodoTask.due_date <= today)
    elif scope == "week":
        query = query.filter(models.TodoTask.due_date <= _end_of_week(today))

    if q:
        pattern = f"%{q.strip()}%"
        query = query.filter(models.TodoTask.title.ilike(pattern))

    tasks = query.order_by(
        models.TodoTask.completed.asc(),
        models.TodoTask.position.asc(),
        models.TodoTask.created_at.asc(),
    ).all()

    if not show_completed:
        tasks = [
            t
            for t in tasks
            if not t.completed
            or (t.completed_at is not None and t.completed_at.date() == today)
        ]

    return TodoListResponse(items=tasks, total=len(tasks))


@router.post("/tasks", response_model=TodoTaskResponse)
def create_task(
    task_in: TodoTaskCreate,
    db: Session = Depends(get_db),
    current_user: models.User = Depends(get_current_user),
):
    task = models.TodoTask(
        id=f"todo-{uuid.uuid4()}",
        user_id=current_user.id,
        title=task_in.title,
        description=task_in.description,
        quadrant=task_in.quadrant,
        due_date=task_in.due_date,
        scheduled_date=task_in.scheduled_date,
        completed=task_in.completed,
        completed_at=datetime.utcnow() if task_in.completed else None,
        estimated_time=task_in.estimated_time,
        position=_next_position(db, current_user.id, task_in.quadrant),
    )
    db.add(task)
    db.commit()
    db.refresh(task)
    return task


@router.put("/tasks/{task_id}", response_model=TodoTaskResponse)
def update_task(
    task_id: str,
    task_in: TodoTaskUpdate,
    db: Session = Depends(get_db),
    current_user: models.User = Depends(get_current_user),
):
    task = _get_owned_task(db, task_id, current_user.id)
    old_quadrant = task.quadrant
    # `model_fields_set` lets us tell "field omitted" from "field sent as null",
    # so the edit dialog can genuinely clear a due date or a description.
    provided = task_in.model_fields_set

    if task_in.title is not None:
        task.title = task_in.title
    if "description" in provided:
        task.description = task_in.description
    if "due_date" in provided:
        task.due_date = task_in.due_date
    if "scheduled_date" in provided:
        task.scheduled_date = task_in.scheduled_date
    if "estimated_time" in provided:
        task.estimated_time = task_in.estimated_time
    if task_in.position is not None:
        task.position = task_in.position
    if task_in.completed is not None and task_in.completed != task.completed:
        task.completed = task_in.completed
        task.completed_at = datetime.utcnow() if task_in.completed else None
    if task_in.quadrant is not None and task_in.quadrant != old_quadrant:
        task.quadrant = task_in.quadrant
        # Moved via the edit dialog rather than drag-drop: append to the bottom.
        task.position = _next_position(db, current_user.id, task_in.quadrant)

    db.commit()

    if task_in.quadrant is not None and task_in.quadrant != old_quadrant:
        _renumber_quadrant(db, current_user.id, old_quadrant)
        db.commit()

    db.refresh(task)
    return task


@router.post("/tasks/{task_id}/toggle", response_model=TodoTaskResponse)
def toggle_task(
    task_id: str,
    db: Session = Depends(get_db),
    current_user: models.User = Depends(get_current_user),
):
    """Flip the completed flag, stamping/clearing `completed_at` accordingly."""
    task = _get_owned_task(db, task_id, current_user.id)
    task.completed = not task.completed
    task.completed_at = datetime.utcnow() if task.completed else None
    db.commit()
    db.refresh(task)
    return task


@router.post("/tasks/{task_id}/move", response_model=TodoTaskResponse)
def move_task(
    task_id: str,
    move_in: TodoTaskMoveRequest,
    db: Session = Depends(get_db),
    current_user: models.User = Depends(get_current_user),
):
    """Drag-and-drop: place a task at `position` inside `quadrant`.

    Both the source and the target quadrant are renumbered to a dense
    0..n-1 sequence so repeated drags can never accumulate ties or gaps.
    """
    task = _get_owned_task(db, task_id, current_user.id)
    source_quadrant = task.quadrant
    target_quadrant = move_in.quadrant

    siblings = (
        db.query(models.TodoTask)
        .filter(
            models.TodoTask.user_id == current_user.id,
            models.TodoTask.quadrant == target_quadrant,
            models.TodoTask.id != task.id,
        )
        .order_by(
            models.TodoTask.position.asc(),
            models.TodoTask.created_at.asc(),
        )
        .all()
    )

    insert_at = min(move_in.position, len(siblings))
    siblings.insert(insert_at, task)

    task.quadrant = target_quadrant
    for index, sibling in enumerate(siblings):
        sibling.position = index

    db.commit()

    if source_quadrant != target_quadrant:
        _renumber_quadrant(db, current_user.id, source_quadrant)
        db.commit()

    db.refresh(task)
    return task


@router.delete("/tasks/completed")
def delete_completed_tasks(
    db: Session = Depends(get_db),
    current_user: models.User = Depends(get_current_user),
):
    """Clear every finished task. Declared before `/tasks/{task_id}` on
    purpose: FastAPI matches routes in declaration order, so the literal path
    must win over the parameterised one."""
    tasks = (
        db.query(models.TodoTask)
        .filter(
            models.TodoTask.user_id == current_user.id,
            models.TodoTask.completed == True,  # noqa: E712 - SQLAlchemy needs ==
        )
        .all()
    )
    affected = {t.quadrant for t in tasks}
    for task in tasks:
        db.delete(task)
    db.commit()

    for quadrant in affected:
        _renumber_quadrant(db, current_user.id, quadrant)
    db.commit()

    return {"message": f"Đã xoá {len(tasks)} công việc đã hoàn thành.", "deleted": len(tasks)}


@router.delete("/tasks/{task_id}")
def delete_task(
    task_id: str,
    db: Session = Depends(get_db),
    current_user: models.User = Depends(get_current_user),
):
    task = _get_owned_task(db, task_id, current_user.id)
    quadrant = task.quadrant
    db.delete(task)
    db.commit()

    _renumber_quadrant(db, current_user.id, quadrant)
    db.commit()

    return {"message": "Đã xoá công việc."}


# --- Stats ---
@router.get("/stats", response_model=TodoStatsResponse)
def get_todo_stats(
    db: Session = Depends(get_db),
    current_user: models.User = Depends(get_current_user),
):
    """Aggregate the whole task history into the numbers the report page shows.

    Everything is computed in Python over the user's own rows (a personal todo
    list is small), mirroring how `gym.py` builds its stats — no DB-specific
    date functions, so this keeps working on any SQLAlchemy dialect.
    """
    today = date.today()
    tasks: List[models.TodoTask] = (
        db.query(models.TodoTask)
        .filter(models.TodoTask.user_id == current_user.id)
        .all()
    )

    quadrant_stats: List[QuadrantStat] = []
    for quadrant in QUADRANTS:
        bucket = [t for t in tasks if t.quadrant == quadrant]
        completed = sum(1 for t in bucket if t.completed)
        overdue = sum(
            1
            for t in bucket
            if not t.completed and t.due_date is not None and t.due_date < today
        )
        quadrant_stats.append(
            QuadrantStat(
                quadrant=quadrant,
                label=QUADRANT_LABELS[quadrant],
                total=len(bucket),
                completed=completed,
                open_count=len(bucket) - completed,
                overdue=overdue,
            )
        )

    # 7-day activity window, oldest first (today inclusive).
    daily_completion: List[DailyCompletion] = []
    for offset in range(6, -1, -1):
        day = today - timedelta(days=offset)
        daily_completion.append(
            DailyCompletion(
                date=day,
                completed_count=sum(
                    1
                    for t in tasks
                    if t.completed_at is not None and t.completed_at.date() == day
                ),
                created_count=sum(
                    1
                    for t in tasks
                    if t.created_at is not None and t.created_at.date() == day
                ),
            )
        )

    total = len(tasks)
    total_completed = sum(1 for t in tasks if t.completed)
    total_open = total - total_completed
    open_tasks = [t for t in tasks if not t.completed]
    focused_open = sum(1 for t in open_tasks if t.quadrant in ("do", "schedule"))

    return TodoStatsResponse(
        quadrant_stats=quadrant_stats,
        daily_completion=daily_completion,
        total_open=total_open,
        total_completed=total_completed,
        overdue_count=sum(
            1 for t in open_tasks if t.due_date is not None and t.due_date < today
        ),
        due_today_count=sum(1 for t in open_tasks if t.due_date == today),
        completed_today=sum(
            1
            for t in tasks
            if t.completed_at is not None and t.completed_at.date() == today
        ),
        completion_rate=round(total_completed / total * 100, 1) if total else 0.0,
        focus_rate=round(focused_open / total_open * 100, 1) if total_open else 0.0,
    )
