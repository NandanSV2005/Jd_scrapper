"""
Naukri.com Job Scraper - scrapes job listings from Naukri.com search results.
"""

import re
from urllib.parse import urljoin, urlparse

from bs4 import BeautifulSoup

from .base_scraper import BaseScraper, JobListing, ScrapeResult


class NaukriScraper(BaseScraper):
    """Scraper for Naukri.com job listings."""

    BASE_URL = "https://www.naukri.com"
    SUPPORTED_DOMAINS = ["naukri.com", "www.naukri.com"]

    def _is_naukri_url(self, url: str) -> bool:
        """Check if the URL is a Naukri domain."""
        domain = urlparse(url).netloc.lower()
        return any(d in domain for d in ["naukri.com"])

    def _extract_job_card_data(self, card) -> dict:
        """Extract job details from a Naukri job card."""
        job_data = {}

        # Job title
        title_elem = card.select_one("a[class*='title']")
        if not title_elem:
            title_elem = card.select_one("a[data-job-id]")
        if not title_elem:
            title_elem = card.find("a", class_=re.compile(r"title|jobTitle|job-link"))
        if title_elem:
            job_data["title"] = self._clean_text(title_elem.get_text())
            href = title_elem.get("href", "")
            if href and not href.startswith("http"):
                href = urljoin(self.BASE_URL, href)
            job_data["link"] = href

        # Company name
        company_elem = card.select_one("a[class*='company']")
        if not company_elem:
            company_elem = card.find("a", class_=re.compile(r"company|subTitle|org"))
        if not company_elem:
            company_elem = card.find("div", class_=re.compile(r"companyInfo|company-name"))
        if company_elem:
            job_data["company"] = self._clean_text(company_elem.get_text())

        # Experience
        exp_elem = card.find("span", class_=re.compile(r"experience|exp"))
        if exp_elem:
            job_data["experience"] = self._clean_text(exp_elem.get_text())

        # Location
        loc_elem = card.find("span", class_=re.compile(r"location|loc"))
        if not loc_elem:
            loc_elem = card.find("li", class_=re.compile(r"location|loc"))
        if loc_elem:
            job_data["location"] = self._clean_text(loc_elem.get_text())

        # Salary
        salary_elem = card.find("span", class_=re.compile(r"salary|sal"))
        if salary_elem:
            job_data["salary"] = self._clean_text(salary_elem.get_text())

        # Description snippet
        desc_elem = card.find("div", class_=re.compile(r"description|desc|job-desc"))
        if not desc_elem:
            desc_elem = card.find("span", class_=re.compile(r"description|desc|job-desc"))
        if desc_elem:
            job_data["description_snippet"] = self._clean_text(desc_elem.get_text())

        return job_data

    def _scrape_individual_job(self, job_url: str) -> tuple:
        """
        Scrape a single Naukri job page for full description.
        Returns (description_text, description_bullets).
        """
        html = self._fetch_page(job_url, referer="https://www.naukri.com/")
        if not html:
            return "", []

        soup = BeautifulSoup(html, "lxml")

        # Try multiple selectors for job description
        desc_elem = None
        for selector in [
            "div[class*='job-description']",
            "div[class*='description']",
            "section[class*='description']",
            "div[class*='jd']",
            "#jobDescription",
            "[class*='job-desc']",
            "article[class*='description']",
        ]:
            desc_elem = soup.select_one(selector)
            if desc_elem:
                break

        if not desc_elem:
            # Try generic approach
            desc_elem = soup.find("div", class_=re.compile(r"description|jobDescription", re.I))

        if not desc_elem:
            return "", []

        description_text = desc_elem.get_text(separator="\n", strip=True)
        bullets = self._extract_bullet_points(description_text)

        return description_text, bullets

    def scrape(self, url: str) -> ScrapeResult:
        """
        Scrape job listings from a Naukri.com search page.

        Args:
            url: Naukri search URL (e.g., https://www.naukri.com/it-jobs)

        Returns:
            ScrapeResult with scraped job data
        """
        result = ScrapeResult(source="Naukri")

        if not self._is_naukri_url(url):
            result.error_message = "URL does not appear to be a Naukri.com domain."
            return result

        print(f"[Naukri] Fetching search page: {url}")
        html = self._fetch_page(url)
        if not html:
            result.error_message = "Failed to fetch Naukri search page."
            return result

        soup = BeautifulSoup(html, "lxml")

        # Find job cards - Naukri uses various structures
        job_cards = []

        # Try various selectors
        for selector in [
            "article[class*='job']",
            "div[class*='jobCard']",
            "div[class*='list'] > div",
            "section[class*='job']",
            "div[class*='srp-job']",
            "div[class*='tuple']",
            "[data-job-id]",
            "li[class*='job']",
        ]:
            cards = soup.select(selector)
            if cards:
                job_cards = cards
                print(f"[Naukri] Found {len(cards)} job cards with selector: {selector}")
                break

        if not job_cards:
            # Last resort: try to find any div containing job-related attributes
            job_cards = soup.find_all("div", attrs={"data-job-id": re.compile(r".*")})

        print(f"[Naukri] Found {len(job_cards)} job listings on search page")
        result.total_found = len(job_cards)

        for i, card in enumerate(job_cards):
            try:
                job_info = self._extract_job_card_data(card)
                if not job_info.get("title") or not job_info.get("company"):
                    continue

                # Get description
                description_text = ""
                description_bullets = []

                if job_info.get("link"):
                    print(f"[Naukri] Fetching details for: {job_info['title']} at {job_info['company']}")
                    self._random_delay()
                    description_text, description_bullets = self._scrape_individual_job(job_info["link"])

                # Deduplicate
                if description_text and self.is_duplicate(description_text):
                    print(f"[Naukri] Skipping duplicate: {job_info['title']}")
                    continue

                # Fall back to snippet if full description not available
                if not description_text and job_info.get("description_snippet"):
                    snippet = job_info["description_snippet"]
                    description_text = snippet
                    description_bullets = [snippet]

                job = JobListing(
                    company=job_info.get("company", "N/A"),
                    job_role=job_info.get("title", "N/A"),
                    description=description_text,
                    description_bullets=description_bullets or [description_text] if description_text else [],
                    source="Naukri",
                )
                result.jobs.append(job)

            except Exception as e:
                print(f"[Naukri] Error processing job card {i}: {e}")
                continue

        result.total_new = len(result.jobs)
        result.success = len(result.jobs) > 0

        if result.success:
            print(f"[Naukri] Successfully scraped {result.total_new} job listings")
        else:
            result.error_message = "No job listings could be extracted from this page."

        return result
