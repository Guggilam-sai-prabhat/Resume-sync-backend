from datetime import datetime, timezone

from fastapi import HTTPException

from schemas.resume import ResumeFileEntry, SyncResponse
from services.supabase_client import get_supabase


def get_all_resumes_for_sync() -> SyncResponse:
    sb = get_supabase()

    try:
        resp = (
            sb.table("resumes")
            .select("id, title, filename, checksum_sha256, size_bytes, updated_at, storage_path")
            .order("updated_at", desc=True)
            .execute()
        )
    except Exception as e:
        raise HTTPException(
            status_code=500,
            detail=f"Supabase query failed: {e}",
        )

    files: dict[str, ResumeFileEntry] = {}
    for row in resp.data:
        filename = row.get("filename")
        if not filename:
            continue
        files[filename] = ResumeFileEntry(
            id=row["id"],
            title=row.get("title"),
            checksum=row["checksum_sha256"],
            size=row["size_bytes"],
            updated_at=row["updated_at"],
            storage_path=row["storage_path"],
        )

    return SyncResponse(
        sync_version=1,
        server_time=datetime.now(timezone.utc),
        total_files=len(files),
        files=files,
    )