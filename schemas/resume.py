from pydantic import BaseModel, Field
from datetime import datetime
from uuid import UUID


# ── Sync response models ─────────────────────────────────
class ResumeFileEntry(BaseModel):
    id: UUID
    title: str | None = None
    checksum: str
    size: int
    updated_at: datetime
    storage_path: str
    filename: str | None = None


class SyncResponse(BaseModel):
    sync_version: int = 1
    server_time: datetime
    total_files: int
    files: dict[str, ResumeFileEntry]


# ── Upload response ──────────────────────────────────────
class ResumeUploadResponse(BaseModel):
    id: UUID
    filename: str
    storage_path: str
    checksum_sha256: str
    content_type: str
    size_bytes: int
    created_at: datetime


# ── Update model ─────────────────────────────────────────
class ResumeUpdate(BaseModel):
    title: str | None = Field(None, min_length=1, max_length=200)
    full_name: str | None = Field(None, min_length=1, max_length=100)
    email: str | None = None
    phone: str | None = None
    summary: str | None = None
    experience: list[dict] | None = None
    education: list[dict] | None = None
    skills: list[str] | None = None