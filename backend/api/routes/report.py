"""
backend/api/routes/report.py
──────────────────────────────────────────────────────────────────────────────
GET /report/{job_id}  — retrieve the completed CheckResult for a job.

Objections are returned sorted:
  1. CRITICAL before MAJOR before MINOR
  2. Within each severity: definite errors (requires_manual_verification=False) first
"""

from __future__ import annotations

import json
import logging

from fastapi import APIRouter, Depends, HTTPException
from supabase import Client

from backend.api.constants import TABLE_CHECKS, JobStatus
from backend.api.deps import supabase_dep

logger = logging.getLogger(__name__)
router = APIRouter()

_SEVERITY_ORDER = {"CRITICAL": 0, "MAJOR": 1, "MINOR": 2}


def _sort_objections(objections: list[dict]) -> list[dict]:
    """
    Sort objections list:
      Primary key:   severity (CRITICAL < MAJOR < MINOR)
      Secondary key: requires_manual_verification (False first)
    """
    return sorted(
        objections,
        key=lambda o: (
            _SEVERITY_ORDER.get(o.get("severity", "MINOR"), 99),
            int(o.get("requires_manual_verification", False)),
        ),
    )


@router.get("/report/{job_id}", summary="Retrieve the completed scrutiny report")
async def get_report(
    job_id: str,
    supabase: Client = Depends(supabase_dep),
) -> dict:
    """
    Return the full CheckResult JSON for a completed job.

    Raises:
        404: If the job_id does not exist.
        400: If the job has not completed yet (status != 'complete').
        502: On Supabase query failure.
    """
    try:
        response = (
            supabase.table(TABLE_CHECKS)
            .select(
                "id, status, filename, result_json, checked_at, "
                "total_ai_tokens_used, critical_count, major_count, minor_count"
            )
            .eq("id", job_id)
            .maybe_single()
            .execute()
        )
    except Exception as exc:
        logger.error("Supabase query failed for report job_id=%s: %s", job_id, exc)
        raise HTTPException(
            status_code=502,
            detail="Failed to retrieve report. Please try again.",
        ) from exc

    if response.data is None:
        raise HTTPException(
            status_code=404,
            detail=f"Job '{job_id}' not found.",
        )

    row: dict = response.data

    if row["status"] != JobStatus.COMPLETE:
        raise HTTPException(
            status_code=400,
            detail=(
                f"Report is not ready yet. Current status: '{row['status']}'. "
                "Poll /status/{job_id} until status is 'complete'."
            ),
        )

    # Deserialise the stored JSON result
    result_json_str: str = row.get("result_json") or "{}"
    try:
        result: dict = json.loads(result_json_str)
    except json.JSONDecodeError as exc:
        logger.error(
            "Corrupt result_json for job_id=%s: %s", job_id, exc
        )
        raise HTTPException(
            status_code=500,
            detail="Report data is corrupt. Please re-submit the document.",
        ) from exc

    # Pull objections from the stored result and re-sort them
    objections: list[dict] = result.get("objections", [])
    sorted_objections = _sort_objections(objections)

    return {
        "job_id":               job_id,
        "filename":             row.get("filename", ""),
        "checked_at":           row.get("checked_at", ""),
        "checklist_version":    result.get("checklist_version", ""),
        "total_ai_tokens_used": row.get("total_ai_tokens_used", 0),
        "critical_count":       row.get("critical_count", 0),
        "major_count":          row.get("major_count", 0),
        "minor_count":          row.get("minor_count", 0),
        "objections":           sorted_objections,
    }
