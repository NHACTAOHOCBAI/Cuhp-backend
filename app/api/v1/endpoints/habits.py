import uuid
from datetime import date, datetime, timedelta
from typing import List, Optional
from fastapi import APIRouter, Depends, HTTPException, Query
from sqlalchemy.orm import Session
from loguru import logger

from app import models
from app.api.deps import get_current_user
from app.core.database import get_db
from app.schemas.habit import (
    HabitCreate,
    HabitUpdate,
    HabitResponse,
    HabitLogToggle,
    HabitLogResponse,
)

router = APIRouter()

def calculate_habit_streak(db: Session, habit_id: str, today: date) -> int:
    """Calculate the current streak of consecutive days a habit was completed.
    
    Allow completion on 'today', or if not yet completed today, check 'yesterday'.
    """
    logs = (
        db.query(models.HabitLog)
        .filter(models.HabitLog.habit_id == habit_id, models.HabitLog.completed == True)
        .order_by(models.HabitLog.date.desc())
        .all()
    )

    if not logs:
        return 0

    completed_dates = {log.date for log in logs}
    streak = 0
    current_date = today

    # Check today
    if current_date in completed_dates:
        streak += 1
        current_date -= timedelta(days=1)
    else:
        # Check yesterday
        yesterday = current_date - timedelta(days=1)
        if yesterday in completed_dates:
            current_date = yesterday
        else:
            return 0

    # Go back day by day
    while current_date in completed_dates:
        streak += 1
        current_date -= timedelta(days=1)

    return streak


@router.get("", response_model=List[HabitResponse])
async def get_habits(
    db: Session = Depends(get_db),
    current_user: models.User = Depends(get_current_user)
):
    """Get all habits of the current user, including their current streak."""
    habits = (
        db.query(models.Habit)
        .filter(models.Habit.user_id == current_user.id)
        .order_by(models.Habit.order.asc(), models.Habit.created_at.asc())
        .all()
    )

    today = date.today()
    response_habits = []
    for h in habits:
        # We convert to dict and add the streak, or assign to habit object
        # Since pydantic will parse it, assigning streak is cleaner
        h.streak = calculate_habit_streak(db, h.id, today)
        response_habits.append(h)

    return response_habits


@router.post("", response_model=HabitResponse)
async def create_habit(
    payload: HabitCreate,
    db: Session = Depends(get_db),
    current_user: models.User = Depends(get_current_user)
):
    """Create a new habit."""
    habit = models.Habit(
        id=f"hab-{uuid.uuid4().hex[:12]}",
        user_id=current_user.id,
        name=payload.name,
        icon=payload.icon,
        description=payload.description,
        is_active=payload.is_active,
        order=payload.order
    )
    db.add(habit)
    db.commit()
    db.refresh(habit)
    habit.streak = 0
    return habit


@router.put("/{id}", response_model=HabitResponse)
async def update_habit(
    id: str,
    payload: HabitUpdate,
    db: Session = Depends(get_db),
    current_user: models.User = Depends(get_current_user)
):
    """Update an existing habit."""
    habit = (
        db.query(models.Habit)
        .filter(models.Habit.id == id, models.Habit.user_id == current_user.id)
        .first()
    )
    if not habit:
        raise HTTPException(status_code=404, detail="Không tìm thấy thói quen này.")

    if payload.name is not None:
        habit.name = payload.name
    if payload.icon is not None:
        habit.icon = payload.icon
    if payload.description is not None:
        habit.description = payload.description
    if payload.is_active is not None:
        habit.is_active = payload.is_active
    if payload.order is not None:
        habit.order = payload.order

    db.commit()
    db.refresh(habit)
    habit.streak = calculate_habit_streak(db, habit.id, date.today())
    return habit


@router.delete("/{id}")
async def delete_habit(
    id: str,
    db: Session = Depends(get_db),
    current_user: models.User = Depends(get_current_user)
):
    """Delete a habit and all of its history logs."""
    habit = (
        db.query(models.Habit)
        .filter(models.Habit.id == id, models.Habit.user_id == current_user.id)
        .first()
    )
    if not habit:
        raise HTTPException(status_code=404, detail="Không tìm thấy thói quen này.")

    db.delete(habit)
    db.commit()
    return {"message": "Xóa thói quen thành công."}


@router.get("/logs", response_model=List[HabitLogResponse])
async def get_habit_logs(
    start_date: date,
    end_date: date,
    db: Session = Depends(get_db),
    current_user: models.User = Depends(get_current_user)
):
    """Retrieve completion logs of the user's habits in the specified date range."""
    # Query only logs for habits that belong to current_user
    logs = (
        db.query(models.HabitLog)
        .join(models.Habit, models.Habit.id == models.HabitLog.habit_id)
        .filter(
            models.Habit.user_id == current_user.id,
            models.HabitLog.date >= start_date,
            models.HabitLog.date <= end_date
        )
        .all()
    )
    return logs


@router.post("/logs/toggle", response_model=HabitLogResponse)
async def toggle_habit_log(
    payload: HabitLogToggle,
    db: Session = Depends(get_db),
    current_user: models.User = Depends(get_current_user)
):
    """Toggle a habit's completion log for a specific date."""
    habit = (
        db.query(models.Habit)
        .filter(models.Habit.id == payload.habit_id, models.Habit.user_id == current_user.id)
        .first()
    )
    if not habit:
        raise HTTPException(status_code=404, detail="Không tìm thấy thói quen.")

    log = (
        db.query(models.HabitLog)
        .filter(models.HabitLog.habit_id == payload.habit_id, models.HabitLog.date == payload.date)
        .first()
    )

    if log:
        log.completed = payload.completed
    else:
        log = models.HabitLog(
            id=f"hbl-{uuid.uuid4().hex[:12]}",
            habit_id=payload.habit_id,
            date=payload.date,
            completed=payload.completed
        )
        db.add(log)

    db.commit()
    db.refresh(log)
    return log
