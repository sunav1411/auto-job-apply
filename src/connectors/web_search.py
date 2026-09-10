import logging
import urllib.parse
from typing import List
from bs4 import BeautifulSoup
from src.models import Job
from .base import BaseConnector

logger = logging.getLogger(__name__)


class WebSearchConnector(BaseConnector):
    """Broad web search connector querying Greenhouse, Lever, Workday, and Google Search for tech internships."""

    def __init__(self, enabled: bool = True):
        super().__init__(name="WebSearch", enabled=enabled)
        # Target broad ATS job boards & search queries across the web
        self.search_queries = [
            "Software Engineering Intern site:greenhouse.io OR site:lever.co",
            "AI ML Intern site:greenhouse.io OR site:lever.co",
            "Backend Developer Intern Java site:myworkdayjobs.com OR site:smartrecruiters.com",
        ]

    def fetch_jobs(self, limit: int = 20) -> List[Job]:
        if not self.enabled:
            logger.info("[%s] Connector is disabled.", self.name)
            return []

        logger.info("[%s] Surfing the web for active ATS & portal internship listings...", self.name)
        jobs: List[Job] = []

        for query in self.search_queries:
            if len(jobs) >= limit:
                break

            encoded_q = urllib.parse.quote(query)
            search_url = f"https://html.duckduckgo.com/html/?q={encoded_q}"
            
            response = self.safe_get(search_url)
            if not response:
                continue

            try:
                soup = BeautifulSoup(response.text, "html.parser")
                results = soup.find_all("div", class_="result")

                for res in results[:8]:
                    if len(jobs) >= limit:
                        break

                    title_elem = res.find("a", class_="result__a")
                    snippet_elem = res.find("a", class_="result__snippet")

                    if not title_elem:
                        continue

                    title_text = title_elem.get_text(strip=True)
                    link = title_elem["href"]

                    # Extract company and clean title if present in ATS format (e.g. "Software Intern - Stripe")
                    company = "Tech Company / ATS Board"
                    if " - " in title_text:
                        parts = title_text.split(" - ")
                        title_text = parts[0]
                        company = parts[1]
                    elif " | " in title_text:
                        parts = title_text.split(" | ")
                        title_text = parts[0]
                        company = parts[1]

                    snippet = snippet_elem.get_text(strip=True) if snippet_elem else title_text
                    full_desc = f"{title_text} at {company}. Search Snippet: {snippet}. Requirements: Java, Python, AI/ML, Fullstack, DSA."

                    # Basic check to filter out non-internship search results
                    if not any(k in title_text.lower() or k in snippet.lower() for k in ["intern", "co-op", "trainee", "student"]):
                        continue

                    job = Job(
                        title=title_text,
                        company=company,
                        location="Remote / India / Global",
                        link=link,
                        description=full_desc,
                        posted_date="Live Web Listing",
                        source=self.name,
                        requirements=["Java", "Python", "Full Stack", "AI/ML", "DSA"],
                    )
                    jobs.append(job)

            except Exception as e:
                logger.error("[%s] Error parsing web search for query '%s': %s", self.name, query, str(e))
                continue

        logger.info("[%s] Successfully retrieved %d broad web listings.", self.name, len(jobs))
        return jobs
