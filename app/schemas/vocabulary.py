from pydantic import BaseModel, ConfigDict, Field
from typing import Optional, List, Generic, TypeVar
from datetime import datetime

class VocabularyBase(BaseModel):
    word: str = Field(..., min_length=1, max_length=100, description="Từ vựng")
    pronunciation: Optional[str] = Field(None, max_length=100, description="Phiên âm")
    meaning: str = Field(..., min_length=1, max_length=500, description="Nghĩa của từ")
    word_type: Optional[str] = Field(None, max_length=64, description="Loại từ (ví dụ: Noun, Verb, Adjective...)")
    notes: Optional[str] = Field(None, max_length=2000, description="Ghi chú thêm")

class VocabularyCreate(VocabularyBase):
    pass

class VocabularyUpdate(BaseModel):
    word: Optional[str] = Field(None, min_length=1, max_length=100)
    pronunciation: Optional[str] = Field(None, max_length=100)
    meaning: Optional[str] = Field(None, min_length=1, max_length=500)
    word_type: Optional[str] = Field(None, max_length=64)
    notes: Optional[str] = Field(None, max_length=2000)

class VocabularyResponse(VocabularyBase):
    id: str
    user_id: str
    box_number: int
    next_review_at: datetime
    created_at: datetime
    updated_at: datetime

    model_config = ConfigDict(from_attributes=True)

class VocabularyReviewRequest(BaseModel):
    known: bool

class VocabularyReviewResponse(BaseModel):
    vocabulary: VocabularyResponse
    daily_target: int
    current_streak: int
    words_reviewed_today: int
    streak_incremented_today: bool

T = TypeVar("T")

class VocabularyListResponse(BaseModel, Generic[T]):
    items: List[T]
    total: int
    page: int
    page_size: int

class VocabularyBulkDeleteRequest(BaseModel):
    ids: List[str] = Field(..., min_length=1, max_length=200)

class VocabularyBulkDeleteResponse(BaseModel):
    deleted: int
    failed: List[str] = []
