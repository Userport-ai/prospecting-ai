from pydantic import BaseModel
from datetime import datetime
from utils.loguru_setup import logger


class UserportPydanticBaseModel(BaseModel):
    class Config:
        json_encoders = {
            datetime: lambda v: v.isoformat(),
        }
