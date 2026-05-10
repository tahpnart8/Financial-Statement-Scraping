"""
Jobs Router
===========
Endpoints for creating, polling, and downloading BCTC extraction jobs.
"""
from __future__ import annotations

import os
import logging

from fastapi import APIRouter, HTTPException
from fastapi.responses import FileResponse

from app.models import (
    JobCreateRequest,
    JobCreateResponse,
    JobStatusResponse,
    JobStatus,
)
from app.jobs.manager import job_manager

logger = logging.getLogger(__name__)

router = APIRouter(prefix="/api/jobs", tags=["Jobs"])


@router.post(
    "",
    response_model=JobCreateResponse,
    status_code=202,
    summary="Tạo job trích xuất BCTC",
    description=(
        "Tạo một job mới để trích xuất dữ liệu báo cáo tài chính. "
        "Job sẽ được xử lý bất đồng bộ trong nền. "
        "Sử dụng endpoint GET /api/jobs/{job_id} để theo dõi trạng thái."
    ),
)
async def create_job(request: JobCreateRequest):
    """Create a new BCTC extraction job."""
    job_id = job_manager.create_job(
        tickers=request.tickers,
        report_type=request.report_type.value,
        period=request.period.value,
        year_from=request.year_from,
        year_to=request.year_to,
    )

    logger.info(
        f"Job created: {job_id} | Tickers: {request.tickers} | "
        f"Type: {request.report_type} | Period: {request.period} | "
        f"Years: {request.year_from}-{request.year_to}"
    )

    return JobCreateResponse(job_id=job_id)


@router.get(
    "/{job_id}",
    response_model=JobStatusResponse,
    summary="Kiểm tra trạng thái job",
    description="Polling endpoint để kiểm tra tiến trình xử lý của job.",
)
async def get_job_status(job_id: str):
    """Get the status of an existing job."""
    job = job_manager.get_job(job_id)
    if not job:
        raise HTTPException(
            status_code=404,
            detail=f"Job {job_id} không tồn tại hoặc đã hết hạn.",
        )

    download_url = None
    if job.status == JobStatus.COMPLETED and job.output_files:
        download_url = f"/api/jobs/{job_id}/download"

    return JobStatusResponse(
        job_id=job.job_id,
        status=job.status,
        progress=job.progress,
        message=job.message,
        download_url=download_url,
        error=job.error,
        created_at=job.created_at,
        completed_at=job.completed_at,
    )


@router.get(
    "/{job_id}/download",
    summary="Tải file Excel kết quả",
    description="Tải file Excel đã được generate. Chỉ khả dụng khi job đã hoàn thành.",
    responses={
        200: {
            "content": {
                "application/vnd.openxmlformats-officedocument.spreadsheetml.sheet": {}
            },
            "description": "File Excel BCTC",
        },
    },
)
async def download_result(job_id: str):
    """Download the generated Excel file."""
    job = job_manager.get_job(job_id)
    if not job:
        raise HTTPException(status_code=404, detail="Job không tồn tại.")

    if job.status != JobStatus.COMPLETED:
        raise HTTPException(
            status_code=400,
            detail=f"Job chưa hoàn thành. Trạng thái hiện tại: {job.status.value}",
        )

    if not job.output_files:
        raise HTTPException(status_code=404, detail="Không tìm thấy file kết quả.")

    # Return the first file (for single ticker) or we could zip multiple
    filepath = job.output_files[0]
    if not os.path.exists(filepath):
        raise HTTPException(status_code=404, detail="File đã bị xóa hoặc hết hạn.")

    filename = os.path.basename(filepath)
    return FileResponse(
        path=filepath,
        filename=filename,
        media_type="application/vnd.openxmlformats-officedocument.spreadsheetml.sheet",
    )
