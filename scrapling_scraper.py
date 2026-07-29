"""
Job Scraper Pro — Scrapling Engine (v2.0)
==========================================
A production-ready job scraper powered by Scrapling that:
- Bypasses anti-bot protection (Cloudflare, Akamai) via DynamicFetcher/StealthyFetcher
- Renders JavaScript-heavy pages 
- Extracts job listings + full individual job details
- Saves to styled Excel

Usage:
    from scrapling_scraper import NaukriScraper
    
    scraper = NaukriScraper()
    jobs = scraper.scrape_listing("https://www.naukri.com/ai-jobs")
    scraper.export_excel(jobs, "output.xlsx")
    
    # CLI:
    python scrapling_scraper.py "https://www.naukri.com/ai-jobs" -o results.xlsx
"""

import re
import sys
import time
import argparse
from typing import Optional


# ─── Helpers ────────────────────────────────────────────────────────────

def extract_bullets(text: str) -> list:
    """Extract bullet points from description text."""
    if not text or len(text) < 20:
        return []
    lines = re.split(r'[•·●◆◇▪▸▹►▻‣⁃⦿✦✧]\s*|[\n\r]+|(?:\d+[.)])\s*', text)
    result = []
    for line in lines:
        line = re.sub(r'\s+', ' ', line).strip()
        if len(line) > 10:
            result.append(line)
            if len(result) >= 50:
                break
    return result


def score_job_url(url: str) -> int:
    """Score URL as individual job posting (3+ = high confidence, 0 = not a job)."""
    try:
        from urllib.parse import urlparse
        path = urlparse(url).path
    except Exception:
        return 0
    score = 0
    if re.search(r'/(?:jobs|search|companies?|recruiters?|skills|location|salary)', path, re.I):
        if len(path.split('/')) <= 3 and not re.search(r'\d{5,}', path):
            return 0
        score = 1
    if re.search(r'/[a-zA-Z-]+-\d{5,}', path): score += 2
    if re.search(r'/\d{6,}', path): score += 3
    if re.search(r'\d{6,}', path): score += 1
    if '/job-listings' in path.lower(): score += 2
    if '/job-details' in path.lower(): score += 3
    if 'viewjob' in path.lower() or '?jk=' in url: score += 3
    if re.search(r'/jobs/view/', path, re.I): score += 3
    if re.search(r'/jobs/\d+/', path): score += 3
    if re.search(r'reviews?|rating|interview|salary|benefit|contact', path, re.I): return 0
    if len([p for p in path.split('/') if p]) <= 1: return 0
    return score


# ─── Excel Export ───────────────────────────────────────────────────────

def export_excel(jobs: list, filename: str = "jd_scraper_output.xlsx") -> str:
    """Export scraped jobs to a styled Excel file."""
    if not jobs:
        print("[!] No jobs to export.")
        return ""

    try:
        from openpyxl import Workbook
        from openpyxl.styles import Font, Alignment, PatternFill, Border, Side
        from openpyxl.utils import get_column_letter
    except ImportError:
        print("[!] openpyxl not installed. Install with: pip install openpyxl")
        return ""

    wb = Workbook()
    ws = wb.active
    ws.title = "Job Listings"

    header_font = Font(name='Calibri', bold=True, color='FFFFFF', size=11)
    header_fill = PatternFill(start_color='2F5496', end_color='2F5496', fill_type='solid')
    header_align = Alignment(horizontal='center', vertical='center', wrap_text=True)
    thin_border = Border(
        left=Side(style='thin'), right=Side(style='thin'),
        top=Side(style='thin'), bottom=Side(style='thin'),
    )
    data_font = Font(name='Calibri', size=10)
    data_align = Alignment(vertical='top', wrap_text=True)

    headers = [
        'S.No', 'Company Name', 'Job Role',
        'Job Description (Bullet Points)', 'Key Skills',
        'Location', 'Experience', 'Education',
        'Employment Type', 'Department', 'Industry',
        'Job Highlights', 'Source'
    ]
    col_widths = [6, 28, 35, 80, 35, 20, 15, 25, 18, 25, 25, 50, 15]

    for col_idx, (header, width) in enumerate(zip(headers, col_widths), 1):
        cell = ws.cell(row=1, column=col_idx, value=header)
        cell.font = header_font
        cell.fill = header_fill
        cell.alignment = header_align
        cell.border = thin_border
        ws.column_dimensions[get_column_letter(col_idx)].width = width

    for row_idx, job in enumerate(jobs, 2):
        desc_bullets = job.get('descriptionBullets', [])
        desc_text = '\n'.join(f'• {b}' for b in desc_bullets) if desc_bullets else job.get('description', '')
        skills_str = ', '.join(job.get('skills', [])) if job.get('skills') else ''

        row_data = [
            row_idx - 1,
            job.get('company', ''),
            job.get('role', ''),
            desc_text,
            skills_str,
            job.get('location', ''),
            job.get('experience', ''),
            job.get('education', ''),
            job.get('employmentType', ''),
            job.get('department', ''),
            job.get('industry', ''),
            job.get('highlights', ''),
            job.get('source', 'Scrapling'),
        ]
        for col_idx, value in enumerate(row_data, 1):
            cell = ws.cell(row=row_idx, column=col_idx, value=value)
            cell.font = data_font
            cell.alignment = data_align
            cell.border = thin_border

        bcount = len(desc_bullets)
        if bcount > 10:
            ws.row_dimensions[row_idx].height = min(400, bcount * 18)
        elif bcount > 3:
            ws.row_dimensions[row_idx].height = 120

    ws.freeze_panes = 'A2'
    ws.auto_filter.ref = f"A1:{get_column_letter(len(headers))}{len(jobs) + 1}"
    wb.save(filename)
    print(f"[OK] Saved {len(jobs)} jobs to '{filename}'")
    return filename


