import os
import sys
import yaml
import argparse
import logging
from dotenv import load_dotenv

# Load environment variables from .env file if available
load_dotenv()

# Configure UTF-8 encoding for stdout on Windows
if hasattr(sys.stdout, "reconfigure"):
    sys.stdout.reconfigure(encoding="utf-8")

# Configure logging
logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s [%(levelname)s] %(name)s: %(message)s",
    handlers=[logging.StreamHandler(sys.stdout)],
)
logger = logging.getLogger("AutoJobApply")

from src.models import CandidateProfile, Job
from src.database import DatabaseManager
from src.connectors import (
    RemoteOKConnector,
    InternshalaConnector,
    CompanyCareersConnector,
    WebSearchConnector,
)
from src.matching.engine import MatchingEngine
from src.drafting.generator import DraftGenerator
from src.automation.form_filler import FormFiller
from src.notifier.telegram_bot import TelegramNotifier


def load_profile(profile_path: str = "config/profile.yaml") -> CandidateProfile:
    """Loads candidate profile from YAML file."""
    if not os.path.exists(profile_path):
        raise FileNotFoundError(f"Profile config file not found at '{profile_path}'")

    with open(profile_path, "r", encoding="utf-8") as f:
        data = yaml.safe_load(f)
    return CandidateProfile(**data)


def load_resume_text(resume_path: str = "data/resume.txt") -> str:
    """Loads resume text from file."""
    if not os.path.exists(resume_path):
        logger.warning("Resume text file missing at '%s'. Using fallback text.", resume_path)
        return "Java Spring Boot SDE Intern AI ML 470 LeetCode 1692 rating"

    with open(resume_path, "r", encoding="utf-8") as f:
        return f.read()


def run_pipeline(dry_run: bool = False, min_score: float = None):
    """Executes the daily search, deduplication, matching, drafting, and notification pipeline."""
    mode_str = "DRY-RUN (TEST MODE)" if dry_run else "PRODUCTION RUN"
    logger.info("==================================================")
    logger.info("Starting Daily Internship Search Pipeline [%s]", mode_str)
    logger.info("==================================================")

    # 1. Load inputs & profile
    profile = load_profile()
    if min_score is not None:
        profile.min_match_threshold = min_score

    resume_text = load_resume_text()
    db = DatabaseManager()

    # 2. Instantiate connectors with resilience
    connectors = [
        RemoteOKConnector(enabled=True),
        InternshalaConnector(enabled=True),
        CompanyCareersConnector(enabled=True),
        WebSearchConnector(enabled=True),
    ]

    all_fetched_jobs = []
    for connector in connectors:
        try:
            logger.info("Fetching jobs from connector: %s", connector.name)
            jobs = connector.fetch_jobs(limit=15)
            all_fetched_jobs.extend(jobs)
        except Exception as e:
            logger.error("Error running connector %s: %s (Continuing remaining connectors)", connector.name, str(e))

    logger.info("Fetched a total of %d raw job listings.", len(all_fetched_jobs))

    # 3. Deduplication against SQLite database
    unseen_jobs = []
    for job in all_fetched_jobs:
        if db.is_job_seen(job.id):
            logger.debug("Skipping already seen job: %s at %s", job.title, job.company)
        else:
            unseen_jobs.append(job)

    logger.info("Found %d new unseen jobs to evaluate.", len(unseen_jobs))

    # 4. Matching & Scoring Engine
    matcher = MatchingEngine(profile=profile, resume_text=resume_text)
    shortlisted_jobs = []

    for job in unseen_jobs:
        score, match_result = matcher.score_job(job)
        logger.info(
            "Job '%s' @ %s -> Score: %.1f%% (Threshold: %.1f%%) | Shortlisted: %s",
            job.title,
            job.company,
            score,
            profile.min_match_threshold,
            match_result.is_shortlisted,
        )

        if match_result.is_shortlisted:
            shortlisted_jobs.append(job)

    logger.info(
        "Scoring complete. %d out of %d new jobs passed the %.1f%% threshold.",
        len(shortlisted_jobs),
        len(unseen_jobs),
        profile.min_match_threshold,
    )

    # 5. Draft Generator
    draft_gen = DraftGenerator(profile=profile)
    for job in shortlisted_jobs:
        draft_gen.generate_drafts(job)

    # 6. Save to DB (Unless Dry-Run)
    if not dry_run:
        for job in unseen_jobs:
            db.save_job(job)
        logger.info("Persisted %d job records to SQLite database.", len(unseen_jobs))
    else:
        logger.info("[DRY-RUN] Skipped saving records to SQLite database.")

    # 7. Notify via Telegram Digest / Report
    notifier = TelegramNotifier()
    notifier.send_digest(shortlisted_jobs, total_scraped=len(all_fetched_jobs))

    # Summary report output
    print("\n" + "=" * 65)
    print(f"PIPELINE RUN SUMMARY [{mode_str}]")
    print("=" * 65)
    print(f"Total Raw Scraped : {len(all_fetched_jobs)}")
    print(f"New Unseen Jobs   : {len(unseen_jobs)}")
    print(f"Shortlisted (>={profile.min_match_threshold:.0f}%): {len(shortlisted_jobs)}")
    print("=" * 65)

    if shortlisted_jobs:
        print("\nTOP MATCHES FOUND:")
        for idx, j in enumerate(shortlisted_jobs, start=1):
            print(f"  {idx}. [{j.id}] {j.title} @ {j.company} - Match Score: {j.match_score:.1f}%")
            print(f"     Location: {j.location} | Source: {j.source}")
            print(f"     Link:     {j.link}")
            print(f"     Why Fit:  {j.fit_blurb[:120]}...\n")
    else:
        print("\nNo jobs exceeded the current match threshold.")
        if dry_run:
            print("Tip: You can adjust 'min_match_threshold' in config/profile.yaml or pass --min-score <value>")


