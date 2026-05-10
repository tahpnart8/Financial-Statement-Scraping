"""
Data Fetcher Service
====================
Dual-source strategy:
  1. PRIMARY  – vnstock library (TCBS/VCI/KBS API)
  2. FALLBACK – CafeF HTML scraper (BeautifulSoup)

Each method returns a standardised pandas DataFrame with consistent
column names regardless of source.
"""
from __future__ import annotations

import logging
import time
from typing import Optional

import pandas as pd

from app.config import settings

logger = logging.getLogger(__name__)


# ── Column name standardisation ────────────────────────────────────────────────

# Map vnstock Vietnamese column names → internal standard keys.
# These mappings may need updating when vnstock changes its output schema.
VNSTOCK_IS_COLUMNS = {
    "Doanh thu bán hàng và cung cấp dịch vụ": "revenue",
    "Các khoản giảm trừ doanh thu": "revenue_deductions",
    "Doanh thu thuần về bán hàng và cung cấp dịch vụ": "net_revenue",
    "Giá vốn hàng bán": "cost_of_goods_sold",
    "Lợi nhuận gộp về bán hàng và cung cấp dịch vụ": "gross_profit",
    "Doanh thu hoạt động tài chính": "financial_income",
    "Chi phí tài chính": "financial_expenses",
    "Trong đó: Chi phí lãi vay": "interest_expenses",
    "Phần lãi lỗ hoặc lỗ trong công ty liên doanh, liên kết": "jv_profit_loss",
    "Chi phí bán hàng": "selling_expenses",
    "Chi phí quản lý doanh nghiệp": "admin_expenses",
    "Lợi nhuận thuần từ hoạt động kinh doanh": "operating_profit",
    "Thu nhập khác": "other_income",
    "Chi phí khác": "other_expenses",
    "Lợi nhuận khác": "other_profit",
    "Tổng lợi nhuận kế toán trước thuế": "profit_before_tax",
    "Chi phí thuế TNDN hiện hành": "current_tax_expense",
    "Chi phí thuế TNDN hoãn lại": "deferred_tax_expense",
    "Lợi nhuận sau thuế thu nhập doanh nghiệp": "profit_after_tax",
    "Lợi ích của cổ đông thiểu số": "minority_interest",
    "Lợi nhuận sau thuế của cổ đông của Công ty mẹ": "parent_profit_after_tax",
    "Lãi cơ bản trên cổ phiếu": "eps",
}

