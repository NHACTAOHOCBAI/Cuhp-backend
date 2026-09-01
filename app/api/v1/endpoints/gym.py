from fastapi import APIRouter, Depends, HTTPException, status, Query
from sqlalchemy.orm import Session
from typing import List, Optional
from datetime import date, datetime, timedelta
import uuid

from app import models
from app.core.database import get_db
from app.api.deps import get_current_user
from app.schemas.gym import (
    WorkoutCategoryCreate,
    WorkoutCategoryUpdate,
    WorkoutCategoryResponse,
    WorkoutExerciseCreate,
    WorkoutExerciseUpdate,
    WorkoutExerciseResponse,
    GymStatsResponse,
    DailyVolume,
    ExerciseProgress,
    ExerciseProgressPoint,
    CopyDayForwardRequest,
    CopyDayForwardResponse,
)

router = APIRouter()

# --- Helper function to seed default categories ---
def ensure_default_categories(db: Session, user_id: str):
    count = db.query(models.WorkoutCategory).filter(models.WorkoutCategory.user_id == user_id).count()
    if count == 0:
        defaults = [
            {"name": "Ngực", "color": "blue"},
            {"name": "Lưng", "color": "emerald"},
            {"name": "Chân", "color": "violet"},
            {"name": "Vai", "color": "amber"},
            {"name": "Tay", "color": "cyan"},
            {"name": "Bụng", "color": "rose"},
            {"name": "Cardio", "color": "orange"}
        ]
        for item in defaults:
            cat = models.WorkoutCategory(
                id=f"cat-{uuid.uuid4()}",
                user_id=user_id,
                name=item["name"],
                color=item["color"]
            )
            db.add(cat)
        db.commit()

# --- Workout Category Endpoints ---

@router.get("/categories", response_model=List[WorkoutCategoryResponse])
def get_categories(
    db: Session = Depends(get_db),
    current_user: models.User = Depends(get_current_user)
):
    ensure_default_categories(db, current_user.id)
    return db.query(models.WorkoutCategory).filter(
        models.WorkoutCategory.user_id == current_user.id
    ).order_by(models.WorkoutCategory.created_at.asc()).all()

@router.post("/categories", response_model=WorkoutCategoryResponse)
def create_category(
    category_in: WorkoutCategoryCreate,
    db: Session = Depends(get_db),
    current_user: models.User = Depends(get_current_user)
):
    # Check if category already exists
    existing = db.query(models.WorkoutCategory).filter(
        models.WorkoutCategory.user_id == current_user.id,
        models.WorkoutCategory.name == category_in.name
    ).first()
    if existing:
        raise HTTPException(
            status_code=400,
            detail="Nhóm cơ này đã tồn tại."
        )
        
    category = models.WorkoutCategory(
        id=f"cat-{uuid.uuid4()}",
        user_id=current_user.id,
        name=category_in.name,
        color=category_in.color
    )
    db.add(category)
    db.commit()
    db.refresh(category)
    return category

@router.put("/categories/{category_id}", response_model=WorkoutCategoryResponse)
def update_category(
    category_id: str,
    category_in: WorkoutCategoryUpdate,
    db: Session = Depends(get_db),
    current_user: models.User = Depends(get_current_user)
):
    category = db.query(models.WorkoutCategory).filter(
        models.WorkoutCategory.id == category_id,
        models.WorkoutCategory.user_id == current_user.id
    ).first()
    if not category:
        raise HTTPException(
            status_code=404,
            detail="Không tìm thấy phân loại nhóm cơ này."
        )
        
    if category_in.name is not None:
        category.name = category_in.name
    if category_in.color is not None:
        category.color = category_in.color
        
    db.commit()
    db.refresh(category)
    return category

@router.delete("/categories/{category_id}")
def delete_category(
    category_id: str,
    db: Session = Depends(get_db),
    current_user: models.User = Depends(get_current_user)
):
    category = db.query(models.WorkoutCategory).filter(
        models.WorkoutCategory.id == category_id,
        models.WorkoutCategory.user_id == current_user.id
    ).first()
    if not category:
        raise HTTPException(
            status_code=404,
            detail="Không tìm thấy phân loại nhóm cơ này."
        )
        
    db.delete(category)
    db.commit()
    return {"message": "Đã xóa phân loại nhóm cơ thành công."}


