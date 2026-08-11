import uuid
from datetime import datetime
from typing import Optional, List
from fastapi import APIRouter, Depends, HTTPException, status, Query
from sqlalchemy import or_, func
from sqlalchemy.orm import Session

from app import models
from app.core.database import get_db
from app.api.deps import get_current_user
from app.schemas.reading import (
    ReadingPassageCreate,
    ReadingPassageUpdate,
    ReadingPassageResponse,
    ReadingPassageListItem,
    ReadingPassageListResponse,
    TranslationPracticeCreate,
    TranslationPracticeResponse,
    ReadingCommentCreate,
    ReadingCommentUpdate,
    ReadingCommentResponse,
)

router = APIRouter()


@router.post("", response_model=ReadingPassageResponse, status_code=status.HTTP_201_CREATED)
def create_reading_passage(
    payload: ReadingPassageCreate,
    db: Session = Depends(get_db),
    current_user: models.User = Depends(get_current_user),
):
    passage_id = f"rdg-{uuid.uuid4().hex[:8]}"
    db_passage = models.ReadingPassage(
        id=passage_id,
        title=payload.title.strip(),
        content=payload.content.strip(),
        level=payload.level.strip() if payload.level else None,
        category=payload.category.strip() if payload.category else None,
        user_id=current_user.id,
    )
    db.add(db_passage)
    db.commit()
    db.refresh(db_passage)
    return db_passage


@router.get("", response_model=ReadingPassageListResponse[ReadingPassageListItem])
def list_reading_passages(
    db: Session = Depends(get_db),
    current_user: models.User = Depends(get_current_user),
    page: int = Query(1, ge=1),
    page_size: int = Query(20, ge=1, le=100),
    q: Optional[str] = Query(None, description="Tìm theo tiêu đề hoặc nội dung"),
    level: Optional[str] = Query(None),
    category: Optional[str] = Query(None),
):
    query = db.query(models.ReadingPassage)
    if q:
        like = f"%{q.lower()}%"
        query = query.filter(
            or_(
                func.lower(models.ReadingPassage.title).like(like),
                func.lower(models.ReadingPassage.content).like(like),
            )
        )
    if level:
        query = query.filter(models.ReadingPassage.level == level)
    if category:
        query = query.filter(models.ReadingPassage.category == category)

    total = query.count()
    passages = (
        query.order_by(models.ReadingPassage.created_at.desc())
        .offset((page - 1) * page_size)
        .limit(page_size)
        .all()
    )
    return ReadingPassageListResponse(
        items=passages, total=total, page=page, page_size=page_size
    )


@router.get("/{passage_id}", response_model=ReadingPassageResponse)
def get_reading_passage(
    passage_id: str,
    db: Session = Depends(get_db),
    current_user: models.User = Depends(get_current_user),
):
    passage = db.query(models.ReadingPassage).filter(models.ReadingPassage.id == passage_id).first()
    if not passage:
        raise HTTPException(status_code=404, detail="Không tìm thấy bài đọc.")
    return passage


@router.patch("/{passage_id}", response_model=ReadingPassageResponse)
def update_reading_passage(
    passage_id: str,
    payload: ReadingPassageUpdate,
    db: Session = Depends(get_db),
    current_user: models.User = Depends(get_current_user),
):
    passage = db.query(models.ReadingPassage).filter(models.ReadingPassage.id == passage_id).first()
    if not passage:
        raise HTTPException(status_code=404, detail="Không tìm thấy bài đọc.")

    # Permission check: owner or admin
    if passage.user_id != current_user.id and current_user.role != "admin":
        raise HTTPException(status_code=403, detail="Bạn không có quyền chỉnh sửa bài đọc này.")

    data = payload.model_dump(exclude_unset=True)
    for k, v in data.items():
        if isinstance(v, str):
            v = v.strip()
        setattr(passage, k, v if v != "" else None)

    db.commit()
    db.refresh(passage)
    return passage


@router.delete("/{passage_id}")
def delete_reading_passage(
    passage_id: str,
    db: Session = Depends(get_db),
    current_user: models.User = Depends(get_current_user),
):
    passage = db.query(models.ReadingPassage).filter(models.ReadingPassage.id == passage_id).first()
    if not passage:
        raise HTTPException(status_code=404, detail="Không tìm thấy bài đọc.")

    # Permission check: owner or admin
    if passage.user_id != current_user.id and current_user.role != "admin":
        raise HTTPException(status_code=403, detail="Bạn không có quyền xóa bài đọc này.")

    db.delete(passage)
    db.commit()
    return {"message": "Đã xóa bài đọc thành công."}


