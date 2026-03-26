"""
backend/worker/tasks.py
──────────────────────────────────────────────────────────────────────────────
Core background task: process_document(file_id)

Pipeline:
  1. Mark job "processing" (10%)
  2. Download PDF from Supabase Storage → /tmp/{file_id}.pdf
  3. PDFParser.parse()                   (30%)
  4. SectionDetector.detect()            (50%)
  5. RuleEngine.run()                    (80%)
  6. Serialise CheckResult → Supabase    (100%, "complete")
  7. Schedule file deletion via cleanup.schedule_deletion()

On any exception → mark job "failed", clean up temp file, re-raise.
"""

from __future__ import annotations

import asyncio
import json
import logging
import os
from datetime import datetime, timezone
from pathlib import Path

from backend.api.constants import (
    STORAGE_BUCKET,
    TABLE_CHECKS,
    JobStatus,
    storage_filename,
    tmp_pdf_path,
)
from backend.api.deps import get_supabase
from backend.ocr.pdf_parser import PDFParser
from backend.ocr.section_detector import SectionDetector
from backend.rule_engine.engine import RuleEngine

logger = logging.getLogger(__name__)

# Rule engine is constructed once per worker process (checklist loaded once)
_rule_engine: RuleEngine | None = None


def _get_rule_engine() -> RuleEngine:
    """Return a cached RuleEngine instance."""
    global _rule_engine
    if _rule_engine is None:
        _rule_engine = RuleEngine()
    return _rule_engine


def _update_job(
    file_id: str,
    *,
    status: str | None = None,
    progress_percent: int | None = None,
    error_message: str | None = None,
    result_json: str | None = None,
    checked_at: str | None = None,
    total_ai_tokens_used: int | None = None,
    critical_count: int | None = None,
    major_count: int | None = None,
    minor_count: int | None = None,
) -> None:
    """
    Update the checks row for file_id.  Only non-None kwargs are included.
    Wrapped in try/except — a DB failure here must not swallow the real error.
    """
    payload: dict = {"updated_at": datetime.now(tz=timezone.utc).isoformat()}
    if status is not None:
        payload["status"] = status
    if progress_percent is not None:
        payload["progress_percent"] = progress_percent
    if error_message is not None:
        payload["error_message"] = error_message
    if result_json is not None:
        payload["result_json"] = result_json
    if checked_at is not None:
        payload["checked_at"] = checked_at
    if total_ai_tokens_used is not None:
        payload["total_ai_tokens_used"] = total_ai_tokens_used
    if critical_count is not None:
        payload["critical_count"] = critical_count
    if major_count is not None:
        payload["major_count"] = major_count
    if minor_count is not None:
        payload["minor_count"] = minor_count

    try:
        get_supabase().table(TABLE_CHECKS).update(payload).eq("id", file_id).execute()
    except Exception as exc:
        logger.warning("Failed to update checks row for file_id=%s: %s", file_id, exc)


async def process_document(file_id: str) -> None:
    """
    Full asynchronous processing pipeline for one uploaded PDF.

    Called by FastAPI BackgroundTasks after a successful /upload.
    """
    tmp_path = tmp_pdf_path(file_id)
    storage_key = storage_filename(file_id)

    logger.info("process_document START file_id=%s", file_id)

    # ── Step 1: Mark processing ────────────────────────────────
    _update_job(file_id, status=JobStatus.PROCESSING, progress_percent=10)

    try:
        # ── Step 2: Download from Supabase Storage ─────────────
        logger.info("Downloading %s from bucket %s …", storage_key, STORAGE_BUCKET)
        try:
            file_bytes: bytes = (
                get_supabase()
                .storage.from_(STORAGE_BUCKET)
                .download(storage_key)
            )
        except Exception as exc:
            raise RuntimeError(
                f"Failed to download file from storage: {exc}"
            ) from exc

        # Write to temp file
        Path(tmp_path).write_bytes(file_bytes)
        logger.info("Saved to %s (%d bytes)", tmp_path, len(file_bytes))

        # ── Step 3: OCR / text extraction ──────────────────────
        logger.info("Running PDFParser for file_id=%s …", file_id)
        parser = PDFParser(tmp_path)
        document = await parser.parse(file_id=file_id)
        _update_job(file_id, progress_percent=30)
        logger.info(
            "PDFParser done: %d pages, ocr_path=%s, confidence=%.2f",
            document.total_pages,
            document.ocr_path_used,
            document.overall_ocr_confidence,
        )

        # ── Step 4: Section detection ──────────────────────────
        logger.info("Running SectionDetector for file_id=%s …", file_id)
        detector = SectionDetector()
        detector.detect(document)
        _update_job(file_id, progress_percent=50)
        logger.info(
            "SectionDetector done: sections=%s",
            list(document.sections.keys()),
        )

        # ── Step 5: Rule engine ────────────────────────────────
        logger.info("Running RuleEngine for file_id=%s …", file_id)
        engine = _get_rule_engine()
        result = await engine.run(document)
        _update_job(file_id, progress_percent=80)
        logger.info(
            "RuleEngine done: CRITICAL=%d MAJOR=%d MINOR=%d AI_tokens=%d",
            result.critical_count,
            result.major_count,
            result.minor_count,
            result.total_ai_tokens_used,
        )

        # ── Step 6: Persist result ─────────────────────────────
        result_dict = result.to_dict()
        result_json = json.dumps(result_dict, ensure_ascii=False)
        checked_at = datetime.now(tz=timezone.utc).isoformat()

        _update_job(
            file_id,
            status=JobStatus.COMPLETE,
            progress_percent=100,
            result_json=result_json,
            checked_at=checked_at,
            total_ai_tokens_used=result.total_ai_tokens_used,
            critical_count=result.critical_count,
            major_count=result.major_count,
            minor_count=result.minor_count,
        )
        logger.info("process_document COMPLETE file_id=%s", file_id)

        # ── Step 7: Schedule file deletion ─────────────────────
        from backend.worker.cleanup import schedule_deletion  # local import avoids circular
        asyncio.ensure_future(schedule_deletion(file_id))

    except Exception as exc:
        error_msg = str(exc)
        logger.error(
            "process_document FAILED file_id=%s: %s", file_id, error_msg, exc_info=True
        )
        _update_job(
            file_id,
            status=JobStatus.FAILED,
            error_message=error_msg[:2000],  # cap at 2 000 chars for DB column
        )
        # Clean up temp file on failure
        _cleanup_tmp(tmp_path)
        raise

    # Temp file is left on disk; cleanup.schedule_deletion will remove it later.


def _cleanup_tmp(path: str) -> None:
    """Delete the temp PDF file if it exists — best effort."""
    try:
        p = Path(path)
        if p.exists():
            p.unlink()
            logger.info("Deleted temp file %s", path)
    except Exception as exc:
        logger.warning("Could not delete temp file %s: %s", path, exc)