VNSTOCK_BS_COLUMNS = {
    "TÀI SẢN": "total_assets",
    "A. TÀI SẢN NGẮN HẠN": "current_assets",
    "I. Tiền và các khoản tương đương tiền": "cash_and_equivalents",
    "1. Tiền": "cash",
    "2. Các khoản tương đương tiền": "cash_equivalents",
    "II. Đầu tư tài chính ngắn hạn": "short_term_investments",
    "1. Chứng khoán kinh doanh": "trading_securities",
    "2. Dự phòng giảm giá chứng khoán kinh doanh": "trading_securities_provision",
    "3. Đầu tư nắm giữ đến ngày đáo hạn": "held_to_maturity_investments",
    "III. Các khoản phải thu ngắn hạn": "short_term_receivables",
    "1. Phải thu ngắn hạn của khách hàng": "trade_receivables",
    "2. Trả trước cho người bán ngắn hạn": "prepayments_to_suppliers",
    "3. Phải thu nội bộ ngắn hạn": "internal_receivables_st",
    "4. Phải thu theo tiến độ kế hoạch hợp đồng xây dựng": "construction_contract_receivables",
    "5. Phải thu về cho vay ngắn hạn": "short_term_lending",
    "6. Phải thu ngắn hạn khác": "other_receivables_st",
    "7. Dự phòng phải thu ngắn hạn khó đòi": "bad_debt_provision_st",
    "8. Tài sản thiếu chờ xử lý": "assets_awaiting_resolution",
    "IV. Hàng tồn kho": "inventories",
    "1. Hàng tồn kho": "inventory_goods",
    "2. Dự phòng giảm giá hàng tồn kho": "inventory_provision",
    "V. Tài sản ngắn hạn khác": "other_current_assets",
    "1. Chi phí trả trước ngắn hạn": "prepaid_expenses_st",
    "2. Thuế GTGT được khấu trừ": "vat_deductible",
    "3. Thuế và các khoản khác phải thu của nhà nước": "tax_receivables_state",
    "4. Giao dịch mua bán lại trái phiếu chính phủ": "govt_bond_repo",
    "5. Tài sản ngắn hạn khác": "other_current_assets_detail",
    "B. TÀI SẢN DÀI HẠN": "non_current_assets",
    "I. Các khoản phải thu dài hạn": "long_term_receivables",
    "II. Tài sản cố định": "fixed_assets",
    "1. Tài sản cố định hữu hình": "tangible_fixed_assets",
    "2. Tài sản cố định thuê tài chính": "finance_lease_assets",
    "3. Tài sản cố định vô hình": "intangible_fixed_assets",
    "III. Bất động sản đầu tư": "investment_property",
    "IV. Tài sản dở dang dài hạn": "long_term_wip",
    "V. Đầu tư tài chính dài hạn": "long_term_investments",
    "VI. Tài sản dài hạn khác": "other_non_current_assets",
    "NGUỒN VỐN": "total_equity_and_liabilities",
    "C. NỢ PHẢI TRẢ": "total_liabilities",
    "I. Nợ ngắn hạn": "current_liabilities",
    "1. Phải trả người bán ngắn hạn": "trade_payables_st",
    "2. Người mua trả tiền trước ngắn hạn": "advances_from_customers_st",
    "3. Thuế và các khoản phải nộp Nhà nước": "tax_payables_state",
    "4. Phải trả người lao động": "employee_payables",
    "5. Chi phí phải trả ngắn hạn": "accrued_expenses_st",
    "6. Phải trả nội bộ ngắn hạn": "internal_payables_st",
    "7. Phải trả theo tiến độ kế hoạch hợp đồng xây dựng": "construction_payables",
    "8. Doanh thu chưa thực hiện ngắn hạn": "unearned_revenue_st",
    "9. Phải trả ngắn hạn khác": "other_payables_st",
    "10. Vay và nợ thuê tài chính ngắn hạn": "short_term_borrowings",
    "11. Dự phòng phải trả ngắn hạn": "provisions_st",
    "12. Quỹ khen thưởng, phúc lợi": "bonus_welfare_fund",
    "II. Nợ dài hạn": "non_current_liabilities",
    "D. VỐN CHỦ SỞ HỮU": "total_equity",
    "I. Vốn chủ sở hữu": "owners_equity",
    "1. Vốn góp của chủ sở hữu": "charter_capital",
    "2. Thặng dư vốn cổ phần": "share_premium",
    "3. Quyền chọn chuyển đổi trái phiếu": "convertible_bond_options",
    "4. Vốn khác của chủ sở hữu": "other_owner_capital",
    "5. Cổ phiếu quỹ": "treasury_shares",
    "6. Chênh lệch đánh giá lại tài sản": "asset_revaluation_diff",
    "7. Chênh lệch tỷ giá hối đoái": "forex_diff",
    "8. Quỹ đầu tư phát triển": "investment_development_fund",
    "9. Quỹ hỗ trợ sắp xếp doanh nghiệp": "enterprise_restructuring_fund",
    "10. Quỹ khác thuộc vốn chủ sở hữu": "other_equity_funds",
    "11. Lợi nhuận sau thuế chưa phân phối": "retained_earnings",
    "12. Nguồn vốn đầu tư XDCB": "construction_investment_capital",
    "13. Lợi ích cổ đông không kiểm soát": "non_controlling_interests",
    "II. Nguồn kinh phí và quỹ khác": "other_funds",
}

