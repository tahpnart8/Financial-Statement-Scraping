"""
Data Mapper Service
===================
Maps raw vnstock/CafeF DataFrames → standardised dict structure
that the Excel writer can consume.

The mapper handles:
  - Column name normalisation (Vietnamese → internal keys)
  - Unit conversion (vnstock returns values in VND, CafeF may vary)
  - Year/quarter filtering based on user's time range
  - Missing data handling (NaN → 0)
"""
from __future__ import annotations

import logging
from typing import Any, Optional

import pandas as pd
import numpy as np

from app.services.data_fetcher import (
    VNSTOCK_IS_COLUMNS,
    VNSTOCK_BS_COLUMNS,
    VNSTOCK_CF_COLUMNS,
)

logger = logging.getLogger(__name__)


# ── Template Row Mapping ──────────────────────────────────────────────────────
# Maps internal standardised keys → row index in the "BCTC du phong" sheet.
# Based on the DMC model.xlsx template structure analysis.

# Profit & Loss rows (section starts at row 1 with "PL" header)
PL_ROW_MAP: dict[str, int] = {
    "revenue": 3,
    "revenue_deductions": 4,
    "net_revenue": 5,
    "cost_of_goods_sold": 6,
    "gross_profit": 7,
    "financial_income": 8,
    "financial_expenses": 9,
    "interest_expenses": 10,
    "jv_profit_loss": 11,
    "selling_expenses": 12,
    "admin_expenses": 13,
    "operating_profit": 14,
    "other_income": 15,
    "other_expenses": 16,
    "other_profit": 17,
    "profit_before_tax": 18,
    "current_tax_expense": 19,
    # row 20 = tax rate (computed)
    "deferred_tax_expense": 21,
    "profit_after_tax": 22,
    "minority_interest": 23,
    # row 24 = % LNST
    "parent_profit_after_tax": 25,
    # row 26 = % growth
    "eps": 27,
}

# Balance Sheet rows (section starts at row 30 with "BS" header)
BS_ROW_MAP: dict[str, int] = {
    "current_assets": 33,
    "cash_and_equivalents": 34,
    "cash": 35,
    "cash_equivalents": 36,
    "short_term_investments": 37,
    "trading_securities": 38,
    "trading_securities_provision": 39,
    "held_to_maturity_investments": 40,
    "short_term_receivables": 41,
    "trade_receivables": 42,
    "prepayments_to_suppliers": 43,
    "internal_receivables_st": 44,
    "construction_contract_receivables": 45,
    "short_term_lending": 46,
    "other_receivables_st": 47,
    "bad_debt_provision_st": 48,
    "assets_awaiting_resolution": 49,
    "inventories": 50,
    "inventory_goods": 51,
    "inventory_provision": 52,
    "other_current_assets": 53,
    "prepaid_expenses_st": 54,
    "vat_deductible": 55,
    "tax_receivables_state": 56,
    "govt_bond_repo": 57,
    "other_current_assets_detail": 58,
    "non_current_assets": 60,
    "long_term_receivables": 61,
    "fixed_assets": 69,
    "tangible_fixed_assets": 70,
    "intangible_fixed_assets": 76,
    "investment_property": 79,
}

# Cash Flow rows - these will be in a separate section of the "BCTC du phong" sheet
# The exact rows depend on how far the BS section extends.
# We'll map them dynamically based on BS end position.
CF_ROW_MAP: dict[str, int] = {
    "cfo_net": 0,       # Placeholder — will be offset in the writer
    "cfi_net": 0,
    "cff_net": 0,
    "net_cash_flow": 0,
    "cash_beginning": 0,
    "cash_ending": 0,
}


