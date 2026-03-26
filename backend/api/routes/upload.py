"""
backend/api/routes/upload.py
──────────────────────────────────────────────────────────────────────────────
POST /upload  — accept a PDF, validate it, store it in Supabase Storage,
create a job row in the "checks" table, and enqueue the background task.
"""

from __future__ import annotations

import logging
import os
import uuid
from datetime import datetime, timezone

from fastapi import APIRouter, BackgroundTasks, Depends, File, HTTPException, UploadFile
from supabase import Client

from backend.api.constants import (
    DEFAULT_MAX_UPLOAD_MB,
    PDF_MAGIC,
    STORAGE_BUCKET,
    TABLE_CHECKS,
    JobStatus,
    storage_filename,
)
from backend.api.deps import supabase_dep
from backend.worker.tasks import process_document

logger = logging.getLogger(__name__)
router = APIRouter()

_MAX_MB: int = int(os.getenv("MAX_UPLOAD_SIZE_MB", str(DEFAULT_MAX_UPLOAD_MB)))
_MAX_BYTES: int = _MAX_MB * 1024 * 1024


@router.post("/upload", summary="Upload a civil draft PDF for scrutiny")
async def upload_document(
    background_tasks: BackgroundTasks,
    file: UploadFile = File(..., description="PDF file to check"),
    supabase: Client = Depends(supabase_dep),
) -> dict:
    """
    Accept a multipart PDF upload, validate it, persist it to Supabase
    Storage, record a job row, and enqueue the background processing task.

    Returns:
        {"job_id": str, "status": "queued", "filename": str}
    """
    # ── Validation: content type ───────────────────────────────
    content_type = (file.content_type or "").lower()
    if "pdf" not in content_type:
        raise HTTPException(
            status_code=415,
            detail=(
                f"Only PDF files are accepted. "
                f"Received content-type: '{file.content_type}'."
            ),
        )

    # Read entire file into memory for size + magic-byte checks
    file_bytes = await file.read()

    # ── Validation: magic bytes ────────────────────────────────
    if not file_bytes[:4] == PDF_MAGIC:
        raise HTTPException(
            status_code=415,
            detail="File does not appear to be a valid PDF (bad magic bytes).",
        )

    # ── Validation: file size ──────────────────────────────────
    if len(file_bytes) > _MAX_BYTES:
        raise HTTPException(
            status_code=413,
            detail=(
                f"File size {len(file_bytes) / 1024 / 1024:.1f} MB exceeds "
                f"the maximum allowed {_MAX_MB} MB."
            ),
        )

    original_filename = file.filename or "document.pdf"
    file_id = str(uuid.uuid4())
    storage_key = storage_filename(file_id)

    # ── Upload to Supabase Storage ─────────────────────────────
    try:
        supabase.storage.from_(STORAGE_BUCKET).upload(
            path=storage_key,
            file=file_bytes,
            file_options={"content-type": "application/pdf"},
        )
        logger.info(
            "Uploaded file to storage: bucket=%s key=%s size=%d bytes",
            STORAGE_BUCKET,
            storage_key,
            len(file_bytes),
        )
    except Exception as exc:
        logger.error("Supabase Storage upload failed for file_id=%s: %s", file_id, exc)
        raise HTTPException(
            status_code=502,
            detail="Failed to upload file to storage. Please try again.",
        ) from exc

    # ── Insert job row into "checks" table ─────────────────────
    now_iso = datetime.now(tz=timezone.utc).isoformat()
    row = {
        "id": file_id,
        "user_id": "anonymous",   # replace with JWT sub when auth is added
        "filename": original_filename,
        "status": JobStatus.QUEUED,
        "progress_percent": 0,
        "created_at": now_iso,
        "updated_at": now_iso,
    }

    try:
        supabase.table(TABLE_CHECKS).insert(row).execute()
        logger.info("Created checks row for file_id=%s", file_id)
    except Exception as exc:
        logger.error("Supabase insert failed for file_id=%s: %s", file_id, exc)
        # Best-effort: try to delete the uploaded blob
        try:
            supabase.storage.from_(STORAGE_BUCKET).remove([storage_key])
        except Exception:
            pass
        raise HTTPException(
            status_code=502,
            detail="Failed to create job record. Please try again.",
        ) from exc

    # ── Enqueue background task ────────────────────────────────
    background_tasks.add_task(process_document, file_id)
    logger.info("Enqueued process_document for file_id=%s", file_id)

    return {
        "job_id": file_id,
        "status": JobStatus.QUEUED,
        "filename": original_filename,
    }
