"""
backend/worker/cleanup.py
──────────────────────────────────────────────────────────────────────────────
File purge scheduler.  Called after process_document completes.

schedule_deletion(file_id):
  1. Sleep FILE_PURGE_HOURS * 3600 seconds.
  2. Delete /tmp/{file_id}.pdf from the local filesystem.
  3. Delete {file_id}.pdf from Supabase Storage bucket "draft-uploads".
  4. Log both deletions.

FILE_PURGE_HOURS is read from the environment (default 24).
"""

from __future__ import annotations

import asyncio
import logging
import os
from pathlib import Path

from backend.api.constants import (
    DEFAULT_FILE_PURGE_HOURS,
    STORAGE_BUCKET,
    storage_filename,
    tmp_pdf_path,
)
from backend.api.deps import get_supabase

logger = logging.getLogger(__name__)

_PURGE_HOURS: int = int(os.getenv("FILE_PURGE_HOURS", str(DEFAULT_FILE_PURGE_HOURS)))


async def schedule_deletion(file_id: str) -> None:
    """
    Wait FILE_PURGE_HOURS and then delete all traces of the uploaded PDF.

    This coroutine is fire-and-forget via asyncio.ensure_future().
    Failures are logged but do not propagate — a failed cleanup does not
    affect the client-visible job status.
    """
    purge_seconds = _PURGE_HOURS * 3600
    logger.info(
        "Scheduled deletion of file_id=%s in %d hours (%d seconds).",
        file_id,
        _PURGE_HOURS,
        purge_seconds,
    )

    await asyncio.sleep(purge_seconds)

    # ── Delete local temp file ─────────────────────────────────
    local_path = tmp_pdf_path(file_id)
    _delete_local(file_id, local_path)

    # ── Delete from Supabase Storage ───────────────────────────
    await _delete_from_storage(file_id)

    logger.info("Purge complete for file_id=%s.", file_id)


def _delete_local(file_id: str, path: str) -> None:
    """Remove the temp PDF from the local filesystem."""
    try:
        p = Path(path)
        if p.exists():
            p.unlink()
            logger.info(
                "Deleted local temp file: %s (file_id=%s)", path, file_id
            )
        else:
            logger.debug(
                "Local temp file already absent: %s (file_id=%s)", path, file_id
            )
    except Exception as exc:
        logger.warning(
            "Could not delete local temp file %s (file_id=%s): %s",
            path,
            file_id,
            exc,
        )


async def _delete_from_storage(file_id: str) -> None:
    """Remove the PDF object from Supabase Storage."""
    storage_key = storage_filename(file_id)
    try:
        get_supabase().storage.from_(STORAGE_BUCKET).remove([storage_key])
        logger.info(
            "Deleted from Supabase Storage: bucket=%s key=%s (file_id=%s)",
            STORAGE_BUCKET,
            storage_key,
            file_id,
        )
    except Exception as exc:
        logger.warning(
            "Could not delete %s from Supabase Storage (file_id=%s): %s",
            storage_key,
            file_id,
            exc,
        )
