"""
Excel Writer Service
====================
Dynamically generates an Excel workbook populated with financial data.
The template is generated programmatically (not from a static .xlsx file)
to support dynamic year ranges.

Sheet structure mirrors the DMC model.xlsx:
  1. BCTC du phong    – Consolidated PL + BS + CF
  2. Doanh thu        – Revenue analysis
  3. Vốn lưu động     – Working capital
  4. TSCĐ             – Fixed assets
  5. Vốn CSH          – Owner's equity
  6. DT&CP tài chính  – Financial income/expenses
  7. Định giá          – Valuation (empty template)
  8. Giả định          – Assumptions (empty template)
"""
from __future__ import annotations

import logging
import os
from typing import Any

from openpyxl import Workbook
from openpyxl.styles import (
    Font,
    PatternFill,
    Alignment,
    Border,
    Side,
    numbers,
)
from openpyxl.utils import get_column_letter

from app.services.data_mapper import PL_ROW_MAP, BS_ROW_MAP

logger = logging.getLogger(__name__)


# ── Style Constants ────────────────────────────────────────────────────────────

HEADER_FONT = Font(name="Times New Roman", size=11, bold=True, color="FFFFFF")
HEADER_FILL = PatternFill(start_color="2F5496", end_color="2F5496", fill_type="solid")
SECTION_FONT = Font(name="Times New Roman", size=11, bold=True)
SECTION_FILL = PatternFill(start_color="D6E4F0", end_color="D6E4F0", fill_type="solid")
DATA_FONT = Font(name="Times New Roman", size=10)
NUMBER_FORMAT = '#,##0'
PERCENT_FORMAT = '0.00%'
THIN_BORDER = Border(
    left=Side(style="thin", color="B4C6E7"),
    right=Side(style="thin", color="B4C6E7"),
    top=Side(style="thin", color="B4C6E7"),
    bottom=Side(style="thin", color="B4C6E7"),
)


# ── Vietnamese Labels ──────────────────────────────────────────────────────────

PL_LABELS = {
    3: "1. Doanh thu bán hàng và cung cấp dịch vụ",
    4: "2. Các khoản giảm trừ doanh thu",
    5: "3. Doanh thu thuần về bán hàng và cung cấp dịch vụ",
    6: "4. Giá vốn hàng bán",
    7: "5. Lợi nhuận gộp về bán hàng và cung cấp dịch vụ",
    8: "6. Doanh thu hoạt động tài chính",
    9: "7. Chi phí tài chính",
    10: "   Trong đó: Chi phí lãi vay",
    11: "8. Phần lãi/lỗ trong công ty liên doanh, liên kết",
    12: "9. Chi phí bán hàng",
    13: "10. Chi phí quản lý doanh nghiệp",
    14: "11. Lợi nhuận thuần từ hoạt động kinh doanh",
    15: "12. Thu nhập khác",
    16: "13. Chi phí khác",
    17: "14. Lợi nhuận khác",
    18: "15. Tổng lợi nhuận kế toán trước thuế",
    19: "16. Chi phí thuế TNDN hiện hành",
    20: "Thuế suất",
    21: "17. Chi phí thuế TNDN hoãn lại",
    22: "18. Lợi nhuận sau thuế thu nhập doanh nghiệp",
    23: "Lợi ích của cổ đông thiểu số",
    24: "% LNST",
    25: "Lợi nhuận sau thuế của cổ đông của Công ty mẹ",
    27: "19. Lãi cơ bản trên cổ phiếu (*) (VNĐ)",
}

