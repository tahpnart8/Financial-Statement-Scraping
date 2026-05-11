import logging
import json
import time
import google.generativeai as genai
from typing import Optional, Dict, Any
from app.config import settings

logger = logging.getLogger(__name__)

# ── Danh sách TOÀN BỘ chỉ số tài chính cần trích xuất ──────────────────────
# Các key này CHÍNH XÁC khớp với data_mapper.py và excel_writer.py

INCOME_STATEMENT_KEYS = {
    "revenue": "Doanh thu bán hàng và cung cấp dịch vụ",
    "revenue_deductions": "Các khoản giảm trừ doanh thu",
    "net_revenue": "Doanh thu thuần về bán hàng và cung cấp dịch vụ",
    "cost_of_goods_sold": "Giá vốn hàng bán",
    "gross_profit": "Lợi nhuận gộp về bán hàng và cung cấp dịch vụ",
    "financial_income": "Doanh thu hoạt động tài chính",
    "financial_expenses": "Chi phí tài chính",
    "interest_expenses": "Trong đó: Chi phí lãi vay",
    "jv_profit_loss": "Phần lãi/lỗ trong công ty liên doanh, liên kết",
    "selling_expenses": "Chi phí bán hàng",
    "admin_expenses": "Chi phí quản lý doanh nghiệp",
    "operating_profit": "Lợi nhuận thuần từ hoạt động kinh doanh",
    "other_income": "Thu nhập khác",
    "other_expenses": "Chi phí khác",
    "other_profit": "Lợi nhuận khác",
    "profit_before_tax": "Tổng lợi nhuận kế toán trước thuế",
    "current_tax_expense": "Chi phí thuế TNDN hiện hành",
    "deferred_tax_expense": "Chi phí thuế TNDN hoãn lại",
    "profit_after_tax": "Lợi nhuận sau thuế thu nhập doanh nghiệp",
    "minority_interest": "Lợi ích của cổ đông thiểu số",
    "parent_profit_after_tax": "Lợi nhuận sau thuế của cổ đông của Công ty mẹ",
    "eps": "Lãi cơ bản trên cổ phiếu (VNĐ)",
}

