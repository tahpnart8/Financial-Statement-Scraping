"""
Data Mapper Service
===================
Maps raw vnstock/Vietcap Direct/CafeF DataFrames → standardised dict structure
that the Excel writer can consume.
"""
from __future__ import annotations

import logging
from typing import Any, Optional

import pandas as pd
import numpy as np
import re

logger = logging.getLogger(__name__)


# ── Vietcap (Direct API) Mappings ─────────────────────────────────────────────

VIETCAP_IS_COLUMNS = {
    "isa1": "revenue",
    "isa2": "revenue_deductions",
    "isa3": "net_revenue",
    "isa4": "cost_of_goods_sold",
    "isa5": "gross_profit",
    "isa6": "financial_income",
    "isa7": "financial_expenses",
    "isa8": "interest_expenses",
    "isa102": "jv_profit_loss",
    "isa9": "selling_expenses",
    "isa10": "admin_expenses",
    "isa11": "operating_profit",
    "isa14": "other_profit",
    "isa12": "other_income",
    "isa13": "other_expenses",
    "isa16": "profit_before_tax",
    "isa19": "tax_expense_total",
    "isa17": "current_tax_expense",
    "isa18": "deferred_tax_expense",
    "isa20": "profit_after_tax",
    "isa21": "minority_interest",
    "isa22": "parent_profit_after_tax",
    "isa23": "eps",
}

