from pydantic import BaseModel, ConfigDict, Field
from typing import Optional, List, Generic, TypeVar
from datetime import datetime

LEVEL_CHOICES = ["beginner", "intermediate", "advanced"]

# Max length for transcript to stay safely under Starlette's 1 MiB multipart field cap
MAX_TRANSCRIPT_LENGTH = 50_000


class AudioBase(BaseModel):
    title: str = Field(..., min_length=1, max_length=200, description="Tiêu đề bài nghe")


class AudioCreate(AudioBase):
    pass


class AudioUpdate(BaseModel):
    """All fields optional — only provided fields will be updated."""
    title: Optional[str] = Field(None, min_length=1, max_length=200)
    level: Optional[str] = Field(None, max_length=32)
    category: Optional[str] = Field(None, max_length=64)
    transcript: Optional[str] = Field(None, max_length=MAX_TRANSCRIPT_LENGTH)


class AudioListItem(AudioBase):
    """Lightweight representation for list endpoints — omits transcript text."""
    id: str
    filename: str
    url: str
    user_id: str
    created_at: datetime
    level: Optional[str] = None
    category: Optional[str] = None
    has_transcript: bool = False

    model_config = ConfigDict(from_attributes=True)


class AudioResponse(AudioBase):
    """Full representation including transcript — for detail endpoint."""
    id: str
    filename: str
    url: str
    r2_key: str
    user_id: str
    created_at: datetime
    level: Optional[str] = None
    category: Optional[str] = None
    transcript: Optional[str] = None

    model_config = ConfigDict(from_attributes=True)


T = TypeVar("T")


class AudioListResponse(BaseModel, Generic[T]):
    items: List[T]
    total: int
    page: int
    page_size: int


class BulkDeleteRequest(BaseModel):
    ids: List[str] = Field(..., min_length=1, max_length=200)


class BulkDeleteResponse(BaseModel):
    deleted: int
    failed: List[str] = []


class AudioCommentUser(BaseModel):
    id: str
    name: str
    initials: str
    role: str

    model_config = ConfigDict(from_attributes=True)


class AudioCommentBase(BaseModel):
    content: str = Field(..., min_length=1, description="Nội dung bình luận")
    selected_text: Optional[str] = Field(None, description="Từ bôi đen được bình luận")


class AudioCommentCreate(AudioCommentBase):
    pass


class AudioCommentUpdate(BaseModel):
    content: str = Field(..., min_length=1, description="Nội dung bình luận")


class AudioCommentResponse(AudioCommentBase):
    id: str
    audio_id: str
    user_id: str
    created_at: datetime
    user: AudioCommentUser

    model_config = ConfigDict(from_attributes=True)