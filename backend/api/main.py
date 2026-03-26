"""
backend/api/main.py
──────────────────────────────────────────────────────────────────────────────
FastAPI application entry point.

Start the server with:
  uvicorn backend.api.main:app --reload --port 8000

(run from the scrutinyai/ project root so package imports resolve)
"""

from __future__ import annotations

import logging
import os

from dotenv import load_dotenv

# Load .env before any os.getenv() call fires
load_dotenv()

from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware

from backend.api.deps import get_supabase
from backend.api.routes import feedback, report, status, upload

# ── Logging ───────────────────────────────────────────────────
logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s  %(levelname)-8s  %(name)s  %(message)s",
)
logger = logging.getLogger(__name__)

# ── Max upload size (read once at startup) ────────────────────
MAX_UPLOAD_SIZE_MB: int = int(os.getenv("MAX_UPLOAD_SIZE_MB", "20"))

# ── CORS origins ──────────────────────────────────────────────
_NEXT_PUBLIC_API_URL = os.getenv("NEXT_PUBLIC_API_URL", "")
_ALLOWED_ORIGINS: list[str] = list(
    filter(
        None,
        [
            "http://localhost:3000",
            "https://localhost:3000",
            _NEXT_PUBLIC_API_URL,
        ],
    )
)

# ── App ───────────────────────────────────────────────────────
app = FastAPI(
    title="ScrutinyAI API",
    description=(
        "AI-powered pre-filing document checker for civil drafts "
        "at the Karnataka High Court."
    ),
    version="1.0.0",
    docs_url="/docs",
    redoc_url="/redoc",
)

app.add_middleware(
    CORSMiddleware,
    allow_origins=_ALLOWED_ORIGINS,
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

# ── Startup ───────────────────────────────────────────────────

@app.on_event("startup")
async def startup_event() -> None:
    """
    Verify Supabase connectivity on startup.
    If the client cannot be constructed (missing env vars),
    the exception propagates and the server refuses to start.
    """
    logger.info("ScrutinyAI API starting up …")
    logger.info("Max upload size: %d MB", MAX_UPLOAD_SIZE_MB)
    logger.info("Allowed CORS origins: %s", _ALLOWED_ORIGINS)
    try:
        get_supabase()  # warm the lru_cache and validate credentials
        logger.info("Supabase connection established.")
    except RuntimeError as exc:
        logger.error("STARTUP FAILED — Supabase not configured: %s", exc)
        raise


# ── Routers ───────────────────────────────────────────────────

app.include_router(upload.router,   tags=["upload"])
app.include_router(status.router,   tags=["status"])
app.include_router(report.router,   tags=["report"])
app.include_router(feedback.router, tags=["feedback"])


# ── Health check ──────────────────────────────────────────────

@app.get("/health", summary="Health check")
async def health() -> dict:
    """
    Returns {"status": "ok"} when the server is running.
    Used by Render health checks and the frontend polling loop.
    """
    return {"status": "ok"}
