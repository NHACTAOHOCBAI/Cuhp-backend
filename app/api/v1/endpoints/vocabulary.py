import uuid
from fastapi import APIRouter, Depends, HTTPException, status, Query
from sqlalchemy.orm import Session
from sqlalchemy import or_, func
from typing import Optional, List

from app import models
from datetime import datetime, date, timedelta
from app.schemas.vocabulary import (
    VocabularyCreate,
    VocabularyUpdate,
    VocabularyResponse,
    VocabularyListResponse,
    VocabularyBulkDeleteRequest,
    VocabularyBulkDeleteResponse,
    VocabularyReviewRequest,
    VocabularyReviewResponse,
)
from app.core.database import get_db
from app.api.deps import get_current_user

router = APIRouter()

def _can_modify(vocab: models.Vocabulary, current_user: models.User) -> bool:
    """Only owner or admin can modify/delete."""
    return vocab.user_id == current_user.id or current_user.role == "admin"

@router.post("", response_model=VocabularyResponse, status_code=status.HTTP_201_CREATED)
def create_vocabulary(
    payload: VocabularyCreate,
    db: Session = Depends(get_db),
    current_user: models.User = Depends(get_current_user)
):
    vocab_id = f"voc-{uuid.uuid4().hex[:8]}"
    db_vocab = models.Vocabulary(
        id=vocab_id,
        word=payload.word.strip(),
        pronunciation=payload.pronunciation.strip() if payload.pronunciation else None,
        meaning=payload.meaning.strip(),
        word_type=payload.word_type.strip() if payload.word_type else None,
        notes=payload.notes.strip() if payload.notes else None,
        user_id=current_user.id,
    )
    db.add(db_vocab)
    db.commit()
    db.refresh(db_vocab)
    return db_vocab

@router.get("", response_model=VocabularyListResponse[VocabularyResponse])
def list_vocabularies(
    db: Session = Depends(get_db),
    current_user: models.User = Depends(get_current_user),
    page: int = Query(1, ge=1),
    page_size: int = Query(20, ge=1, le=100),
    q: Optional[str] = Query(None, description="Tìm theo từ, nghĩa hoặc ghi chú"),
    word_type: Optional[str] = Query(None),
    due: Optional[bool] = Query(None, description="Lọc từ đến hạn ôn tập"),
):
    query = db.query(models.Vocabulary).filter(models.Vocabulary.user_id == current_user.id)

    # Search filter
    if q:
        like = f"%{q.lower()}%"
        query = query.filter(
            or_(
                func.lower(models.Vocabulary.word).like(like),
                func.lower(models.Vocabulary.meaning).like(like),
                func.lower(models.Vocabulary.notes).like(like),
            )
        )

    # Specific filters
    if word_type:
        query = query.filter(models.Vocabulary.word_type == word_type)

    if due:
        now = datetime.utcnow()
        query = query.filter(models.Vocabulary.next_review_at <= now)

    total = query.count()
    vocab_rows = (
        query.order_by(models.Vocabulary.created_at.desc())
        .offset((page - 1) * page_size)
        .limit(page_size)
        .all()
    )

    return VocabularyListResponse(
        items=vocab_rows,
        total=total,
        page=page,
        page_size=page_size
    )

@router.get("/{vocab_id}", response_model=VocabularyResponse)
def get_vocabulary(
    vocab_id: str,
    db: Session = Depends(get_db),
    current_user: models.User = Depends(get_current_user)
):
    vocab = db.query(models.Vocabulary).filter(models.Vocabulary.id == vocab_id).first()
    if not vocab:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Không tìm thấy từ vựng."
        )
    return vocab

@router.patch("/{vocab_id}", response_model=VocabularyResponse)
def update_vocabulary(
    vocab_id: str,
    payload: VocabularyUpdate,
    db: Session = Depends(get_db),
    current_user: models.User = Depends(get_current_user)
):
    vocab = db.query(models.Vocabulary).filter(models.Vocabulary.id == vocab_id).first()
    if not vocab:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Không tìm thấy từ vựng."
        )

    if not _can_modify(vocab, current_user):
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="Bạn không có quyền chỉnh sửa từ vựng này."
        )

    data = payload.model_dump(exclude_unset=True)

    for k, v in data.items():
        if isinstance(v, str):
            v = v.strip()
        setattr(vocab, k, v if v != "" else None)

    db.commit()
    db.refresh(vocab)
    return vocab

