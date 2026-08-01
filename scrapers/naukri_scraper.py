"""
Naukri.com Job Scraper - scrapes job listings & single job pages from Naukri.com.
"""

from urllib.parse import urlparse
from .base_scraper import BaseScraper, JobListing, ScrapeResult
from scrapling_scraper import NaukriScraper as StealthNaukriScraper


class NaukriScraper(BaseScraper):
    """Scraper for Naukri.com job listings & single job pages."""

    BASE_URL = "https://www.naukri.com"
    SUPPORTED_DOMAINS = ["naukri.com", "www.naukri.com"]

    def _is_naukri_url(self, url: str) -> bool:
        """Check if the URL is a Naukri domain."""
        domain = urlparse(url).netloc.lower()
        return "naukri.com" in domain

    def scrape(self, url: str, use_playwright: bool = True) -> ScrapeResult:
        """
        Scrape job listings or single job posting from Naukri.com.
        """
        result = ScrapeResult(source="Naukri")

        if not self._is_naukri_url(url):
            result.error_message = "URL does not appear to be a Naukri.com domain."
            return result

        try:
            stealth_scraper = StealthNaukriScraper(headless=use_playwright, verbose=False)
            job_dicts = stealth_scraper.scrape_listing(url)

            if job_dicts:
                for jd in job_dicts:
                    job = JobListing(
                        company=jd.get("company", "Naukri Organization"),
                        job_role=jd.get("role", "Software Role"),
                        description=jd.get("description", ""),
                        description_bullets=jd.get("descriptionBullets", []),
                        source="Naukri",
                    )
                    if not self.is_duplicate(job.job_role + job.company):
                        result.jobs.append(job)

                result.total_found = len(result.jobs)
                result.total_new = len(result.jobs)
                result.success = len(result.jobs) > 0

            if not result.success:
                result.error_message = "No job listings could be extracted from Naukri."

            return result

        except Exception as e:
            result.error_message = f"Naukri scraping failed: {e}"
            return result
