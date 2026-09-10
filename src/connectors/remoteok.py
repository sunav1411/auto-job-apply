import logging
from typing import List
from src.models import Job
from .base import BaseConnector

logger = logging.getLogger(__name__)


class RemoteOKConnector(BaseConnector):
    """Connector for fetching remote engineering and intern jobs from RemoteOK public API."""

    def __init__(self, enabled: bool = True):
        super().__init__(name="RemoteOK", enabled=enabled)
        self.api_url = "https://remoteok.com/api"

    def fetch_jobs(self, limit: int = 20) -> List[Job]:
        if not self.enabled:
            logger.info("[%s] Connector is disabled.", self.name)
            return []

        logger.info("[%s] Fetching jobs from API...", self.name)
        response = self.safe_get(self.api_url)
        if not response:
            return []

        try:
            data = response.json()
            # First item in RemoteOK JSON response is legal/meta disclaimer
            if isinstance(data, list) and len(data) > 1:
                raw_jobs = data[1:]
            else:
                raw_jobs = data

            jobs: List[Job] = []
            for item in raw_jobs[:limit]:
                if not isinstance(item, dict):
                    continue

                position = item.get("position", "")
                company = item.get("company", "Remote Company")
                url = item.get("url") or item.get("apply_url") or "https://remoteok.com"
                description = item.get("description", "")
                location = item.get("location", "Remote")
                tags = item.get("tags", [])
                date = item.get("date", "")

                full_desc = f"{position} at {company}. Skills/Tags: {', '.join(tags)}. {description}"

                job = Job(
                    title=position,
                    company=company,
                    location=location,
                    link=url,
                    description=full_desc,
                    posted_date=str(date),
                    source=self.name,
                    requirements=tags,
                )
                jobs.append(job)

            logger.info("[%s] Successfully retrieved %d jobs.", self.name, len(jobs))
            return jobs
        except Exception as e:
            logger.error("[%s] Error parsing API response: %s", self.name, str(e))
            return []
