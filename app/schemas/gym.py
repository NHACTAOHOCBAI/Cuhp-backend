import datetime as dt_module
from pydantic import BaseModel, ConfigDict
from datetime import datetime, date
from typing import Optional, List

# --- Workout Category Schemas ---
class WorkoutCategoryBase(BaseModel):
    name: str
    color: str = "emerald"

class WorkoutCategoryCreate(WorkoutCategoryBase):
    pass

class WorkoutCategoryUpdate(BaseModel):
    name: Optional[str] = None
    color: Optional[str] = None

class WorkoutCategoryResponse(WorkoutCategoryBase):
    id: str
    user_id: str
    created_at: datetime

    model_config = ConfigDict(from_attributes=True)


# --- Workout Exercise Schemas ---
class WorkoutExerciseBase(BaseModel):
    name: str
    date: date
    sets: int = 3
    reps: int = 10
    weight: Optional[float] = None
    completed: bool = False
    category_id: Optional[str] = None

class WorkoutExerciseCreate(WorkoutExerciseBase):
    pass

class WorkoutExerciseUpdate(BaseModel):
    name: Optional[str] = None
    date: Optional[dt_module.date] = None
    sets: Optional[int] = None
    reps: Optional[int] = None
    weight: Optional[float] = None
    completed: Optional[bool] = None
    category_id: Optional[str] = None

class WorkoutExerciseResponse(WorkoutExerciseBase):
    id: str
    user_id: str
    created_at: datetime
    category: Optional[WorkoutCategoryResponse] = None

    model_config = ConfigDict(from_attributes=True)


# --- Workout Stats Schemas ---
class DailyVolume(BaseModel):
    date: date
    volume: float
    completed_count: int
    total_count: int

class ExerciseProgressPoint(BaseModel):
    date: date
    max_weight: float
    volume: float

class ExerciseProgress(BaseModel):
    exercise_name: str
    points: List[ExerciseProgressPoint]

class GymStatsResponse(BaseModel):
    weekly_volume: List[DailyVolume]
    exercise_progress: List[ExerciseProgress]


class CopyDayForwardRequest(BaseModel):
    """Request body for copying a single day's schedule forward N weeks.

    For each k in [1..weeks_ahead], copy all exercises on `source_date` to
    the same weekday exactly k weeks later. Days that already contain
    exercises are skipped (no overwrite). Backend validates
    `weeks_ahead` ∈ [1, 12].
    """

    source_date: date
    weeks_ahead: int = 4


class CopyDayForwardResponse(BaseModel):
    """Response: total exercises created and how many target days were skipped."""

    created: int
    skipped_days: int
