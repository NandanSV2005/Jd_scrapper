"""
Base scraper module with shared utilities for job scraping.
Provides common functionality used by all site-specific scrapers.
"""

import re
import time
import random
from typing import Optional
from dataclasses import dataclass, field

import requests
from bs4 import BeautifulSoup
from fake_useragent import UserAgent


@dataclass
class JobListing:
    """Represents a single job listing scraped from any website."""
    company: str = ""
    job_role: str = ""
    description: str = ""
    description_bullets: list = field(default_factory=list)
    skills: list = field(default_factory=list)
    location: str = ""
    experience: str = ""
    source: str = ""


@dataclass
class ScrapeResult:
    """Result of a scraping operation."""
    success: bool = False
    jobs: list = field(default_factory=list)
    total_found: int = 0
    total_new: int = 0
    error_message: str = ""
    source: str = ""


class BaseScraper:
    """Base class for job scrapers with shared utilities."""

    # Known description hash fingerprints to prevent duplicates
    _seen_descriptions: set = set()

    def __init__(self, timeout: int = 30, delay: tuple = (1, 3)):
        self.timeout = timeout
        self.delay = delay
        self.ua = UserAgent()
        self.session = requests.Session()

    def _get_headers(self, referer: str = "") -> dict:
        """Generate realistic browser headers to avoid blocking."""
        headers = {
            "Accept": "text/html,application/xhtml+xml,application/xml;q=0.9,image/avif,image/webp,image/apng,*/*;q=0.8",
            "Accept-Language": "en-US,en;q=0.9",
            "Accept-Encoding": "gzip, deflate, br",
            "Connection": "keep-alive",
            "Upgrade-Insecure-Requests": "1",
            "Sec-Fetch-Dest": "document",
            "Sec-Fetch-Mode": "navigate",
            "Sec-Fetch-Site": "none",
            "Sec-Fetch-User": "?1",
            "Cache-Control": "max-age=0",
            "User-Agent": self.ua.random,
        }
        if referer:
            headers["Referer"] = referer
        return headers

    def _fetch_page(self, url: str, referer: str = "") -> Optional[str]:
        """
        Fetch a page using requests with proper headers.
        Returns HTML content as string, or None on failure.
        """
        try:
            headers = self._get_headers(referer)
            response = self.session.get(url, headers=headers, timeout=self.timeout)
            response.raise_for_status()
            return response.text
        except requests.RequestException as e:
            print(f"[ERROR] Failed to fetch {url}: {e}")
            return None

    def _random_delay(self):
        """Add a random delay between requests to be respectful."""
        time.sleep(random.uniform(*self.delay))

    def _clean_text(self, text: str) -> str:
        """Clean and normalize scraped text."""
        if not text:
            return ""
        # Remove excess whitespace
        text = re.sub(r'\s+', ' ', text).strip()
        # Remove non-breaking spaces
        text = text.replace('\xa0', ' ')
        return text

    def _extract_bullet_points(self, text: str) -> list:
        """Convert job description text into structured bullet points."""
        if not text:
            return []

        bullets = []

        # Try splitting by common bullet indicators
        lines = re.split(r'[•·●◆◇▪▸▹►▻‣⁃⦿✦✧⬩⬨⬦▪️▫️-]\s*|\n+|(?:\d+[.)])\s*', text)

        for line in lines:
            line = self._clean_text(line)
            if line and len(line) > 10:  # Filter out very short fragments
                bullets.append(line)

        # If splitting didn't produce meaningful bullets, create sentences
        if len(bullets) < 2:
            # Try splitting by sentences
            sentences = re.split(r'(?<=[.!?])\s+', text)
            for sentence in sentences:
                sentence = self._clean_text(sentence)
                if sentence and len(sentence) > 15:
                    bullets.append(sentence)

        return bullets[:50]  # Limit to first 50 bullets

    def _generate_description_fingerprint(self, description: str) -> str:
        """Generate a fingerprint for a job description to detect duplicates."""
        # Normalize and hash the description
        normalized = re.sub(r'\s+', ' ', description.lower().strip())
        # Use first 100 chars as fingerprint (good enough for dedup)
        return normalized[:100]

    def is_duplicate(self, description: str) -> bool:
        """Check if a job description has already been seen."""
        fingerprint = self._generate_description_fingerprint(description)
        if fingerprint in self._seen_descriptions:
            return True
        self._seen_descriptions.add(fingerprint)
        return False

    @staticmethod
    def reset_duplicates():
        """Reset the duplicate tracking set (useful for new scraping sessions)."""
        BaseScraper._seen_descriptions.clear()

    def scrape(self, url: str, use_playwright: bool = True) -> ScrapeResult:
        """Override in subclasses to implement site-specific scraping."""
        raise NotImplementedError("Subclasses must implement scrape()")
