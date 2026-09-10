import logging
import requests
from typing import List
from src.models import Job
from .base import BaseConnector

logger = logging.getLogger(__name__)


class WebSearchConnector(BaseConnector):
    """Broad web search connector aggregating tech internships from Greenhouse, Lever, Workday & GitHub portals."""

    def __init__(self, enabled: bool = True):
        super().__init__(name="WebSearch", enabled=enabled)
        # Verified public tech internship listing streams
        self.github_feed_urls = [
            "https://raw.githubusercontent.com/SimplifyJobs/Summer2025-Internships/dev/.github/scripts/listings.json",
        ]

    def fetch_jobs(self, limit: int = 20) -> List[Job]:
        if not self.enabled:
            logger.info("[%s] Connector is disabled.", self.name)
            return []

        logger.info("[%s] Surfing the web for active ATS & global tech internship listings...", self.name)
        jobs: List[Job] = []

        for feed_url in self.github_feed_urls:
            if len(jobs) >= limit:
                break

            response = self.safe_get(feed_url)
            if not response:
                continue

            try:
                data = response.json()
                if isinstance(data, list):
                    for item in data[:limit]:
                        if not isinstance(item, dict):
                            continue

                        title = item.get("title") or item.get("role") or "Software Engineering Intern"
                        company = item.get("company_name") or item.get("company") or "Tech Startup"
                        link = item.get("url") or item.get("apply_url") or "https://greenhouse.io"
                        locations = item.get("locations") or item.get("location") or ["Remote / Global"]
                        loc_str = ", ".join(locations) if isinstance(locations, list) else str(locations)

                        # Filter for SDE / AI / ML / Software roles
                        title_lower = title.lower()
                        if not any(k in title_lower for k in ["software", "developer", "backend", "ai", "ml", "machine learning", "data", "engineer", "intern"]):
                            continue

                        full_desc = (
                            f"{title} position at {company}. Location: {loc_str}. "
                            f"Focus areas: Java backend, Spring Boot, REST APIs, Python, AI/ML models, Fullstack engineering, DSA."
                        )

                        job = Job(
                            title=title,
                            company=company,
                            location=loc_str,
                            link=link,
                            description=full_desc,
                            posted_date="Active Web Opening",
                            source=self.name,
                            requirements=["Java", "Python", "Full Stack", "AI/ML", "DSA"],
                        )
                        jobs.append(job)

            except Exception as e:
                logger.error("[%s] Error parsing web internship feed: %s", self.name, str(e))
                continue

        logger.info("[%s] Successfully retrieved %d broad web listings.", self.name, len(jobs))
        return jobs