# --- Workout Exercise Endpoints ---

@router.get("/exercises", response_model=List[WorkoutExerciseResponse])
def get_exercises(
    date_filter: Optional[date] = Query(None, alias="date"),
    db: Session = Depends(get_db),
    current_user: models.User = Depends(get_current_user)
):
    query = db.query(models.WorkoutExercise).filter(
        models.WorkoutExercise.user_id == current_user.id
    )
    if date_filter:
        query = query.filter(models.WorkoutExercise.date == date_filter)
        
    return query.order_by(models.WorkoutExercise.created_at.asc()).all()

@router.post("/exercises", response_model=WorkoutExerciseResponse)
def create_exercise(
    exercise_in: WorkoutExerciseCreate,
    db: Session = Depends(get_db),
    current_user: models.User = Depends(get_current_user)
):
    # Verify category if provided
    if exercise_in.category_id:
        category = db.query(models.WorkoutCategory).filter(
            models.WorkoutCategory.id == exercise_in.category_id,
            models.WorkoutCategory.user_id == current_user.id
        ).first()
        if not category:
            raise HTTPException(
                status_code=400,
                detail="Phân loại nhóm cơ không hợp lệ."
            )
            
    exercise = models.WorkoutExercise(
        id=f"ex-{uuid.uuid4()}",
        user_id=current_user.id,
        category_id=exercise_in.category_id,
        name=exercise_in.name,
        date=exercise_in.date,
        sets=exercise_in.sets,
        reps=exercise_in.reps,
        weight=exercise_in.weight,
        completed=exercise_in.completed
    )
    db.add(exercise)
    db.commit()
    db.refresh(exercise)
    return exercise

@router.put("/exercises/{exercise_id}", response_model=WorkoutExerciseResponse)
def update_exercise(
    exercise_id: str,
    exercise_in: WorkoutExerciseUpdate,
    db: Session = Depends(get_db),
    current_user: models.User = Depends(get_current_user)
):
    exercise = db.query(models.WorkoutExercise).filter(
        models.WorkoutExercise.id == exercise_id,
        models.WorkoutExercise.user_id == current_user.id
    ).first()
    if not exercise:
        raise HTTPException(
            status_code=404,
            detail="Không tìm thấy bài tập này."
        )
        
    provided = exercise_in.model_fields_set
        
    # Verify category if changing
    if "category_id" in provided:
        if exercise_in.category_id is None or exercise_in.category_id == "":
            exercise.category_id = None
        else:
            category = db.query(models.WorkoutCategory).filter(
                models.WorkoutCategory.id == exercise_in.category_id,
                models.WorkoutCategory.user_id == current_user.id
            ).first()
            if not category:
                raise HTTPException(
                    status_code=400,
                    detail="Phân loại nhóm cơ không hợp lệ."
                )
            exercise.category_id = exercise_in.category_id

    if "name" in provided:
        exercise.name = exercise_in.name
    if "date" in provided:
        exercise.date = exercise_in.date
    if "sets" in provided:
        exercise.sets = exercise_in.sets
    if "reps" in provided:
        exercise.reps = exercise_in.reps
    if "weight" in provided:
        exercise.weight = exercise_in.weight
    if "completed" in provided:
        exercise.completed = exercise_in.completed
        
    db.commit()
    db.refresh(exercise)
    return exercise

@router.delete("/exercises/{exercise_id}")
def delete_exercise(
    exercise_id: str,
    db: Session = Depends(get_db),
    current_user: models.User = Depends(get_current_user)
):
    exercise = db.query(models.WorkoutExercise).filter(
        models.WorkoutExercise.id == exercise_id,
        models.WorkoutExercise.user_id == current_user.id
    ).first()
    if not exercise:
        raise HTTPException(
            status_code=404,
            detail="Không tìm thấy bài tập này."
        )
        
    db.delete(exercise)
    db.commit()
    return {"message": "Đã xóa bài tập thành công."}


