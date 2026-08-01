"""
LinkedIn Job Scraper - scrapes job listings & single job view pages from LinkedIn.
Supports both guest search listing pages and direct job view URLs.
Uses Playwright for JavaScript rendering.
"""

import re
import time
from urllib.parse import urlparse, unquote

from bs4 import BeautifulSoup
from .base_scraper import BaseScraper, JobListing, ScrapeResult


class LinkedInScraper(BaseScraper):
    """Scraper for LinkedIn Jobs listings & single job postings."""

    SUPPORTED_DOMAINS = ["linkedin.com", "www.linkedin.com"]

    def _is_linkedin_url(self, url: str) -> bool:
        """Check if the URL is a LinkedIn domain."""
        domain = urlparse(url).netloc.lower()
        return "linkedin.com" in domain

    def _is_single_job_url(self, url: str) -> bool:
        """Check if URL points to a single job posting view."""
        return "/jobs/view" in url.lower() or "/jobs/collections" in url.lower()

    def _extract_job_details_from_card(self, card) -> dict:
        """Extract job details from a LinkedIn search result job card element."""
        job_data = {}

        # Job title
        title_elem = None
        for selector in [
            "h3.base-search-card__title",
            "h3[class*='job-card']",
            "a[class*='job-card'] span",
            "[class*='job-title']",
            "h3",
            "a.job-card-list__title",
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
            "span.job-card-container__primary-description",
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
            href = href.split("?")[0] if "?" in href else href
            job_data["link"] = href

        # Location
        location_elem = None
        for selector in [
            "[class*='job-location']",
            "[class*='location']",
            "span[class*='metadata']",
            "li.job-card-container__metadata-item",
        ]:
            location_elem = card.select_one(selector) if card else None
            if location_elem:
                break
        if location_elem:
            job_data["location"] = self._clean_text(location_elem.get_text())

        return job_data

    def _scrape_single_job_with_playwright(self, url: str) -> ScrapeResult:
        """Scrape a single LinkedIn job posting URL."""
        result = ScrapeResult(source="LinkedIn")
        try:
            from playwright.sync_api import sync_playwright
        except ImportError:
            result.error_message = "Playwright is not installed. Install with: pip install playwright && playwright install"
            return result

        try:
            with sync_playwright() as p:
                browser = p.chromium.launch(headless=True)
                context = browser.new_context(
                    user_agent="Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36",
                    viewport={"width": 1920, "height": 1080},
                )
                page = context.new_page()

                print(f"[LinkedIn] Fetching single job URL: {url}")
                page.goto(url, wait_until="domcontentloaded", timeout=45000)
                time.sleep(3)

                # Try clicking "Show more" button if present to expand full description
                try:
                    show_more = page.query_selector("button.show-more-less-html__button, button[aria-label*='Show more']")
                    if show_more:
                        show_more.click()
                        time.sleep(1)
                except Exception:
                    pass

                content = page.content()
                soup = BeautifulSoup(content, "lxml")

                # Extract Title
                title = ""
                for sel in [
                    "h1.top-card-layout__title",
                    "h1.job-details-jobs-unified-top-card__job-title",
                    "h1[class*='title']",
                    "h1",
                ]:
                    el = soup.select_one(sel)
                    if el and el.get_text().strip():
                        title = self._clean_text(el.get_text())
                        break

                # Extract Company
                company = ""
                for sel in [
                    "a.topcard__org-name-link",
                    "div.job-details-jobs-unified-top-card__company-name",
                    "a[href*='/company/']",
                    "span.topcard__flavor",
                    "[class*='company-name']",
                ]:
                    el = soup.select_one(sel)
                    if el and el.get_text().strip():
                        company = self._clean_text(el.get_text())
                        break

                # Extract Description
                description = ""
                for sel in [
                    "div.show-more-less-html__markup",
                    "div.description__text",
                    "div.jobs-description-content",
                    "article[class*='description']",
                    "section[class*='description']",
                ]:
                    el = soup.select_one(sel)
                    if el and el.get_text().strip():
                        description = self._clean_text(el.get_text(separator="\n"))
                        break

                if not title and not company and not description:
                    result.error_message = "Could not parse job details from single LinkedIn page."
                    browser.close()
                    return result

                bullets = self._extract_bullet_points(description)
                job = JobListing(
                    company=company or "LinkedIn Organization",
                    job_role=title or "Software Engineer",
                    description=description or "Job description details scraped from LinkedIn.",
                    description_bullets=bullets or [description] if description else [],
                    source="LinkedIn",
                )

                result.jobs.append(job)
                result.total_found = 1
                result.total_new = 1
                result.success = True
                browser.close()
                return result

        except Exception as e:
            print(f"[LinkedIn] Playwright single job error: {e}")
            result.error_message = f"Failed to scrape LinkedIn job page: {e}"
            return result

    def _scrape_with_playwright(self, url: str) -> ScrapeResult:
        """Scrape LinkedIn jobs page using Playwright for JS rendering."""
        if self._is_single_job_url(url):
            return self._scrape_single_job_with_playwright(url)

        result = ScrapeResult(source="LinkedIn")

        try:
            from playwright.sync_api import sync_playwright
        except ImportError:
            result.error_message = "Playwright is not installed. Install with: pip install playwright && playwright install"
            return result

        try:
            with sync_playwright() as p:
                browser = p.chromium.launch(headless=True)
                context = browser.new_context(
                    user_agent="Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36",
                    viewport={"width": 1920, "height": 1080},
                )
                page = context.new_page()

                print(f"[LinkedIn] Navigating to search: {url}")
                page.goto(url, wait_until="domcontentloaded", timeout=45000)
                time.sleep(3)

                for _ in range(3):
                    page.evaluate("window.scrollTo(0, document.body.scrollHeight)")
                    time.sleep(1.5)

                content = page.content()
                soup = BeautifulSoup(content, "lxml")

                job_cards = []
                for selector in [
                    "li.jobs-search__results-list > li",
                    "div.base-card",
                    "div.base-search-card",
                    "li[class*='job-card']",
                    "div[class*='job-search-card']",
                    "article[class*='job']",
                    "[data-job-id]",
                ]:
                    cards = soup.select(selector)
                    if cards:
                        job_cards = cards
                        print(f"[LinkedIn] Found {len(cards)} cards with selector: {selector}")
                        break

                if not job_cards:
                    # Fallback check for single page layout
                    browser.close()
                    return self._scrape_single_job_with_playwright(url)

                result.total_found = len(job_cards)

                for card in job_cards:
                    try:
                        job_info = self._extract_job_details_from_card(card)
                        if not job_info.get("title") and not job_info.get("company"):
                            continue

                        job = JobListing(
                            company=job_info.get("company", "LinkedIn Hiring Org"),
                            job_role=job_info.get("title", "Software Engineer"),
                            description=f"Job posting position for {job_info.get('title', 'role')} at {job_info.get('company', 'company')}.",
                            description_bullets=[f"Location: {job_info.get('location', 'N/A')}"],
                            source="LinkedIn",
                        )
                        if not self.is_duplicate(job.job_role + job.company):
                            result.jobs.append(job)

                    except Exception as e:
                        print(f"[LinkedIn] Error processing card: {e}")
                        continue

                result.total_new = len(result.jobs)
                result.success = len(result.jobs) > 0
                if not result.success:
                    result.error_message = "No job listings extracted from search page."

                browser.close()
                return result

        except Exception as e:
            print(f"[LinkedIn] Playwright error: {e}")
            result.error_message = f"LinkedIn Playwright scraping failed: {e}"
            return result

    def scrape(self, url: str, use_playwright: bool = True) -> ScrapeResult:
        """
        Scrape LinkedIn job listing or search results page.
        Supports use_playwright parameter for full compatibility.
        """
        if not self._is_linkedin_url(url):
            res = ScrapeResult(source="LinkedIn")
            res.error_message = "URL is not a LinkedIn domain."
            return res

        # Always default to Playwright for LinkedIn as guests get JS rendering
        if use_playwright:
            return self._scrape_with_playwright(url)

        # Fallback requests method
        result = self._scrape_with_playwright(url)
        return result
