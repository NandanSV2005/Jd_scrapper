"""
Indeed Job Scraper - scrapes job listings & single job view pages from Indeed.
Uses Playwright for JavaScript rendering to bypass anti-bot & Cloudflare blocks.
"""

import re
import time
from urllib.parse import urljoin, urlparse

from bs4 import BeautifulSoup
from .base_scraper import BaseScraper, JobListing, ScrapeResult


class IndeedScraper(BaseScraper):
    """Scraper for Indeed.com job listings."""

    BASE_URL = "https://www.indeed.com"
    SUPPORTED_DOMAINS = [
        "indeed.com", "www.indeed.com", "in.indeed.com",
        "uk.indeed.com", "ca.indeed.com", "au.indeed.com",
        "de.indeed.com", "fr.indeed.com"
    ]

    def _is_indeed_url(self, url: str) -> bool:
        """Check if the URL is an Indeed domain."""
        domain = urlparse(url).netloc.lower()
        return "indeed.com" in domain

    def _is_single_job_url(self, url: str) -> bool:
        """Check if URL points to a single viewjob page."""
        return "/viewjob" in url.lower() or "jk=" in url.lower() or "/rc/clk" in url.lower()

    def _parse_job_card(self, card) -> dict:
        """Parse job details from an Indeed search result card."""
        job_data = {}

        # Extract job title
        title_elem = card.find("h2", class_=re.compile(r"jobTitle|title"))
        if not title_elem:
            title_elem = card.find("a", attrs={"data-tn-element": "jobTitle"})
        if not title_elem:
            title_elem = card.select_one("a[id*='job_']")
        if title_elem:
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

        # Extract location
        loc_elem = card.find("div", attrs={"data-testid": "text-location"})
        if not loc_elem:
            loc_elem = card.find("div", class_=re.compile(r"companyLocation|location"))
        if loc_elem:
            job_data["location"] = self._clean_text(loc_elem.get_text())

        # Extract job link
        link_elem = card.find("a", href=re.compile(r"/company/|/pagead/|/rc/|/viewjob"))
        if link_elem:
            href = link_elem.get("href", "")
            job_data["link"] = urljoin(self.BASE_URL, href)

        return job_data

    def _scrape_single_job_with_playwright(self, url: str) -> ScrapeResult:
        """Scrape a single Indeed job posting page."""
        result = ScrapeResult(source="Indeed")

        try:
            from playwright.sync_api import sync_playwright
        except ImportError:
            result.error_message = "Playwright is required for Indeed scraping. Install with: pip install playwright && playwright install"
            return result

        try:
            with sync_playwright() as p:
                browser = p.chromium.launch(headless=True)
                context = browser.new_context(
                    user_agent="Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36",
                    viewport={"width": 1920, "height": 1080},
                )
                page = context.new_page()

                print(f"[Indeed] Navigating to single job: {url}")
                page.goto(url, wait_until="domcontentloaded", timeout=45000)
                time.sleep(3)

                content = page.content()
                soup = BeautifulSoup(content, "lxml")

                # Extract title
                title = ""
                for sel in ["h1.jobsearch-JobInfoHeader-title", "h1[class*='JobInfoHeader']", "h1"]:
                    el = soup.select_one(sel)
                    if el and el.get_text().strip():
                        title = self._clean_text(el.get_text())
                        break

                # Extract company
                company = ""
                for sel in ["div[data-testid='inlineHeader-companyName']", "span.jobsearch-CompanyReview--heading", "[data-company-name]"]:
                    el = soup.select_one(sel)
                    if el and el.get_text().strip():
                        company = self._clean_text(el.get_text())
                        break

                # Extract description
                description = ""
                desc_elem = soup.find(id="jobDescriptionText") or soup.select_one("div.jobsearch-JobComponent-description")
                if desc_elem:
                    description = self._clean_text(desc_elem.get_text(separator="\n"))

                if not title and not company and not description:
                    result.error_message = "Could not parse job details from Indeed viewjob page."
                    browser.close()
                    return result

                bullets = self._extract_bullet_points(description)
                job = JobListing(
                    company=company or "Indeed Featured Hiring Org",
                    job_role=title or "Software Engineer",
                    description=description or "Job posting details scraped from Indeed.",
                    description_bullets=bullets or [description] if description else [],
                    source="Indeed",
                )

                result.jobs.append(job)
                result.total_found = 1
                result.total_new = 1
                result.success = True
                browser.close()
                return result

        except Exception as e:
            print(f"[Indeed] Playwright single job error: {e}")
            result.error_message = f"Failed to scrape Indeed job page: {e}"
            return result

    def _scrape_with_playwright(self, url: str) -> ScrapeResult:
        """Scrape Indeed search or job page using Playwright."""
        if self._is_single_job_url(url):
            return self._scrape_single_job_with_playwright(url)

        result = ScrapeResult(source="Indeed")

        try:
            from playwright.sync_api import sync_playwright
        except ImportError:
            result.error_message = "Playwright is required for Indeed scraping. Install with: pip install playwright && playwright install"
            return result

        try:
            with sync_playwright() as p:
                browser = p.chromium.launch(headless=True)
                context = browser.new_context(
                    user_agent="Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36",
                    viewport={"width": 1920, "height": 1080},
                )
                page = context.new_page()

                print(f"[Indeed] Navigating to search URL: {url}")
                page.goto(url, wait_until="domcontentloaded", timeout=45000)
                time.sleep(3)

                for _ in range(2):
                    page.evaluate("window.scrollTo(0, document.body.scrollHeight)")
                    time.sleep(1)

                content = page.content()
                soup = BeautifulSoup(content, "lxml")

                job_cards = soup.find_all("div", class_=re.compile(r"job_seen_beacon|cardOutline|jobCard"))
                if not job_cards:
                    job_cards = soup.find_all("div", attrs={"data-testid": re.compile(r"job-card|slider")})
                if not job_cards:
                    job_cards = soup.find_all("li", class_=re.compile(r"jobListing|result"))

                if not job_cards:
                    browser.close()
                    return self._scrape_single_job_with_playwright(url)

                result.total_found = len(job_cards)

                for card in job_cards:
                    try:
                        job_info = self._parse_job_card(card)
                        if not job_info.get("title") and not job_info.get("company"):
                            continue

                        job = JobListing(
                            company=job_info.get("company", "Indeed Employer"),
                            job_role=job_info.get("title", "Software Engineer"),
                            description=f"Job posting for {job_info.get('title', 'role')} at {job_info.get('company', 'company')}.",
                            description_bullets=[f"Location: {job_info.get('location', 'N/A')}"],
                            source="Indeed",
                        )
                        if not self.is_duplicate(job.job_role + job.company):
                            result.jobs.append(job)

                    except Exception as e:
                        print(f"[Indeed] Error parsing card: {e}")
                        continue

                result.total_new = len(result.jobs)
                result.success = len(result.jobs) > 0
                if not result.success:
                    result.error_message = "No job cards extracted from Indeed page."

                browser.close()
                return result

        except Exception as e:
            print(f"[Indeed] Playwright error: {e}")
            result.error_message = f"Indeed Playwright scraping failed: {e}"
            return result

    def scrape(self, url: str, use_playwright: bool = True) -> ScrapeResult:
        """
        Scrape Indeed job listings with full Playwright & signature compatibility.
        """
        if not self._is_indeed_url(url):
            res = ScrapeResult(source="Indeed")
            res.error_message = "URL is not an Indeed domain."
            return res

        return self._scrape_with_playwright(url)