def _normalise_vnstock_df(
    df: pd.DataFrame,
    report_type: str,
    year_from: int,
    year_to: int,
) -> dict[str, dict[int, Any]]:
    """
    Normalise a vnstock DataFrame into:
      { "internal_key": { year: value, ... }, ... }

    vnstock DataFrames typically have structure:
      - First column: Vietnamese metric name (str)
      - Subsequent columns: year or quarter values

    Parameters
    ----------
    df : pd.DataFrame
        Raw DataFrame from vnstock.
    report_type : str
        "income_statement", "balance_sheet", or "cash_flow".
    year_from, year_to : int
        Filter years.

    Returns
    -------
    dict[str, dict[int, Any]]
        { metric_key: { 2019: 1234567, 2020: 2345678, ... } }
    """
    # Select the correct column mapping
    col_map = {
        "income_statement": VNSTOCK_IS_COLUMNS,
        "balance_sheet": VNSTOCK_BS_COLUMNS,
        "cash_flow": VNSTOCK_CF_COLUMNS,
    }.get(report_type, {})

    result: dict[str, dict[int, Any]] = {}

    # vnstock returns DataFrames in different formats depending on version.
    # Common format: rows = time periods, columns = metrics
    # OR: rows = metrics, columns = time periods
    # We need to detect the orientation.

    # Check if the DataFrame has a 'year' or 'yearReport' column (row-per-period)
    year_col = None
    for candidate in ["year", "yearReport", "Năm", "Year"]:
        if candidate in df.columns:
            year_col = candidate
            break

    if year_col is not None:
        # Format: each row = one period, columns = metrics
        df_filtered = df[
            (df[year_col].astype(int) >= year_from)
            & (df[year_col].astype(int) <= year_to)
        ].copy()

        for vn_name, internal_key in col_map.items():
            if vn_name in df_filtered.columns:
                yearly_data = {}
                for _, row in df_filtered.iterrows():
                    year = int(row[year_col])
                    val = row[vn_name]
                    if pd.notna(val):
                        yearly_data[year] = float(val)
                    else:
                        yearly_data[year] = 0
                result[internal_key] = yearly_data
    else:
        # Format: each row = one metric, columns = periods
        # First column is typically the metric name
        metric_col = df.columns[0]

        for _, row in df.iterrows():
            metric_name = str(row[metric_col]).strip() if pd.notna(row[metric_col]) else ""
            internal_key = col_map.get(metric_name)

            if internal_key is None:
                # Try fuzzy match (remove extra whitespace)
                cleaned = " ".join(metric_name.split())
                internal_key = col_map.get(cleaned)

            if internal_key is None:
                continue

            yearly_data = {}
            for col in df.columns[1:]:
                try:
                    year = int(str(col).strip()[:4])  # Extract year from column name
                    if year_from <= year <= year_to:
                        val = row[col]
                        yearly_data[year] = float(val) if pd.notna(val) else 0
                except (ValueError, TypeError):
                    continue

            if yearly_data:
                result[internal_key] = yearly_data

    logger.info(
        f"Normalised {len(result)} metrics for {report_type} "
        f"(years {year_from}-{year_to})"
    )
    return result


def map_financial_data(
    reports: dict[str, pd.DataFrame],
    year_from: int,
    year_to: int,
) -> dict[str, dict[str, dict[int, Any]]]:
    """
    Map all fetched reports into a standardised structure.

    Parameters
    ----------
    reports : dict
        { "income_statement": DataFrame, "balance_sheet": ..., "cash_flow": ... }
    year_from, year_to : int
        Year filter range.

    Returns
    -------
    dict
        {
            "income_statement": { "revenue": {2019: 1234, ...}, ... },
            "balance_sheet": { ... },
            "cash_flow": { ... },
        }
    """
    mapped = {}

    for report_type, df in reports.items():
        source = df.attrs.get("source", "unknown")
        logger.info(f"Mapping {report_type} (source: {source})...")

        mapped[report_type] = _normalise_vnstock_df(
            df, report_type, year_from, year_to
        )

    return mapped


def get_row_map(report_type: str) -> dict[str, int]:
    """Return the row mapping for a given report type."""
    return {
        "income_statement": PL_ROW_MAP,
        "balance_sheet": BS_ROW_MAP,
        "cash_flow": CF_ROW_MAP,
    }.get(report_type, {})
