import os
import uuid
import boto3
from botocore.config import Config
from fastapi import APIRouter, Depends, HTTPException, status, UploadFile, File, Form, Query
from sqlalchemy.orm import Session
from sqlalchemy import or_, func
from datetime import datetime
from typing import Optional, List

from app import models
from app.schemas.audio import (
    AudioResponse,
    AudioUpdate,
    AudioListItem,
    AudioListResponse,
    BulkDeleteRequest,
    BulkDeleteResponse,
    LEVEL_CHOICES,
    MAX_TRANSCRIPT_LENGTH,
    AudioCommentCreate,
    AudioCommentUpdate,
    AudioCommentResponse,
)
from app.core.database import get_db
from app.api.deps import get_current_user
from app.core.config import settings

router = APIRouter()

# Maximum audio file size: 100 MB
MAX_FILE_SIZE_BYTES = 100 * 1024 * 1024

# Initialize Cloudflare R2 client (S3-compatible)
r2_client = boto3.client(
    "s3",
    endpoint_url=settings.r2_endpoint,
    aws_access_key_id=settings.r2_access_key,
    aws_secret_access_key=settings.r2_secret_key,
    config=Config(signature_version="s3v4"),
)


def _can_modify(audio: models.Audio, current_user: models.User) -> bool:
    """Owner or admin can modify/delete."""
    return audio.user_id == current_user.id or current_user.role == "admin"


def _delete_from_r2(r2_key: str) -> None:
    """Best-effort R2 delete. Logs errors but never raises."""
    try:
        r2_client.delete_object(Bucket=settings.r2_bucket, Key=r2_key)
    except Exception as e:
        import logging
        logging.warning(f"Failed to delete R2 object {r2_key}: {e}")


def _to_list_item(audio: models.Audio) -> AudioListItem:
    """Convert ORM model → AudioListItem with computed has_transcript flag."""
    return AudioListItem(
        id=audio.id,
        title=audio.title,
        filename=audio.filename,
        url=audio.url,
        user_id=audio.user_id,
        created_at=audio.created_at,
        level=audio.level,
        category=audio.category,
        has_transcript=bool(audio.transcript and audio.transcript.strip()),
    )


@router.post("/upload", response_model=AudioResponse)
def upload_audio(
    title: str = Form(..., min_length=1, max_length=200),
    file: UploadFile = File(...),
    level: Optional[str] = Form(None),
    category: Optional[str] = Form(None),
    transcript: Optional[str] = Form(None),
    db: Session = Depends(get_db),
    current_user: models.User = Depends(get_current_user)
):
    content_type = file.content_type or ""
    filename_lower = file.filename.lower() if file.filename else ""

    if not (content_type.startswith("audio/") or filename_lower.endswith((".mp3", ".wav", ".m4a", ".aac", ".ogg"))):
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Tập tin không hợp lệ. Chỉ chấp nhận các định dạng âm thanh (mp3, wav, m4a, aac, ogg)."
        )

    if file.size is not None and file.size > MAX_FILE_SIZE_BYTES:
        raise HTTPException(
            status_code=status.HTTP_413_REQUEST_ENTITY_TOO_LARGE,
            detail=f"File quá lớn. Giới hạn tối đa {MAX_FILE_SIZE_BYTES // (1024 * 1024)} MB."
        )

    if level is not None and level != "" and level not in LEVEL_CHOICES:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=f"Level không hợp lệ. Chỉ chấp nhận: {', '.join(LEVEL_CHOICES)}."
        )

    # Validate transcript length
    transcript_value = transcript.strip() if transcript else None
    if transcript_value and len(transcript_value) > MAX_TRANSCRIPT_LENGTH:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=f"Transcript quá dài. Giới hạn tối đa {MAX_TRANSCRIPT_LENGTH} ký tự."
        )

    file_ext = os.path.splitext(file.filename)[1] if file.filename else ".mp3"
    if not file_ext:
        file_ext = ".mp3"

    unique_filename = f"{uuid.uuid4().hex}{file_ext}"
    r2_key = f"audio/{unique_filename}"

    try:
        r2_client.upload_fileobj(
            file.file,
            settings.r2_bucket,
            r2_key,
            ExtraArgs={"ContentType": content_type or "audio/mpeg"}
        )
    except Exception as e:
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Không thể tải file lên Cloudflare R2: {str(e)}"
        )

    audio_id = f"aud-{uuid.uuid4().hex[:8]}"

    base_url = settings.r2_public_url.rstrip("/")
    public_url = f"{base_url}/{r2_key}"

    db_audio = models.Audio(
        id=audio_id,
        title=title,
        filename=file.filename or unique_filename,
        url=public_url,
        r2_key=r2_key,
        user_id=current_user.id,
        level=level if level else None,
        category=category if category else None,
        transcript=transcript_value,
    )
    db.add(db_audio)
    db.commit()
    db.refresh(db_audio)

    return db_audio