@router.post("/exercises/copy-day-forward", response_model=CopyDayForwardResponse)
def copy_day_forward(
    body: CopyDayForwardRequest,
    db: Session = Depends(get_db),
    current_user: models.User = Depends(get_current_user)
):
    """Copy all exercises on `source_date` to the same weekday N weeks ahead.

    For each k in [1..weeks_ahead], target_date = source_date + timedelta(weeks=k).
    Days that already contain at least one exercise (for this user) are skipped.
    Copied exercises keep name/sets/reps/weight/category but reset completed=False.
    """
    if body.weeks_ahead < 1 or body.weeks_ahead > 12:
        raise HTTPException(
            status_code=400,
            detail="weeks_ahead phải nằm trong khoảng 1 đến 12.",
        )

    source_exercises = (
        db.query(models.WorkoutExercise)
        .filter(
            models.WorkoutExercise.user_id == current_user.id,
            models.WorkoutExercise.date == body.source_date,
        )
        .all()
    )

    if not source_exercises:
        return CopyDayForwardResponse(created=0, skipped_days=0)

    # Pre-compute all target dates + whether each already has data
    target_dates = [
        body.source_date + timedelta(weeks=k) for k in range(1, body.weeks_ahead + 1)
    ]
    existing_target_dates = {
        row.date
        for row in db.query(models.WorkoutExercise.date)
        .filter(
            models.WorkoutExercise.user_id == current_user.id,
            models.WorkoutExercise.date.in_(target_dates),
        )
        .all()
    }

    created_count = 0
    skipped_days = 0
    for k, target_date in enumerate(target_dates, start=1):
        if target_date in existing_target_dates:
            skipped_days += 1
            continue

        for src in source_exercises:
            new_ex = models.WorkoutExercise(
                id=f"ex-{uuid.uuid4()}",
                user_id=current_user.id,
                category_id=src.category_id,
                name=src.name,
                date=target_date,
                sets=src.sets,
                reps=src.reps,
                weight=src.weight,
                completed=False,
            )
            db.add(new_ex)
            created_count += 1

    db.commit()

    return CopyDayForwardResponse(
        created=created_count,
        skipped_days=skipped_days,
    )


# --- Gym Stats Endpoint ---

@router.get("/stats", response_model=GymStatsResponse)
def get_gym_stats(
    db: Session = Depends(get_db),
    current_user: models.User = Depends(get_current_user)
):
    today = date.today()
    weekly_volume = []
    
    # Calculate daily volumes for current calendar week (Monday to Sunday)
    start_of_week = today - timedelta(days=today.weekday())
    for i in range(7):
        d = start_of_week + timedelta(days=i)
        exercises = db.query(models.WorkoutExercise).filter(
            models.WorkoutExercise.user_id == current_user.id,
            models.WorkoutExercise.date == d
        ).all()
        
        total = len(exercises)
        completed = sum(1 for e in exercises if e.completed)
        # Volume = sets * reps * weight
        volume = sum(
            float(e.sets * e.reps * (e.weight or 0.0))
            for e in exercises if e.completed
        )
        
        weekly_volume.append(
            DailyVolume(
                date=d,
                volume=volume,
                completed_count=completed,
                total_count=total
            )
        )
        
    # Get all completed exercises to build exercise progress line chart
    completed_exercises = db.query(models.WorkoutExercise).filter(
        models.WorkoutExercise.user_id == current_user.id,
        models.WorkoutExercise.completed == True
    ).order_by(models.WorkoutExercise.date.asc()).all()
    
    # Group weight & volume details by exercise name and date
    progress_map = {}
    for e in completed_exercises:
        name = e.name.strip()
        if not name:
            continue
        if name not in progress_map:
            progress_map[name] = {}
            
        d_str = e.date.isoformat()
        vol = float(e.sets * e.reps * (e.weight or 0.0))
        w = float(e.weight or 0.0)
        
        if d_str not in progress_map[name]:
            progress_map[name][d_str] = {"max_weight": w, "volume": vol}
        else:
            progress_map[name][d_str]["max_weight"] = max(progress_map[name][d_str]["max_weight"], w)
            progress_map[name][d_str]["volume"] += vol
            
    exercise_progress = []
    for name, dates in progress_map.items():
        points = []
        for d_str, val in dates.items():
            points.append(
                ExerciseProgressPoint(
                    date=date.fromisoformat(d_str),
                    max_weight=val["max_weight"],
                    volume=val["volume"]
                )
            )
        points.sort(key=lambda x: x.date)
        exercise_progress.append(
            ExerciseProgress(
                exercise_name=name,
                points=points
            )
        )
        
    return GymStatsResponse(
        weekly_volume=weekly_volume,
        exercise_progress=exercise_progress
    )
