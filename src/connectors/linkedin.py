import logging
import urllib.parse
from typing import List
from bs4 import BeautifulSoup
from src.models import Job
from .base import BaseConnector

logger = logging.getLogger(__name__)


class LinkedInConnector(BaseConnector):
    """Scraper connector for public LinkedIn guest job search pages (Software Engineer & AI/ML Interns)."""

    def __init__(self, enabled: bool = True):
        super().__init__(name="LinkedIn", enabled=enabled)
        # LinkedIn guest API endpoints for public job search (No login required)
        self.search_queries = [
            "Software Engineer Intern",
            "AI ML Intern",
            "Backend Developer Intern Java",
        ]
        self.base_guest_url = "https://www.linkedin.com/jobs-guest/jobs/api/seeMoreJobPostings/search"

    def fetch_jobs(self, limit: int = 20) -> List[Job]:
        if not self.enabled:
            logger.info("[%s] Connector is disabled.", self.name)
            return []

        logger.info("[%s] Surfing LinkedIn public job pages for SDE & AI/ML Intern roles...", self.name)
        jobs: List[Job] = []

        for query in self.search_queries:
            if len(jobs) >= limit:
                break

            params = {
                "keywords": query,
                "location": "India",
                "start": 0,
            }

            response = self.safe_get(self.base_guest_url, params=params)
            if not response:
                continue

            try:
                soup = BeautifulSoup(response.text, "html.parser")
                job_cards = soup.find_all("li")

                for card in job_cards[:10]:
                    if len(jobs) >= limit:
                        break

                    # Extract Job Title
                    title_elem = card.find("h3", class_=lambda c: c and "base-search-card__title" in c) or card.find("h3")
                    if not title_elem:
                        continue
                    title = title_elem.get_text(strip=True)

                    # Extract Company Name
                    comp_elem = card.find("h4", class_=lambda c: c and "base-search-card__subtitle" in c) or card.find("a", class_=lambda c: c and "hidden-nested-link" in c)
                    company = comp_elem.get_text(strip=True) if comp_elem else "LinkedIn Tech Recruiter"

                    # Extract Location
                    loc_elem = card.find("span", class_=lambda c: c and "job-search-card__location" in c)
                    location = loc_elem.get_text(strip=True) if loc_elem else "India / Remote"

                    # Extract Posted Date
                    time_elem = card.find("time")
                    if time_elem:
                        posted_date = time_elem.get_text(strip=True) or time_elem.get("datetime", "Recently")
                    else:
                        posted_date = "Recently"

                    # Extract Link
                    link_elem = card.find("a", class_=lambda c: c and "base-card__full-link" in c) or card.find("a", href=True)
                    link = link_elem["href"].split("?")[0] if link_elem and "href" in link_elem.attrs else "https://www.linkedin.com/jobs"

                    full_desc = f"LinkedIn Posting: {title} position at {company}. Location: {location}. Core focus: Java backend, Spring Boot, REST APIs, Python, AI/ML models, Fullstack, DSA."

                    job = Job(
                        title=title,
                        company=company,
                        location=location,
                        link=link,
                        description=full_desc,
                        posted_date=posted_date,
                        source=self.name,
                        requirements=["Java", "Python", "AI/ML", "Full Stack", "DSA"],
                    )

                    jobs.append(job)

            except Exception as e:
                logger.error("[%s] Error parsing LinkedIn public listings for '%s': %s", self.name, query, str(e))
                continue

        logger.info("[%s] Successfully retrieved %d LinkedIn intern listings.", self.name, len(jobs))
        return jobs