VIETCAP_BS_COLUMNS = {
    "bsa1": "current_assets",
    "bsa2": "cash_and_equivalents",
    "bsa3": "cash",
    "bsa4": "cash_equivalents",
    "bsa5": "short_term_investments",
    "bsa6": "trading_securities",
    "bsa7": "trading_securities_provision",
    "bsb108": "held_to_maturity_st",
    "bsa8": "short_term_receivables",
    "bsa9": "trade_receivables",
    "bsa10": "prepayments_to_suppliers",
    "bsa11": "internal_receivables_st",
    "bsa12": "construction_contract_receivables",
    "bsa159": "short_term_lending",
    "bsa13": "other_receivables_st",
    "bsa14": "bad_debt_provision_st",
    "bsi141": "assets_awaiting_resolution",
    "bsa15": "inventories",
    "bsa16": "inventory_goods",
    "bsa17": "inventory_provision",
    "bsa18": "other_current_assets",
    "bsa19": "prepaid_expenses_st",
    "bsa20": "vat_deductible",
    "bsa21": "tax_receivables_state",
    "bsa160": "govt_bond_repo",
    "bsa22": "other_current_assets_detail",
    "bsa23": "non_current_assets",
    "bsa24": "long_term_receivables",
    "bsa25": "lt_trade_receivables",
    "bsa161": "lt_prepayments",
    "bss134": "working_capital_subordinates",
    "bsa26": "lt_internal_receivables",
    "bsa162": "lt_lending",
    "bsa27": "lt_other_receivables",
    "bsa28": "lt_bad_debt_provision",
    "bsa29": "fixed_assets",
    "bsa30": "tangible_fixed_assets",
    "bsa31": "tangible_fixed_assets_cost",
    "bsa32": "tangible_fixed_assets_depreciation",
    "bsa33": "finance_lease_assets",
    "bsa34": "finance_lease_assets_cost",
    "bsa35": "finance_lease_assets_depreciation",
    "bsa36": "intangible_fixed_assets",
    "bsa37": "intangible_fixed_assets_cost",
    "bsa38": "intangible_fixed_assets_depreciation",
    "bsa40": "investment_property",
    "bsa41": "investment_property_cost",
    "bsa42": "investment_property_depreciation",
    "bsa163": "long_term_wip",
    "bsa164": "lt_wip_cost",
    "bsa188": "lt_construction_wip",
    "bsa43": "lt_financial_investments",
    "bsa44": "investments_in_subsidiaries",
    "bsa45": "investments_in_associates",
    "bsa46": "other_lt_investments",
    "bsa47": "provision_for_lt_investments",
    "bsa165": "ht_maturity_lt",
    "bsa49": "other_lt_assets",
    "bsa50": "lt_prepaid_expenses",
    "bsa51": "deferred_tax_assets",
    "bsa166": "lt_equipment_supplies",
    "bsa52": "other_lt_assets_detail",
    "bsa209": "goodwill",
    "bsa53": "total_assets",
    "bsa54": "total_liabilities",
    "bsa55": "current_liabilities",
    "bsa57": "st_trade_payables",
    "bsa58": "st_advances_from_customers",
    "bsa59": "st_taxes_payable",
    "bsa60": "st_payable_to_employees",
    "bsa61": "st_accrued_expenses",
    "bsa62": "st_internal_payables",
    "bsa63": "st_construction_payables",
    "bsa167": "st_unearned_revenue",
    "bsa64": "st_other_payables",
    "bsa56": "st_borrowings",
    "bsa65": "st_provisions",
    "bsa66": "bonus_welfare_fund",
    "bsa168": "price_stabilization_fund",
    "bsa169": "govt_bond_repo_payables",
    "bsa67": "non_current_liabilities",
    "bsa68": "lt_trade_payables",
    "bsa170": "lt_advances_from_customers",
    "bsa171": "lt_accrued_expenses",
    "bsa172": "lt_internal_payables_capital",
    "bsa69": "lt_internal_payables",
    "bsa76": "lt_unearned_revenue",
    "bsa70": "lt_other_payables",
    "bsa71": "lt_borrowings",
    "bsa173": "convertible_bonds",
    "bsa120": "preferred_shares_liabilities",
    "bsa72": "deferred_tax_liabilities",
    "bsa74": "lt_provisions",
    "bsa77": "science_technology_fund",
    "bsa73": "severance_allowance_provision",
    "bsa78": "total_equity",
    "bsa79": "owners_equity",
    "bsa80": "charter_capital",
    "bsa175": "common_shares",
    "bsa174": "preferred_shares",
    "bsa81": "share_premium",
    "bsa176": "convertible_bond_options",
    "bsa82": "other_owners_capital",
    "bsa83": "treasury_shares",
    "bsa84": "asset_revaluation_differences",
    "bsa85": "fx_differences",
    "bsa86": "investment_development_fund",
    "bsa91": "enterprise_reorganization_fund",
    "bsa89": "other_equity_funds",
    "bsa90": "retained_earnings",
    "bsa177": "accumulated_retained_earnings",
    "bsa178": "current_retained_earnings",
    "bsa211": "construction_investment_fund",
    "bsa210": "non_controlling_interests",
    "bsa87": "financial_reserve_fund",
    "bsa92": "other_funds",
    "bsa94": "funds",
    "bsa95": "minority_interest_equity",
    "bsa96": "total_resources",
}

VIETCAP_CF_COLUMNS = {
    "cfa1": "cfo_profit",
    "cfa2": "cfo_depreciation",
    "cfa18": "cfo_net",
    "cfa19": "cfi_purchases",
    "cfa20": "cfi_disposals",
    "cfa21": "cfi_loans_granted",
    "cfa22": "cfi_loans_collected",
    "cfa23": "cfi_investments",
    "cfa24": "cfi_divestments",
    "cfa25": "cfi_dividends_interest",
    "cfa26": "cfi_net",
    "cfa27": "cff_issue_shares",
    "cfa28": "cff_repurchase_shares",
    "cfa29": "cff_borrowings",
    "cfa30": "cff_repayments",
    "cfa31": "cff_finance_lease",
    "cfa32": "cff_dividends_paid",
    "cfa34": "cff_net",
    "cfa35": "net_cash_flow",
    "cfa36": "cash_beginning",
    "cfa37": "cf_fx_differences",
    "cfa38": "cash_ending",
}


# ── vnstock (Vietnamese) Mappings ─────────────────────────────────────────────

