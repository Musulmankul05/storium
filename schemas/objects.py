import re
from datetime import datetime

from pydantic import BaseModel, Field, field_validator


class ObjectResponseSchema(BaseModel):
    id: int
    key: str
    etag: str
    bucket_id: int


class BucketNameSchema(BaseModel):
    name: str = Field(..., min_length=3, max_length=32)

    @field_validator("name")
    @classmethod
    def check_name(cls, v: str):
        if not re.match(r"^[a-z][a-z0-9_]*$", v):
            raise ValueError(
                "name can only starts with lowercase letter and contain numbers and underscores"
            )
        return v


class BucketSchema(BaseModel):
    id: int
    name: str
    created_at: datetime
