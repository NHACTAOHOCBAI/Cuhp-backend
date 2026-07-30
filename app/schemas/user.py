from pydantic import BaseModel, ConfigDict
from datetime import datetime
from typing import Optional

class UserBase(BaseModel):
    username: str
    name: str
    role: str = "user"  # "admin" or "user"
    status: str = "offline"

class UserRegister(BaseModel):
    username: str
    password: str
    name: str
    role: str = "user"  # "admin" or "user"

class UserLogin(BaseModel):
    username: str
    password: str

class UserResponse(UserBase):
    id: str
    initials: str
    created_at: datetime

    model_config = ConfigDict(from_attributes=True)

class TokenResponse(BaseModel):
    token: str
    expires_at: datetime
    user: UserResponse

    model_config = ConfigDict(from_attributes=True)

class RoleUpdate(BaseModel):
    role: str