VNSTOCK_IS_COLUMNS = {
    "Doanh thu bán hàng và cung cấp dịch vụ": "revenue",
    "Các khoản giảm trừ doanh thu": "revenue_deductions",
    "Doanh thu thuần về bán hàng và cung cấp dịch vụ": "net_revenue",
    "Giá vốn hàng bán": "cost_of_goods_sold",
    "Lợi nhuận gộp về bán hàng và cung cấp dịch vụ": "gross_profit",
    "Doanh thu hoạt động tài chính": "financial_income",
    "Chi phí tài chính": "financial_expenses",
    "Trong đó: Chi phí lãi vay": "interest_expenses",
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
    "Lợi nhuận sau thuế của cổ đông của Công ty mẹ": "parent_profit_after_tax",
    "Lãi cơ bản trên cổ phiếu": "eps",
}

VNSTOCK_BS_COLUMNS = {
    "TÀI SẢN": "total_assets",
    "A. TÀI SẢN NGẮN HẠN": "current_assets",
    "I. Tiền và các khoản tương đương tiền": "cash_and_equivalents",
    "II. Đầu tư tài chính ngắn hạn": "short_term_investments",
    "III. Các khoản phải thu ngắn hạn": "short_term_receivables",
    "1. Phải thu ngắn hạn của khách hàng": "trade_receivables",
    "7. Dự phòng phải thu ngắn hạn khó đòi": "bad_debt_provision_st",
    "IV. Hàng tồn kho": "inventories",
    "V. Tài sản ngắn hạn khác": "other_current_assets",
    "B. TÀI SẢN DÀI HẠN": "non_current_assets",
    "II. Tài sản cố định": "fixed_assets",
    "1. Tài sản cố định hữu hình": "tangible_fixed_assets",
    "3. Tài sản cố định vô hình": "intangible_fixed_assets",
    "III. Bất động sản đầu tư": "investment_property",
}

VNSTOCK_CF_COLUMNS = {
    "Lưu chuyển tiền thuần từ hoạt động kinh doanh": "cfo_net",
    "Lưu chuyển tiền thuần từ hoạt động đầu tư": "cfi_net",
    "Lưu chuyển tiền thuần từ hoạt động tài chính": "cff_net",
    "Lưu chuyển tiền thuần trong kỳ": "net_cash_flow",
    "Tiền và tương đương tiền đầu kỳ": "cash_beginning",
    "Tiền và tương đương tiền cuối kỳ": "cash_ending",
}


# ── Template Row Mapping ──────────────────────────────────────────────────────

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
    # 20 is tax_rate (calculated)
    "deferred_tax_expense": 21,
    "profit_after_tax": 22,
    "minority_interest": 23,
    # 24 is profit margin
    "parent_profit_after_tax": 25,
    "eps": 27,
}

