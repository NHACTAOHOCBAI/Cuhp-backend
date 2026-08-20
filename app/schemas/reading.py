from pydantic import BaseModel, ConfigDict, Field
from typing import Optional, List, Generic, TypeVar
from datetime import datetime

class ReadingCommentUser(BaseModel):
    id: str
    name: str
    initials: str
    role: str

    model_config = ConfigDict(from_attributes=True)


class ReadingCommentBase(BaseModel):
    content: str = Field(..., min_length=1, description="Nội dung bình luận")
    selected_text: Optional[str] = Field(None, description="Từ bôi đen được bình luận")


class ReadingCommentCreate(ReadingCommentBase):
    pass


class ReadingCommentUpdate(BaseModel):
    content: str = Field(..., min_length=1, description="Nội dung bình luận")


class ReadingCommentResponse(ReadingCommentBase):
    id: str
    passage_id: str
    user_id: str
    created_at: datetime
    user: ReadingCommentUser

    model_config = ConfigDict(from_attributes=True)


class TranslationPracticeBase(BaseModel):
    translation_content: str = Field(..., min_length=1, description="Nội dung bản dịch")


class TranslationPracticeCreate(TranslationPracticeBase):
    pass


class TranslationPracticeResponse(TranslationPracticeBase):
    id: str
    passage_id: str
    user_id: str
    created_at: datetime
    updated_at: datetime

    model_config = ConfigDict(from_attributes=True)


class ReadingPassageBase(BaseModel):
    title: str = Field(..., min_length=1, max_length=200, description="Tiêu đề bài đọc")
    content: str = Field(..., min_length=1, description="Nội dung bài đọc gốc")
    level: Optional[str] = Field(None, max_length=32, description="Cấp độ bài đọc")
    category: Optional[str] = Field(None, max_length=64, description="Danh mục bài đọc")


class ReadingPassageCreate(ReadingPassageBase):
    pass


class ReadingPassageUpdate(BaseModel):
    title: Optional[str] = Field(None, min_length=1, max_length=200)
    content: Optional[str] = Field(None, min_length=1)
    level: Optional[str] = Field(None, max_length=32)
    category: Optional[str] = Field(None, max_length=64)


class ReadingPassageListItem(BaseModel):
    id: str
    title: str
    content: str = Field("", description="Trích đoạn nội dung để hiển thị preview")
    level: Optional[str] = None
    category: Optional[str] = None
    user_id: str
    created_at: datetime

    model_config = ConfigDict(from_attributes=True)


class ReadingPassageResponse(ReadingPassageBase):
    id: str
    user_id: str
    created_at: datetime

    model_config = ConfigDict(from_attributes=True)


T = TypeVar("T")


class ReadingPassageListResponse(BaseModel, Generic[T]):
    items: List[T]
    total: int
    page: int
    page_size: int
