from pydantic import BaseModel, ConfigDict
from datetime import datetime

class AudioBase(BaseModel):
    title: str

class AudioCreate(AudioBase):
    pass

class AudioResponse(AudioBase):
    id: str
    filename: str
    url: str
    r2_key: str
    user_id: str
    created_at: datetime

    model_config = ConfigDict(from_attributes=True)