VNSTOCK_CF_COLUMNS = {
    "I. Lưu chuyển tiền từ hoạt động kinh doanh": "cfo_total",
    "1. Lợi nhuận trước thuế": "cfo_profit_before_tax",
    "2. Điều chỉnh cho các khoản": "cfo_adjustments",
    "3. Lợi nhuận từ hoạt động kinh doanh trước thay đổi vốn lưu động": "cfo_before_wc_changes",
    "4. Thay đổi vốn lưu động": "cfo_wc_changes",
    "Lưu chuyển tiền thuần từ hoạt động kinh doanh": "cfo_net",
    "II. Lưu chuyển tiền từ hoạt động đầu tư": "cfi_total",
    "Lưu chuyển tiền thuần từ hoạt động đầu tư": "cfi_net",
    "III. Lưu chuyển tiền từ hoạt động tài chính": "cff_total",
    "Lưu chuyển tiền thuần từ hoạt động tài chính": "cff_net",
    "Lưu chuyển tiền thuần trong kỳ": "net_cash_flow",
    "Tiền và tương đương tiền đầu kỳ": "cash_beginning",
    "Ảnh hưởng của thay đổi tỷ giá hối đoái quy đổi ngoại tệ": "forex_effect",
    "Tiền và tương đương tiền cuối kỳ": "cash_ending",
}


# ── Primary Source: vnstock ────────────────────────────────────────────────────

def _fetch_vnstock(
    ticker: str,
    report_type: str,
    period: str,
) -> Optional[pd.DataFrame]:
    """
    Fetch financial data using the vnstock library.

    Parameters
    ----------
    ticker : str
        Stock ticker symbol (e.g. "DMC").
    report_type : str
        One of "income_statement", "balance_sheet", "cash_flow".
    period : str
        One of "year", "quarter".

    Returns
    -------
    pd.DataFrame or None
        Standardised DataFrame with columns: [metric, year_YYYY, ...] or None on failure.
    """
    try:
        from vnstock.api.financial import Finance

        finance = Finance(symbol=ticker, source=settings.VNSTOCK_SOURCE)

        fetch_map = {
            "income_statement": finance.income_statement,
            "balance_sheet": finance.balance_sheet,
            "cash_flow": finance.cash_flow,
        }

        func = fetch_map.get(report_type)
        if func is None:
            logger.error(f"Unknown report_type: {report_type}")
            return None

        df = func(period=period, lang="vi")

        if df is None or df.empty:
            logger.warning(f"vnstock returned empty data for {ticker}/{report_type}/{period}")
            return None

        logger.info(f"vnstock: fetched {len(df)} rows for {ticker}/{report_type}/{period}")
        return df

    except Exception as e:
        logger.error(f"vnstock fetch failed for {ticker}/{report_type}: {e}")
        return None


# ── Fallback Source: CafeF Scraper ─────────────────────────────────────────────

CAFEF_REPORT_URLS = {
    "income_statement": "https://s.cafef.vn/bao-cao-tai-chinh/{ticker}/IncSta/{period}/0/0/0/0/bao-cao-ket-qua-hoat-dong-kinh-doanh-.chn",
    "balance_sheet": "https://s.cafef.vn/bao-cao-tai-chinh/{ticker}/BSheet/{period}/0/0/0/0/bang-can-doi-ke-toan-.chn",
    "cash_flow": "https://s.cafef.vn/bao-cao-tai-chinh/{ticker}/CashFlow/{period}/0/0/0/0/bao-cao-luu-chuyen-tien-te-.chn",
}


