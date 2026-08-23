from pydantic import BaseModel, ConfigDict
from datetime import datetime, date
from typing import Optional, List

class SleepLogCreate(BaseModel):
    sleep_date: date
    sleep_time_actual: datetime
    wake_time_actual: datetime
    notes: Optional[str] = None

class SleepLogResponse(SleepLogCreate):
    id: str
    user_id: str
    duration_minutes: float
    created_at: datetime

    model_config = ConfigDict(from_attributes=True)

class SleepStatsResponse(BaseModel):
    average_duration_hours: float
    average_bedtime: str  # e.g., "22:30"
    average_waketime: str  # e.g., "06:15"
    sleep_logs_7_days: List[SleepLogResponse]

    model_config = ConfigDict(from_attributes=True)

class SleepSettingsUpdate(BaseModel):
    sleep_bedtime: str  # e.g., "22:00"
    sleep_waketime: str  # e.g., "06:00"
    sleep_reminder_enabled: bool