BS_LABELS = {
    32: "TÀI SẢN",
    33: "A. TÀI SẢN NGẮN HẠN",
    34: "I. Tiền và các khoản tương đương tiền",
    35: "1. Tiền",
    36: "2. Các khoản tương đương tiền",
    37: "II. Đầu tư tài chính ngắn hạn",
    38: "1. Chứng khoán kinh doanh",
    39: "2. Dự phòng giảm giá chứng khoán kinh doanh (*)",
    40: "3. Đầu tư nắm giữ đến ngày đáo hạn",
    41: "III. Các khoản phải thu ngắn hạn",
    42: "1. Phải thu ngắn hạn của khách hàng",
    43: "2. Trả trước cho người bán ngắn hạn",
    44: "3. Phải thu nội bộ ngắn hạn",
    45: "4. Phải thu theo tiến độ kế hoạch hợp đồng xây dựng",
    46: "5. Phải thu về cho vay ngắn hạn",
    47: "6. Phải thu ngắn hạn khác",
    48: "7. Dự phòng phải thu ngắn hạn khó đòi (*)",
    49: "8. Tài sản thiếu chờ xử lý",
    50: "IV. Hàng tồn kho",
    51: "1. Hàng tồn kho",
    52: "2. Dự phòng giảm giá hàng tồn kho (*)",
    53: "V. Tài sản ngắn hạn khác",
    54: "1. Chi phí trả trước ngắn hạn",
    55: "2. Thuế GTGT được khấu trừ",
    56: "3. Thuế và các khoản khác phải thu của nhà nước",
    57: "4. Giao dịch mua bán lại trái phiếu chính phủ",
    58: "5. Tài sản ngắn hạn khác",
    60: "B. TÀI SẢN DÀI HẠN",
    61: "I. Các khoản phải thu dài hạn",
    69: "II. Tài sản cố định",
    70: "1. Tài sản cố định hữu hình",
    71: "      - Nguyên giá",
    72: "      - Giá trị hao mòn lũy kế (*)",
    73: "2. Tài sản cố định thuê tài chính",
    76: "3. Tài sản cố định vô hình",
    79: "III. Bất động sản đầu tư",
}


def _apply_cell_style(ws, row: int, col: int, value: Any, is_header: bool = False,
                       is_section: bool = False, fmt: str | None = None):
    """Apply value and styling to a cell."""
    cell = ws.cell(row=row, column=col, value=value)
    cell.border = THIN_BORDER
    cell.alignment = Alignment(vertical="center", wrap_text=True)

    if is_header:
        cell.font = HEADER_FONT
        cell.fill = HEADER_FILL
        cell.alignment = Alignment(horizontal="center", vertical="center")
    elif is_section:
        cell.font = SECTION_FONT
        cell.fill = SECTION_FILL
    else:
        cell.font = DATA_FONT

    if fmt:
        cell.number_format = fmt


def _write_year_headers(ws, start_row: int, label: str, years: list[int],
                        label_col: int = 2):
    """Write section header + year column headers."""
    _apply_cell_style(ws, start_row, label_col, label, is_header=True)
    for i, year in enumerate(years):
        _apply_cell_style(ws, start_row, label_col + 1 + i, year, is_header=True)


def _write_data_row(ws, row: int, label: str, data: dict[int, Any],
                    years: list[int], label_col: int = 2,
                    is_section: bool = False, fmt: str | None = NUMBER_FORMAT):
    """Write a label + yearly values into a row."""
    _apply_cell_style(ws, row, label_col, label, is_section=is_section)
    for i, year in enumerate(years):
        val = data.get(year, 0)
        _apply_cell_style(ws, row, label_col + 1 + i, val, fmt=fmt)


# ── Sheet Builders ─────────────────────────────────────────────────────────────