BS_ROW_MAP: dict[str, int] = {
    "current_assets": 33,
    "cash_and_equivalents": 34,
    "cash": 35,
    "cash_equivalents": 36,
    "short_term_investments": 37,
    "trading_securities": 38,
    "trading_securities_provision": 39,
    "held_to_maturity_st": 40,
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
    "lt_trade_receivables": 62,
    "lt_prepayments": 63,
    "working_capital_subordinates": 64,
    "lt_internal_receivables": 65,
    "lt_lending": 66,
    "lt_other_receivables": 67,
    "lt_bad_debt_provision": 68,
    "fixed_assets": 69,
    "tangible_fixed_assets": 70,
    "tangible_fixed_assets_cost": 71,
    "tangible_fixed_assets_depreciation": 72,
    "finance_lease_assets": 73,
    "finance_lease_assets_cost": 74,
    "finance_lease_assets_depreciation": 75,
    "intangible_fixed_assets": 76,
    "intangible_fixed_assets_cost": 77,
    "intangible_fixed_assets_depreciation": 78,
    "investment_property": 79,
    "investment_property_cost": 80,
    "investment_property_depreciation": 81,
    "long_term_wip": 82,
    "lt_wip_cost": 83,
    "lt_construction_wip": 84,
    "lt_financial_investments": 85,
    "investments_in_subsidiaries": 86,
    "investments_in_associates": 87,
    "other_lt_investments": 88,
    "provision_for_lt_investments": 89,
    "ht_maturity_lt": 90,
    "other_lt_investments_detail": 91,
    "other_lt_assets": 92,
    "lt_prepaid_expenses": 93,
    "deferred_tax_assets": 94,
    "lt_equipment_supplies": 95,
    "other_lt_assets_detail": 96,
    "goodwill": 97,
    "total_assets": 98,
    
    "total_liabilities": 101,
    "current_liabilities": 102,
    "st_trade_payables": 103,
    "st_advances_from_customers": 104,
    "st_taxes_payable": 105,
    "st_payable_to_employees": 106,
    "st_accrued_expenses": 107,
    "st_internal_payables": 108,
    "st_construction_payables": 109,
    "st_unearned_revenue": 110,
    "st_other_payables": 111,
    "st_borrowings": 112,
    "st_provisions": 113,
    "bonus_welfare_fund": 114,
    "price_stabilization_fund": 115,
    "govt_bond_repo_payables": 116,
    "non_current_liabilities": 117,
    "lt_trade_payables": 118,
    "lt_advances_from_customers": 119,
    "lt_accrued_expenses": 120,
    "lt_internal_payables_capital": 121,
    "lt_internal_payables": 122,
    "lt_unearned_revenue": 123,
    "lt_other_payables": 124,
    "lt_borrowings": 125,
    "convertible_bonds": 126,
    "preferred_shares_liabilities": 127,
    "deferred_tax_liabilities": 128,
    "lt_provisions": 129,
    "science_technology_fund": 130,
    "severance_allowance_provision": 131,
    
    "total_equity": 132,
    "owners_equity": 133,
    "charter_capital": 134,
    "common_shares": 135,
    "preferred_shares": 136,
    "share_premium": 137,
    "convertible_bond_options": 138,
    "other_owners_capital": 139,
    "treasury_shares": 140,
    "asset_revaluation_differences": 141,
    "fx_differences": 142,
    "investment_development_fund": 143,
    "enterprise_reorganization_fund": 144,
    "other_equity_funds": 145,
    "retained_earnings": 146,
    "accumulated_retained_earnings": 147,
    "current_retained_earnings": 148,
    "construction_investment_fund": 149,
    "non_controlling_interests": 150,
    "financial_reserve_fund": 151,
    "other_funds": 152,
    "funds": 153,
    "funds_formed_fixed_assets": 154,
    "minority_interest_equity": 155,
    "total_resources": 156,
}

CF_ROW_MAP: dict[str, int] = {
    "cfo_profit": 161,
    "cfo_depreciation": 162,
    "cfo_net": 165,
    "cfi_purchases": 168,
    "cfi_disposals": 169,
    "cfi_loans_granted": 170,
    "cfi_loans_collected": 171,
    "cfi_investments": 172,
    "cfi_divestments": 173,
    "cfi_dividends_interest": 174,
    "cfi_net": 179,
    "cff_issue_shares": 182,
    "cff_repurchase_shares": 183,
    "cff_borrowings": 184,
    "cff_repayments": 185,
    "cff_finance_lease": 186,
    "cff_dividends_paid": 187,
    "cff_net": 190,
    "net_cash_flow": 192,
    "cash_beginning": 193,
    "cf_fx_differences": 194,
    "cash_ending": 195,
}


