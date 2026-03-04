from pydantic import BaseModel, Field
from datetime import datetime
from uuid import UUID


class ResumeBase(BaseModel):
    title: str = Field(..., min_length=1, max_length=200)
    full_name: str = Field(..., min_length=1, max_length=100)
    email: str
    phone: str | None = None
    summary: str | None = None
    experience: list[dict] = Field(default_factory=list)
    education: list[dict] = Field(default_factory=list)
    skills: list[str] = Field(default_factory=list)


class ResumeCreate(ResumeBase):
    pass


class ResumeUpdate(BaseModel):
    title: str | None = Field(None, min_length=1, max_length=200)
    full_name: str | None = Field(None, min_length=1, max_length=100)
    email: str | None = None
    phone: str | None = None
    summary: str | None = None
    experience: list[dict] | None = None
    education: list[dict] | None = None
    skills: list[str] | None = None


class ResumeResponse(ResumeBase):
    id: UUID
    created_at: datetime
    updated_at: datetime

    model_config = {"from_attributes": True}


class ResumeListItem(BaseModel):
    id: UUID
    filename: str | None = None
    checksum_sha256: str | None = None
    size_bytes: int | None = None
    updated_at: datetime


class ResumeUploadResponse(BaseModel):
    id: UUID
    filename: str
    storage_path: str
    checksum_sha256: str
    content_type: str
    size_bytes: int
    created_at: datetime