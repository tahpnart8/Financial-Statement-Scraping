"""
Pydantic models for API request/response validation.
"""
from __future__ import annotations

from datetime import datetime
from typing import Optional

from pydantic import BaseModel, Field, field_validator


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
