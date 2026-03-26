"""
backend/api/routes/feedback.py
──────────────────────────────────────────────────────────────────────────────
POST /feedback/{objection_id}
Record whether an advocate considered an objection correct or not.
"""

from __future__ import annotations

import logging
from datetime import datetime, timezone

from fastapi import APIRouter, Depends, HTTPException
from pydantic import BaseModel, Field
from supabase import Client

from backend.api.constants import TABLE_FEEDBACK
from backend.api.deps import supabase_dep

logger = logging.getLogger(__name__)
router = APIRouter()


class FeedbackBody(BaseModel):
    """Request body for the feedback endpoint."""

    is_correct: bool = Field(
        ..., description="True if the objection was valid; False if it was wrong."
    )
    job_id: str = Field(
        ..., description="The job_id (file_id) that produced this objection."
    )


@router.post(
    "/feedback/{objection_id}",
    summary="Record advocate feedback on an objection",
)
async def record_feedback(
    objection_id: str,
    body: FeedbackBody,
    supabase: Client = Depends(supabase_dep),
) -> dict:
    """
    Upsert a feedback row in the objection_feedback table.

    If feedback for this (objection_id, job_id) pair already exists,
    it is overwritten (last write wins).

    Returns:
        {"status": "recorded"}
    """
    now_iso = datetime.now(tz=timezone.utc).isoformat()

    row = {
        "objection_id": objection_id,
        "job_id":       body.job_id,
        "is_correct":   body.is_correct,
        "created_at":   now_iso,
    }

    try:
        (
            supabase.table(TABLE_FEEDBACK)
            .upsert(row, on_conflict="objection_id,job_id")
            .execute()
        )
        logger.info(
            "Feedback recorded: objection_id=%s job_id=%s is_correct=%s",
            objection_id,
            body.job_id,
            body.is_correct,
        )
    except Exception as exc:
        logger.error(
            "Supabase upsert failed for feedback objection_id=%s: %s",
            objection_id,
            exc,
        )
        raise HTTPException(
            status_code=502,
            detail="Failed to record feedback. Please try again.",
        ) from exc

    return {"status": "recorded"}
