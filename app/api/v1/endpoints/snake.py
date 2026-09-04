import uuid
from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy.orm import Session
from app import models
from app.schemas.snake import SnakeGameStatResponse, SnakeSessionSubmit
from app.core.database import get_db
from app.api.deps import get_current_user

router = APIRouter()

@router.get("/stats", response_model=SnakeGameStatResponse)
def get_snake_stats(
    db: Session = Depends(get_db),
    current_user: models.User = Depends(get_current_user),
):
    stat = db.query(models.SnakeGameStat).filter(models.SnakeGameStat.user_id == current_user.id).first()
    if not stat:
        stat = models.SnakeGameStat(
            id=f"snake-{uuid.uuid4().hex[:8]}",
            user_id=current_user.id,
            high_score=0,
            max_combo=0,
            total_games=0,
            total_wins=0,
        )
        db.add(stat)
        db.commit()
        db.refresh(stat)
    return stat

@router.post("/session", response_model=SnakeGameStatResponse)
def submit_snake_session(
    payload: SnakeSessionSubmit,
    db: Session = Depends(get_db),
    current_user: models.User = Depends(get_current_user),
):
    stat = db.query(models.SnakeGameStat).filter(models.SnakeGameStat.user_id == current_user.id).first()
    if not stat:
        stat = models.SnakeGameStat(
            id=f"snake-{uuid.uuid4().hex[:8]}",
            user_id=current_user.id,
            high_score=0,
            max_combo=0,
            total_games=0,
            total_wins=0,
        )
        db.add(stat)

    stat.total_games += 1
    if payload.is_win:
        stat.total_wins += 1
    if payload.score > stat.high_score:
        stat.high_score = payload.score
    if payload.max_combo > stat.max_combo:
        stat.max_combo = payload.max_combo

    db.commit()
    db.refresh(stat)
    return stat