def _build_bctc_sheet(
    wb: Workbook,
    mapped_data: dict[str, dict[str, dict[int, Any]]],
    years: list[int],
):
    """Build the main 'BCTC du phong' sheet with PL + BS + CF sections."""
    ws = wb.active
    ws.title = "BCTC du phong"

    # Set column widths
    ws.column_dimensions["A"].width = 3
    ws.column_dimensions["B"].width = 50
    for i, _ in enumerate(years):
        col_letter = get_column_letter(3 + i)
        ws.column_dimensions[col_letter].width = 18

    # ── Profit & Loss Section ──
    _write_year_headers(ws, 1, "PL", years)

    is_data = mapped_data.get("income_statement", {})
    for internal_key, row_idx in PL_ROW_MAP.items():
        label = PL_LABELS.get(row_idx, internal_key)
        data = is_data.get(internal_key, {})
        is_section = row_idx in {5, 7, 14, 18, 22, 25}
        fmt = PERCENT_FORMAT if row_idx == 20 else NUMBER_FORMAT
        _write_data_row(ws, row_idx, label, data, years, is_section=is_section, fmt=fmt)

    # Tax rate row (row 20) — computed from data
    pbt = is_data.get("profit_before_tax", {})
    tax = is_data.get("current_tax_expense", {})
    tax_rate_data = {}
    for y in years:
        pbt_val = pbt.get(y, 0)
        tax_val = tax.get(y, 0)
        if pbt_val and pbt_val != 0:
            tax_rate_data[y] = tax_val / pbt_val
    _write_data_row(ws, 20, "Thuế suất", tax_rate_data, years, fmt=PERCENT_FORMAT)

    # ── Balance Sheet Section ──
    bs_start = 30
    _write_year_headers(ws, bs_start, "BS", years)

    bs_data = mapped_data.get("balance_sheet", {})
    for internal_key, row_idx in BS_ROW_MAP.items():
        label = BS_LABELS.get(row_idx, internal_key)
        data = bs_data.get(internal_key, {})
        is_section = row_idx in {32, 33, 60}
        _write_data_row(ws, row_idx, label, data, years, is_section=is_section)

    # ── Cash Flow Section ──
    cf_start = 130  # Start CF section after BS
    _write_year_headers(ws, cf_start, "CF", years)

    cf_data = mapped_data.get("cash_flow", {})
    cf_labels = {
        "cfo_net": "Lưu chuyển tiền thuần từ HĐKD",
        "cfi_net": "Lưu chuyển tiền thuần từ HĐ đầu tư",
        "cff_net": "Lưu chuyển tiền thuần từ HĐ tài chính",
        "net_cash_flow": "Lưu chuyển tiền thuần trong kỳ",
        "cash_beginning": "Tiền và tương đương tiền đầu kỳ",
        "cash_ending": "Tiền và tương đương tiền cuối kỳ",
    }
    for i, (key, label) in enumerate(cf_labels.items()):
        row = cf_start + 2 + i
        data = cf_data.get(key, {})
        _write_data_row(ws, row, label, data, years)


