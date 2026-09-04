import hashlib
from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy.orm import Session
import uuid
from datetime import datetime, timedelta

from app import models
from app.schemas.user import UserRegister, UserLogin, TokenResponse, UserResponse, RefreshTokenRequest
from app.core.database import get_db
from app.api.deps import get_current_user

router = APIRouter()

def get_password_hash(password: str) -> str:
    salt = "chat_pepper_123"
    return hashlib.sha256((password + salt).encode("utf-8")).hexdigest()

def verify_password(plain_password: str, hashed_password: str) -> bool:
    return get_password_hash(plain_password) == hashed_password

def generate_initials(name: str) -> str:
    parts = name.strip().split()
    if not parts:
        return "UN"
    if len(parts) == 1:
        return parts[0][:2].upper()
    return (parts[0][0] + parts[-1][0]).upper()

@router.post("/register", response_model=UserResponse)
def register(user_in: UserRegister, db: Session = Depends(get_db)):
    # Check if username exists
    existing = db.query(models.User).filter(models.User.username == user_in.username).first()
    if existing:
        raise HTTPException(
            status_code=400,
            detail="Tên đăng nhập đã tồn tại."
        )
    
    # Validate role - only 'admin' is supported now
    role = "admin"
        
    user_id = f"usr-{uuid.uuid4().hex[:8]}"
    initials = generate_initials(user_in.name)
    hashed_pwd = get_password_hash(user_in.password)
    
    db_user = models.User(
        id=user_id,
        username=user_in.username,
        hashed_password=hashed_pwd,
        name=user_in.name,
        initials=initials,
        role=role,
        status="offline"
    )
    db.add(db_user)
        
    db.commit()
    db.refresh(db_user)
    return db_user

@router.post("/login", response_model=TokenResponse)
def login(login_in: UserLogin, db: Session = Depends(get_db)):
    from loguru import logger
    logger.info(f"Received login request for user: {login_in.username}")
    user = db.query(models.User).filter(models.User.username == login_in.username).first()
    if not user:
        logger.warning(f"Login failed: User {login_in.username} not found in database.")
        raise HTTPException(
            status_code=400,
            detail="Tên đăng nhập hoặc mật khẩu không chính xác."
        )
        
    if not verify_password(login_in.password, user.hashed_password):
        logger.warning(f"Login failed: Incorrect password for user {login_in.username}.")
        raise HTTPException(
            status_code=400,
            detail="Tên đăng nhập hoặc mật khẩu không chính xác."
        )
        
    # Set status to online
    user.status = "online"
    logger.info(f"User {login_in.username} authenticated successfully. Generating tokens...")
    
    # Create session tokens
    token_str = f"tok-{uuid.uuid4().hex}"
    refresh_token_str = f"ref-{uuid.uuid4().hex}"
    expires_at = datetime.utcnow() + timedelta(days=7)
    refresh_expires_at = datetime.utcnow() + timedelta(days=30)
    
    db_token = models.Token(
        token=token_str,
        refresh_token=refresh_token_str,
        user_id=user.id,
        expires_at=expires_at,
        refresh_expires_at=refresh_expires_at
    )
    db.add(db_token)
    db.commit()
    db.refresh(user)
    
    logger.info(f"Tokens generated successfully for user {login_in.username}.")
    return {
        "token": token_str,
        "refresh_token": refresh_token_str,
        "expires_at": expires_at,
        "refresh_expires_at": refresh_expires_at,
        "user": user
    }

@router.post("/refresh", response_model=TokenResponse)
def refresh_token(body: RefreshTokenRequest, db: Session = Depends(get_db)):
    db_token = db.query(models.Token).filter(models.Token.refresh_token == body.refresh_token).first()
    if not db_token:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Refresh token không tồn tại hoặc đã bị thu hồi. Vui lòng đăng nhập lại."
        )
    
    if db_token.refresh_expires_at and db_token.refresh_expires_at < datetime.utcnow():
        db.delete(db_token)
        db.commit()
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Refresh token đã hết hạn. Vui lòng đăng nhập lại."
        )
    
    user = db.query(models.User).filter(models.User.id == db_token.user_id).first()
    if not user:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Người dùng không tồn tại."
        )
    
    # Issue a new access token while retaining or renewing the refresh token
    new_access_token = f"tok-{uuid.uuid4().hex}"
    db_token.token = new_access_token
    db_token.expires_at = datetime.utcnow() + timedelta(days=7)
    
    db.commit()
    db.refresh(db_token)
    db.refresh(user)
    
    return {
        "token": db_token.token,
        "refresh_token": db_token.refresh_token,
        "expires_at": db_token.expires_at,
        "refresh_expires_at": db_token.refresh_expires_at,
        "user": user
    }

@router.post("/logout")
def logout(current_user: models.User = Depends(get_current_user), db: Session = Depends(get_db)):
    # Set status to offline
    current_user.status = "offline"
    
    # Delete token
    db.query(models.Token).filter(models.Token.user_id == current_user.id).delete()
    db.commit()
    return {"message": "Đăng xuất thành công."}
