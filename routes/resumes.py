import hashlib
from uuid import UUID, uuid4

from fastapi import APIRouter, HTTPException, UploadFile, File, Form

from schemas.resume import (
    ResumeUpdate,
    ResumeUploadResponse,
    SyncResponse,
)
from services.supabase_client import get_supabase
from services.resume_service import get_all_resumes_for_sync

router = APIRouter(prefix="/resumes", tags=["resumes"])
TABLE = "resumes"
BUCKET = "resumes"
ALLOWED_TYPES = {
    "application/pdf",
    "application/msword",
    "application/vnd.openxmlformats-officedocument.wordprocessingml.document",
}
MAX_SIZE = 10 * 1024 * 1024  # 10 MB


# ── Sync endpoint ────────────────────────────────────────
@router.get("/", response_model=SyncResponse)
async def list_resumes():
    return get_all_resumes_for_sync()


# ── Upload endpoint ──────────────────────────────────────
@router.post("/upload", response_model=ResumeUploadResponse, status_code=201)
async def upload_resume(
    file: UploadFile = File(...),
    title: str = Form(...),
):
    if file.content_type not in ALLOWED_TYPES:
        raise HTTPException(
            status_code=400,
            detail=f"Unsupported file type: {file.content_type}. "
                   f"Allowed: PDF, DOC, DOCX",
        )

    content = await file.read()
    if len(content) > MAX_SIZE:
        raise HTTPException(status_code=400, detail="File exceeds 10 MB limit")

    checksum = hashlib.sha256(content).hexdigest()

    resume_id = uuid4()
    storage_path = f"{resume_id}/{file.filename}"

    sb = get_supabase()
    try:
        sb.storage.from_(BUCKET).upload(
            path=storage_path,
            file=content,
            file_options={"content-type": file.content_type},
        )
    except Exception as e:
        raise HTTPException(status_code=502, detail=f"Storage upload failed: {e}")

    row = {
        "id": str(resume_id),
        "title": title,
        "filename": file.filename,
        "storage_path": storage_path,
        "checksum_sha256": checksum,
        "content_type": file.content_type,
        "size_bytes": len(content),
    }

    try:
        resp = sb.table(TABLE).insert(row).execute()
    except Exception as e:
        try:
            sb.storage.from_(BUCKET).remove([storage_path])
        except Exception:
            pass
        raise HTTPException(
            status_code=502,
            detail=f"Database insert failed (storage rolled back): {e}",
        )

    data = resp.data[0]
    return ResumeUploadResponse(
        id=data["id"],
        filename=data["filename"],
        storage_path=data["storage_path"],
        checksum_sha256=data["checksum_sha256"],
        content_type=data["content_type"],
        size_bytes=data["size_bytes"],
        created_at=data["created_at"],
    )


# ── Download (signed URL) ───────────────────────────────
@router.get("/{resume_id}")
async def get_resume(resume_id: UUID):
    sb = get_supabase()

    try:
        resp = (
            sb.table(TABLE)
            .select("id, filename, storage_path, content_type, size_bytes")
            .eq("id", str(resume_id))
            .maybe_single()
            .execute()
        )
    except Exception:
        resp = None

    if resp is None or resp.data is None:
        raise HTTPException(status_code=404, detail="Resume not found")

    storage_path = resp.data.get("storage_path")
    if not storage_path:
        raise HTTPException(status_code=404, detail="No file associated with this resume")

    try:
        signed = sb.storage.from_(BUCKET).create_signed_url(
            path=storage_path,
            expires_in=3600,
        )
    except Exception as e:
        raise HTTPException(status_code=502, detail=f"Failed to generate signed URL: {e}")

    return {
        "id": str(resume_id),
        "filename": resp.data.get("filename"),
        "content_type": resp.data.get("content_type"),
        "size_bytes": resp.data.get("size_bytes"),
        "signed_url": signed.get("signedURL") or signed.get("signedUrl"),
        "expires_in": 3600,
    }


# ── Update metadata ─────────────────────────────────────
@router.patch("/{resume_id}")
async def update_resume(resume_id: UUID, payload: ResumeUpdate):
    updates = payload.model_dump(exclude_unset=True)
    if not updates:
        raise HTTPException(status_code=400, detail="No fields to update")

    resp = (
        get_supabase()
        .table(TABLE)
        .update(updates)
        .eq("id", str(resume_id))
        .maybe_single()
        .execute()
    )
    if resp.data is None:
        raise HTTPException(status_code=404, detail="Resume not found")
    return resp.data


# ── Delete (storage + DB) ───────────────────────────────
@router.delete("/{resume_id}")
async def delete_resume(resume_id: UUID):
    sb = get_supabase()

    resp = (
        sb.table(TABLE)
        .select("id, storage_path")
        .eq("id", str(resume_id))
        .maybe_single()
        .execute()
    )
    if resp.data is None:
        raise HTTPException(status_code=404, detail="Resume not found")

    storage_path = resp.data.get("storage_path")

    if storage_path:
        try:
            sb.storage.from_(BUCKET).remove([storage_path])
        except Exception as e:
            raise HTTPException(
                status_code=502,
                detail=f"Storage deletion failed: {e}",
            )

    try:
        sb.table(TABLE).delete().eq("id", str(resume_id)).execute()
    except Exception as e:
        raise HTTPException(
            status_code=502,
            detail=f"Database deletion failed: {e}",
        )

    return {
        "status": "deleted",
        "id": str(resume_id),
        "storage_path": storage_path,
    }