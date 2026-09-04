from pydantic import BaseModel
from typing import Optional
from datetime import datetime

class SnakeGameStatResponse(BaseModel):
    id: str
    user_id: str
    high_score: int
    max_combo: int
    total_games: int
    total_wins: int
    created_at: datetime
    updated_at: datetime

    class Config:
        from_attributes = True

class SnakeSessionSubmit(BaseModel):
    score: int
    max_combo: int
    is_win: bool
    correct_words_count: int
    wrong_words_count: int
