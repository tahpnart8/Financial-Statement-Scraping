"""
Pydantic models for API request/response validation.
"""
from __future__ import annotations

import uuid
from datetime import datetime
from enum import Enum
from typing import Optional

from pydantic import BaseModel, Field, field_validator


# ── Enums ──────────────────────────────────────────────────────────────────────

class ReportType(str, Enum):
    """Loại báo cáo tài chính."""
    BALANCE_SHEET = "balance_sheet"
    INCOME_STATEMENT = "income_statement"
    CASH_FLOW = "cash_flow"
    ALL = "all"


class PeriodType(str, Enum):
    """Kỳ báo cáo."""
    YEAR = "year"
    QUARTER = "quarter"


class JobStatus(str, Enum):
    """Trạng thái job."""
    PENDING = "pending"
    PROCESSING = "processing"
    COMPLETED = "completed"
    FAILED = "failed"


# ── Request Models ─────────────────────────────────────────────────────────────

class JobCreateRequest(BaseModel):
    """Request body for creating a new extraction job."""

    tickers: list[str] = Field(
        ...,
        min_length=1,
        max_length=10,
        description="Danh sách mã cổ phiếu (tối đa 10 mã)",
        examples=[["DMC", "FPT"]],
    )
    report_type: ReportType = Field(
        default=ReportType.ALL,
        description="Loại báo cáo: balance_sheet, income_statement, cash_flow, all",
    )
    period: PeriodType = Field(
        default=PeriodType.YEAR,
        description="Kỳ báo cáo: year hoặc quarter",
    )
    year_from: int = Field(
        ...,
        ge=2000,
        le=2030,
        description="Năm bắt đầu",
        examples=[2019],
    )
    year_to: int = Field(
        ...,
        ge=2000,
        le=2030,
        description="Năm kết thúc",
        examples=[2024],
    )

    @field_validator("tickers", mode="before")
    @classmethod
    def uppercase_tickers(cls, v: list[str]) -> list[str]:
        return [t.strip().upper() for t in v]

    @field_validator("year_to")
    @classmethod
    def validate_year_range(cls, v: int, info) -> int:
        year_from = info.data.get("year_from")
        if year_from and v < year_from:
            raise ValueError("year_to phải >= year_from")
        return v


# ── Response Models ────────────────────────────────────────────────────────────

class JobCreateResponse(BaseModel):
    """Response after creating a job."""
    job_id: str = Field(default_factory=lambda: str(uuid.uuid4()))
    status: JobStatus = JobStatus.PENDING
    created_at: datetime = Field(default_factory=datetime.utcnow)


class JobStatusResponse(BaseModel):
    """Response for job status polling."""
    job_id: str
    status: JobStatus
    progress: int = Field(default=0, ge=0, le=100)
    message: str = ""
    download_url: Optional[str] = None
    error: Optional[str] = None
    created_at: datetime
    completed_at: Optional[datetime] = None


class TickerListResponse(BaseModel):
    """Response for available tickers."""
    tickers: list[str]
    count: int


class HealthResponse(BaseModel):
    """Health check response."""
    status: str = "ok"
    timestamp: datetime = Field(default_factory=datetime.utcnow)
    version: str = "1.0.0"
