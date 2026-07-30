import os
import uuid
import boto3
from botocore.config import Config
from fastapi import APIRouter, Depends, HTTPException, status, UploadFile, File, Form
from sqlalchemy.orm import Session
from datetime import datetime
from typing import List

from app import models
from app.schemas.audio import AudioResponse
from app.core.database import get_db
from app.api.deps import get_current_user
from app.core.config import settings

router = APIRouter()

# Initialize Cloudflare R2 client (S3-compatible)
r2_client = boto3.client(
    "s3",
    endpoint_url=settings.r2_endpoint,
    aws_access_key_id=settings.r2_access_key,
    aws_secret_access_key=settings.r2_secret_key,
    config=Config(signature_version="s3v4"),
)

@router.post("/upload", response_model=AudioResponse)
def upload_audio(
    title: str = Form(...),
    file: UploadFile = File(...),
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
    
    file_ext = os.path.splitext(file.filename)[1] if file.filename else ".mp3"
    if not file_ext:
        file_ext = ".mp3"
        
    unique_filename = f"{uuid.uuid4().hex}{file_ext}"
    r2_key = f"audio/{unique_filename}"
    
    try:
        # Upload file to R2
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
    
    # Construct R2 Public URL
    base_url = settings.r2_public_url.rstrip("/")
    public_url = f"{base_url}/{r2_key}"
    
    db_audio = models.Audio(
        id=audio_id,
        title=title,
        filename=file.filename or unique_filename,
        url=public_url,
        r2_key=r2_key,
        user_id=current_user.id
    )
    db.add(db_audio)
    db.commit()
    db.refresh(db_audio)
    
    return db_audio

@router.get("", response_model=List[AudioResponse])
def list_audios(
    db: Session = Depends(get_db),
    current_user: models.User = Depends(get_current_user)
):
    return db.query(models.Audio).order_by(models.Audio.created_at.desc()).all()

@router.delete("/{audio_id}")
def delete_audio(
    audio_id: str,
    db: Session = Depends(get_db),
    current_user: models.User = Depends(get_current_user)
):
    audio = db.query(models.Audio).filter(models.Audio.id == audio_id).first()
    if not audio:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Không tìm thấy bài nghe."
        )
        
    # Only the user who uploaded or admin can delete
    if audio.user_id != current_user.id and current_user.role != "admin":
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="Bạn không có quyền xóa bài nghe này."
        )
        
    # Delete from R2
    try:
        r2_client.delete_object(
            Bucket=settings.r2_bucket,
            Key=audio.r2_key
        )
    except Exception as e:
        # Log error but continue deleting from database
        pass
        
    db.delete(audio)
    db.commit()
    return {"message": "Đã xóa bài nghe thành công."}
