import random
import time
import logging
import requests
from abc import ABC, abstractmethod
from typing import List, Optional
from src.models import Job

logger = logging.getLogger(__name__)

USER_AGENTS = [
    "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/122.0.0.0 Safari/537.36",
    "Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/121.0.0.0 Safari/537.36",
    "Mozilla/5.0 (X11; Linux x86_64; rv:109.0) Gecko/20100101 Firefox/122.0",
]


class BaseConnector(ABC):
    """Abstract base class for all job source connectors with resilience and polite scraping limits."""

    def __init__(self, name: str, enabled: bool = True):
        self.name = name
        self.enabled = enabled
        self.session = requests.Session()

    def get_headers(self) -> dict:
        return {
            "User-Agent": random.choice(USER_AGENTS),
            "Accept": "text/html,application/xhtml+xml,application/xml;q=0.9,image/webp,*/*;q=0.8",
            "Accept-Language": "en-US,en;q=0.9",
        }

    def polite_delay(self, min_seconds: float = 1.5, max_seconds: float = 3.5):
        """Adds a random pause between scraping requests to prevent rate limiting / IP bans."""
        delay = random.uniform(min_seconds, max_seconds)
        time.sleep(delay)

    def safe_get(
        self, url: str, params: Optional[dict] = None, timeout: int = 15
    ) -> Optional[requests.Response]:
        """Performs HTTP GET with error catching, rate-limiting, and response validation."""
        try:
            self.polite_delay()
            response = self.session.get(
                url, headers=self.get_headers(), params=params, timeout=timeout
            )
            response.raise_for_status()
            return response
        except Exception as e:
            logger.error(
                "[%s] Connector failed to fetch URL '%s': %s", self.name, url, str(e)
            )
            return None

    @abstractmethod
    def fetch_jobs(self, limit: int = 20) -> List[Job]:
        """Fetches and normalizes job listings into Job objects."""
        pass
