"""
FinXtract - FastAPI Application
=======================================
AI-powered financial report extraction system.
Upload PDF → Gemini AI reads & extracts → Excel output.
"""
from __future__ import annotations

import logging
from datetime import datetime

from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware

from app.config import settings
from app.models import HealthResponse
from app.routers import jobs

# ── Logging Setup ──────────────────────────────────────────────────────────────

logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s | %(levelname)-7s | %(name)s | %(message)s",
    datefmt="%Y-%m-%d %H:%M:%S",
)
logger = logging.getLogger(__name__)

# ── Application ────────────────────────────────────────────────────────────────

app = FastAPI(
    title=settings.APP_TITLE,
    version=settings.APP_VERSION,
    description=settings.APP_DESCRIPTION,
    docs_url="/docs",
    redoc_url="/redoc",
)

# ── CORS ───────────────────────────────────────────────────────────────────────

app.add_middleware(
    CORSMiddleware,
    allow_origins=settings.ALLOWED_ORIGINS + ["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

# ── Routers ────────────────────────────────────────────────────────────────────

app.include_router(jobs.router)

# ── Health Check ───────────────────────────────────────────────────────────────

@app.get(
    "/health",
    response_model=HealthResponse,
    tags=["System"],
    summary="Health Check",
)
async def health_check():
    return HealthResponse(
        status="ok",
        timestamp=datetime.utcnow(),
        version=settings.APP_VERSION,
    )

@app.get("/", tags=["System"], include_in_schema=False)
async def root():
    return {
        "message": "FinXtract API",
        "docs": "/docs",
        "health": "/health",
    }

# ── Startup Event ──────────────────────────────────────────────────────────────

@app.on_event("startup")
async def startup_event():
    logger.info(f"🚀 {settings.APP_TITLE} v{settings.APP_VERSION} started")
    logger.info(f"📂 Output dir: {settings.OUTPUT_DIR}")
