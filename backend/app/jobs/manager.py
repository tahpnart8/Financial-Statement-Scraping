"""
Job Manager
===========
In-memory job queue for processing BCTC extraction requests asynchronously.
"""
from __future__ import annotations

import logging
import os
import threading
import time
import uuid
from datetime import datetime
from typing import Any, Optional

from app.config import settings
from app.models import JobStatus
from app.services.data_fetcher import fetch_financial_data, fetch_all_reports
from app.services.data_mapper import map_financial_data
from app.services.excel_writer import generate_excel

logger = logging.getLogger(__name__)


class JobInfo:
    """Container for job state."""

    def __init__(
        self,
        job_id: str,
        tickers: list[str],
        report_type: str,
        period: str,
        year_from: int,
        year_to: int,
        links: dict[str, str] = None
    ):
        self.job_id = job_id
        self.tickers = tickers
        self.report_type = report_type
        self.period = period
        self.year_from = year_from
        self.year_to = year_to
        self.links = links or {}

        self.status: JobStatus = JobStatus.PENDING
        self.progress: int = 0
        self.message: str = "Đang chờ xử lý..."
        self.error: Optional[str] = None
        self.output_files: list[str] = []
        self.preview_data: dict[str, dict] = {}
        self.created_at: datetime = datetime.utcnow()
        self.completed_at: Optional[datetime] = None


class JobManager:
    """Thread-safe in-memory job manager."""

    def __init__(self):
        self._jobs: dict[str, JobInfo] = {}
        self._lock = threading.Lock()
        self._start_cleanup_thread()

    def create_job(
        self,
        tickers: list[str],
        report_type: str,
        period: str,
        year_from: int,
        year_to: int,
        links: dict[str, str] = None
    ) -> str:
        """Create a new job and start processing in background."""
        job_id = str(uuid.uuid4())

        job = JobInfo(
            job_id=job_id,
            tickers=tickers,
            report_type=report_type,
            period=period,
            year_from=year_from,
            year_to=year_to,
            links=links
        )

        with self._lock:
            self._jobs[job_id] = job

        thread = threading.Thread(target=self._process_job, args=(job_id,), daemon=True)
        thread.start()

        return job_id

    def get_job(self, job_id: str) -> Optional[JobInfo]:
        """Get job info by ID."""
        with self._lock:
            return self._jobs.get(job_id)

    def _process_job(self, job_id: str):
        """Background worker: fetch data using provided links and AI."""
        job = self.get_job(job_id)
        if not job: return

        try:
            self._update_status(job_id, JobStatus.PROCESSING, 0, "Bắt đầu trích xuất AI...")

            # Since we support 1 ticker for now in this flow
            ticker = job.tickers[0]
            
            # Map of Year -> DataFrame (Each DF contains all 150+ fields)
            all_years_dfs = []
            
            total_links = len(job.links)
            for idx, (period_label, url) in enumerate(job.links.items()):
                # period_label could be "2015" or "2026-Q1"
                try:
                    # Extract year from label
                    year = int(period_label.split('-')[0])
                    
                    self._update_status(
                        job_id, JobStatus.PROCESSING, 
                        int((idx / total_links) * 100),
                        f"AI đang đọc báo cáo {period_label}..."
                    )
                    
                    # Call fetcher with direct URL
                    # Note: fetch_financial_data returns a list of DFs.
                    # We pass the URL as pdf_path.
                    from app.services.data_fetcher import _fetch_from_pdf_ai
                    df = _fetch_from_pdf_ai(ticker, "all", year, user_pdf_path=url)
                    if df is not None:
                        # Fixup the year if it was a quarter
                        if "-" in period_label:
                            # If it's a quarter, we might need special handling in future,
                            # for now we treat as specific data points for that year or store label.
                            pass
                        all_years_dfs.append(df)
                except Exception as e:
                    logger.error(f"Error processing {period_label}: {e}")

            if not all_years_dfs:
                raise ValueError("Không thể trích xuất dữ liệu từ các link đã cung cấp.")

            # Construct reports dict for the mapper
            reports = {
                "income_statement": all_years_dfs,
                "balance_sheet": all_years_dfs,
                "cash_flow": all_years_dfs
            }

            # Map data
            mapped = map_financial_data(reports, job.year_from, job.year_to)
            
            with self._lock:
                job.preview_data[ticker] = mapped

            # Generate Excel
            output_dir = os.path.join(settings.OUTPUT_DIR, job_id)
            filepath = generate_excel(ticker, mapped, job.year_from, job.year_to, output_dir)

            with self._lock:
                job.output_files.append(filepath)

            self._update_status(job_id, JobStatus.COMPLETED, 100, "Trích xuất hoàn tất!")

        except Exception as e:
            logger.exception(f"Job {job_id} failed: {e}")
            self._update_status(job_id, JobStatus.FAILED, 0, str(e))

    def _update_status(self, job_id: str, status: JobStatus, progress: int, message: str):
        with self._lock:
            job = self._jobs.get(job_id)
            if job:
                job.status = status
                job.progress = progress
                job.message = message
                if status in (JobStatus.COMPLETED, JobStatus.FAILED):
                    job.completed_at = datetime.utcnow()

    def _start_cleanup_thread(self):
        def cleanup():
            while True:
                time.sleep(300)
                now = datetime.utcnow()
                with self._lock:
                    expired = [jid for jid, j in self._jobs.items() if (now - j.created_at).total_seconds() > 1800]
                    for jid in expired:
                        job = self._jobs[jid]
                        # Cleanup files
                        for f in job.output_files:
                            try: os.remove(f)
                            except: pass
                        del self._jobs[jid]
                
                # Cleanup PDFs older than 10 mins
                tmp_dir = "/tmp/bctc_pdfs"
                if os.path.exists(tmp_dir):
                    curr = time.time()
                    for f in os.listdir(tmp_dir):
                        p = os.path.join(tmp_dir, f)
                        if os.path.isfile(p) and curr - os.path.getmtime(p) > 600:
                            try: os.remove(p)
                            except: pass
        threading.Thread(target=cleanup, daemon=True).start()

job_manager = JobManager()