def _build_revenue_sheet(
    wb: Workbook,
    mapped_data: dict[str, dict[str, dict[int, Any]]],
    years: list[int],
):
    """Build the 'Doanh thu' (Revenue) analysis sheet."""
    ws = wb.create_sheet("Doanh thu")
    ws.column_dimensions["A"].width = 40
    for i, _ in enumerate(years):
        ws.column_dimensions[get_column_letter(2 + i)].width = 18

    _write_year_headers(ws, 1, "I/ Dự phóng doanh thu", years, label_col=1)

    is_data = mapped_data.get("income_statement", {})

    # Net revenue
    _write_data_row(ws, 3, "Doanh thu thuần", is_data.get("net_revenue", {}),
                    years, label_col=1, is_section=True)

    # Revenue growth rate
    net_rev = is_data.get("net_revenue", {})
    growth = {}
    sorted_years = sorted(years)
    for i in range(1, len(sorted_years)):
        prev = net_rev.get(sorted_years[i - 1], 0)
        curr = net_rev.get(sorted_years[i], 0)
        if prev and prev != 0:
            growth[sorted_years[i]] = (curr - prev) / prev
    _write_data_row(ws, 4, "% tăng trưởng", growth, years, label_col=1,
                    fmt=PERCENT_FORMAT)

    # COGS
    row = 6
    _apply_cell_style(ws, row, 1, "II/ Dự phóng giá vốn", is_section=True)
    row += 1
    _write_data_row(ws, row, "Giá vốn", is_data.get("cost_of_goods_sold", {}),
                    years, label_col=1)

    # COGS/Revenue ratio
    cogs = is_data.get("cost_of_goods_sold", {})
    cogs_ratio = {}
    for y in years:
        rev = net_rev.get(y, 0)
        c = cogs.get(y, 0)
        if rev and rev != 0:
            cogs_ratio[y] = c / rev
    _write_data_row(ws, row + 1, "% doanh thu thuần", cogs_ratio, years,
                    label_col=1, fmt=PERCENT_FORMAT)

    # Selling expenses
    row += 3
    _write_data_row(ws, row, "CP bán hàng", is_data.get("selling_expenses", {}),
                    years, label_col=1)
    sell_exp = is_data.get("selling_expenses", {})
    sell_ratio = {y: sell_exp.get(y, 0) / net_rev.get(y, 1) for y in years if net_rev.get(y, 0)}
    _write_data_row(ws, row + 1, "% doanh thu", sell_ratio, years,
                    label_col=1, fmt=PERCENT_FORMAT)

    # Admin expenses
    row += 3
    _write_data_row(ws, row, "CP quản lý DN", is_data.get("admin_expenses", {}),
                    years, label_col=1)
    admin_exp = is_data.get("admin_expenses", {})
    admin_ratio = {y: admin_exp.get(y, 0) / net_rev.get(y, 1) for y in years if net_rev.get(y, 0)}
    _write_data_row(ws, row + 1, "% doanh thu", admin_ratio, years,
                    label_col=1, fmt=PERCENT_FORMAT)


def _build_working_capital_sheet(
    wb: Workbook,
    mapped_data: dict[str, dict[str, dict[int, Any]]],
    years: list[int],
):
    """Build the 'Vốn lưu động' (Working Capital) sheet."""
    ws = wb.create_sheet("Vốn lưu động")
    ws.column_dimensions["A"].width = 45
    for i, _ in enumerate(years):
        ws.column_dimensions[get_column_letter(2 + i)].width = 18

    _write_year_headers(ws, 1, "TS ngắn hạn", years, label_col=1)

    bs_data = mapped_data.get("balance_sheet", {})
    is_data = mapped_data.get("income_statement", {})
    net_rev = is_data.get("net_revenue", {})
    cogs = is_data.get("cost_of_goods_sold", {})

    # Short-term receivables section
    row = 3
    items_receivables = [
        ("short_term_receivables", "III. Các khoản phải thu ngắn hạn", True),
        ("trade_receivables", "1. Phải thu ngắn hạn của khách hàng", False),
        ("prepayments_to_suppliers", "2. Trả trước cho người bán ngắn hạn", False),
        ("other_receivables_st", "6. Phải thu ngắn hạn khác", False),
        ("bad_debt_provision_st", "7. Dự phòng phải thu ngắn hạn khó đòi (*)", False),
    ]

    for key, label, is_sec in items_receivables:
        _write_data_row(ws, row, label, bs_data.get(key, {}), years,
                        label_col=1, is_section=is_sec)
        # Add turnover ratio for trade receivables
        if key == "trade_receivables":
            row += 1
            ar = bs_data.get(key, {})
            turnover = {}
            for y in years:
                ar_val = ar.get(y, 0)
                if ar_val and ar_val != 0:
                    turnover[y] = net_rev.get(y, 0) / ar_val
            _write_data_row(ws, row, "Vòng quay phải thu", turnover, years,
                            label_col=1, fmt='0.00')
        row += 2

    # Inventory section
    row += 1
    inv_items = [
        ("inventories", "IV. Hàng tồn kho", True),
        ("inventory_goods", "1. Hàng tồn kho", False),
        ("inventory_provision", "2. Dự phòng giảm giá hàng tồn kho (*)", False),
    ]
    for key, label, is_sec in inv_items:
        _write_data_row(ws, row, label, bs_data.get(key, {}), years,
                        label_col=1, is_section=is_sec)
        if key == "inventory_goods":
            row += 1
            inv = bs_data.get(key, {})
            inv_turnover = {}
            for y in years:
                inv_val = inv.get(y, 0)
                if inv_val and inv_val != 0:
                    inv_turnover[y] = cogs.get(y, 0) / inv_val
            _write_data_row(ws, row, "Vòng quay HTK", inv_turnover, years,
                            label_col=1, fmt='0.00')
        row += 1