@router.get("", response_model=AudioListResponse[AudioListItem])
def list_audios(
    db: Session = Depends(get_db),
    current_user: models.User = Depends(get_current_user),
    page: int = Query(1, ge=1),
    page_size: int = Query(20, ge=1, le=100),
    q: Optional[str] = Query(None, description="Tìm theo title/filename/category"),
    level: Optional[str] = Query(None),
    category: Optional[str] = Query(None),
):
    query = db.query(models.Audio)

    if q:
        like = f"%{q.lower()}%"
        query = query.filter(
            or_(
                func.lower(models.Audio.title).like(like),
                func.lower(models.Audio.filename).like(like),
                func.lower(models.Audio.category).like(like),
            )
        )
    if level:
        query = query.filter(models.Audio.level == level)
    if category:
        query = query.filter(models.Audio.category == category)

    total = query.count()
    audio_rows = (
        query.order_by(models.Audio.created_at.desc())
        .offset((page - 1) * page_size)
        .limit(page_size)
        .all()
    )

    # Build lightweight list items without serializing transcript in the response
    items = [_to_list_item(a) for a in audio_rows]

    return AudioListResponse(items=items, total=total, page=page, page_size=page_size)


@router.get("/{audio_id}", response_model=AudioResponse)
def get_audio(
    audio_id: str,
    db: Session = Depends(get_db),
    current_user: models.User = Depends(get_current_user),
):
    audio = db.query(models.Audio).filter(models.Audio.id == audio_id).first()
    if not audio:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Không tìm thấy bài nghe."
        )
    return audio


@router.patch("/{audio_id}", response_model=AudioResponse)
def update_audio(
    audio_id: str,
    payload: AudioUpdate,
    db: Session = Depends(get_db),
    current_user: models.User = Depends(get_current_user),
):
    audio = db.query(models.Audio).filter(models.Audio.id == audio_id).first()
    if not audio:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Không tìm thấy bài nghe."
        )

    if not _can_modify(audio, current_user):
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="Bạn không có quyền chỉnh sửa bài nghe này."
        )

    data = payload.model_dump(exclude_unset=True)

    if "level" in data and data["level"] is not None and data["level"] not in LEVEL_CHOICES:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=f"Level không hợp lệ. Chỉ chấp nhận: {', '.join(LEVEL_CHOICES)}."
        )

    # Normalize empty transcript → None
    if "transcript" in data and data["transcript"] is not None:
        stripped = data["transcript"].strip()
        data["transcript"] = stripped if stripped else None

    for k, v in data.items():
        setattr(audio, k, v)

    db.commit()
    db.refresh(audio)
    return audio


@router.post("/bulk-delete", response_model=BulkDeleteResponse)
def bulk_delete_audios(
    payload: BulkDeleteRequest,
    db: Session = Depends(get_db),
    current_user: models.User = Depends(get_current_user),
):
    deleted = 0
    failed: list[str] = []

    for audio_id in payload.ids:
        audio = db.query(models.Audio).filter(models.Audio.id == audio_id).first()
        if not audio:
            failed.append(audio_id)
            continue
        if not _can_modify(audio, current_user):
            failed.append(audio_id)
            continue

        _delete_from_r2(audio.r2_key)
        db.delete(audio)
        deleted += 1

    db.commit()
    return BulkDeleteResponse(deleted=deleted, failed=failed)


@router.delete("/{audio_id}")
def delete_audio(
    audio_id: str,
    db: Session = Depends(get_db),
    current_user: models.User = Depends(get_current_user),
):
    audio = db.query(models.Audio).filter(models.Audio.id == audio_id).first()
    if not audio:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Không tìm thấy bài nghe."
        )

    if not _can_modify(audio, current_user):
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="Bạn không có quyền xóa bài nghe này."
        )

    _delete_from_r2(audio.r2_key)

    db.delete(audio)
    db.commit()
    return {"message": "Đã xóa bài nghe thành công."}


@router.get("/{audio_id}/comments", response_model=List[AudioCommentResponse])
def list_comments(
    audio_id: str,
    db: Session = Depends(get_db),
    current_user: models.User = Depends(get_current_user),
):
    audio = db.query(models.Audio).filter(models.Audio.id == audio_id).first()
    if not audio:
        raise HTTPException(status_code=404, detail="Không tìm thấy bài nghe.")

    comments = (
        db.query(models.AudioComment)
        .filter(models.AudioComment.audio_id == audio_id)
        .order_by(models.AudioComment.created_at.asc())
        .all()
    )

    return comments


@router.post("/{audio_id}/comments", response_model=AudioCommentResponse)
def create_comment(
    audio_id: str,
    payload: AudioCommentCreate,
    db: Session = Depends(get_db),
    current_user: models.User = Depends(get_current_user),
):
    audio = db.query(models.Audio).filter(models.Audio.id == audio_id).first()
    if not audio:
        raise HTTPException(status_code=404, detail="Không tìm thấy bài nghe.")

    comment = models.AudioComment(
        id=f"cmt-{uuid.uuid4().hex[:8]}",
        audio_id=audio_id,
        user_id=current_user.id,
        content=payload.content.strip(),
        selected_text=payload.selected_text.strip() if payload.selected_text else None,
    )
    db.add(comment)
    db.commit()
    db.refresh(comment)
    return comment


@router.patch("/comments/{comment_id}", response_model=AudioCommentResponse)
def update_comment(
    comment_id: str,
    payload: AudioCommentUpdate,
    db: Session = Depends(get_db),
    current_user: models.User = Depends(get_current_user),
):
    comment = db.query(models.AudioComment).filter(models.AudioComment.id == comment_id).first()
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
    comment = db.query(models.AudioComment).filter(models.AudioComment.id == comment_id).first()
    if not comment:
        raise HTTPException(status_code=404, detail="Không tìm thấy bình luận.")

    if comment.user_id != current_user.id and current_user.role != "admin":
        raise HTTPException(status_code=403, detail="Bạn không có quyền xóa bình luận này.")

    db.delete(comment)
    db.commit()
    return {"message": "Đã xóa bình luận thành công."}