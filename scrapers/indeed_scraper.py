"""
Indeed Job Scraper - scrapes job listings from Indeed.com search results.
"""

import re
from urllib.parse import urljoin, urlparse, parse_qs

from bs4 import BeautifulSoup

from .base_scraper import BaseScraper, JobListing, ScrapeResult


class IndeedScraper(BaseScraper):
    """Scraper for Indeed.com job listings."""

    BASE_URL = "https://www.indeed.com"
    SUPPORTED_DOMAINS = ["indeed.com", "www.indeed.com", "in.indeed.com",
                         "uk.indeed.com", "ca.indeed.com", "au.indeed.com",
                         "de.indeed.com", "fr.indeed.com"]

    def _is_indeed_url(self, url: str) -> bool:
        """Check if the URL is an Indeed domain."""
        domain = urlparse(url).netloc.lower()
        return any(d in domain for d in ["indeed.com"])

    def _parse_job_card(self, card) -> dict:
        """Parse job details from an Indeed search result card."""
        job_data = {}

        # Extract job title
        title_elem = card.find("h2", class_=re.compile(r"jobTitle|title"))
        if not title_elem:
            title_elem = card.find("a", attrs={"data-tn-element": "jobTitle"})
        if title_elem:
            # Indeed often uses span inside the title element
            span = title_elem.find("span")
            if span:
                job_data["title"] = self._clean_text(span.get_text())
            else:
                job_data["title"] = self._clean_text(title_elem.get_text())

        # Extract company name
        company_elem = card.find("span", attrs={"data-testid": "company-name"})
        if not company_elem:
            company_elem = card.find("span", class_=re.compile(r"companyName|company"))
        if not company_elem:
            company_elem = card.find("div", class_=re.compile(r"heading6|company_location"))
        if company_elem:
            job_data["company"] = self._clean_text(company_elem.get_text())

        # Extract job link
        link_elem = card.find("a", href=re.compile(r"/company/|/pagead/|/rc/|/viewjob"))
        if link_elem:
            href = link_elem.get("href", "")
            job_data["link"] = urljoin(self.BASE_URL, href)

        # Extract salary if available
        salary_elem = card.find("div", class_=re.compile(r"salary|metadata"))
        if salary_elem:
            job_data["salary"] = self._clean_text(salary_elem.get_text())

        return job_data

    def _parse_job_description_page(self, job_url: str) -> tuple:
        """
        Fetch and parse a single job description page.
        Returns (description_text, description_bullets).
        """
        html = self._fetch_page(job_url, referer="https://www.indeed.com/")
        if not html:
            return "", []

        soup = BeautifulSoup(html, "lxml")

        # Try multiple selectors for job description
        desc_elem = None
        selectors = [
            {"id": "jobDescriptionText"},
            {"class_": "jobsearch-JobComponent-description"},
            {"class_": re.compile(r"jobDescription|job-description")},
            {"id": re.compile(r"jobDescription|job-description")},
            {"itemprop": "description"},
        ]

        for selector in selectors:
            if "id" in selector:
                desc_elem = soup.find(id=selector["id"])
            elif "class_" in selector:
                if isinstance(selector["class_"], str):
                    desc_elem = soup.find(class_=selector["class_"])
                else:
                    desc_elem = soup.find(class_=selector["class_"])
            elif "itemprop" in selector:
                desc_elem = soup.find(attrs={"itemprop": selector["itemprop"]})
            if desc_elem:
                break

        if not desc_elem:
            return "", []

        description_text = desc_elem.get_text(separator="\n", strip=True)
        bullets = self._extract_bullet_points(description_text)

        return description_text, bullets

    def scrape(self, url: str) -> ScrapeResult:
        """
        Scrape job listings from an Indeed search results page.

        Args:
            url: Indeed search URL (e.g., https://www.indeed.com/jobs?q=it)

        Returns:
            ScrapeResult with scraped job data
        """
        result = ScrapeResult(source="Indeed")

        if not self._is_indeed_url(url):
            result.error_message = "URL does not appear to be an Indeed.com domain."
            return result

        print(f"[Indeed] Fetching search page: {url}")
        html = self._fetch_page(url)
        if not html:
            result.error_message = "Failed to fetch Indeed search page."
            return result

        soup = BeautifulSoup(html, "lxml")

        # Find all job cards on the search results page
        job_cards = soup.find_all("div", class_=re.compile(r"job_seen_beacon|cardOutline|jobCard"))
        if not job_cards:
            # Try alternative selectors
            job_cards = soup.find_all("div", attrs={"data-testid": re.compile(r"job-card|slider")})
        if not job_cards:
            job_cards = soup.find_all("li", class_=re.compile(r"jobListing|result"))

        print(f"[Indeed] Found {len(job_cards)} job listings on search page")

        result.total_found = len(job_cards)

        for i, card in enumerate(job_cards):
            try:
                job_info = self._parse_job_card(card)
                if not job_info.get("title") or not job_info.get("company"):
                    continue

                # Fetch job description if we have a link
                description_text = ""
                description_bullets = []
                job_link = job_info.get("link", "")

                if job_link:
                    print(f"[Indeed] Fetching details for: {job_info['title']} at {job_info['company']}")
                    self._random_delay()
                    description_text, description_bullets = self._parse_job_description_page(job_link)

                # Deduplicate based on description
                if description_text and self.is_duplicate(description_text):
                    print(f"[Indeed] Skipping duplicate: {job_info['title']}")
                    continue

                # Fall back to snippet on search page if full description not available
                if not description_text:
                    snippet = card.find("div", class_=re.compile(r"job-snippet|summary"))
                    if snippet:
                        description_text = self._clean_text(snippet.get_text())
                        description_bullets = [description_text]

                job = JobListing(
                    company=job_info.get("company", "N/A"),
                    job_role=job_info.get("title", "N/A"),
                    description=description_text,
                    description_bullets=description_bullets or [description_text] if description_text else [],
                    source="Indeed",
                )
                result.jobs.append(job)

            except Exception as e:
                print(f"[Indeed] Error processing job card {i}: {e}")
                continue

        result.total_new = len(result.jobs)
        result.success = len(result.jobs) > 0

        if result.success:
            print(f"[Indeed] Successfully scraped {result.total_new} job listings")
        else:
            result.error_message = "No job listings could be extracted from this page."

        return result
