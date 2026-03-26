"""
backend/api/routes/status.py
──────────────────────────────────────────────────────────────────────────────
GET /status/{job_id}  — poll the progress of a document check job.
"""

from __future__ import annotations

import logging

from fastapi import APIRouter, Depends, HTTPException
from supabase import Client

from backend.api.constants import TABLE_CHECKS
from backend.api.deps import supabase_dep

logger = logging.getLogger(__name__)
router = APIRouter()


@router.get("/status/{job_id}", summary="Poll the status of a check job")
async def get_status(
    job_id: str,
    supabase: Client = Depends(supabase_dep),
) -> dict:
    """
    Return the current processing status for a given job_id.

    Possible status values: queued | processing | complete | failed

    Returns:
        {
            "job_id": str,
            "status": str,
            "progress_percent": int,
            "filename": str,
            "created_at": str,
            "error_message": str | null
        }

    Raises:
        404: If the job_id does not exist in the checks table.
    """
    try:
        response = (
            supabase.table(TABLE_CHECKS)
            .select(
                "id, status, progress_percent, filename, "
                "created_at, error_message"
            )
            .eq("id", job_id)
            .maybe_single()
            .execute()
        )
    except Exception as exc:
        logger.error("Supabase query failed for job_id=%s: %s", job_id, exc)
        raise HTTPException(
            status_code=502,
            detail="Failed to retrieve job status. Please try again.",
        ) from exc

    if response.data is None:
        raise HTTPException(
            status_code=404,
            detail=f"Job '{job_id}' not found.",
        )

    row: dict = response.data
    return {
        "job_id":           row["id"],
        "status":           row["status"],
        "progress_percent": row.get("progress_percent", 0),
        "filename":         row.get("filename", ""),
        "created_at":       row.get("created_at", ""),
        "error_message":    row.get("error_message"),
    }
