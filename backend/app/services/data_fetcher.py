"""
Data Fetcher Service
====================
PURE PDF EXTRACTION STRATEGY:
Extracts all financial data exclusively from Audited Financial Statements (PDFs)
using Llama 3 via Groq API. No web HTML scraping or direct numeric APIs are used.
"""
from __future__ import annotations

import logging
import time
import os
from typing import Optional

import pandas as pd
import numpy as np

from app.config import settings
from app.services.pdf_downloader import get_bctc_pdf_url, download_pdf
from app.services.pdf_extractor import extract_financial_tables_from_pdf
from app.services.llm_processor import process_markdown_with_llm

logger = logging.getLogger(__name__)


def _fetch_from_pdf_ai(ticker: str, report_type: str, year: int, user_pdf_path: str = None) -> Optional[pd.DataFrame]:
    """
    Executes the AI Pipeline for a specific year: 
    Download PDF (or use cache/upload) -> OCR/Extract Tables -> Groq Llama -> DataFrame
    """
    logger.info(f"Starting AI PDF Pipeline for {ticker} {year}")
    
    local_pdf_path = None

    # 1. Determine which PDF to use
    if user_pdf_path:
        if os.path.exists(user_pdf_path):
            logger.info(f"Using user-uploaded file for {ticker} {year}")
            local_pdf_path = user_pdf_path
        elif user_pdf_path.startswith("http"):
            logger.info(f"Using user-provided URL for {ticker} {year}: {user_pdf_path}")
            local_pdf_path = download_pdf(user_pdf_path, ticker, year)
    
    if not local_pdf_path:
        # Auto-search (might be blocked, but we keep it as a hail mary)
        url = get_bctc_pdf_url(ticker, year)
        if url:
            local_pdf_path = download_pdf(url, ticker, year)
            
    if not local_pdf_path:
        logger.warning(f"Could not resolve PDF for {ticker} {year}")
        return None

            
    try:
        # 2. Extract Markdown Tables
        markdown_data = extract_financial_tables_from_pdf(local_pdf_path)
        if not markdown_data:
            logger.warning(f"No tables extracted from PDF for {ticker} {year}")
            return None
            
        # 3. LLM Processing (extracting 150+ fields)
        structured_data = process_markdown_with_llm(markdown_data, ticker, year)
        if not structured_data:
            logger.error(f"LLM failed to process markdown for {ticker} {year}")
            return None
            
        # 4. Convert to DataFrame
        structured_data['yearReport'] = year
        df = pd.DataFrame([structured_data])
        # Mark source as 'llm'
        df.attrs["source"] = "llm" 
        
        logger.info(f"Successfully extracted full AI data for {ticker} {year}")
        return df
        
    except Exception as e:
        logger.error(f"Exception in AI Pipeline for {ticker} {year}: {e}")
        return None
        
    # NOTE: We do NOT delete the PDF here in the 'finally' block anymore.
    # Caching handles it. The JobManager will periodically clean up old PDFs in /tmp.


def fetch_financial_data(
    ticker: str,
    report_type: str,
    period: str = "year",
    pdf_path: str = None,
    pdf_year: int = None,
    year_from: int = 2015,
    year_to: int = 2024
) -> list[pd.DataFrame]:
    """
    Fetch financial data using PURE PDF EXTRACTION.
    Iterates through all requested years and runs the AI pipeline for each.
    """
    if period.lower() not in ["year", "y"]:
        raise ValueError("Pure PDF AI Extraction currently only supports YEARLY data.")

    dfs = []
    
    for year in range(year_from, year_to + 1):
        # Use uploaded PDF if it matches the current year in the loop
        current_pdf = pdf_path if (pdf_path and pdf_year == year) else None
        
        df = _fetch_from_pdf_ai(ticker, report_type, year, current_pdf)
        if df is not None and not df.empty:
            dfs.append(df)
            
        # Rate limiting safety to avoid hammering APIs
        time.sleep(settings.FETCH_RATE_LIMIT_DELAY)

    if not dfs:
        raise ValueError(
            f"Không thể trích xuất dữ liệu {report_type} cho mã {ticker} từ PDF. "
            "Có thể hệ thống không tìm thấy file PDF trên nguồn công khai hoặc file bị lỗi."
        )
        
    return dfs


def fetch_all_reports(
    ticker: str,
    period: str = "year",
    year_from: int = 2015,
    year_to: int = 2024,
    pdf_path: str = None,
    pdf_year: int = None
) -> dict[str, list[pd.DataFrame]]:
    """
    Fetch all three financial reports for a ticker using pure PDF AI pipeline.
    Because the AI reads the entire document and extracts all 150+ fields at once,
    we only need to run the PDF pipeline ONCE per year, and copy the dataframe
    to all three report types.
    """
    reports = {
        "income_statement": [],
        "balance_sheet": [],
        "cash_flow": []
    }
    
    # We call fetch_financial_data once (e.g. for 'income_statement') and it returns
    # DataFrames containing ALL fields (since LLM extracts everything).
    # Then we distribute those DataFrames to all report types.
    
    logger.info(f"Initiating Pure PDF Extraction for {ticker} ({year_from}-{year_to})")
    dfs = fetch_financial_data(ticker, "all", period, pdf_path, pdf_year, year_from, year_to)
    
    reports["income_statement"] = dfs
    reports["balance_sheet"] = dfs
    reports["cash_flow"] = dfs
            
    return reports
