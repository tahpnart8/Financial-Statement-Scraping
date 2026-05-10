"""
Tickers Router
==============
Provides list of valid stock tickers and validation.
"""
from __future__ import annotations

import logging

from fastapi import APIRouter, HTTPException

from app.models import TickerListResponse

logger = logging.getLogger(__name__)

router = APIRouter(prefix="/api/tickers", tags=["Tickers"])

# Cache the ticker list to avoid repeated API calls
_cached_tickers: list[str] | None = None


def _load_tickers() -> list[str]:
    """Load all available tickers from vnstock."""
    global _cached_tickers
    if _cached_tickers is not None:
        return _cached_tickers

    try:
        from vnstock.api.listing import Listing

        listing = Listing(source='VCI')
        df = listing.all_symbols()
        if df is not None and not df.empty:
            # The column name may vary; try common ones
            for col in ["ticker", "symbol", "code", "Mã CK"]:
                if col in df.columns:
                    _cached_tickers = sorted(df[col].dropna().unique().tolist())
                    logger.info(f"Loaded {len(_cached_tickers)} tickers from vnstock")
                    return _cached_tickers

            # If no known column, use first column
            _cached_tickers = sorted(df.iloc[:, 0].dropna().unique().tolist())
            return _cached_tickers

    except Exception as e:
        logger.warning(f"Failed to load tickers from vnstock: {e}")

    # Fallback: return a curated list of popular tickers
    _cached_tickers = [
        "AAA", "ACB", "BCM", "BID", "BVH", "CTG", "DCM", "DGC",
        "DMC", "DPM", "FPT", "GAS", "GVR", "HDB", "HDG", "HPG",
        "HSG", "KDH", "KDC", "MBB", "MSN", "MWG", "NVL", "PDR",
        "PLX", "PNJ", "POW", "REE", "SAB", "SBT", "SSI", "STB",
        "TCB", "TCH", "TPB", "VCB", "VHM", "VIC", "VJC", "VNM",
        "VPB", "VRE",
    ]
    return _cached_tickers


@router.get(
    "",
    response_model=TickerListResponse,
    summary="Danh sách mã cổ phiếu",
    description="Trả về danh sách tất cả các mã cổ phiếu niêm yết hợp lệ.",
)
async def list_tickers():
    """Get list of all valid stock tickers."""
    tickers = _load_tickers()
    return TickerListResponse(tickers=tickers, count=len(tickers))


@router.get(
    "/validate/{ticker}",
    summary="Kiểm tra mã cổ phiếu",
    description="Kiểm tra xem một mã cổ phiếu có hợp lệ hay không.",
)
async def validate_ticker(ticker: str):
    """Validate if a ticker exists."""
    tickers = _load_tickers()
    ticker_upper = ticker.strip().upper()
    is_valid = ticker_upper in tickers

    if not is_valid:
        raise HTTPException(
            status_code=404,
            detail=f"Mã cổ phiếu '{ticker_upper}' không tồn tại trong hệ thống.",
        )

    return {"ticker": ticker_upper, "valid": True}