BALANCE_SHEET_KEYS = {
    "current_assets": "A. Tài sản ngắn hạn",
    "cash_and_equivalents": "I. Tiền và các khoản tương đương tiền",
    "cash": "1. Tiền",
    "cash_equivalents": "2. Các khoản tương đương tiền",
    "short_term_investments": "II. Đầu tư tài chính ngắn hạn",
    "trading_securities": "1. Chứng khoán kinh doanh",
    "trading_securities_provision": "2. Dự phòng giảm giá chứng khoán kinh doanh",
    "held_to_maturity_st": "3. Đầu tư nắm giữ đến ngày đáo hạn (ngắn hạn)",
    "short_term_receivables": "III. Các khoản phải thu ngắn hạn",
    "trade_receivables": "1. Phải thu ngắn hạn của khách hàng",
    "prepayments_to_suppliers": "2. Trả trước cho người bán ngắn hạn",
    "internal_receivables_st": "3. Phải thu nội bộ ngắn hạn",
    "construction_contract_receivables": "4. Phải thu theo tiến độ kế hoạch hợp đồng xây dựng",
    "short_term_lending": "5. Phải thu về cho vay ngắn hạn",
    "other_receivables_st": "6. Phải thu ngắn hạn khác",
    "bad_debt_provision_st": "7. Dự phòng phải thu ngắn hạn khó đòi",
    "assets_awaiting_resolution": "8. Tài sản thiếu chờ xử lý",
    "inventories": "IV. Hàng tồn kho (tổng)",
    "inventory_goods": "1. Hàng tồn kho",
    "inventory_provision": "2. Dự phòng giảm giá hàng tồn kho",
    "other_current_assets": "V. Tài sản ngắn hạn khác",
    "prepaid_expenses_st": "1. Chi phí trả trước ngắn hạn",
    "vat_deductible": "2. Thuế GTGT được khấu trừ",
    "tax_receivables_state": "3. Thuế và các khoản khác phải thu của nhà nước",
    "govt_bond_repo": "4. Giao dịch mua bán lại trái phiếu chính phủ",
    "other_current_assets_detail": "5. Tài sản ngắn hạn khác (chi tiết)",
    "non_current_assets": "B. Tài sản dài hạn",
    "long_term_receivables": "I. Các khoản phải thu dài hạn",
    "lt_trade_receivables": "1. Phải thu dài hạn của khách hàng",
    "lt_prepayments": "2. Trả trước cho người bán dài hạn",
    "working_capital_subordinates": "3. Vốn kinh doanh ở các đơn vị trực thuộc",
    "lt_internal_receivables": "4. Phải thu nội bộ dài hạn",
    "lt_lending": "5. Phải thu về cho vay dài hạn",
    "lt_other_receivables": "6. Phải thu dài hạn khác",
    "lt_bad_debt_provision": "7. Dự phòng phải thu dài hạn khó đòi",
    "fixed_assets": "II. Tài sản cố định",
    "tangible_fixed_assets": "1. Tài sản cố định hữu hình (giá trị còn lại)",
    "tangible_fixed_assets_cost": "   - Nguyên giá TSCĐ hữu hình",
    "tangible_fixed_assets_depreciation": "   - Giá trị hao mòn lũy kế TSCĐ hữu hình",
    "finance_lease_assets": "2. Tài sản cố định thuê tài chính (giá trị còn lại)",
    "finance_lease_assets_cost": "   - Nguyên giá TSCĐ thuê tài chính",
    "finance_lease_assets_depreciation": "   - Giá trị hao mòn lũy kế TSCĐ thuê tài chính",
    "intangible_fixed_assets": "3. Tài sản cố định vô hình (giá trị còn lại)",
    "intangible_fixed_assets_cost": "   - Nguyên giá TSCĐ vô hình",
    "intangible_fixed_assets_depreciation": "   - Giá trị hao mòn lũy kế TSCĐ vô hình",
    "investment_property": "III. Bất động sản đầu tư (giá trị còn lại)",
    "investment_property_cost": "   - Nguyên giá BĐS đầu tư",
    "investment_property_depreciation": "   - Giá trị hao mòn lũy kế BĐS đầu tư",
    "long_term_wip": "IV. Tài sản dở dang dài hạn",
    "lt_wip_cost": "1. Chi phí sản xuất, kinh doanh dở dang dài hạn",
    "lt_construction_wip": "2. Chi phí xây dựng cơ bản dở dang",
    "lt_financial_investments": "V. Đầu tư tài chính dài hạn",
    "investments_in_subsidiaries": "1. Đầu tư vào công ty con",
    "investments_in_associates": "2. Đầu tư vào công ty liên kết, liên doanh",
    "other_lt_investments": "3. Đầu tư góp vốn vào đơn vị khác",
    "provision_for_lt_investments": "4. Dự phòng đầu tư tài chính dài hạn",
    "ht_maturity_lt": "5. Đầu tư nắm giữ đến ngày đáo hạn (dài hạn)",
    "other_lt_assets": "VI. Tài sản dài hạn khác",
    "lt_prepaid_expenses": "1. Chi phí trả trước dài hạn",
    "deferred_tax_assets": "2. Tài sản thuế thu nhập hoãn lại",
    "lt_equipment_supplies": "3. Thiết bị, vật tư, phụ tùng thay thế dài hạn",
    "other_lt_assets_detail": "4. Tài sản dài hạn khác (chi tiết)",
    "goodwill": "VII. Lợi thế thương mại",
    "total_assets": "TỔNG CỘNG TÀI SẢN",
    "total_liabilities": "A. NỢ PHẢI TRẢ (tổng)",
    "current_liabilities": "I. Nợ ngắn hạn",
    "st_trade_payables": "1. Phải trả người bán ngắn hạn",
    "st_advances_from_customers": "2. Người mua trả tiền trước ngắn hạn",
    "st_taxes_payable": "3. Thuế và các khoản phải nộp Nhà nước",
    "st_payable_to_employees": "4. Phải trả người lao động",
    "st_accrued_expenses": "5. Chi phí phải trả ngắn hạn",
    "st_internal_payables": "6. Phải trả nội bộ ngắn hạn",
    "st_construction_payables": "7. Phải trả theo tiến độ kế hoạch hợp đồng xây dựng",
    "st_unearned_revenue": "8. Doanh thu chưa thực hiện ngắn hạn",
    "st_other_payables": "9. Phải trả ngắn hạn khác",
    "st_borrowings": "10. Vay và nợ thuê tài chính ngắn hạn",
    "st_provisions": "11. Dự phòng phải trả ngắn hạn",
    "bonus_welfare_fund": "12. Quỹ khen thưởng, phúc lợi",
    "price_stabilization_fund": "13. Quỹ bình ổn giá",
    "govt_bond_repo_payables": "14. Giao dịch mua bán lại trái phiếu Chính phủ",
    "non_current_liabilities": "II. Nợ dài hạn",
    "lt_trade_payables": "1. Phải trả người bán dài hạn",
    "lt_advances_from_customers": "2. Người mua trả tiền trước dài hạn",
    "lt_accrued_expenses": "3. Chi phí phải trả dài hạn",
    "lt_internal_payables_capital": "4. Phải trả nội bộ về vốn kinh doanh",
    "lt_internal_payables": "5. Phải trả nội bộ dài hạn",
    "lt_unearned_revenue": "6. Doanh thu chưa thực hiện dài hạn",
    "lt_other_payables": "7. Phải trả dài hạn khác",
    "lt_borrowings": "8. Vay và nợ thuê tài chính dài hạn",
    "convertible_bonds": "9. Trái phiếu chuyển đổi",
    "preferred_shares_liabilities": "10. Cổ phiếu ưu đãi (Nợ)",
    "deferred_tax_liabilities": "11. Thuế thu nhập hoãn lại phải trả",
    "lt_provisions": "12. Dự phòng phải trả dài hạn",
    "science_technology_fund": "13. Quỹ phát triển khoa học và công nghệ",
    "severance_allowance_provision": "14. Dự phòng trợ cấp mất việc làm",
    "total_equity": "B. VỐN CHỦ SỞ HỮU (tổng)",
    "owners_equity": "I. Vốn chủ sở hữu",
    "charter_capital": "1. Vốn góp của chủ sở hữu",
    "common_shares": "   - Cổ phiếu phổ thông có quyền biểu quyết",
    "preferred_shares": "   - Cổ phiếu ưu đãi",
    "share_premium": "2. Thặng dư vốn cổ phần",
    "convertible_bond_options": "3. Quyền chọn chuyển đổi trái phiếu",
    "other_owners_capital": "4. Vốn khác của chủ sở hữu",
    "treasury_shares": "5. Cổ phiếu quỹ",
    "asset_revaluation_differences": "6. Chênh lệch đánh giá lại tài sản",
    "fx_differences": "7. Chênh lệch tỷ giá hối đoái",
    "investment_development_fund": "8. Quỹ đầu tư phát triển",
    "enterprise_reorganization_fund": "9. Quỹ hỗ trợ sắp xếp doanh nghiệp",
    "other_equity_funds": "10. Quỹ khác thuộc vốn chủ sở hữu",
    "retained_earnings": "11. Lợi nhuận sau thuế chưa phân phối",
    "accumulated_retained_earnings": "   - LNST chưa phân phối lũy kế đến cuối kỳ trước",
    "current_retained_earnings": "   - LNST chưa phân phối kỳ này",
    "construction_investment_fund": "12. Nguồn vốn đầu tư XDCB",
    "non_controlling_interests": "13. Lợi ích cổ đông không kiểm soát",
    "financial_reserve_fund": "14. Quỹ dự phòng tài chính",
    "total_resources": "TỔNG CỘNG NGUỒN VỐN",
}

