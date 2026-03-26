"""
backend/api/deps.py
──────────────────────────────────────────────────────────────────────────────
Shared infrastructure objects — Supabase client and a FastAPI dependency
getter — imported by routes and the worker.

The Supabase client is constructed lazily on first call and cached for the
lifetime of the process.  All env vars are read here; nowhere else.
"""

from __future__ import annotations

import logging
import os
from functools import lru_cache

from supabase import Client, create_client

logger = logging.getLogger(__name__)


@lru_cache(maxsize=1)
def get_supabase() -> Client:
    """
    Return a cached Supabase client built from environment variables.

    Required env vars:
        SUPABASE_URL          — project URL  (e.g. https://xyzabc.supabase.co)
        SUPABASE_SERVICE_KEY  — service-role key (bypasses RLS for backend ops)

    Raises:
        RuntimeError: If SUPABASE_URL or SUPABASE_SERVICE_KEY are not set.
    """
    url = os.getenv("SUPABASE_URL", "")
    key = os.getenv("SUPABASE_SERVICE_KEY", "")

    if not url or not key:
        raise RuntimeError(
            "SUPABASE_URL and SUPABASE_SERVICE_KEY must be set in the environment. "
            "Copy .env.example to .env and fill in your Supabase credentials."
        )

    client: Client = create_client(url, key)
    logger.info("Supabase client initialised (project: %s)", url)
    return client


# FastAPI dependency — routes use `Depends(supabase_dep)` to receive the client
def supabase_dep() -> Client:
    """FastAPI dependency that returns the shared Supabase client."""
    return get_supabase()
