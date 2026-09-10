import logging
from typing import List
from bs4 import BeautifulSoup
from src.models import Job
from .base import BaseConnector

logger = logging.getLogger(__name__)


class InternshalaConnector(BaseConnector):
    """Scraper connector for Internshala public internship listing pages."""

    def __init__(self, enabled: bool = True):
        super().__init__(name="Internshala", enabled=enabled)
        self.search_urls = [
            "https://internshala.com/internships/software-development-internship/",
            "https://internshala.com/internships/java-development-internship/",
            "https://internshala.com/internships/artificial-intelligence-ai-internship/",
            "https://internshala.com/internships/machine-learning-internship/",
        ]

    def fetch_jobs(self, limit: int = 20) -> List[Job]:
        if not self.enabled:
            logger.info("[%s] Connector is disabled.", self.name)
            return []

        logger.info("[%s] Scraping internship listings...", self.name)
        jobs: List[Job] = []

        for search_url in self.search_urls:
            if len(jobs) >= limit:
                break

            response = self.safe_get(search_url)
            if not response:
                continue

            try:
                soup = BeautifulSoup(response.text, "html.parser")
                # Look for internship container blocks using multiple generic CSS classes
                containers = soup.find_all("div", class_=lambda c: c and ("internship_list_container" in c or "individual_internship" in c or "container-fluid" in c))
                if not containers:
                    containers = soup.find_all("div", id=lambda i: i and "internship_list" in i)

                for item in containers[:10]:
                    if len(jobs) >= limit:
                        break

                    # Find headings and links
                    headings = item.find_all(["h3", "h4", "div", "a"], class_=lambda c: c and ("job-internship-name" in c or "heading_4_5" in c or "profile" in c or "view_detail_button" in c))
                    if not headings:
                        continue

                    title = headings[0].get_text(strip=True)
                    if not title or len(title) < 3:
                        continue

                    # Company name
                    comp_elem = item.find(class_=lambda c: c and ("company-name" in c or "company_name" in c or "link_display_like_text" in c))
                    company = comp_elem.get_text(strip=True) if comp_elem else "Internshala Partner"

                    # Location
                    loc_elem = item.find(class_=lambda c: c and ("location" in c or "location_link" in c))
                    location = loc_elem.get_text(strip=True) if loc_elem else "India / Remote"

                    # Details link
                    link_elem = item.find("a", href=True)
                    link = "https://internshala.com" + link_elem["href"] if link_elem and link_elem["href"].startswith("/") else (link_elem["href"] if link_elem else search_url)

                    desc = f"Internship Role: {title} at {company}. Location: {location}. Focus areas: Java, Python, AI/ML, Full Stack, Software Development."

                    job = Job(
                        title=title,
                        company=company,
                        location=location,
                        link=link,
                        description=desc,
                        posted_date="Recently",
                        source=self.name,
                        requirements=["Java", "Python", "Full Stack", "AI/ML", "DSA"],
                    )
                    jobs.append(job)

            except Exception as e:
                logger.error("[%s] Error parsing HTML from %s: %s", self.name, search_url, str(e))
                continue

        logger.info("[%s] Successfully retrieved %d jobs.", self.name, len(jobs))
        return jobs
