from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy.orm import Session
from typing import List

from app import models
from app.schemas.user import UserResponse, RoleUpdate
from app.core.database import get_db
from app.api.deps import get_current_user, get_current_admin

router = APIRouter()

@router.get("/me", response_model=UserResponse)
def read_user_me(current_user: models.User = Depends(get_current_user)):
    return current_user

@router.get("", response_model=List[UserResponse])
def read_users(
    db: Session = Depends(get_db),
    current_admin: models.User = Depends(get_current_admin)
):
    return db.query(models.User).order_by(models.User.created_at.desc()).all()

@router.delete("/{user_id}")
def delete_user(
    user_id: str,
    db: Session = Depends(get_db),
    current_admin: models.User = Depends(get_current_admin)
):
    if user_id == current_admin.id:
        raise HTTPException(
            status_code=400,
            detail="Bạn không thể tự xóa tài khoản của chính mình."
        )
    user = db.query(models.User).filter(models.User.id == user_id).first()
    if not user:
        raise HTTPException(
            status_code=404,
            detail="Người dùng không tồn tại."
        )
    db.delete(user)
    db.commit()
    return {"message": "Đã xóa người dùng thành công."}

@router.put("/{user_id}/role", response_model=UserResponse)
def update_user_role(
    user_id: str,
    role_in: RoleUpdate,
    db: Session = Depends(get_db),
    current_admin: models.User = Depends(get_current_admin)
):
    if user_id == current_admin.id:
        raise HTTPException(
            status_code=400,
            detail="Bạn không thể tự thay đổi vai trò của chính mình."
        )
        
    role = role_in.role.lower()
    if role not in ["admin", "user"]:
        raise HTTPException(
            status_code=400,
            detail="Vai trò không hợp lệ. Chỉ chấp nhận 'admin' hoặc 'user'."
        )
        
    user = db.query(models.User).filter(models.User.id == user_id).first()
    if not user:
        raise HTTPException(
            status_code=404,
            detail="Người dùng không tồn tại."
        )
        
    user.role = role
    db.commit()
    db.refresh(user)
    return user
