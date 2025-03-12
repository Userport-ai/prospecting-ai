from pydantic import BaseModel
from datetime import datetime


class UserportPydanticBaseModel(BaseModel):
    class Config:
        json_encoders = {
            datetime: lambda v: v.isoformat(),
        }
