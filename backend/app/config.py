"""
Configuration settings for the BCTC Crawling System.
"""
import os
from dotenv import load_dotenv
from pydantic import Field

load_dotenv()


class Settings:
    """Application settings loaded from environment or defaults."""

    # ── AI Processing ─────────────────────────────────────────────────────────
    GROQ_API_KEY: str = os.getenv("GROQ_API_KEY", "")
    GEMINI_API_KEY: str = os.getenv("GEMINI_API_KEY", "")

    APP_TITLE: str = "BCTC Crawling System API"
    APP_VERSION: str = "1.0.0"
    APP_DESCRIPTION: str = (
        "Hệ thống trích xuất và xử lý Báo cáo Tài chính (BCTC) "
        "của các doanh nghiệp niêm yết tại Việt Nam."
    )

    # CORS
    ALLOWED_ORIGINS: list[str] = os.getenv(
        "ALLOWED_ORIGINS", "http://localhost:3000,http://localhost:5500"
    ).split(",")

    # Job settings
    JOB_EXPIRY_SECONDS: int = int(os.getenv("JOB_EXPIRY_SECONDS", "3600"))
    MAX_CONCURRENT_JOBS: int = int(os.getenv("MAX_CONCURRENT_JOBS", "3"))

    # Data fetch settings
    VNSTOCK_SOURCE: str = os.getenv("VNSTOCK_SOURCE", "VCI")
    FETCH_RETRY_COUNT: int = int(os.getenv("FETCH_RETRY_COUNT", "3"))
    FETCH_RETRY_DELAY: float = float(os.getenv("FETCH_RETRY_DELAY", "1.0"))
    FETCH_RATE_LIMIT_DELAY: float = float(os.getenv("FETCH_RATE_LIMIT_DELAY", "0.5"))

    # File output
    OUTPUT_DIR: str = os.getenv("OUTPUT_DIR", "/tmp/bctc_output")


settings = Settings()
