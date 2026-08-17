from pydantic import BaseModel, ConfigDict, field_validator
from datetime import datetime, date
from typing import Optional, List

# The four Eisenhower quadrants. Kept as plain strings (not a DB enum) so new
# values never require a migration, but validated on the way in.
QUADRANTS = ("do", "schedule", "delegate", "eliminate")

QUADRANT_LABELS = {
    "do": "Khẩn cấp & Quan trọng",
    "schedule": "Quan trọng, không khẩn cấp",
    "delegate": "Khẩn cấp, không quan trọng",
    "eliminate": "Không khẩn cấp, không quan trọng",
}


def _validate_quadrant(value: str) -> str:
    if value not in QUADRANTS:
        raise ValueError(
            f"Góc phần tư không hợp lệ. Chỉ chấp nhận: {', '.join(QUADRANTS)}."
        )
    return value


# --- Todo Task Schemas ---
class TodoTaskBase(BaseModel):
    title: str
    description: Optional[str] = None
    quadrant: str = "do"
    due_date: Optional[date] = None
    completed: bool = False

    @field_validator("quadrant")
    @classmethod
    def check_quadrant(cls, v: str) -> str:
        return _validate_quadrant(v)

    @field_validator("title")
    @classmethod
    def check_title(cls, v: str) -> str:
        v = (v or "").strip()
        if not v:
            raise ValueError("Tiêu đề công việc không được để trống.")
        return v


class TodoTaskCreate(TodoTaskBase):
    pass


class TodoTaskUpdate(BaseModel):
    title: Optional[str] = None
    description: Optional[str] = None
    quadrant: Optional[str] = None
    due_date: Optional[date] = None
    completed: Optional[bool] = None
    position: Optional[int] = None

    @field_validator("quadrant")
    @classmethod
    def check_quadrant(cls, v: Optional[str]) -> Optional[str]:
        if v is None:
            return v
        return _validate_quadrant(v)

    @field_validator("title")
    @classmethod
    def check_title(cls, v: Optional[str]) -> Optional[str]:
        if v is None:
            return v
        v = v.strip()
        if not v:
            raise ValueError("Tiêu đề công việc không được để trống.")
        return v


class TodoTaskResponse(TodoTaskBase):
    id: str
    user_id: str
    position: int
    completed_at: Optional[datetime] = None
    created_at: datetime
    updated_at: Optional[datetime] = None

    model_config = ConfigDict(from_attributes=True)


class TodoTaskMoveRequest(BaseModel):
    """Drag-and-drop payload: move a task to `quadrant` at index `position`.

    `position` is the 0-based slot the card should occupy inside the target
    quadrant *after* the move; the server renumbers the whole quadrant so the
    ordering stays dense and stable.
    """

    quadrant: str
    position: int = 0

    @field_validator("quadrant")
    @classmethod
    def check_quadrant(cls, v: str) -> str:
        return _validate_quadrant(v)

    @field_validator("position")
    @classmethod
    def check_position(cls, v: int) -> int:
        return max(0, v)


# --- Todo Stats Schemas ---
class QuadrantStat(BaseModel):
    """Aggregate counts for one quadrant, used by the distribution chart."""

    quadrant: str
    label: str
    total: int
    completed: int
    open_count: int
    overdue: int


class DailyCompletion(BaseModel):
    """One bar in the 7-day completion chart."""

    date: date
    completed_count: int
    created_count: int


class TodoStatsResponse(BaseModel):
    quadrant_stats: List[QuadrantStat]
    daily_completion: List[DailyCompletion]
    total_open: int
    total_completed: int
    overdue_count: int
    due_today_count: int
    completed_today: int
    # Percentage (0-100) of tasks finished out of all tasks ever created.
    completion_rate: float
    # Percentage (0-100) of *open* effort sitting in the "do" + "schedule"
    # quadrants — the classic Eisenhower health metric.
    focus_rate: float


class TodoListResponse(BaseModel):
    items: List[TodoTaskResponse]
    total: int