def _fetch_cafef(
    ticker: str,
    report_type: str,
    period: str,
) -> Optional[pd.DataFrame]:
    """
    Fallback scraper: Fetch financial data from CafeF website via HTML parsing.

    The CafeF financial statement pages render data in an HTML <table>.
    This function fetches the page content and extracts the table using
    BeautifulSoup + pandas.read_html().

    Parameters
    ----------
    ticker, report_type, period : str
        Same semantics as _fetch_vnstock().

    Returns
    -------
    pd.DataFrame or None
    """
    import requests
    from bs4 import BeautifulSoup

    url_template = CAFEF_REPORT_URLS.get(report_type)
    if url_template is None:
        logger.error(f"CafeF: no URL template for report_type={report_type}")
        return None

    period_code = "1" if period == "year" else "0"
    url = url_template.format(ticker=ticker, period=period_code)

    headers = {
        "User-Agent": (
            "Mozilla/5.0 (Windows NT 10.0; Win64; x64) "
            "AppleWebKit/537.36 (KHTML, like Gecko) "
            "Chrome/120.0.0.0 Safari/537.36"
        ),
        "Accept-Language": "vi-VN,vi;q=0.9,en-US;q=0.8",
    }

    try:
        for attempt in range(settings.FETCH_RETRY_COUNT):
            resp = requests.get(url, headers=headers, timeout=30)
            if resp.status_code == 200:
                break
            logger.warning(
                f"CafeF: attempt {attempt + 1} returned status {resp.status_code}"
            )
            time.sleep(settings.FETCH_RETRY_DELAY * (2 ** attempt))
        else:
            logger.error(f"CafeF: all {settings.FETCH_RETRY_COUNT} retries failed for {url}")
            return None

        soup = BeautifulSoup(resp.text, "html.parser")

        # CafeF renders financial statements inside a table with id="tableContent"
        # or similar class patterns.  We try to find the main data table.
        table = soup.find("table", {"id": "tableContent"})
        if table is None:
            # Fallback: try to find the largest table on the page
            tables = soup.find_all("table")
            if not tables:
                logger.error(f"CafeF: no tables found on page for {ticker}/{report_type}")
                return None
            table = max(tables, key=lambda t: len(t.find_all("tr")))

        # Parse with pandas
        dfs = pd.read_html(str(table), thousands=".", decimal=",")
        if not dfs:
            logger.error(f"CafeF: pd.read_html returned empty for {ticker}/{report_type}")
            return None

        df = dfs[0]
        logger.info(f"CafeF: scraped {len(df)} rows for {ticker}/{report_type}/{period}")
        return df

    except Exception as e:
        logger.error(f"CafeF scrape failed for {ticker}/{report_type}: {e}")
        return None


# ── Public API ─────────────────────────────────────────────────────────────────

def fetch_financial_data(
    ticker: str,
    report_type: str,
    period: str,
) -> pd.DataFrame:
    """
    Fetch financial data with dual-source fallback strategy.

    Primary:  vnstock library
    Fallback: CafeF HTML scraper

    Parameters
    ----------
    ticker : str
        Stock ticker symbol (e.g. "DMC").
    report_type : str
        One of "income_statement", "balance_sheet", "cash_flow".
    period : str
        One of "year", "quarter".

    Returns
    -------
    pd.DataFrame
        Financial data. Empty DataFrame if both sources fail.

    Raises
    ------
    ValueError
        If no data could be retrieved from any source.
    """
    # 1. Try vnstock (primary)
    logger.info(f"Fetching {report_type} for {ticker} via vnstock...")
    df = _fetch_vnstock(ticker, report_type, period)

    if df is not None and not df.empty:
        df.attrs["source"] = "vnstock"
        return df

    # 2. Fallback to CafeF
    logger.warning(f"vnstock failed for {ticker}/{report_type}, trying CafeF fallback...")
    time.sleep(settings.FETCH_RATE_LIMIT_DELAY)
    df = _fetch_cafef(ticker, report_type, period)

    if df is not None and not df.empty:
        df.attrs["source"] = "cafef"
        return df

    raise ValueError(
        f"Không thể lấy dữ liệu {report_type} cho mã {ticker} từ cả vnstock lẫn CafeF. "
        "Vui lòng kiểm tra lại mã cổ phiếu hoặc thử lại sau."
    )


def fetch_all_reports(
    ticker: str,
    period: str,
) -> dict[str, pd.DataFrame]:
    """
    Fetch all three financial reports for a ticker.

    Returns
    -------
    dict with keys: "income_statement", "balance_sheet", "cash_flow"
    """
    reports = {}
    for rtype in ["income_statement", "balance_sheet", "cash_flow"]:
        reports[rtype] = fetch_financial_data(ticker, rtype, period)
        time.sleep(settings.FETCH_RATE_LIMIT_DELAY)
    return reports