def _build_fixed_assets_sheet(
    wb: Workbook,
    mapped_data: dict[str, dict[str, dict[int, Any]]],
    years: list[int],
):
    """Build the 'TSCĐ' (Fixed Assets) sheet."""
    ws = wb.create_sheet("TSCĐ")
    ws.column_dimensions["A"].width = 45
    for i, _ in enumerate(years):
        ws.column_dimensions[get_column_letter(2 + i)].width = 18

    _write_year_headers(ws, 1, "TSCĐ hữu hình", years, label_col=1)

    bs_data = mapped_data.get("balance_sheet", {})

    items = [
        ("tangible_fixed_assets", "1. Tài sản cố định hữu hình", True),
        ("intangible_fixed_assets", "3. Tài sản cố định vô hình", False),
        ("investment_property", "III. Bất động sản đầu tư", False),
        ("long_term_wip", "IV. Tài sản dở dang dài hạn", False),
    ]

    row = 3
    for key, label, is_sec in items:
        _write_data_row(ws, row, label, bs_data.get(key, {}), years,
                        label_col=1, is_section=is_sec)
        row += 2


def _build_equity_sheet(
    wb: Workbook,
    mapped_data: dict[str, dict[str, dict[int, Any]]],
    years: list[int],
):
    """Build the 'Vốn CSH' (Equity) sheet."""
    ws = wb.create_sheet("Vốn CSH")
    ws.column_dimensions["A"].width = 45
    for i, _ in enumerate(years):
        ws.column_dimensions[get_column_letter(2 + i)].width = 18

    _write_year_headers(ws, 1, "Vốn chủ sở hữu", years, label_col=1)

    bs_data = mapped_data.get("balance_sheet", {})

    items = [
        ("owners_equity", "I. Vốn chủ sở hữu", True),
        ("charter_capital", "1. Vốn góp của chủ sở hữu", False),
        ("share_premium", "2. Thặng dư vốn cổ phần", False),
        ("treasury_shares", "5. Cổ phiếu quỹ (*)", False),
        ("investment_development_fund", "8. Quỹ đầu tư phát triển", False),
        ("retained_earnings", "11. Lợi nhuận sau thuế chưa phân phối", False),
        ("non_controlling_interests", "13. Lợi ích cổ đông không kiểm soát", False),
    ]

    row = 3
    for key, label, is_sec in items:
        _write_data_row(ws, row, label, bs_data.get(key, {}), years,
                        label_col=1, is_section=is_sec)
        row += 1


def _build_financial_income_sheet(
    wb: Workbook,
    mapped_data: dict[str, dict[str, dict[int, Any]]],
    years: list[int],
):
    """Build the 'DT&CP tài chính' (Financial Income/Expenses) sheet."""
    ws = wb.create_sheet("DT&CP tài chính")
    ws.column_dimensions["A"].width = 45
    for i, _ in enumerate(years):
        ws.column_dimensions[get_column_letter(2 + i)].width = 18

    _write_year_headers(ws, 1, "DT & CP tài chính", years, label_col=1)

    is_data = mapped_data.get("income_statement", {})
    bs_data = mapped_data.get("balance_sheet", {})

    items = [
        ("financial_income", "DT tài chính", True, "income_statement"),
        ("financial_expenses", "Chi phí tài chính", False, "income_statement"),
        ("interest_expenses", "Lãi vay", False, "income_statement"),
        ("short_term_borrowings", "Vay ngắn hạn", False, "balance_sheet"),
    ]

    row = 3
    for key, label, is_sec, source in items:
        data_src = is_data if source == "income_statement" else bs_data
        _write_data_row(ws, row, label, data_src.get(key, {}), years,
                        label_col=1, is_section=is_sec)
        row += 1


