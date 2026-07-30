from fastapi import Header, HTTPException, Depends
from sqlalchemy.orm import Session
from datetime import datetime
from app.core.database import get_db
from app import models

def get_current_user(authorization: str = Header(None), db: Session = Depends(get_db)) -> models.User:
    if not authorization or not authorization.startswith("Bearer "):
        raise HTTPException(
            status_code=401,
            detail="Xác thực không hợp lệ. Vui lòng đăng nhập lại."
        )
    token_str = authorization.split(" ")[1]
    
    token_record = db.query(models.Token).filter(models.Token.token == token_str).first()
    if not token_record:
        raise HTTPException(
            status_code=401,
            detail="Phiên làm việc không tồn tại hoặc đã hết hạn."
        )
        
    if token_record.expires_at < datetime.utcnow():
        # Clean up expired token
        db.delete(token_record)
        db.commit()
        raise HTTPException(
            status_code=401,
            detail="Phiên đăng nhập đã hết hạn. Vui lòng đăng nhập lại."
        )
        
    user = db.query(models.User).filter(models.User.id == token_record.user_id).first()
    if not user:
        raise HTTPException(
            status_code=401,
            detail="Người dùng không tồn tại."
        )
        
    return user

def get_current_admin(current_user: models.User = Depends(get_current_user)) -> models.User:
    if current_user.role != "admin":
        raise HTTPException(
            status_code=403,
            detail="Bạn không có quyền thực hiện hành động này. Yêu cầu quyền Admin."
        )
    return current_user
