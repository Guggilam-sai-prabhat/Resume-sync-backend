from datetime import datetime, timezone

from fastapi import HTTPException

from schemas.resume import ResumeFileEntry, SyncResponse
from services.supabase_client import get_supabase


def get_all_resumes_for_sync() -> SyncResponse:
    sb = get_supabase()

    try:
        resp = (
            sb.table("resumes")
            .select("id, title, filename, checksum_sha256, size_bytes, updated_at, storage_path", count="exact")
            .order("updated_at", desc=True)
            .limit(1000)
            .execute()
        )
    except Exception as e:
        raise HTTPException(
            status_code=500,
            detail=f"Supabase query failed: {e}",
        )

    print(f"[SYNC] Total rows returned: {len(resp.data)}, count: {resp.count}")

    files: dict[str, ResumeFileEntry] = {}
    for row in resp.data:
        title = row.get("title")
        if not title:
            continue
        # Use title as key; skip duplicates (keep latest since sorted by updated_at desc)
        if title in files:
            continue
        files[title] = ResumeFileEntry(
            id=row["id"],
            title=title,
            checksum=row["checksum_sha256"],
            size=row["size_bytes"],
            updated_at=row["updated_at"],
            storage_path=row["storage_path"],
            filename=row.get("filename"),
        )

    return SyncResponse(
        sync_version=1,
        server_time=datetime.now(timezone.utc),
        total_files=len(files),
        files=files,
    )