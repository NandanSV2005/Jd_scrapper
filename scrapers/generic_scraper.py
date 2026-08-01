"""
Generic/Universal Scraper - extracts company names, job roles, and descriptions
from ANY web page using multiple heuristics and Playwright stealth mode.

Works with:
- Company directory pages (e.g., Naukri company listings)
- Job search result pages from any site
- Any page with a list of companies/jobs
"""

import re
import time
import json

from bs4 import BeautifulSoup

from .base_scraper import BaseScraper, JobListing, ScrapeResult


class GenericScraper(BaseScraper):
    """
    A universal scraper that can extract company/job info from any page
    using multiple intelligent heuristics and browser automation.
    """

    # Common company name suffixes used for detection (structural only)
    COMPANY_SUFFIXES = [
        "inc", "ltd", "limited", "pvt", "private", "corp", "corporation",
        "llc", "llp", "plc", "gmbh", "ag", "sa", "bv", "nv", "pty",
        "technologies", "tech", "solutions", "services", "consulting",
        "group", "holdings", "enterprises", "systems", "software",
        "digital", "global", "international", "industries", "labs",
        "ventures", "partners", "associates", "analytics", "data",
        "infotech",
    ]

    def __init__(self, timeout: int = 60, delay: tuple = (2, 4)):
        super().__init__(timeout=timeout, delay=delay)
        self.custom_selectors = {}

    def set_custom_selectors(self, company_selector: str = "",
                             role_selector: str = "",
                             desc_selector: str = ""):
        """Set custom CSS selectors for data extraction."""
        if company_selector:
            self.custom_selectors["company"] = company_selector
        if role_selector:
            self.custom_selectors["role"] = role_selector
        if desc_selector:
            self.custom_selectors["description"] = desc_selector

    def _fetch_with_playwright(self, url: str) -> tuple:
        """
        Fetch a page using Playwright with stealth-like settings.
        Returns (html_content, page_title) or (None, None) on failure.

        Uses stealth techniques:
        - Realistic viewport
        - Proper headers/User-Agent
        - Waits for network idle
        - Scrolls to trigger lazy loading
        """
        try:
            from playwright.sync_api import sync_playwright
        except ImportError:
            print("[Generic] Playwright not installed.")
            return None, None

        try:
            with sync_playwright() as p:
                browser = p.chromium.launch(headless=True)
                context = browser.new_context(
                    user_agent=self.ua.random,
                    viewport={"width": 1920, "height": 1080},
                    locale="en-US",
                    timezone_id="Asia/Kolkata",
                    permissions=["geolocation"],
                )
                page = context.new_page()

                # Set extra HTTP headers
                page.set_extra_http_headers({
                    "Accept-Language": "en-US,en;q=0.9",
                    "Accept": "text/html,application/xhtml+xml,application/xml;q=0.9,*/*;q=0.8",
                })

                print(f"[Generic] Navigating to: {url}")
                page.goto(url, wait_until="networkidle", timeout=self.timeout * 1000)
                time.sleep(2)

                page_title = page.title()

                # Scroll down slowly to trigger lazy-loaded content
                for _ in range(5):
                    page.evaluate("window.scrollBy(0, 400)")
                    time.sleep(0.3)

                # Scroll back to top
                page.evaluate("window.scrollTo(0, 0)")
                time.sleep(0.3)

                content = page.content()
                browser.close()

                return content, page_title

        except Exception as e:
            print(f"[Generic] Playwright navigation failed: {e}")
            return None, None

    def _extract_via_heuristics(self, soup: BeautifulSoup, url: str) -> list:
        """
        Extract company/job data from ANY page using smart heuristics.
        Tries multiple strategies to find structured data.
        """
        all_extracted = []

        # Strategy 1: Extract JSON-LD structured data (most reliable)
        all_extracted.extend(self._extract_structured_data(soup))

        # Strategy 2: Look for table data
        if not all_extracted:
            all_extracted.extend(self._extract_from_tables(soup))

        # Strategy 3: Find card/list patterns
        if not all_extracted:
            all_extracted.extend(self._extract_from_cards(soup))

        # Strategy 4: Find company names via text patterns
        if not all_extracted:
            all_extracted.extend(self._extract_from_text_patterns(soup))

        return all_extracted

    def _extract_structured_data(self, soup: BeautifulSoup) -> list:
        """Extract data from JSON-LD structured data."""
        items = []
        scripts = soup.find_all("script", type="application/ld+json")

        for script in scripts:
            try:
                data = json.loads(script.string)

                # Handle single item or array
                if isinstance(data, dict):
                    data = [data]

                for item in data:
                    company = ""
                    role = ""
                    desc = ""

                    # Check for various schema types
                    item_type = item.get("@type", "")

                    if "JobPosting" in item_type:
                        company_obj = item.get("hiringOrganization", {})
                        if isinstance(company_obj, dict):
                            company = company_obj.get("name", "")
                        elif isinstance(company_obj, str):
                            company = company_obj
                        role = item.get("title", "")
                        desc = item.get("description", "") or item.get(
                            "responsibilities", "")

                    elif "Organization" in item_type or item_type in [
                        "Corporation", "Company", "LocalBusiness"
                    ]:
                        company = item.get("name", "")
                        role = "Company"

                    elif "ListItem" in item_type or "ItemList" in item_type:
                        # Could be a list of items
                        items_list = item.get("itemListElement", [])
                        for list_item in items_list:
                            if isinstance(list_item, dict):
                                list_item_data = list_item.get("item", list_item)
                                company = list_item_data.get("name", "")
                                if company:
                                    items.append({
                                        "company": company,
                                        "role": "Listed Company",
                                        "description": "",
                                    })
                        continue

                    if company and role:
                        items.append({
                            "company": company,
                            "role": role,
                            "description": desc,
                        })

            except (json.JSONDecodeError, AttributeError):
                continue

        if items:
            print(f"[Generic] Found {len(items)} items via JSON-LD structured data")
        return items

    def _extract_from_tables(self, soup: BeautifulSoup) -> list:
        """Extract data from HTML tables."""
        items = []
        tables = soup.find_all("table")

        for table in tables:
            rows = table.find_all("tr")
            if len(rows) < 2:
                continue

            # Get headers to understand columns
            headers = []
            header_row = table.find("thead")
            if header_row:
                headers = [th.get_text(strip=True).lower()
                          for th in header_row.find_all("th")]
            elif rows:
                headers = [th.get_text(strip=True).lower()
                          for th in rows[0].find_all("th")]

            # Detect which columns have company/job data
            company_col = -1
            role_col = -1
            desc_col = -1
            for i, h in enumerate(headers):
                h_lower = h.lower()
                if any(word in h_lower for word in
                       ["company", "organization", "firm", "employer", "name"]):
                    company_col = i
                elif any(word in h_lower for word in
                         ["job", "title", "position", "role", "designation"]):
                    role_col = i
                elif any(word in h_lower for word in
                         ["description", "details", "info", "about"]):
                    desc_col = i

            # If no headers detected, try to find company columns by content
            if company_col == -1:
                data_rows = rows[1:] if headers else rows
                if data_rows:
                    sample_row = data_rows[0]
                    cells = sample_row.find_all(["td", "th"])
                    for i, cell in enumerate(cells):
                        text = cell.get_text(strip=True).lower()
                        if any(suffix in text for suffix in
                               ["inc.", "ltd", "technologies", "pvt."]):
                            company_col = i
                            break

            # Extract data from rows
            start_row = 1 if headers else 0
            for row in rows[start_row:]:
                cells = row.find_all(["td", "th"])
                if not cells:
                    continue

                company = ""
                role = ""
                desc = ""

                if company_col >= 0 and company_col < len(cells):
                    company = self._clean_text(cells[company_col].get_text())
                elif cells:
                    # Use first cell as company name if it looks like one
                    first_text = self._clean_text(cells[0].get_text())
                    if self._looks_like_company(first_text):
                        company = first_text

                if role_col >= 0 and role_col < len(cells):
                    role = self._clean_text(cells[role_col].get_text())

                if desc_col >= 0 and desc_col < len(cells):
                    desc = self._clean_text(cells[desc_col].get_text())

                if company:
                    items.append({
                        "company": company,
                        "role": role or "Listed Entry",
                        "description": desc,
                    })

        if items:
            print(f"[Generic] Found {len(items)} items via table extraction")
        return items

    def _extract_from_cards(self, soup: BeautifulSoup) -> list:
        """Extract data from card/list patterns on the page."""
        items = []

        # Find potential card containers
        card_selectors = [
            "div[class*='card']", "div[class*='item']", "div[class*='list-item']",
            "div[class*='result']", "div[class*='entry']", "li[class*='list']",
            "article", "div[class*='company']", "div[class*='job']",
            "div[class*='tuple']", "div[class*='row']", "li[class*='item']",
            "div[class*='listing']", "section[class*='card']",
            "div[data-company]", "div[data-job]",
        ]

        cards = []
        for selector in card_selectors:
            found = soup.select(selector)
            if found:
                cards = found
                print(f"[Generic] Found {len(cards)} card elements via '{selector}'")
                break

        if not cards:
            # Try finding elements by common class patterns
            for cls_name in ["company", "employer", "job-card", "listing"]:
                found = soup.find_all(class_=re.compile(cls_name, re.I))
                if found and len(found) > 1:
                    cards = found
                    print(f"[Generic] Found {len(cards)} elements with class '{cls_name}'")
                    break

        if not cards:
            return items

        for card in cards:
            try:
                company = ""
                role = ""
                desc = ""

                # Try custom selectors first
                if self.custom_selectors.get("company"):
                    el = card.select_one(self.custom_selectors["company"])
                    if el:
                        company = self._clean_text(el.get_text())
                if self.custom_selectors.get("role"):
                    el = card.select_one(self.custom_selectors["role"])
                    if el:
                        role = self._clean_text(el.get_text())
                if self.custom_selectors.get("description"):
                    el = card.select_one(self.custom_selectors["description"])
                    if el:
                        desc = self._clean_text(el.get_text())

                # If custom selectors gave us data, use it
                if company and role:
                    items.append({
                        "company": company,
                        "role": role,
                        "description": desc,
                    })
                    continue

                # Auto-detect within card
                # Look for company name
                company_els = card.find_all(["a", "span", "div", "h3", "h4", "h2", "strong"],
                                            class_=re.compile(
                                                r"company|org|employer|name|title|heading", re.I))
                if not company_els:
                    # Try all links - often the most prominent link is the company/title
                    company_els = card.find_all(["a", "strong", "h3", "h4", "h2"])

                for el in company_els:
                    text = self._clean_text(el.get_text())
                    if text and len(text) > 1:
                        if not company and self._looks_like_company(text):
                            company = text
                        elif not role and not self._looks_like_company(text):
                            role = text

                # If we couldn't distinguish, use first as company, second as role
                if not company and not role and company_els:
                    texts = [self._clean_text(e.get_text())
                            for e in company_els
                            if self._clean_text(e.get_text())]
                    texts = [t for t in texts if len(t) > 1]
                    if texts:
                        company = texts[0]
                        if len(texts) > 1:
                            role = texts[1]

                # Get description
                desc_els = card.find_all(["p", "div", "span"],
                                         class_=re.compile(
                                             r"description|desc|summary|details|info|about",
                                             re.I))
                if desc_els:
                    desc = self._clean_text(desc_els[0].get_text())

                if company:
                    items.append({
                        "company": company,
                        "role": role or "Listed Entry",
                        "description": desc or "",
                    })

            except Exception as e:
                print(f"[Generic] Error processing card: {e}")
                continue

        if items:
            print(f"[Generic] Found {len(items)} items via card extraction")
        return items

    def _extract_from_text_patterns(self, soup: BeautifulSoup) -> list:
        """
        Extract company names by scanning page text for known patterns.
        This is a fallback when other methods fail.
        """
        items = []
        page_text = soup.get_text()

        # Look for company names using common patterns
        # Pattern: "Company Name - Job Title" or "Company Name is hiring"
        patterns = [
            # "Company is hiring for Job Title"
            rf'((?:{"|".join(self.COMPANY_SUFFIXES)})\s+(?:is|are|has)\s+hiring)',
            # "Join Company Name as a/an Job Title"
            r'Join\s+([A-Z][A-Za-z0-9\s&.]+?)\s+(?:as\s+(?:a|an)\s+)?([A-Z][A-Za-z\s/]+)',
            # Find words that look like company names (capitalized, followed by Inc/Ltd/LLC etc.)
            r'([A-Z][A-Za-z0-9\s&.-]+?)\s+(?:Inc\.?|Ltd\.?|Limited|LLC|LLP|Pvt\.?\s*Ltd\.?|Corp\.?|GmbH|Technologies|Tech|Solutions)\s',
        ]

        for pattern in patterns:
            matches = re.findall(pattern, page_text, re.IGNORECASE | re.MULTILINE)
            for match in matches:
                if isinstance(match, tuple):
                    company = self._clean_text(match[0])
                    role = self._clean_text(match[1]) if len(match) > 1 else ""
                else:
                    company = self._clean_text(match)
                    role = ""

                if company and len(company) > 2:
                    items.append({
                        "company": company,
                        "role": role or "Listed Entry",
                        "description": "",
                    })

        if items:
            print(f"[Generic] Found {len(items)} items via text pattern analysis")
        return items

    def _looks_like_company(self, text: str) -> bool:
        """Check if a text string looks like a company name."""
        text_lower = text.lower().strip()

        if len(text) < 3 or not text[0].isupper():
            return False

        # Strong signal: contains a company suffix
        if any(suffix in text_lower for suffix in self.COMPANY_SUFFIXES):
            return True

        # Strong signal: has 2+ capitalized words (e.g., "Acme Corp", "Tech Solutions")
        capitalized_words = len(re.findall(r'[A-Z][a-z]+', text))
        if capitalized_words >= 2:
            return True

        # Moderate signal: single capitalized word of reasonable length
        if capitalized_words == 1 and 4 <= len(text) <= 30:
            # Avoid common non-company words
            exclude_words = {
                "home", "about", "contact", "search", "login", "sign", "register",
                "jobs", "careers", "apply", "submit", "next", "previous", "page",
                "loading", "error", "menu", "navigation", "footer", "header",
                "skip", "share", "save", "cancel", "delete", "edit", "filter",
                "sort", "view", "list", "grid", "back", "more", "less", "all",
                "submit", "reset", "send", "close", "open", "help", "faq",
            }
            return text_lower not in exclude_words

        return False

    def scrape(self, url: str, use_playwright: bool = True) -> ScrapeResult:
        """
        Scrape company/job information from any URL.

        Args:
            url: Any URL that contains company or job listings

        Returns:
            ScrapeResult with extracted data
        """
        result = ScrapeResult(source="Generic")
        print(f"[Generic] Starting universal scrape of: {url}")

        # Step 1: Try fetching with Playwright (handles JS rendering)
        print("[Generic] Attempting with Playwright browser...")
        page_content, page_title = self._fetch_with_playwright(url)

        if page_content:
            print(f"[Generic] Page loaded: {page_title}")
            soup = BeautifulSoup(page_content, "lxml")
            extracted = self._extract_via_heuristics(soup, url)
        else:
            # Step 2: Fallback to requests
            print("[Generic] Playwright failed. Trying with requests...")
            html = self._fetch_page(url)
            if html:
                soup = BeautifulSoup(html, "lxml")
                extracted = self._extract_via_heuristics(soup, url)
            else:
                result.error_message = (
                    "Failed to fetch the page. The site may have "
                    "strong anti-bot protection (e.g., Cloudflare, Akamai). "
                    f"\n\nURL: {url}\n\n"
                    "Suggestions:\n"
                    "1. Try copying the page HTML and saving it as a file, "
                    "then use a different tool\n"
                    "2. Try with a different website (Indeed or LinkedIn)\n"
                    "3. For Indeed, use: https://www.indeed.com/jobs?q=your+search"
                )
                return result

        # Process extracted items
        result.total_found = len(extracted)

        for item in extracted:
            try:
                company = item.get("company", "").strip()
                role = item.get("role", "").strip()
                desc = item.get("description", "").strip()

                if not company or len(company) < 2:
                    continue
                if company.lower() in ["home", "about", "contact", "search"]:
                    continue

                # Deduplicate
                desc_key = desc[:100] if desc else company
                if self.is_duplicate(desc_key):
                    continue

                bullets = self._extract_bullet_points(desc) if desc else []

                job = JobListing(
                    company=company,
                    job_role=role or "Listed Entry",
                    description=desc,
                    description_bullets=bullets or ([desc] if desc else []),
                    source="Generic",
                )
                result.jobs.append(job)

            except Exception as e:
                print(f"[Generic] Error processing item: {e}")
                continue

        result.total_new = len(result.jobs)
        result.success = len(result.jobs) > 0

        if result.success:
            print(f"[Generic] Successfully extracted {result.total_new} entries")
        elif not result.error_message:
            result.error_message = (
                "Could not automatically detect company/job data on this page. "
                "Try using the 'Custom CSS Selectors' option in Advanced Settings."
            )

        return result
