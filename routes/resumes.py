import hashlib
from uuid import UUID, uuid4

from fastapi import APIRouter, HTTPException, UploadFile, File, Form


from schemas.resume import (
    ResumeListItem,
    ResumeUpdate,
    ResumeResponse,
    ResumeUploadResponse,
)
from services.supabase_client import get_supabase

router = APIRouter(prefix="/resumes", tags=["resumes"])
TABLE = "resumes"
BUCKET = "resumes"
ALLOWED_TYPES = {
    "application/pdf",
    "application/msword",
    "application/vnd.openxmlformats-officedocument.wordprocessingml.document",
}
MAX_SIZE = 10 * 1024 * 1024  # 10 MB


# ── Upload endpoint ──────────────────────────────────────
@router.post("/upload", response_model=ResumeUploadResponse, status_code=201)
async def upload_resume(
    file: UploadFile = File(...),
    title: str = Form(...),
    full_name: str = Form(...),
    email: str = Form(...),
):
    # 1. Validate content type
    if file.content_type not in ALLOWED_TYPES:
        raise HTTPException(
            status_code=400,
            detail=f"Unsupported file type: {file.content_type}. "
                   f"Allowed: PDF, DOC, DOCX",
        )

    # 2. Read file and enforce size limit
    content = await file.read()
    if len(content) > MAX_SIZE:
        raise HTTPException(status_code=400, detail="File exceeds 10 MB limit")

    # 3. Calculate SHA256 checksum
    checksum = hashlib.sha256(content).hexdigest()

    # 4. Build a unique storage path
    resume_id = uuid4()
    storage_path = f"{resume_id}/{file.filename}"

    # 5. Upload to Supabase Storage
    sb = get_supabase()
    try:
        sb.storage.from_(BUCKET).upload(
            path=storage_path,
            file=content,
            file_options={"content-type": file.content_type},
        )
    except Exception as e:
        raise HTTPException(status_code=502, detail=f"Storage upload failed: {e}")

    # 6. Insert metadata into Postgres
    row = {
        "id": str(resume_id),
        "title": title,
        "full_name": full_name,
        "email": email,
        "filename": file.filename,
        "storage_path": storage_path,
        "checksum_sha256": checksum,
        "content_type": file.content_type,
        "size_bytes": len(content),
    }

    try:
        resp = sb.table(TABLE).insert(row).execute()
    except Exception as e:
        # 7. Rollback: delete the uploaded file if DB insert fails
        try:
            sb.storage.from_(BUCKET).remove([storage_path])
        except Exception:
            pass  # best-effort cleanup
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


# ── CRUD endpoints ───────────────────────────────────────
@router.get("/", response_model=list[ResumeListItem])
async def list_resumes(limit: int = 50, offset: int = 0):
    resp = (
        get_supabase()
        .table(TABLE)
        .select("id, filename, checksum_sha256, size_bytes, updated_at")
        .order("updated_at", desc=True)
        .range(offset, offset + limit - 1)
        .execute()
    )
    return resp.data


@router.get("/{resume_id}")
async def get_resume(resume_id: UUID):
    sb = get_supabase()

    # 1. Fetch storage_path and metadata from DB
    resp = (
        sb.table(TABLE)
        .select("id, filename, storage_path, content_type, size_bytes")
        .eq("id", str(resume_id))
        .maybe_single()
        .execute()
    )
    if resp.data is None:
        raise HTTPException(status_code=404, detail="Resume not found")

    storage_path = resp.data.get("storage_path")
    if not storage_path:
        raise HTTPException(status_code=404, detail="No file associated with this resume")

    # 2. Generate signed URL (valid for 1 hour)
    try:
        signed = sb.storage.from_(BUCKET).create_signed_url(
            path=storage_path,
            expires_in=3600,
        )
    except Exception as e:
        raise HTTPException(status_code=502, detail=f"Failed to generate signed URL: {e}")

    # 3. Return signed URL with metadata
    return {
        "id": str(resume_id),
        "filename": resp.data.get("filename"),
        "content_type": resp.data.get("content_type"),
        "size_bytes": resp.data.get("size_bytes"),
        "signed_url": signed.get("signedURL") or signed.get("signedUrl"),
        "expires_in": 3600,
    }


@router.patch("/{resume_id}", response_model=ResumeResponse)
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


@router.delete("/{resume_id}")
async def delete_resume(resume_id: UUID):
    sb = get_supabase()

    # 1. Fetch storage_path from DB
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

    # 2. Delete file from Supabase Storage
    if storage_path:
        try:
            sb.storage.from_(BUCKET).remove([storage_path])
        except Exception as e:
            raise HTTPException(
                status_code=502,
                detail=f"Storage deletion failed: {e}",
            )

    # 3. Delete metadata row from DB
    try:
        sb.table(TABLE).delete().eq("id", str(resume_id)).execute()
    except Exception as e:
        raise HTTPException(
            status_code=502,
            detail=f"Database deletion failed: {e}",
        )

    # 4. Return success
    return {
        "status": "deleted",
        "id": str(resume_id),
        "storage_path": storage_path,
    }