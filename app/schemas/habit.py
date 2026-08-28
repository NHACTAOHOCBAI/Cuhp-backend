from pydantic import BaseModel, ConfigDict
from datetime import datetime, date
from typing import Optional, List

class HabitBase(BaseModel):
    name: str
    icon: Optional[str] = None
    description: Optional[str] = None
    is_active: bool = True
    order: int = 0

class HabitCreate(HabitBase):
    pass

class HabitUpdate(BaseModel):
    name: Optional[str] = None
    icon: Optional[str] = None
    description: Optional[str] = None
    is_active: Optional[bool] = None
    order: Optional[int] = None

class HabitResponse(HabitBase):
    id: str
    user_id: str
    created_at: datetime
    updated_at: datetime
    streak: int = 0

    model_config = ConfigDict(from_attributes=True)

class HabitLogToggle(BaseModel):
    habit_id: str
    date: date
    completed: bool

class HabitLogResponse(BaseModel):
    id: str
    habit_id: str
    date: date
    completed: bool
    created_at: datetime

    model_config = ConfigDict(from_attributes=True)
