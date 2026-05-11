"""
Configuration settings for FinXtract.
"""
import os
from dotenv import load_dotenv

load_dotenv()


class Settings:
    """Application settings loaded from environment or defaults."""

    # ── AI Processing ─────────────────────────────────────────────────────────
    GEMINI_API_KEY: str = os.getenv("GEMINI_API_KEY", "")

    # ── App Metadata ──────────────────────────────────────────────────────────
    APP_TITLE: str = "FinXtract"
    APP_VERSION: str = "2.0.0"
    APP_DESCRIPTION: str = (
        "Hệ thống trích xuất Báo cáo Tài chính (BCTC) bằng AI. "
        "Upload PDF → Gemini AI đọc & trích xuất → Xuất Excel."
    )

    # ── CORS ──────────────────────────────────────────────────────────────────
    ALLOWED_ORIGINS: list[str] = os.getenv(
        "ALLOWED_ORIGINS", "http://localhost:3000,http://localhost:5500,http://127.0.0.1:5500"
    ).split(",")

    # ── File output ───────────────────────────────────────────────────────────
    OUTPUT_DIR: str = os.getenv("OUTPUT_DIR", "/tmp/bctc_output")


settings = Settings()