def _normalise_df(
    df: pd.DataFrame,
    report_type: str,
    year_from: int,
    year_to: int,
) -> dict[str, dict[int, Any]]:
    """
    Normalise a DataFrame into a standardised dict.
    """
    source = df.attrs.get("source", "vnstock")
    result: dict[str, dict[int, Any]] = {}
    
    if source == "llm":
        # LLM returns data already mapped to internal keys + 'yearReport'
        year_col = "yearReport"
        if year_col in df.columns:
            df_filtered = df.copy()
            df_filtered[year_col] = df_filtered[year_col].astype(int)
            df_filtered = df_filtered[
                (df_filtered[year_col] >= year_from) & (df_filtered[year_col] <= year_to)
            ]
            for internal_key in df_filtered.columns:
                if internal_key == year_col:
                    continue
                result[internal_key] = {
                    int(row[year_col]): float(row[internal_key]) if pd.notna(row[internal_key]) else 0
                    for _, row in df_filtered.iterrows()
                }
        return result

    if source == "vietcap_direct":
        col_map = {
            "income_statement": VIETCAP_IS_COLUMNS,
            "balance_sheet": VIETCAP_BS_COLUMNS,
            "cash_flow": VIETCAP_CF_COLUMNS,
        }.get(report_type, {})
        year_col = "yearReport"
    else:
        col_map = {
            "income_statement": VNSTOCK_IS_COLUMNS,
            "balance_sheet": VNSTOCK_BS_COLUMNS,
            "cash_flow": VNSTOCK_CF_COLUMNS,
        }.get(report_type, {})
        year_col = None
        for candidate in ["year", "yearReport", "Năm", "Year"]:
            if candidate in df.columns:
                year_col = candidate
                break

    if year_col and year_col in df.columns:
        df_filtered = df.copy()
        df_filtered[year_col] = df_filtered[year_col].astype(int)
        df_filtered = df_filtered[
            (df_filtered[year_col] >= year_from) & (df_filtered[year_col] <= year_to)
        ]

        for code, internal_key in col_map.items():
            if code in df_filtered.columns:
                result[internal_key] = {
                    int(row[year_col]): float(row[code]) if pd.notna(row[code]) else 0
                    for _, row in df_filtered.iterrows()
                }
    else:
        # Fallback for vnstock "metric as rows" format or Custom CafeF format
        if df.empty: return {}
        metric_col = df.columns[0]
        for _, row in df.iterrows():
            metric_name = str(row[metric_col]).strip()
            
            # CafeF headers usually have prepended numbers
            if source == "cafef":
                metric_name = re.sub(r'^\d+\.\s*', '', metric_name)
                metric_name = re.sub(r'\s*\(.*?\)\s*$', '', metric_name)

            internal_key = col_map.get(metric_name)
            
            if not internal_key:
                 cleaned = " ".join(metric_name.split()).lower()
                 for k, v in col_map.items():
                     if k.lower() in cleaned or cleaned in k.lower():
                         internal_key = v
                         break
                         
            if not internal_key:
                continue
            
            yearly_data = {}
            for col in df.columns[1:]:
                try:
                    year_str = str(col).strip()
                    if "-" in year_str:
                        year = int(year_str[:4])
                    else:
                        year = int(year_str)
                        
                    if year_from <= year <= year_to:
                        val = row[col]
                        yearly_data[year] = float(val) if pd.notna(val) else 0
                except:
                    continue
            if yearly_data:
                result[internal_key] = yearly_data

    return result


def map_financial_data(
    reports: dict[str, list[pd.DataFrame]],
    year_from: int,
    year_to: int,
) -> dict[str, dict[str, dict[int, Any]]]:
    """Map fetched reports into standardised structure and merge multiple sources."""
    mapped = {}
    for report_type, dfs in reports.items():
        if not dfs: continue
        
        merged_report_data = {}
        for df in dfs:
            source_data = _normalise_df(df, report_type, year_from, year_to)
            for internal_key, year_dict in source_data.items():
                if internal_key not in merged_report_data:
                    merged_report_data[internal_key] = {}
                for year, val in year_dict.items():
                    if year not in merged_report_data[internal_key] or pd.isna(merged_report_data[internal_key][year]):
                        merged_report_data[internal_key][year] = val
                        
        mapped[report_type] = merged_report_data
        
    return mapped

def get_row_map(report_type: str) -> dict[str, int]:
    """Return the row mapping for a given report type."""
    return {
        "income_statement": PL_ROW_MAP,
        "balance_sheet": BS_ROW_MAP,
        "cash_flow": CF_ROW_MAP,
    }.get(report_type, {})
