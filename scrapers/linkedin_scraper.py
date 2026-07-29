"""
LinkedIn Job Scraper - scrapes job listings from LinkedIn Jobs pages.
Uses Playwright for JavaScript-rendered content since LinkedIn is heavily dynamic.
"""

import re
import time
import json
from urllib.parse import urlparse

from bs4 import BeautifulSoup
from .base_scraper import BaseScraper, JobListing, ScrapeResult


class LinkedInScraper(BaseScraper):
    """Scraper for LinkedIn Jobs listings."""

    SUPPORTED_DOMAINS = ["linkedin.com", "www.linkedin.com"]

    def _is_linkedin_url(self, url: str) -> bool:
        """Check if the URL is a LinkedIn domain."""
        domain = urlparse(url).netloc.lower()
        return any(d in domain for d in ["linkedin.com"])

    def _extract_job_details_from_card(self, card) -> dict:
        """Extract job details from a LinkedIn job card element."""
        job_data = {}

        # Job title
        title_elem = None
        for selector in [
            "h3.base-search-card__title",
            "h3[class*='job-card']",
            "a[class*='job-card'] span",
            "[class*='job-title']",
            "h3",
        ]:
            title_elem = card.select_one(selector) if card else None
            if title_elem:
                break

        if title_elem:
            job_data["title"] = self._clean_text(title_elem.get_text())

        # Company name
        company_elem = None
        for selector in [
            "h4.base-search-card__subtitle",
            "a[class*='company']",
            "[class*='company-name']",
            "[class*='org-name']",
            "h4",
        ]:
            company_elem = card.select_one(selector) if card else None
            if company_elem:
                break

        if company_elem:
            job_data["company"] = self._clean_text(company_elem.get_text())

        # Job link
        link_elem = card.select_one("a[href*='/jobs/view']") if card else None
        if not link_elem:
            link_elem = card.find("a", href=re.compile(r"/jobs/view")) if card else None
        if link_elem:
            href = link_elem.get("href", "")
            # Clean up LinkedIn tracking parameters
            href = href.split("?")[0] if "?" in href else href
            job_data["link"] = href

        # Location
        location_elem = None
        for selector in [
            "[class*='job-location']",
            "[class*='location']",
            "span[class*='metadata']",
        ]:
            location_elem = card.select_one(selector) if card else None
            if location_elem:
                break
        if location_elem:
            job_data["location"] = self._clean_text(location_elem.get_text())

        return job_data

    def _parse_with_requests(self, url: str) -> ScrapeResult:
        """Attempt to scrape LinkedIn with requests first (limited success)."""
        result = ScrapeResult(source="LinkedIn")

        html = self._fetch_page(url)
        if not html:
            result.error_message = "Failed to fetch LinkedIn page with requests."
            return result

        soup = BeautifulSoup(html, "lxml")

        # Look for job cards in the search results
        job_cards = soup.select("li[class*='job-card']") or \
                    soup.select("div[class*='job-search-card']") or \
                    soup.select("a[class*='job-card']")

        if not job_cards:
            result.error_message = "No job cards found. LinkedIn requires JavaScript. Try using Playwright mode."
            return result

        result.total_found = len(job_cards)

        for card in job_cards:
            try:
                job_info = self._extract_job_details_from_card(card)
                if not job_info.get("title") or not job_info.get("company"):
                    continue

                job = JobListing(
                    company=job_info.get("company", "N/A"),
                    job_role=job_info.get("title", "N/A"),
                    description="",
                    description_bullets=[],
                    source="LinkedIn",
                )
                result.jobs.append(job)

            except Exception as e:
                print(f"[LinkedIn] Error processing card: {e}")
                continue

        result.total_new = len(result.jobs)
        result.success = len(result.jobs) > 0

        if not result.success:
            result.error_message = "No job listings could be extracted. LinkedIn requires JavaScript rendering."

        return result

    def _scrape_with_playwright(self, url: str) -> ScrapeResult:
        """
        Scrape LinkedIn using Playwright for full JavaScript rendering.
        This handles LinkedIn's dynamic content loading.
        """
        result = ScrapeResult(source="LinkedIn")

        try:
            from playwright.sync_api import sync_playwright
        except ImportError:
            result.error_message = "Playwright is not installed. Install with: pip install playwright && playwright install"
            return result

        jobs_data = []

        try:
            with sync_playwright() as p:
                browser = p.chromium.launch(headless=True)
                context = browser.new_context(
                    user_agent=self.ua.random,
                    viewport={"width": 1920, "height": 1080},
                )
                page = context.new_page()

                print(f"[LinkedIn] Navigating to: {url}")
                page.goto(url, wait_until="networkidle", timeout=60000)

                # Wait for job cards to load
                time.sleep(3)

                # Scroll down to load more jobs
                for _ in range(3):
                    page.evaluate("window.scrollTo(0, document.body.scrollHeight)")
                    time.sleep(1.5)

                # Get page content after JavaScript rendering
                content = page.content()
                soup = BeautifulSoup(content, "lxml")

                # Extract job cards
                job_cards = []

                # Try multiple selectors for job cards
                for selector in [
                    "li[class*='job-card']",
                    "div[class*='job-search-card']",
                    "article[class*='job']",
                    "div[class*='job-card']",
                    "[data-job-id]",
                    "[data-entity-urn*='job']",
                ]:
                    cards = soup.select(selector)
                    if cards:
                        job_cards = cards
                        print(f"[LinkedIn] Found {len(cards)} job cards with selector: {selector}")
                        break

                if not job_cards:
                    # Try finding all linkedin job links
                    job_links = page.query_selector_all("a[href*='/jobs/view']")
                    print(f"[LinkedIn] Found {len(job_links)} job links")

                    for link in job_links:
                        try:
                            href = link.get_attribute("href")
                            if not href:
                                continue

                            # Click on the job to load details
                            link.click()
                            time.sleep(1.5)

                            # Wait for details panel
                            try:
                                page.wait_for_selector("[class*='job-details']", timeout=5000)
                            except:
                                pass

                            # Extract job details from the selected job panel
                            try:
                                title_el = page.query_selector("h2[class*='job-title']")
                                company_el = page.query_selector("a[class*='company']")
                                desc_el = page.query_selector("div[class*='job-description']")

                                title = title_el.inner_text() if title_el else ""
                                company = company_el.inner_text() if company_el else ""
                                description = desc_el.inner_text() if desc_el else ""

                                # Clean up href
                                clean_href = href.split("?")[0]

                                jobs_data.append({
                                    "title": title,
                                    "company": company,
                                    "description": description,
                                    "link": clean_href,
                                })
                            except Exception as e:
                                print(f"[LinkedIn] Error extracting job details: {e}")
                                continue

                        except Exception as e:
                            print(f"[LinkedIn] Error clicking job link: {e}")
                            continue

                else:
                    # Process cards from BeautifulSoup
                    for card in job_cards:
                        job_info = self._extract_job_details_from_card(card)
                        if job_info.get("title") and job_info.get("company"):
                            jobs_data.append({
                                "title": job_info["title"],
                                "company": job_info["company"],
                                "description": "",
                                "link": job_info.get("link", ""),
                            })

                # Now try to get descriptions for each job
                # Click on each job and extract description
                result.total_found = len(jobs_data)

                for idx, job in enumerate(jobs_data):
                    try:
                        if job.get("link"):
                            # Navigate to job detail page
                            page.goto(job["link"], wait_until="networkidle", timeout=30000)
                            time.sleep(2)

                            # Try to expand "Show more" if present
                            try:
                                show_more = page.query_selector("button[aria-label*='Show more']")
                                if show_more:
                                    show_more.click()
                                    time.sleep(0.5)
                            except:
                                pass

                            # Extract description
                            desc_selectors = [
                                "[class*='job-description']",
                                "[class*='description']",
                                "article",
                                "div[class*='show-more']",
                            ]
                            description = ""
                            for sel in desc_selectors:
                                el = page.query_selector(sel)
                                if el:
                                    description = el.inner_text()
                                    break

                            if description:
                                job["description"] = description

                    except Exception as e:
                        print(f"[LinkedIn] Error fetching job details for {job['title']}: {e}")
                        continue

                browser.close()

        except Exception as e:
            result.error_message = f"Playwright scraping failed: {str(e)}"
            return result

        # Convert scraped data to JobListing objects
        for job_data in jobs_data:
            try:
                title = job_data.get("title", "").strip()
                company = job_data.get("company", "").strip()
                description = job_data.get("description", "").strip()

                if not title or not company:
                    continue

                # Deduplicate
                if description and self.is_duplicate(description):
                    print(f"[LinkedIn] Skipping duplicate: {title}")
                    continue

                bullets = self._extract_bullet_points(description) if description else []

                job = JobListing(
                    company=company,
                    job_role=title,
                    description=description,
                    description_bullets=bullets,
                    source="LinkedIn",
                )
                result.jobs.append(job)

            except Exception as e:
                print(f"[LinkedIn] Error processing job: {e}")
                continue

        result.total_new = len(result.jobs)
        result.success = len(result.jobs) > 0

        if not result.success:
            result.error_message = "No job listings could be extracted from LinkedIn."

        return result

    def scrape(self, url: str, use_playwright: bool = True) -> ScrapeResult:
        """
        Scrape job listings from a LinkedIn Jobs search page.

        Args:
            url: LinkedIn Jobs URL (e.g., https://www.linkedin.com/jobs/search/?keywords=it)
            use_playwright: If True, use Playwright for JS rendering. If False, use requests.

        Returns:
            ScrapeResult with scraped job data
        """
        if not self._is_linkedin_url(url):
            result = ScrapeResult(source="LinkedIn")
            result.error_message = "URL does not appear to be a LinkedIn domain."
            return result

        # First try with requests (basic)
        req_result = self._parse_with_requests(url)

        if use_playwright and (not req_result.success or not req_result.jobs):
            print("[LinkedIn] Requests approach failed. Falling back to Playwright...")
            return self._scrape_with_playwright(url)

        return req_result
