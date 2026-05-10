"""
Job Manager
===========
In-memory job queue for processing BCTC extraction requests asynchronously.
Uses threading for background processing (sufficient for MVP on Render free tier).

Jobs are stored in a dict and auto-cleaned after expiry.
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
from app.models import JobStatus, ReportType
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
    ):
        self.job_id = job_id
        self.tickers = tickers
        self.report_type = report_type
        self.period = period
        self.year_from = year_from
        self.year_to = year_to

        self.status: JobStatus = JobStatus.PENDING
        self.progress: int = 0
        self.message: str = "Đang chờ xử lý..."
        self.error: Optional[str] = None
        self.output_files: list[str] = []
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
        )

        with self._lock:
            self._jobs[job_id] = job

        # Start background processing
        thread = threading.Thread(
            target=self._process_job,
            args=(job_id,),
            daemon=True,
        )
        thread.start()

        return job_id

    def get_job(self, job_id: str) -> Optional[JobInfo]:
        """Get job info by ID."""
        with self._lock:
            return self._jobs.get(job_id)

    def _process_job(self, job_id: str):
        """Background worker: fetch data, map, generate Excel for each ticker."""
        job = self.get_job(job_id)
        if not job:
            return

        try:
            self._update_status(job_id, JobStatus.PROCESSING, 0, "Bắt đầu xử lý...")

            total_tickers = len(job.tickers)
            report_types = (
                ["income_statement", "balance_sheet", "cash_flow"]
                if job.report_type == "all"
                else [job.report_type]
            )

            for idx, ticker in enumerate(job.tickers):
                progress = int((idx / total_tickers) * 100)
                self._update_status(
                    job_id, JobStatus.PROCESSING, progress,
                    f"Đang xử lý {ticker} ({idx + 1}/{total_tickers})..."
                )

                try:
                    # Fetch data
                    reports = {}
                    for rtype in report_types:
                        logger.info(f"Job {job_id}: Fetching {rtype} for {ticker}")
                        reports[rtype] = fetch_financial_data(
                            ticker, rtype, job.period
                        )
                        time.sleep(settings.FETCH_RATE_LIMIT_DELAY)

                    # Map data
                    mapped = map_financial_data(reports, job.year_from, job.year_to)

                    # Generate Excel
                    output_dir = os.path.join(settings.OUTPUT_DIR, job_id)
                    filepath = generate_excel(
                        ticker, mapped, job.year_from, job.year_to, output_dir
                    )

                    with self._lock:
                        job.output_files.append(filepath)

                except Exception as e:
                    logger.error(f"Job {job_id}: Error processing {ticker}: {e}")
                    # Continue with other tickers instead of failing the whole job
                    self._update_status(
                        job_id, JobStatus.PROCESSING, progress,
                        f"Lỗi với mã {ticker}: {str(e)}"
                    )

            # Final status
            if job.output_files:
                self._update_status(
                    job_id, JobStatus.COMPLETED, 100,
                    f"Hoàn thành {len(job.output_files)}/{total_tickers} mã"
                )
            else:
                self._update_status(
                    job_id, JobStatus.FAILED, 0,
                    "Không thể xử lý bất kỳ mã nào"
                )

        except Exception as e:
            logger.exception(f"Job {job_id}: Unexpected error: {e}")
            self._update_status(job_id, JobStatus.FAILED, 0, str(e))

    def _update_status(
        self,
        job_id: str,
        status: JobStatus,
        progress: int,
        message: str,
    ):
        """Thread-safe status update."""
        with self._lock:
            job = self._jobs.get(job_id)
            if job:
                job.status = status
                job.progress = progress
                job.message = message
                if status in (JobStatus.COMPLETED, JobStatus.FAILED):
                    job.completed_at = datetime.utcnow()

    def _start_cleanup_thread(self):
        """Periodically remove expired jobs to free memory."""
        def cleanup():
            while True:
                time.sleep(300)  # Run every 5 minutes
                now = datetime.utcnow()
                with self._lock:
                    expired = [
                        jid for jid, job in self._jobs.items()
                        if (now - job.created_at).total_seconds() > settings.JOB_EXPIRY_SECONDS
                    ]
                    for jid in expired:
                        # Clean up output files
                        job = self._jobs[jid]
                        for f in job.output_files:
                            try:
                                os.remove(f)
                            except OSError:
                                pass
                        del self._jobs[jid]
                        logger.info(f"Cleaned up expired job: {jid}")

        thread = threading.Thread(target=cleanup, daemon=True)
        thread.start()


# Singleton instance
job_manager = JobManager()
