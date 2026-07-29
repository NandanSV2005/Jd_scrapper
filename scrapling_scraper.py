"""
Job Scraper Pro — Scrapling Engine (v4.0)
==========================================
Extracts job data from Naukri listing page cards using DynamicFetcher + BeautifulSoup.
No individual job page visits needed — Naukri blocks those server-side.

All data is parsed directly from the listing page's card elements:
  <div class="cust-job-tuple layout-wrapper lay-2 sjw__tuple">
    - Job title (a[href*=job-listings])
    - Company name (a[href*=-jobs-careers-])
    - Experience, Location
    - Description snippet
    - Skills/tags
    - etc.

Usage:
    python scrapling_scraper.py "https://www.naukri.com/ai-jobs" -o results.xlsx
"""

import re
import sys
import time
import argparse
from typing import Optional

from bs4 import BeautifulSoup


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


def clean_text(text: str) -> str:
    """Clean and normalize text."""
    if not text:
        return ''
    text = re.sub(r'\s+', ' ', text).strip()
    return text


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
        'Job Description', 'Key Skills',
        'Location', 'Experience',
        'Source'
    ]
    col_widths = [6, 28, 35, 70, 40, 22, 15, 18]

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
# NAUKRI SCRAPER — v4.0 (Card-based, no individual page visits)
# ═════════════════════════════════════════════════════════════════════════

