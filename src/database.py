import os
import sqlite3
import logging
from typing import List, Optional, Dict, Any
from datetime import datetime
from src.models import Job

logger = logging.getLogger(__name__)


class DatabaseManager:
    """Manages SQLite storage for tracking seen jobs, match scores, drafts, and application status."""

    def __init__(self, db_path: str = "data/jobs.db"):
        self.db_path = db_path
        os.makedirs(os.path.dirname(self.db_path), exist_ok=True)
        self.init_db()

    def _get_connection(self) -> sqlite3.Connection:
        conn = sqlite3.connect(self.db_path)
        conn.row_factory = sqlite3.Row
        return conn

    def init_db(self):
        """Initializes the database schema if tables do not exist."""
        with self._get_connection() as conn:
            cursor = conn.cursor()
            cursor.execute(
                """
                CREATE TABLE IF NOT EXISTS jobs (
                    id TEXT PRIMARY KEY,
                    title TEXT NOT NULL,
                    company TEXT NOT NULL,
                    location TEXT,
                    link TEXT NOT NULL,
                    description TEXT,
                    posted_date TEXT,
                    source TEXT NOT NULL,
                    match_score REAL DEFAULT 0.0,
                    status TEXT DEFAULT 'NEW',
                    fit_blurb TEXT DEFAULT '',
                    cover_note TEXT DEFAULT '',
                    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                    updated_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
                )
                """
            )
            conn.commit()
            logger.info("SQLite Database initialized at %s", self.db_path)

    def is_job_seen(self, job_id: str) -> bool:
        """Returns True if a job has already been scraped/seen."""
        with self._get_connection() as conn:
            cursor = conn.cursor()
            cursor.execute("SELECT 1 FROM jobs WHERE id = ?", (job_id,))
            return cursor.fetchone() is not None

    def save_job(self, job: Job) -> bool:
        """Inserts or updates a job record in SQLite."""
        now = datetime.now().isoformat()
        with self._get_connection() as conn:
            cursor = conn.cursor()
            cursor.execute(
                """
                INSERT INTO jobs (
                    id, title, company, location, link, description, posted_date, 
                    source, match_score, status, fit_blurb, cover_note, created_at, updated_at
                ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
                ON CONFLICT(id) DO UPDATE SET
                    match_score = excluded.match_score,
                    status = excluded.status,
                    fit_blurb = excluded.fit_blurb,
                    cover_note = excluded.cover_note,
                    updated_at = excluded.updated_at
                """,
                (
                    job.id,
                    job.title,
                    job.company,
                    job.location,
                    job.link,
                    job.description,
                    job.posted_date,
                    job.source,
                    job.match_score,
                    job.status,
                    job.fit_blurb,
                    job.cover_note,
                    job.created_at,
                    now,
                ),
            )
            conn.commit()
            return True

    def update_status(self, job_id: str, status: str) -> bool:
        """Updates the status of a given job (e.g. APPLIED, REJECTED, SHORTLISTED)."""
        now = datetime.now().isoformat()
        with self._get_connection() as conn:
            cursor = conn.cursor()
            cursor.execute(
                "UPDATE jobs SET status = ?, updated_at = ? WHERE id = ? OR id LIKE ?",
                (status.upper(), now, job_id, f"{job_id}%"),
            )
            conn.commit()
            affected = cursor.rowcount > 0
            if affected:
                logger.info("Updated job %s status to %s", job_id, status.upper())
            else:
                logger.warning("No job found matching ID %s", job_id)
            return affected

    def get_job(self, job_id: str) -> Optional[Job]:
        """Fetches a single job by exact or prefix ID."""
        with self._get_connection() as conn:
            cursor = conn.cursor()
            cursor.execute(
                "SELECT * FROM jobs WHERE id = ? OR id LIKE ? LIMIT 1",
                (job_id, f"{job_id}%"),
            )
            row = cursor.fetchone()
            if row:
                return Job(**dict(row))
            return None

    def get_shortlisted_jobs(self) -> List[Job]:
        """Returns all jobs marked as SHORTLISTED or DRAFT_READY."""
        with self._get_connection() as conn:
            cursor = conn.cursor()
            cursor.execute(
                "SELECT * FROM jobs WHERE status IN ('SHORTLISTED', 'DRAFT_READY') ORDER BY match_score DESC"
            )
            rows = cursor.fetchall()
            return [Job(**dict(row)) for row in rows]

    def get_all_jobs(self, status_filter: Optional[str] = None) -> List[Job]:
        """Returns all recorded jobs, optionally filtered by status."""
        with self._get_connection() as conn:
            cursor = conn.cursor()
            if status_filter:
                cursor.execute(
                    "SELECT * FROM jobs WHERE status = ? ORDER BY match_score DESC",
                    (status_filter.upper(),),
                )
            else:
                cursor.execute("SELECT * FROM jobs ORDER BY updated_at DESC")
            rows = cursor.fetchall()
            return [Job(**dict(row)) for row in rows]

    def get_stats(self) -> Dict[str, int]:
        """Returns aggregate status summary metrics."""
        with self._get_connection() as conn:
            cursor = conn.cursor()
            cursor.execute(
                """
                SELECT 
                    COUNT(*) as total,
                    SUM(CASE WHEN status = 'SHORTLISTED' THEN 1 ELSE 0 END) as shortlisted,
                    SUM(CASE WHEN status = 'DRAFT_READY' THEN 1 ELSE 0 END) as draft_ready,
                    SUM(CASE WHEN status = 'APPLIED' THEN 1 ELSE 0 END) as applied,
                    SUM(CASE WHEN status = 'REJECTED' THEN 1 ELSE 0 END) as rejected
                FROM jobs
                """
            )
            row = cursor.fetchone()
            return {
                "total_seen": row["total"] or 0,
                "shortlisted": row["shortlisted"] or 0,
                "draft_ready": row["draft_ready"] or 0,
                "applied": row["applied"] or 0,
                "rejected": row["rejected"] or 0,
            }