@router.get("/{passage_id}/translation", response_model=Optional[TranslationPracticeResponse])
def get_translation_practice(
    passage_id: str,
    db: Session = Depends(get_db),
    current_user: models.User = Depends(get_current_user),
):
    # Ensure passage exists
    passage = db.query(models.ReadingPassage).filter(models.ReadingPassage.id == passage_id).first()
    if not passage:
        raise HTTPException(status_code=404, detail="Không tìm thấy bài đọc.")

    practice = (
        db.query(models.TranslationPractice)
        .filter(
            models.TranslationPractice.passage_id == passage_id,
            models.TranslationPractice.user_id == current_user.id,
        )
        .first()
    )
    return practice


@router.post("/{passage_id}/translation", response_model=TranslationPracticeResponse)
def save_translation_practice(
    passage_id: str,
    payload: TranslationPracticeCreate,
    db: Session = Depends(get_db),
    current_user: models.User = Depends(get_current_user),
):
    passage = db.query(models.ReadingPassage).filter(models.ReadingPassage.id == passage_id).first()
    if not passage:
        raise HTTPException(status_code=404, detail="Không tìm thấy bài đọc.")

    practice = (
        db.query(models.TranslationPractice)
        .filter(
            models.TranslationPractice.passage_id == passage_id,
            models.TranslationPractice.user_id == current_user.id,
        )
        .first()
    )

    if practice:
        practice.translation_content = payload.translation_content.strip()
        practice.updated_at = datetime.utcnow()
    else:
        practice = models.TranslationPractice(
            id=f"trn-{uuid.uuid4().hex[:8]}",
            passage_id=passage_id,
            user_id=current_user.id,
            translation_content=payload.translation_content.strip(),
        )
        db.add(practice)

    db.commit()
    db.refresh(practice)
    return practice


@router.get("/{passage_id}/comments", response_model=List[ReadingCommentResponse])
def list_comments(
    passage_id: str,
    db: Session = Depends(get_db),
    current_user: models.User = Depends(get_current_user),
):
    passage = db.query(models.ReadingPassage).filter(models.ReadingPassage.id == passage_id).first()
    if not passage:
        raise HTTPException(status_code=404, detail="Không tìm thấy bài đọc.")

    comments = (
        db.query(models.ReadingComment)
        .filter(models.ReadingComment.passage_id == passage_id)
        .order_by(models.ReadingComment.created_at.asc())
        .all()
    )

    return comments


@router.post("/{passage_id}/comments", response_model=ReadingCommentResponse)
def create_comment(
    passage_id: str,
    payload: ReadingCommentCreate,
    db: Session = Depends(get_db),
    current_user: models.User = Depends(get_current_user),
):
    passage = db.query(models.ReadingPassage).filter(models.ReadingPassage.id == passage_id).first()
    if not passage:
        raise HTTPException(status_code=404, detail="Không tìm thấy bài đọc.")

    comment = models.ReadingComment(
        id=f"cmt-{uuid.uuid4().hex[:8]}",
        passage_id=passage_id,
        user_id=current_user.id,
        content=payload.content.strip(),
        selected_text=payload.selected_text.strip() if payload.selected_text else None,
    )
    db.add(comment)
    db.commit()
    db.refresh(comment)
    return comment


@router.patch("/comments/{comment_id}", response_model=ReadingCommentResponse)
def update_comment(
    comment_id: str,
    payload: ReadingCommentUpdate,
    db: Session = Depends(get_db),
    current_user: models.User = Depends(get_current_user),
):
    comment = db.query(models.ReadingComment).filter(models.ReadingComment.id == comment_id).first()
    if not comment:
        raise HTTPException(status_code=404, detail="Không tìm thấy bình luận.")

    if comment.user_id != current_user.id and current_user.role != "admin":
        raise HTTPException(status_code=403, detail="Bạn không có quyền chỉnh sửa bình luận này.")

    comment.content = payload.content.strip()
    db.commit()
    db.refresh(comment)
    return comment


@router.delete("/comments/{comment_id}")
def delete_comment(
    comment_id: str,
    db: Session = Depends(get_db),
    current_user: models.User = Depends(get_current_user),
):
    comment = db.query(models.ReadingComment).filter(models.ReadingComment.id == comment_id).first()
    if not comment:
        raise HTTPException(status_code=404, detail="Không tìm thấy bình luận.")

    if comment.user_id != current_user.id and current_user.role != "admin":
        raise HTTPException(status_code=403, detail="Bạn không có quyền xóa bình luận này.")

    db.delete(comment)
    db.commit()
    return {"message": "Đã xóa bình luận thành công."}