def main():
    parser = argparse.ArgumentParser(description="Daily Internship Search & Semi-Auto Apply System")
    parser.add_argument("--dry-run", action="store_true", help="Test run without saving to DB or posting Telegram")
    parser.add_argument("--min-score", type=float, default=None, help="Override minimum match threshold percentage")

    subparsers = parser.add_subparsers(dest="command", help="System command to execute")

    # Command: run
    run_parser = subparsers.add_parser("run", help="Run daily search and match pipeline")
    run_parser.add_argument("--dry-run", action="store_true", help="Test run without saving to DB or posting Telegram")
    run_parser.add_argument("--min-score", type=float, default=None, help="Override minimum match threshold percentage")

    # Command: mark-applied
    mark_parser = subparsers.add_parser("mark-applied", help="Mark a job status as APPLIED")
    mark_parser.add_argument("job_id", type=str, help="Job ID or prefix hash to mark as applied")

    # Command: list
    list_parser = subparsers.add_parser("list", help="List stored jobs from SQLite DB")
    list_parser.add_argument("--status", type=str, default=None, help="Filter by status (e.g. SHORTLISTED, DRAFT_READY, APPLIED)")

    # Command: test-fill
    fill_parser = subparsers.add_parser("test-fill", help="Run Playwright form filler proof-of-concept on a job")
    fill_parser.add_argument("--job-id", type=str, default=None, help="Job ID from database or sample URL")

    args = parser.parse_args()

    # Determine command or dry-run flag
    if args.dry_run or args.command == "run" or not args.command:
        is_dry = args.dry_run or (hasattr(args, "dry_run") and args.dry_run)
        score_override = args.min_score if hasattr(args, "min_score") else None
        run_pipeline(dry_run=is_dry, min_score=score_override)

    elif args.command == "mark-applied":
        db = DatabaseManager()
        success = db.update_status(args.job_id, "APPLIED")
        if success:
            print(f"SUCCESS: Job '{args.job_id}' marked as APPLIED in SQLite database.")
        else:
            print(f"ERROR: Could not find job matching ID '{args.job_id}'.")

    elif args.command == "list":
        db = DatabaseManager()
        jobs = db.get_all_jobs(status_filter=args.status)
        stats = db.get_stats()
        print(f"DATABASE SUMMARY: {stats}")
        print(f"Found {len(jobs)} jobs (Status Filter: {args.status or 'ALL'}):")
        print("-" * 70)
        for j in jobs:
            print(f"[{j.id}] {j.title} @ {j.company} | Score: {j.match_score:.1f}% | Status: {j.status}")
            print(f"  Link: {j.link}")

    elif args.command == "test-fill":
        db = DatabaseManager()
        profile = load_profile()
        target_job = None

        if args.job_id:
            target_job = db.get_job(args.job_id)

        if not target_job:
            target_job = Job(
                title="Software Engineering Intern",
                company="Google / Sample Recruiter",
                location="Remote / India",
                link="https://httpbin.org/forms/post",
                description="Software engineering intern position requiring Java, Python, and DSA skills.",
                source="PoC Test",
            )
            draft_gen = DraftGenerator(profile=profile)
            draft_gen.generate_drafts(target_job)

        filler = FormFiller(profile=profile, resume_pdf_path="data/resume.pdf", headless=False)
        success, status_msg = filler.prefill_application(target_job, pause_seconds=5)
        print(f"\nFORM FILLER RESULT: Success={success} | Status='{status_msg}'")


if __name__ == "__main__":
    main()
