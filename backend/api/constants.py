"""
backend/api/constants.py
──────────────────────────────────────────────────────────────────────────────
Single place for all string constants that would otherwise be scattered
across route files and the worker.  Import from here — never hardcode
bucket names, table names, or status strings anywhere else.
"""

from __future__ import annotations

# ── Supabase Storage ───────────────────────────────────────────
STORAGE_BUCKET: str = "draft-uploads"
"""Name of the Supabase Storage bucket that holds uploaded PDFs."""

# ── Supabase Database tables ───────────────────────────────────
TABLE_CHECKS: str = "checks"
"""Main job-tracking table.  One row per uploaded document."""

TABLE_FEEDBACK: str = "objection_feedback"
"""Stores advocate feedback (correct/incorrect) for each objection."""

# ── Temp file layout ───────────────────────────────────────────
TMP_DIR: str = "/tmp"
"""Directory used to store downloaded PDFs during processing."""

def tmp_pdf_path(file_id: str) -> str:
    """Return the canonical temp path for a given file_id."""
    return f"{TMP_DIR}/{file_id}.pdf"

def storage_filename(file_id: str) -> str:
    """Return the Storage object name (key) for a given file_id."""
    return f"{file_id}.pdf"

# ── Job status values ─────────────────────────────────────────
class JobStatus:
    QUEUED     = "queued"
    PROCESSING = "processing"
    COMPLETE   = "complete"
    FAILED     = "failed"

# ── PDF magic number ──────────────────────────────────────────
PDF_MAGIC: bytes = b"%PDF"
"""First 4 bytes that every valid PDF must start with."""

# ── Defaults ─────────────────────────────────────────────────
DEFAULT_MAX_UPLOAD_MB: int = 20
DEFAULT_FILE_PURGE_HOURS: int = 24
