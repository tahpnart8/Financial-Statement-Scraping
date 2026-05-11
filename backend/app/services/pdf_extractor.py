import logging
import os
import re
from typing import Optional, List
import pdfplumber

logger = logging.getLogger(__name__)

def extract_financial_tables_from_pdf(pdf_path: str) -> Optional[str]:
    """
    Extracts financial tables from a PDF using pdfplumber.
    Returns the extracted tables as a Markdown formatted string.
    """
    logger.info(f"Extracting tables from PDF: {pdf_path}")
    markdown_output = []
    
    try:
        with pdfplumber.open(pdf_path) as pdf:
            all_pages_text = []
            
            for page_num, page in enumerate(pdf.pages):
                text = page.extract_text()
                if not text:
                    continue
                    
                # Trích xuất text với layout=True để giữ nguyên định dạng bảng (cột cách nhau bằng khoảng trắng)
                layout_text = page.extract_text(layout=True)
                all_pages_text.append((page_num + 1, layout_text))
                
                # Remove all whitespace, newlines, and convert to lower for robust comparison
                text_clean = re.sub(r'\s+', '', text.lower())
                
                # Heuristic to find financial statement pages
                if (
                    "bảngcânđốikếtoán" in text_clean or 
                    "kếtquảhoạtđộngkinhdoanh" in text_clean or 
                    "lưuchuyểntiềntệ" in text_clean or
                    "bangcandoiketoan" in text_clean or
                    "ketquahoatdongkinhdoanh" in text_clean or
                    "luuchuyentiente" in text_clean
                ):
                    logger.info(f"Found potential financial statement on page {page_num + 1}")
                    markdown_output.append(f"## Page {page_num + 1} Content\n")
                    markdown_output.append("```text\n")
                    markdown_output.append(layout_text)
                    markdown_output.append("\n```\n")
                        
        if not markdown_output:
            logger.warning("Heuristic failed. Falling back to extracting the first 12 pages to avoid Groq token limit.")
            # BCTC thường nằm ở trang 5-12. Ta lấy 12 trang đầu tiên đưa cho LLaMA tự phân tích.
            # Không lấy toàn bộ file để tránh lỗi vượt quá 8192 tokens của Groq (Context Window Exceeded).
            for page_num, layout_text in all_pages_text[:12]:
                markdown_output.append(f"## Page {page_num} Content\n")
                markdown_output.append("```text\n")
                markdown_output.append(layout_text)
                markdown_output.append("\n```\n")
            
        if not markdown_output:
            logger.warning("No readable text found in the PDF.")
            return None
            
        return "\n".join(markdown_output)
        
    except Exception as e:
        logger.error(f"Error extracting PDF {pdf_path}: {e}")
        return None