def _build_valuation_sheet(wb: Workbook, years: list[int]):
    """Build the 'Định giá' (Valuation) template sheet — empty for user to fill."""
    ws = wb.create_sheet("Định giá")
    ws.column_dimensions["A"].width = 40
    _apply_cell_style(ws, 1, 1, "Định giá", is_header=True)
    _apply_cell_style(ws, 3, 1, "Giá theo FCFE", is_section=True)
    _apply_cell_style(ws, 4, 1, "Giá theo FCFF", is_section=True)
    _apply_cell_style(ws, 6, 1, "Giá trị nội tại", is_section=True)
    _apply_cell_style(ws, 7, 1, "Thị giá")
    _apply_cell_style(ws, 8, 1, "UP/DOWN")


def _build_assumptions_sheet(wb: Workbook, years: list[int]):
    """Build the 'Giả định' (Assumptions) template sheet — empty for user to fill."""
    ws = wb.create_sheet("Giả định vs biểu đồ")
    ws.column_dimensions["A"].width = 5
    ws.column_dimensions["B"].width = 45
    ws.column_dimensions["D"].width = 20
    ws.column_dimensions["E"].width = 20
    ws.column_dimensions["F"].width = 25
    ws.column_dimensions["G"].width = 25

    _apply_cell_style(ws, 2, 1, "STT", is_header=True)
    _apply_cell_style(ws, 2, 2, "Giả định", is_header=True)
    _apply_cell_style(ws, 2, 4, "Giá trị năm ngoái", is_header=True)
    _apply_cell_style(ws, 2, 5, "Giá trị hiện tại", is_header=True)
    _apply_cell_style(ws, 2, 6, "Cách tính", is_header=True)
    _apply_cell_style(ws, 2, 7, "Chú thích", is_header=True)


# ── Public API ─────────────────────────────────────────────────────────────────

def generate_excel(
    ticker: str,
    mapped_data: dict[str, dict[str, dict[int, Any]]],
    year_from: int,
    year_to: int,
    output_dir: str,
) -> str:
    """
    Generate a complete financial model Excel workbook.

    Parameters
    ----------
    ticker : str
        Stock ticker (used in filename).
    mapped_data : dict
        Output of data_mapper.map_financial_data().
    year_from, year_to : int
        Year range for column headers.
    output_dir : str
        Directory to save the output file.

    Returns
    -------
    str
        Absolute path to the generated .xlsx file.
    """
    years = list(range(year_from, year_to + 1))

    wb = Workbook()

    # Build all 8 sheets
    _build_bctc_sheet(wb, mapped_data, years)
    _build_revenue_sheet(wb, mapped_data, years)
    _build_working_capital_sheet(wb, mapped_data, years)
    _build_fixed_assets_sheet(wb, mapped_data, years)
    _build_equity_sheet(wb, mapped_data, years)
    _build_financial_income_sheet(wb, mapped_data, years)
    _build_valuation_sheet(wb, years)
    _build_assumptions_sheet(wb, years)

    # Save
    os.makedirs(output_dir, exist_ok=True)
    filename = f"{ticker}_BCTC_{year_from}_{year_to}.xlsx"
    filepath = os.path.join(output_dir, filename)
    wb.save(filepath)

    logger.info(f"Excel file generated: {filepath}")
    return filepath