CASH_FLOW_KEYS = {
    "cfo_profit": "Lãi/lỗ sau thuế (dòng đầu Lưu chuyển tiền)",
    "cfo_depreciation": "Khấu hao TSCĐ",
    "cfo_net": "Lưu chuyển tiền thuần từ hoạt động kinh doanh",
    "cfi_purchases": "1. Tiền chi để mua sắm, xây dựng TSCĐ và các tài sản dài hạn khác",
    "cfi_disposals": "2. Tiền thu từ thanh lý, nhượng bán TSCĐ",
    "cfi_loans_granted": "3. Tiền chi cho vay, mua các công cụ nợ của đơn vị khác",
    "cfi_loans_collected": "4. Tiền thu hồi cho vay, bán lại các công cụ nợ",
    "cfi_investments": "5. Tiền chi đầu tư góp vốn vào đơn vị khác",
    "cfi_divestments": "6. Tiền thu hồi đầu tư góp vốn vào đơn vị khác",
    "cfi_dividends_interest": "7. Tiền thu lãi cho vay, cổ tức và lợi nhuận được chia",
    "cfi_net": "Lưu chuyển tiền thuần từ hoạt động đầu tư",
    "cff_issue_shares": "1. Tiền thu từ phát hành cổ phiếu, nhận vốn góp",
    "cff_repurchase_shares": "2. Tiền chi trả vốn góp cho các chủ sở hữu, mua lại cổ phiếu",
    "cff_borrowings": "3. Tiền thu từ đi vay",
    "cff_repayments": "4. Tiền trả nợ gốc vay",
    "cff_finance_lease": "5. Tiền trả nợ gốc thuê tài chính",
    "cff_dividends_paid": "6. Cổ tức, lợi nhuận đã trả cho chủ sở hữu",
    "cff_net": "Lưu chuyển tiền thuần từ hoạt động tài chính",
    "net_cash_flow": "Lưu chuyển tiền thuần trong kỳ",
    "cash_beginning": "Tiền và tương đương tiền đầu kỳ",
    "cf_fx_differences": "Ảnh hưởng của thay đổi tỷ giá hối đoái quy đổi ngoại tệ",
    "cash_ending": "Tiền và tương đương tiền cuối kỳ",
}


