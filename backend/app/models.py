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

class YearlyDataInput(BaseModel):
    """Extracted data for a specific year."""
    year: int
    data: dict

class GenerateExcelRequest(BaseModel):
    """Request body for generating Excel from AI extracted data."""
    ticker: str = Field(..., min_length=1, max_length=10)
    year_from: int
    year_to: int
    yearly_data: list[YearlyDataInput] = Field(..., description="List of extracted data per year")

    @field_validator("ticker", mode="before")
    @classmethod
    def uppercase_ticker(cls, v: str) -> str:
        return v.strip().upper()

# ── Response Models ────────────────────────────────────────────────────────────

class ExtractPdfResponse(BaseModel):
    """Response after extracting a single PDF."""
    ticker: str
    year: int
    data: dict
    message: str = "Success"

class GenerateExcelResponse(BaseModel):
    """Response after generating excel."""
    download_url: str
    message: str = "Success"


class HealthResponse(BaseModel):
    """Health check response."""
    status: str = "ok"
    timestamp: datetime = Field(default_factory=datetime.utcnow)
    version: str = "1.0.0"

class TickerListResponse(BaseModel):
    """Response containing a list of tickers."""
    tickers: list[str]
    count: int
