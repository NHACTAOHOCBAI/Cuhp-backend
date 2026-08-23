import uuid
from datetime import date, datetime, time, timedelta
from typing import List, Optional
from fastapi import APIRouter, Depends, HTTPException, Query
from sqlalchemy.orm import Session
from loguru import logger

from app import models
from app.api.deps import get_current_user
from app.core.database import get_db
from app.schemas.sleep import (
    SleepLogCreate,
    SleepLogResponse,
    SleepStatsResponse,
    SleepSettingsUpdate,
)
from app.schemas.user import UserResponse

router = APIRouter()

@router.post("", response_model=SleepLogResponse)
async def create_sleep_log(
    payload: SleepLogCreate,
    db: Session = Depends(get_db),
    current_user: models.User = Depends(get_current_user)
):
    if payload.wake_time_actual <= payload.sleep_time_actual:
        raise HTTPException(
            status_code=400,
            detail="Thời gian thức dậy phải sau thời gian đi ngủ."
        )

    # Tự động tính thời lượng ngủ bằng phút
    duration_minutes = (payload.wake_time_actual - payload.sleep_time_actual).total_seconds() / 60.0

    sleep_log = models.SleepLog(
        id=f"slp-{uuid.uuid4().hex[:12]}",
        user_id=current_user.id,
        sleep_date=payload.sleep_date,
        sleep_time_actual=payload.sleep_time_actual,
        wake_time_actual=payload.wake_time_actual,
        duration_minutes=duration_minutes,
        notes=payload.notes
    )

    db.add(sleep_log)
    db.commit()
    db.refresh(sleep_log)
    return sleep_log

@router.get("", response_model=List[SleepLogResponse])
async def get_sleep_logs(
    page: int = Query(1, ge=1),
    page_size: int = Query(20, ge=1, le=100),
    db: Session = Depends(get_db),
    current_user: models.User = Depends(get_current_user)
):
    offset = (page - 1) * page_size
    logs = db.query(models.SleepLog).filter(models.SleepLog.user_id == current_user.id).order_by(models.SleepLog.sleep_date.desc()).offset(offset).limit(page_size).all()
    return logs

@router.get("/stats", response_model=SleepStatsResponse)
async def get_sleep_stats(
    db: Session = Depends(get_db),
    current_user: models.User = Depends(get_current_user)
):
    # Lấy 7 bản ghi giấc ngủ gần nhất
    logs_7_days = (
        db.query(models.SleepLog)
        .filter(models.SleepLog.user_id == current_user.id)
        .order_by(models.SleepLog.sleep_date.desc())
        .limit(7)
        .all()
    )

    # Thống kê tổng quan dựa trên toàn bộ lịch sử (hoặc tối đa 30 bản ghi gần nhất để tránh tải quá nhiều)
    all_logs = (
        db.query(models.SleepLog)
        .filter(models.SleepLog.user_id == current_user.id)
        .order_by(models.SleepLog.sleep_date.desc())
        .limit(30)
        .all()
    )

    if not all_logs:
        return SleepStatsResponse(
            average_duration_hours=0.0,
            average_bedtime=current_user.sleep_bedtime,
            average_waketime=current_user.sleep_waketime,
            sleep_logs_7_days=[]
        )

    # Tính trung bình số giờ ngủ
    total_minutes = sum(log.duration_minutes for log in all_logs)
    avg_hours = (total_minutes / len(all_logs)) / 60.0

    # Tính giờ đi ngủ trung bình (bedtime) và giờ dậy trung bình (waketime)
    # Đưa giờ ngủ về dạng số giờ lệch so với nửa đêm (22:30 -> -1.5, 01:00 -> +1.0)
    bedtime_offsets = []
    waketime_offsets = []

    for log in all_logs:
        # Bedtime offset
        b_hour = log.sleep_time_actual.hour
        b_minute = log.sleep_time_actual.minute
        b_offset = b_hour + b_minute / 60.0
        if b_offset >= 18.0:
            b_offset -= 24.0
        bedtime_offsets.append(b_offset)

        # Waketime offset (thường từ 0h sáng tới 18h tối)
        w_hour = log.wake_time_actual.hour
        w_minute = log.wake_time_actual.minute
        w_offset = w_hour + w_minute / 60.0
        waketime_offsets.append(w_offset)

    avg_bedtime_offset = sum(bedtime_offsets) / len(bedtime_offsets)
    avg_waketime_offset = sum(waketime_offsets) / len(waketime_offsets)

    # Chuyển ngược offset về định dạng string HH:MM
    def offset_to_time_str(offset: float) -> str:
        if offset < 0:
            offset += 24.0
        hours = int(offset)
        minutes = int(round((offset - hours) * 60))
        if minutes == 60:
            hours = (hours + 1) % 24
            minutes = 0
        return f"{hours:02d}:{minutes:02d}"

    avg_bedtime_str = offset_to_time_str(avg_bedtime_offset)
    avg_waketime_str = offset_to_time_str(avg_waketime_offset)

    # Đảo thứ tự logs_7_days thành tăng dần theo ngày để vẽ biểu đồ từ trái qua phải
    logs_7_days_sorted = list(reversed(logs_7_days))

    return SleepStatsResponse(
        average_duration_hours=round(avg_hours, 1),
        average_bedtime=avg_bedtime_str,
        average_waketime=avg_waketime_str,
        sleep_logs_7_days=logs_7_days_sorted
    )

@router.put("/settings", response_model=UserResponse)
async def update_sleep_settings(
    payload: SleepSettingsUpdate,
    db: Session = Depends(get_db),
    current_user: models.User = Depends(get_current_user)
):
    current_user.sleep_bedtime = payload.sleep_bedtime
    current_user.sleep_waketime = payload.sleep_waketime
    current_user.sleep_reminder_enabled = payload.sleep_reminder_enabled
    db.commit()
    db.refresh(current_user)
    return current_user

@router.delete("/{id}")
async def delete_sleep_log(
    id: str,
    db: Session = Depends(get_db),
    current_user: models.User = Depends(get_current_user)
):
    log = (
        db.query(models.SleepLog)
        .filter(models.SleepLog.id == id, models.SleepLog.user_id == current_user.id)
        .first()
    )
    if not log:
        raise HTTPException(status_code=404, detail="Không tìm thấy bản ghi giấc ngủ này.")
    
    db.delete(log)
    db.commit()
    return {"message": "Xóa bản ghi giấc ngủ thành công."}