# ═════════════════════════════════════════════════════════════════════════
# NAUKRI SCRAPER
# ═════════════════════════════════════════════════════════════════════════

class NaukriScraper:
    """
    Scrape Naukri.com jobs using Scrapling with full anti-bot bypass.
    
    Example:
        scraper = NaukriScraper()
        jobs = scraper.scrape_listing("https://www.naukri.com/ai-jobs")
        scraper.export_excel(jobs, "output.xlsx")
    """

    def __init__(self, headless: bool = True, verbose: bool = True):
        self.headless = headless
        self.verbose = verbose
        self._logs = []

    def log(self, msg: str):
        if self.verbose:
            print(msg)
        self._logs.append(msg)

    # ── Scrapling API helpers ─────────────────────────────────────────
    # Scrapling Selector API:
    #   - el.text       → text content of element (string)
    #   - el.attrib     → dict of attributes
    #   - el.html_content → raw HTML string
    #   - el.css('::text').get()    → first text match
    #   - el.css('::text').getall() → all text matches as list

    def _sel_text(self, el) -> str:
        """Extract text from a Scrapling Selector element."""
        if el is None:
            return ''
        try:
            t = el.text
            return (t or '').strip()
        except Exception:
            return ''

    def _fetch_page(self, url: str):
        """Fetch a page using Scrapling's DynamicFetcher."""
        try:
            from scrapling.fetchers import DynamicFetcher
            page = DynamicFetcher.fetch(url, headless=self.headless, network_idle=True)
            return page
        except ImportError:
            try:
                from scrapling.fetchers import StealthyFetcher
                StealthyFetcher.adaptive = True
                page = StealthyFetcher.fetch(url, headless=self.headless, network_idle=True)
                return page
            except ImportError:
                self.log("[ERROR] Scrapling not installed! Run: pip install scrapling")
                return None

    def _check_captcha(self, page) -> bool:
        """Detect if page has anti-bot challenge."""
        body = (page.text or '').lower()
        return any(w in body for w in ['captcha', 'verify you are human', 'just a moment'])

    def _extract_text(self, page, selectors: list) -> str:
        """Extract text from first matching CSS selector."""
        for sel in selectors:
            els = page.css(sel)
            if els:
                t = self._sel_text(els[0])
                if t:
                    return t
        return ''

    def _extract_all_texts(self, page, selectors: list) -> list:
        """Extract text from ALL matching elements."""
        for sel in selectors:
            els = page.css(sel)
            if els:
                results = []
                seen = set()
                for el in els:
                    t = self._sel_text(el)
                    if t and t not in seen:
                        seen.add(t)
                        results.append(t)
                if results:
                    return results
        return []

    # ── Job Link Extraction ──────────────────────────────────────────

    def extract_job_links(self, page) -> list:
        """Extract all individual job URLs from a Naukri listing page."""
        links = []
        seen_urls = set()
        self.log("  Scanning for job links...")

        # ── Primary: Direct job link detection ────────────────
        # Naukri job URLs follow: /job-listings-{slug}-{id}
        job_link_els = page.css('a[href*="job-listings"]')
        if job_link_els:
            self.log(f"  [OK] Found {len(job_link_els)} direct job links")
            for link in job_link_els:
                try:
                    href = link.attrib.get('href', '')
                    if not href:
                        continue
                    if href.startswith('/'):
                        href = 'https://www.naukri.com' + href
                    if href in seen_urls:
                        continue
                    seen_urls.add(href)
                    title = (self._sel_text(link) or '').strip()
                    if len(title) < 2:
                        continue
                    links.append({'url': href, 'company': '', 'title': title[:120]})
                except Exception:
                    continue

        if links:
            self.log(f"  [OK] Extracted {len(links)} job links")
            return links

        # ── Tertiary: Fallback with score_job_url ─────────────
        self.log("  [!] Direct job links not found, scanning all links with URL scoring...")
        all_links = page.css('a[href]')
        for link in all_links:
            try:
                href = link.attrib.get('href', '')
                if not href or href.startswith('#') or href.startswith('javascript:'):
                    continue
                if href.startswith('/'):
                    href = 'https://www.naukri.com' + href
                s = score_job_url(href)
                if s >= 2 and href not in seen_urls:
                    seen_urls.add(href)
                    title = (self._sel_text(link) or '').strip()
                    if len(title) < 3:
                        continue
                    if any(w in title.lower() for w in ['view all', 'register', 'career',
                                                          'help center', 'interview', 'resume',
                                                          'salary', 'recommended', 'filter',
                                                          'review', 'rating']):
                        continue
                    links.append({'url': href, 'company': '', 'title': title[:120]})
            except Exception:
                continue
        self.log(f"  [OK] Fallback link scan: {len(links)} job links")
        return links

    # ── Individual Job Page ──────────────────────────────────────────

    def scrape_job_page(self, url: str) -> Optional[dict]:
        """Extract full job details from an individual Naukri job page."""
        self.log(f"\n  Fetching: {url[:80]}...")
        page = self._fetch_page(url)
        if not page:
            self.log("  [FAIL] Empty page")
            return None
        if self._check_captcha(page):
            self.log("  [FAIL] CAPTCHA")
            return None

        company = self._extract_text(page, ['.jd-header-title-company', 'a[class*="company"]',
                                            '[class*="company-name"]', '.companyInfo .companyName'])
        role = self._extract_text(page, ['.jd-header-title', 'h1[class*="title"]', 'h1'])
        description = self._extract_text(page, ['.job-details-description', '.jd-desc',
                                                'div[class*="description"]', '.job-description'])
        bullets = extract_bullets(description) if description else []
        skills = self._extract_all_texts(page, ['.key-skill', '.skill', '[class*="skill"] a'])
        location = self._extract_text(page, ['.location', '.loc', '[class*="location"]'])
        experience = self._extract_text(page, ['.experience', '.exp', '[class*="exp"]', '.work-exp'])
        education = self._extract_text(page, ['.education', '.edu', '[class*="education"]'])
        highlights = self._extract_text(page, ['.job-highlights', '.job-summary', '[class*="highlight"]'])

        emp_type = dept = industry = ''
        dt = self._extract_text(page, ['.other-details', '.job-other-details', '[class*="detail"]'])
        if dt:
            for line in re.split(r'[\n•▪]', dt):
                line = line.strip()
                if not line: continue
                if re.search(r'employment\s*type', line, re.I):
                    emp_type = re.sub(r'employment\s*type\s*:?\s*', '', line, flags=re.I).strip()
                elif re.search(r'industry', line, re.I) and 'employment' not in line.lower():
                    industry = re.sub(r'industry\s*(type)?\s*:?\s*', '', line, flags=re.I).strip()
                elif re.search(r'department|dept', line, re.I):
                    dept = re.sub(r'department\s*:?\s*', '', line, flags=re.I).strip()

        self.log(f"    Company: {company[:60] or '[MISSING]'}{' [OK]' if company else ''}")
        self.log(f"    Role: {role[:60] or '[MISSING]'}")
        self.log(f"    Description: {len(description)} chars, {len(bullets)} bullets")
        if skills: self.log(f"    Skills: {len(skills)}")
        if location: self.log(f"    Location: {location[:40]}")

        return {
            'company': company or '[COMPANY_NOT_FOUND]',
            'role': role or '[ROLE_NOT_FOUND]',
            'description': description or '',
            'descriptionBullets': bullets,
            'skills': skills, 'location': location or '',
            'experience': experience or '', 'education': education or '',
            'employmentType': emp_type or '', 'department': dept or '',
            'industry': industry or '', 'highlights': highlights or '',
            'source': 'scrapling-naukri',
        }

    # ── Full Pipeline ────────────────────────────────────────────────

    def scrape_listing(self, url: str, max_jobs: int = 50) -> list:
        """Full pipeline: listing page → extract URLs → scrape each → Excel."""
        self.log(f"\n{'='*60}")
        self.log("NAUKRI SCRAPER v2.0 (Scrapling)")
        self.log(f"{'='*60}")
        self.log(f"URL: {url}\n")

        # Step 1: Fetch listing
        self.log("Step 1: Fetching listing page...")
        page = self._fetch_page(url)
        if not page:
            self.log("[FAIL] Could not fetch")
            return []
        if self._check_captcha(page):
            self.log("[FAIL] CAPTCHA!")
            return []
        self.log(f"[OK] Loaded (title: {(page.css('title::text').get() or '')[:60]})")

        # Step 2: Extract links
        self.log("\nStep 2: Extracting job links...")
        job_links = self.extract_job_links(page)
        if not job_links:
            self.log("[FAIL] No job links found")
            return []
        if len(job_links) > max_jobs:
            job_links = job_links[:max_jobs]
        self.log(f"  Processing {len(job_links)} jobs")

        # Step 3: Scrape each
        self.log(f"\nStep 3: Scraping {len(job_links)} job pages...")
        jobs, seen_fp = [], set()
        for i, jl in enumerate(job_links, 1):
            self.log(f"\n--- Job {i}/{len(job_links)} ---")
            result = self.scrape_job_page(jl['url'])
            if result:
                if not result['company'] or result['company'].startswith('[COMPANY_'):
                    result['company'] = jl.get('company', '') or result['company']
                if not result['role'] or result['role'].startswith('[ROLE_'):
                    result['role'] = jl.get('title', '') or result['role']
                fp = f"{result['company']}|{result['role']}|{result['description'][:100]}"
                if fp not in seen_fp:
                    seen_fp.add(fp)
                    jobs.append(result)
                    self.log(f"  [OK] Added: {result['company'][:40]} — {result['role'][:40]}")
                else:
                    self.log(f"  [-] Duplicate")
            elif jl.get('company') or jl.get('title'):
                fb = {'company': jl.get('company', '') or '[MISSING]',
                       'role': jl.get('title', '') or '[MISSING]',
                       'description': '', 'descriptionBullets': [],
                       'skills': [], 'location': '', 'experience': '', 'education': '',
                       'employmentType': '', 'department': '', 'industry': '', 'highlights': '',
                       'source': 'listing-card'}
                jobs.append(fb)
                self.log(f"  [!] Listing card fallback: {fb['company'][:40]}")
            if i < len(job_links):
                time.sleep(1.5)

        self.log(f"\n{'='*60}")
        self.log(f"RESULT: {len(jobs)} jobs scraped!")
        self.log(f"{'='*60}")
        return jobs

    def export_excel(self, jobs: list, filename: str = "jd_scraper_output.xlsx") -> str:
        return export_excel(jobs, filename)


# ═════════════════════════════════════════════════════════════════════════
# CLI
# ═════════════════════════════════════════════════════════════════════════

def main():
    p = argparse.ArgumentParser(description='Job Scraper Pro — Scrapling Engine')
    p.add_argument('url', help='Naukri job search URL')
    p.add_argument('-o', '--output', default='jd_scraper_output.xlsx')
    p.add_argument('-m', '--max', type=int, default=50)
    p.add_argument('--quiet', action='store_true')
    p.add_argument('--visible', action='store_true')
    args = p.parse_args()

    scraper = NaukriScraper(headless=not args.visible, verbose=not args.quiet)
    jobs = scraper.scrape_listing(args.url, max_jobs=args.max)
    if jobs:
        scraper.export_excel(jobs, args.output)
        print(f"\nDone! {len(jobs)} jobs → '{args.output}'")
        return 0
    print("\nNo jobs found.")
    return 1


if __name__ == '__main__':
    sys.exit(main())