@router.delete("/{vocab_id}")
def delete_vocabulary(
    vocab_id: str,
    db: Session = Depends(get_db),
    current_user: models.User = Depends(get_current_user)
):
    vocab = db.query(models.Vocabulary).filter(models.Vocabulary.id == vocab_id).first()
    if not vocab:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Không tìm thấy từ vựng."
        )

    if not _can_modify(vocab, current_user):
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="Bạn không có quyền xóa từ vựng này."
        )

    db.delete(vocab)
    db.commit()
    return {"message": "Đã xóa từ vựng thành công."}

@router.post("/bulk-delete", response_model=VocabularyBulkDeleteResponse)
def bulk_delete_vocabularies(
    payload: VocabularyBulkDeleteRequest,
    db: Session = Depends(get_db),
    current_user: models.User = Depends(get_current_user)
):
    deleted = 0
    failed: List[str] = []

    for vocab_id in payload.ids:
        vocab = db.query(models.Vocabulary).filter(models.Vocabulary.id == vocab_id).first()
        if not vocab:
            failed.append(vocab_id)
            continue
        if not _can_modify(vocab, current_user):
            failed.append(vocab_id)
            continue

        db.delete(vocab)
        deleted += 1

    db.commit()
    return VocabularyBulkDeleteResponse(deleted=deleted, failed=failed)

@router.post("/{vocab_id}/review", response_model=VocabularyReviewResponse)
def review_vocabulary(
    vocab_id: str,
    payload: VocabularyReviewRequest,
    db: Session = Depends(get_db),
    current_user: models.User = Depends(get_current_user)
):
    vocab = db.query(models.Vocabulary).filter(models.Vocabulary.id == vocab_id).first()
    if not vocab:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Không tìm thấy từ vựng."
        )

    if vocab.user_id != current_user.id:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="Bạn không có quyền ôn tập từ vựng này."
        )

    # 1. Update SRS Leitner Box & next_review_at
    if payload.known:
        vocab.box_number = min(vocab.box_number + 1, 5)
    else:
        vocab.box_number = 1

    # Leitner intervals: Box 1: 1d, Box 2: 2d, Box 3: 4d, Box 4: 7d, Box 5: 14d
    intervals = {1: 1, 2: 2, 3: 4, 4: 7, 5: 14}
    days = intervals.get(vocab.box_number, 1)
    vocab.next_review_at = datetime.utcnow() + timedelta(days=days)
    vocab.updated_at = datetime.utcnow()

    # 2. Daily Goal & Streak calculations
    today = date.today()
    streak_incremented_today = False

    # Check if last streak activity was before yesterday -> reset streak to 0
    if current_user.last_streak_increment_date:
        if current_user.last_streak_increment_date != today and current_user.last_streak_increment_date != (today - timedelta(days=1)):
            current_user.current_streak = 0

    # Handle daily reviewed words counting
    if current_user.last_reviewed_date != today:
        current_user.words_reviewed_today = 1
        current_user.last_reviewed_date = today
    else:
        current_user.words_reviewed_today += 1

    # Check if target is met today
    if current_user.words_reviewed_today >= current_user.daily_target:
        if current_user.last_streak_increment_date != today:
            current_user.current_streak += 1
            current_user.last_streak_increment_date = today
            streak_incremented_today = True

    db.commit()
    db.refresh(vocab)
    db.refresh(current_user)

    return VocabularyReviewResponse(
        vocabulary=vocab,
        daily_target=current_user.daily_target,
        current_streak=current_user.current_streak,
        words_reviewed_today=current_user.words_reviewed_today,
        streak_incremented_today=streak_incremented_today
    )
