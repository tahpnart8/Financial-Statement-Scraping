import os
import logging
import tempfile
import uuid

from fastapi import APIRouter, HTTPException, UploadFile, File, Form
from fastapi.responses import FileResponse, JSONResponse

from app.models import (
    GenerateExcelRequest,
    ExtractPdfResponse,
    GenerateExcelResponse
)
from app.services.llm_processor import process_pdf_with_gemini
from app.services.excel_writer import generate_excel
from app.config import settings

logger = logging.getLogger(__name__)

router = APIRouter(prefix="/api/jobs", tags=["Jobs"])


@router.post(
    "/extract-pdf",
    response_model=ExtractPdfResponse,
    summary="Trích xuất dữ liệu BCTC từ 1 file PDF",
)
async def extract_pdf(
    ticker: str = Form(...),
    year: int = Form(...),
    file: UploadFile = File(...)
):
    """
    Nhận 1 file PDF, lưu tạm, dùng OCR/pdfplumber trích xuất bảng,
    sau đó gọi LLaMA để bóc tách thành JSON chuẩn.
    """
    logger.info(f"Received PDF for {ticker} - {year}")
    
    # Save uploaded file to temp
    with tempfile.NamedTemporaryFile(delete=False, suffix=".pdf") as tmp:
        tmp.write(await file.read())
        tmp_path = tmp.name

    try:
        # 1. Trích xuất trực tiếp bằng Gemini 2.5 Flash (Xử lý được cả PDF scan ảnh)
        json_data, error_msg = process_pdf_with_gemini(tmp_path, ticker, year)
        
        if not json_data:
            raise HTTPException(status_code=500, detail=f"Lỗi AI: {error_msg or 'Không xác định'}")

        return ExtractPdfResponse(
            ticker=ticker,
            year=year,
            data=json_data,
            message="Trích xuất thành công bằng Gemini AI"
        )
    finally:
        if os.path.exists(tmp_path):
            os.remove(tmp_path)


@router.post(
    "/generate-excel",
    response_model=GenerateExcelResponse,
    summary="Sinh file Excel từ tập JSON đã trích xuất",
)
async def generate_excel_endpoint(request: GenerateExcelRequest):
    """
    Nhận danh sách dữ liệu JSON các năm, ghép lại và sinh ra file Excel.
    """
    logger.info(f"Generating Excel for {request.ticker} ({request.year_from}-{request.year_to})")
    
    try:
        # Convert yearly_data into the nested dict format required by excel_writer
        # Format: {"income_statement": { "revenue": { 2022: 100, 2023: 120 } }, ...}
        mapped_data = {
            "income_statement": {},
            "balance_sheet": {},
            "cash_flow": {}
        }
        
        # Populate mapped_data
        for y_data in request.yearly_data:
            year = y_data.year
            data = y_data.data
            
            # Since LLM schema is flat, we just iterate through all keys and try to map them
            # We don't have a strict segregation of keys by section in the flat output,
            # so we'll just put them all into income_statement for now, OR better,
            # we can put them into all sections and let the excel_writer pick them up.
            
            for key, val in data.items():
                if key == "year": continue
                
                # Assign to all sections for simplicity, excel_writer will filter by its MAPs
                for section in mapped_data:
                    if key not in mapped_data[section]:
                        mapped_data[section][key] = {}
                    mapped_data[section][key][year] = val

        # Ensure output dir exists
        os.makedirs(settings.OUTPUT_DIR, exist_ok=True)
        
        # Generate file
        filepath = generate_excel(
            ticker=request.ticker,
            mapped_data=mapped_data,
            year_from=request.year_from,
            year_to=request.year_to,
            output_dir=settings.OUTPUT_DIR
        )
        
        filename = os.path.basename(filepath)
        download_url = f"/api/jobs/download/{filename}"
        
        return GenerateExcelResponse(download_url=download_url)
        
    except Exception as e:
        logger.error(f"Error generating Excel: {e}")
        raise HTTPException(status_code=500, detail=str(e))


@router.get(
    "/download/{filename}",
    summary="Tải file Excel kết quả",
)
async def download_result(filename: str):
    """Download the generated Excel file."""
    filepath = os.path.join(settings.OUTPUT_DIR, filename)
    if not os.path.exists(filepath):
        raise HTTPException(status_code=404, detail="File không tồn tại.")

    return FileResponse(
        path=filepath,
        filename=filename,
        media_type="application/vnd.openxmlformats-officedocument.spreadsheetml.sheet",
    )
