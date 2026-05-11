import os
import logging
import tempfile
import threading
from uuid import uuid4

from fastapi import APIRouter, HTTPException, UploadFile, File, Form
from fastapi.responses import FileResponse

from app.models import (
    GenerateExcelRequest,
    GenerateExcelResponse
)
from app.services.llm_processor import process_pdf_with_gemini
from app.services.excel_writer import generate_excel
from app.config import settings

logger = logging.getLogger(__name__)

router = APIRouter(prefix="/api/jobs", tags=["Jobs"])

# ── In-memory Job Store ───────────────────────────────────────────────────────
# Simple dict-based store. Sufficient for single-instance Render deployment.
# Jobs auto-clean after result is fetched.

jobs_store: dict[str, dict] = {}


def _run_extraction(job_id: str, pdf_path: str, ticker: str, year: int):
    """Background worker: runs Gemini extraction and stores result."""
    try:
        json_data, error_msg = process_pdf_with_gemini(pdf_path, ticker, year)

        if json_data:
            jobs_store[job_id] = {
                "status": "done",
                "ticker": ticker,
                "year": year,
                "data": json_data,
                "message": "Trích xuất thành công bằng Gemini AI",
            }
        else:
            jobs_store[job_id] = {
                "status": "error",
                "detail": f"Lỗi AI: {error_msg or 'Không xác định'}",
            }
    except Exception as e:
        logger.error(f"Background extraction failed for {job_id}: {e}")
        jobs_store[job_id] = {
            "status": "error",
            "detail": f"Lỗi hệ thống: {str(e)}",
        }
    finally:
        # Clean up temp PDF
        if os.path.exists(pdf_path):
            os.remove(pdf_path)


# ── Endpoints ─────────────────────────────────────────────────────────────────

@router.post(
    "/extract-pdf",
    summary="Upload PDF và bắt đầu trích xuất (async)",
)
async def extract_pdf(
    ticker: str = Form(...),
    year: int = Form(...),
    file: UploadFile = File(...)
):
    """
    Nhận 1 file PDF, lưu tạm, khởi chạy trích xuất Gemini ở background.
    Trả về job_id ngay lập tức (< 2 giây) để frontend poll kết quả.
    """
    logger.info(f"Received PDF for {ticker} - {year}")

    # Save uploaded file to temp (persistent, not auto-delete)
    with tempfile.NamedTemporaryFile(delete=False, suffix=".pdf") as tmp:
        tmp.write(await file.read())
        tmp_path = tmp.name

    # Create job
    job_id = str(uuid4())
    jobs_store[job_id] = {"status": "processing"}

    # Start background thread (does NOT block the response)
    thread = threading.Thread(
        target=_run_extraction,
        args=(job_id, tmp_path, ticker, year),
        daemon=True,
    )
    thread.start()

    logger.info(f"Job {job_id} started in background for {ticker}/{year}")
    return {"job_id": job_id, "status": "processing"}


@router.get(
    "/status/{job_id}",
    summary="Kiểm tra trạng thái job trích xuất",
)
async def get_job_status(job_id: str):
    """
    Frontend poll endpoint này mỗi 3 giây.
    Returns: {status: "processing"} hoặc {status: "done", data: {...}} hoặc {status: "error", detail: "..."}
    """
    job = jobs_store.get(job_id)
    if not job:
        raise HTTPException(status_code=404, detail="Job không tồn tại hoặc đã hết hạn.")
    return job


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