def _build_key_list_for_prompt() -> str:
    """Tạo danh sách key JSON cho prompt, dùng format: key (Tên tiếng Việt)"""
    lines = []
    lines.append("=== KẾT QUẢ HOẠT ĐỘNG KINH DOANH (Income Statement) ===")
    for key, vn_name in INCOME_STATEMENT_KEYS.items():
        lines.append(f'  "{key}": <số> // {vn_name}')
    
    lines.append("\n=== BẢNG CÂN ĐỐI KẾ TOÁN (Balance Sheet) ===")
    for key, vn_name in BALANCE_SHEET_KEYS.items():
        lines.append(f'  "{key}": <số> // {vn_name}')
    
    lines.append("\n=== LƯU CHUYỂN TIỀN TỆ (Cash Flow Statement) ===")
    for key, vn_name in CASH_FLOW_KEYS.items():
        lines.append(f'  "{key}": <số> // {vn_name}')
    
    return "\n".join(lines)


def process_pdf_with_gemini(pdf_path: str, ticker: str, year: int) -> tuple[Optional[Dict[str, Any]], Optional[str]]:
    """
    Sử dụng Google Gemini 2.5 Flash để đọc trực tiếp file PDF (kể cả dạng scan)
    và trích xuất TOÀN BỘ dữ liệu tài chính sang định dạng JSON.
    Returns: (Result_JSON, Error_Message)
    """
    if not settings.GEMINI_API_KEY:
        logger.error("GEMINI_API_KEY is not set in environment variables.")
        return None, "GEMINI_API_KEY chưa được cấu hình trên server (Render)."

    try:
        # 1. Cấu hình Gemini
        genai.configure(api_key=settings.GEMINI_API_KEY)
        model = genai.GenerativeModel("gemini-2.5-flash")

        # 2. Upload file PDF lên Gemini File API
        logger.info(f"Uploading PDF to Gemini: {pdf_path}")
        uploaded_file = genai.upload_file(path=pdf_path, display_name=f"BCTC_{ticker}_{year}")
        
        # Đợi file được xử lý
        while uploaded_file.state.name == "PROCESSING":
            time.sleep(2)
            uploaded_file = genai.get_file(uploaded_file.name)

        if uploaded_file.state.name == "FAILED":
            logger.error("Gemini file processing failed.")
            return None, "Google Gemini từ chối hoặc không thể xử lý file PDF này."

        key_list = _build_key_list_for_prompt()

        # 3. Tạo Prompt trích xuất TOÀN BỘ chỉ số
        prompt = f"""Bạn là một chuyên gia phân tích tài chính cao cấp tại Việt Nam.
Nhiệm vụ: Đọc file Báo cáo tài chính (BCTC) đính kèm của công ty {ticker} cho năm tài chính {year}.

Hãy trích xuất TOÀN BỘ các chỉ số tài chính từ 3 bảng chính:
1. Kết quả hoạt động kinh doanh (Income Statement / Báo cáo KQKD)
2. Bảng cân đối kế toán (Balance Sheet / BCĐKT)
3. Lưu chuyển tiền tệ (Cash Flow Statement / LCTT)

QUY TẮC BẮT BUỘC:
- Đơn vị: Giữ nguyên đơn vị gốc trong báo cáo (thường là VNĐ hoặc triệu VNĐ). KHÔNG nhân/chia thêm.
- Số âm: Nếu số nằm trong ngoặc đơn ví dụ (123.456.789) thì chuyển thành -123456789.
- Dấu phân cách hàng nghìn: Loại bỏ hết (ví dụ: 1.234.567 → 1234567).
- Dấu thập phân: Giữ nguyên nếu có (ví dụ: EPS = 3.456 → 3456 nếu không có phần thập phân, hoặc 3456.78 nếu có).
- Nếu KHÔNG TÌM THẤY chỉ số trong BCTC, để giá trị = 0.
- Lấy cột "Năm nay" hoặc "Cuối kỳ" (KHÔNG lấy cột "Năm trước" hay "Đầu kỳ").
- Trả về JSON thuần túy. KHÔNG thêm bất kỳ text giải thích nào.

DANH SÁCH CÁC KEY JSON VÀ TÊN TIẾNG VIỆT TƯƠNG ỨNG:
{key_list}

Trả về JSON với đúng các key trên. Ví dụ:
{{
  "ticker": "{ticker}",
  "year": {year},
  "revenue": 1500000000000,
  "net_revenue": 1480000000000,
  "cost_of_goods_sold": 1100000000000,
  ...tất cả các key khác...
}}
"""

        # 4. Gọi Gemini để trích xuất
        logger.info(f"Calling Gemini 2.5 Flash for full extraction (~150 indicators)...")
        response = model.generate_content(
            [uploaded_file, prompt],
            generation_config=genai.GenerationConfig(
                response_mime_type="application/json",
            ),
        )

        # 5. Dọn dẹp file trên Google Cloud
        try:
            genai.delete_file(uploaded_file.name)
            logger.info(f"Deleted temp file from Gemini API: {uploaded_file.name}")
        except Exception as e:
            logger.warning(f"Failed to delete temp file from Gemini: {e}")

        # 6. Parse và trả về kết quả
        if response and response.text:
            try:
                result = json.loads(response.text)
                logger.info(f"Successfully extracted {len(result)} indicators for {ticker}/{year}")
                return result, None
            except json.JSONDecodeError as e:
                logger.error(f"JSON Parse Error: {e} - Raw text: {response.text}")
                return None, "Gemini không trả về đúng định dạng JSON."
        
        return None, "Gemini không trả về bất kỳ dữ liệu nào."

    except Exception as e:
        logger.error(f"Error processing with Gemini: {e}")
        return None, f"Lỗi kết nối Gemini API: {str(e)}"


def process_markdown_with_llm(markdown_text: str, ticker: str, year: int) -> Optional[Dict[str, Any]]:
    """Legacy fallback - deprecated."""
    logger.warning("process_markdown_with_llm is deprecated. Use process_pdf_with_gemini instead.")
    return None