class NaukriScraper:
    """
    Scrape Naukri.com jobs by parsing listing page cards with DynamicFetcher + BS4.
    
    Naukri blocks individual job page access (301 redirects). So this scraper
    extracts ALL available data from the listing page cards:
      <div class="cust-job-tuple layout-wrapper lay-2 sjw__tuple">
    
    Each card contains: job title, company name, experience, location,
    description snippet, and skills/tags.
    """

    def __init__(self, headless: bool = True, verbose: bool = True):
        self.headless = headless
        self.verbose = verbose
        self._logs = []

    def log(self, msg: str):
        if self.verbose:
            print(msg)
        self._logs.append(msg)

    # ── Page Fetching ─────────────────────────────────────────────

    def _fetch_listing(self, url: str) -> str:
        """Fetch listing page HTML using DynamicFetcher (JS rendering)."""
        try:
            from scrapling.fetchers import DynamicFetcher
            self.log("  Using DynamicFetcher (stealth browser)...")
            page = DynamicFetcher.fetch(url, headless=self.headless, network_idle=True)
            if not page:
                return ''
            html = page.html_content
            if not html or len(html) < 1000:
                # Try .text as fallback
                html = page.text or ''
            self.log(f"  [OK] Page loaded: {len(html)} chars")
            return html
        except ImportError:
            self.log("[ERROR] Scrapling not installed! Run: pip install scrapling")
            return ''
        except Exception as e:
            self.log(f"[ERROR] Failed to fetch: {e}")
            return ''

    # ── Card Extraction ──────────────────────────────────────────

    def extract_cards(self, html: str) -> list:
        """
        Parse job cards from listing page HTML using BeautifulSoup.
        Returns list of dicts with job data.
        """
        soup = BeautifulSoup(html, 'lxml')

        # Find all job card containers
        cards = soup.select('div.cust-job-tuple, div[class*="cust-job-tuple"], div.sjw__tuple')
        if not cards:
            self.log("[!] No job cards found via CSS selectors")
            return []

        self.log(f"  [OK] Found {len(cards)} job cards")

        jobs = []
        for card in cards:
            try:
                job = self._parse_card(card)
                if job.get('role'):
                    jobs.append(job)
            except Exception as e:
                continue

        self.log(f"  [OK] Parsed {len(jobs)} jobs from cards")
        return jobs

    def _parse_card(self, card) -> dict:
        """Extract all data from a single job card element."""

        # ── Job Title ──
        title_el = card.select_one('a[href*="job-listings"]')
        role = clean_text(title_el.get_text()) if title_el else ''

        # ── Company Name ──
        company_el = card.select_one('a[href*="-jobs-careers-"]')
        company = clean_text(company_el.get_text()) if company_el else ''

        # ── Full Card Text ──
        all_text = card.get_text(separator=' ', strip=True)
        all_text = re.sub(r'\s+', ' ', all_text)

        # ── Experience ──
        exp_match = re.search(r'(\d+[-\s]to\s*\d+|\d+[-\s]*\d+)\s*Yrs?', all_text, re.I)
        experience = exp_match.group(1).strip() + ' Yrs' if exp_match else ''

        # ── Location ──
        # After experience, the location is typically the next word/phrase
        locations = ['Bengaluru', 'Bangalore', 'Mumbai', 'Delhi', 'Pune', 'Hyderabad',
                     'Chennai', 'Kolkata', 'Ahmedabad', 'Gurugram', 'Gurgaon', 'Noida',
                     'Remote', 'Work From Home', 'India']
        location = ''
        if exp_match:
            after_exp = all_text[exp_match.end():]
            for loc in sorted(locations, key=len, reverse=True):
                if loc.lower() in after_exp.lower()[:80]:
                    # Find the actual location text
                    idx = after_exp.lower().find(loc.lower())
                    location = after_exp[idx:idx+len(loc)].strip()
                    break
        if not location:
            for loc in locations:
                if loc.lower() in all_text.lower():
                    idx = all_text.lower().find(loc.lower())
                    location = all_text[idx:idx+len(loc)].strip()
                    break

        # ── Skills ──
        # Skills are typically comma-separated or space-separated words after the description
        # Look for skill tag elements specifically
        skill_elements = card.select('[class*="skill"], [class*="key"], a[class*="skill"], span[class*="skill"]')
        skills = []
        for se in skill_elements:
            t = clean_text(se.get_text())
            if t and len(t) > 1:
                skills.append(t)

        # Fallback: extract skills from card text by looking for known skill patterns
        if not skills:
            # Skills are typically the words after "..." and before "day(s) ago"
            parts = re.split(r'\d+\s+day[s]?\s+ago|\d+\s+hour[s]?\s+ago|Today|Just now', all_text, flags=re.I)
            if len(parts) >= 2:
                skills_text = parts[-2]  # Part before the time ago
                # Remove description-like text
                skills_text = re.sub(r'Description:.*?Requirements:', '', skills_text, flags=re.I)
                # Extract capitalized words (common in skills)
                potential_skills = re.findall(r'\b[A-Z][a-zA-Z+#.]{2,40}\b', skills_text)
                # Filter out common non-skills
                exclude = {'Reviews', 'Yrs', 'Save', 'Today', 'Apply', 'View', 'More',
                           'Register', 'Login', 'Share', 'Facebook', 'Twitter', 'LinkedIn',
                           'Data', 'Science', 'Engineer', 'Engineering', 'Description',
                           'Requirements', 'Education', 'Job', 'Work', 'Bangalore',
                           'Bengaluru', 'Mumbai', 'India', 'Monday', 'Tuesday', 'Wednesday',
                           'Thursday', 'Friday', 'Saturday', 'Sunday', 'January', 'February',
                           'March', 'April', 'May', 'June', 'July', 'August', 'September',
                           'October', 'November', 'December', 'Senior', 'Junior', 'Lead',
                           'Principal', 'Staff', 'Associate', 'Manager', 'Director', 'Head'}
                skills = [s for s in potential_skills if s not in exclude][:15]

        # ── Description ──
        # Extract text between company+exp and skills  
        # The card text has this pattern:
        #   "Job Title Company Rating Reviews X-Y Yrs Location Description text... Skill1 Skill2 Skill3 N days ago"
        description = ''
        if exp_match:
            # Get text after experience+location and before skills
            desc_start = exp_match.end()
            desc_end = len(all_text)
            
            # Try to find where skills start (look for common patterns)
            skills_markers = ['\xa0', '  ', '…', '...']
            desc_segment = all_text[desc_start:]

            # Remove location from desc_segment
            if location and location in desc_segment:
                desc_segment = desc_segment[desc_segment.find(location) + len(location):]

            # Get clean description (first 200 chars or until we hit skill-like text)
            desc_segment = desc_segment.strip()
            # Remove "Apply" "Save" "Share" etc.
            desc_segment = re.sub(r'\b(Apply|Save|Share|View|More)\b.*', '', desc_segment, flags=re.I)
            # Remove age indicator
            desc_segment = re.sub(r'\d+\s+day[s]?\s+ago.*$', '', desc_segment, flags=re.I)
            desc_segment = re.sub(r'(Today|Just now).*$', '', desc_segment, flags=re.I)

            description = clean_text(desc_segment)

        if not description:
            # Try to get description from text after company
            if company and company in all_text:
                after_company = all_text[all_text.find(company) + len(company):]
                # Remove rating/reviews
                after_company = re.sub(r'\d+\.?\d*\s*\d*\s*Reviews?\s*', '', after_company)
                # Remove experience
                after_company = re.sub(r'\d+[-\s]\d+\s*Yrs?\s*', '', after_company)
                # Remove location
                if location:
                    after_company = after_company.replace(location, '')
                # Clean up
                description = clean_text(after_company[:300])

        # Limit description to first 300 chars for the snippet
        if len(description) > 300:
            description = description[:297] + '...'

        # Generate bullet points from description
        bullets = extract_bullets(description) if description else []

        return {
            'company': company or '',
            'role': role,
            'description': description,
            'descriptionBullets': bullets,
            'skills': skills,
            'location': location,
            'experience': experience,
            'source': 'scrapling-card',
        }

    # ── Full Pipeline ────────────────────────────────────────────

    def scrape_listing(self, url: str, max_jobs: int = 50) -> list:
        """Scrape Naukri listing: fetch page → parse cards → return data."""
        self.log(f"\n{'='*60}")
        self.log("NAUKRI SCRAPER v4.0 (Card-based extraction)")
        self.log(f"{'='*60}")
        self.log(f"URL: {url}\n")

        # Step 1: Fetch
        self.log("Step 1: Fetching listing page...")
        html = self._fetch_listing(url)
        if not html or len(html) < 5000:
            self.log("[FAIL] Page too small or empty")
            return []

        if 'access denied' in html[:2000].lower():
            self.log("[FAIL] Access denied by server")
            return []

        # Check page title
        title_match = re.search(r'<title>([^<]+)</title>', html, re.I)
        if title_match:
            self.log(f"  Title: {title_match.group(1)[:70]}")
        self.log(f"  Size: {len(html)} chars")

        # Step 2: Parse cards
        self.log("\nStep 2: Extracting job cards...")
        all_jobs = self.extract_cards(html)

        # Step 3: Deduplicate & limit
        if not all_jobs:
            self.log("[FAIL] No jobs extracted")
            return []

        seen = set()
        unique = []
        for job in all_jobs:
            fp = f"{job['company']}|{job['role']}|{job['description'][:50]}"
            if fp not in seen:
                seen.add(fp)
                unique.append(job)

        if len(unique) > max_jobs:
            unique = unique[:max_jobs]

        self.log(f"\n{'='*60}")
        self.log(f"RESULT: {len(unique)} jobs extracted!")
        has_desc = sum(1 for j in unique if j.get('description'))
        self.log(f"  With descriptions: {has_desc}/{len(unique)}")
        has_skills = sum(1 for j in unique if j.get('skills'))
        self.log(f"  With skills: {has_skills}/{len(unique)}")
        self.log(f"{'='*60}")
        return unique

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
        print(f"\nDone! {len(jobs)} jobs -> '{args.output}'")
        return 0
    print("\nNo jobs found.")
    return 1


if __name__ == '__main__':
    sys.exit(main())
