"""
Test script to verify all project components work correctly.
"""

import os
import sys

# Ensure we can import project modules
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

print("=" * 60)
print("Job Scraper Pro - Test Suite")
print("=" * 60)

# Test 1: Module imports
print("\n[Test 1] Module imports...")
from scrapers.base_scraper import BaseScraper, JobListing, ScrapeResult
from scrapers.indeed_scraper import IndeedScraper
from scrapers.linkedin_scraper import LinkedInScraper
from scrapers.naukri_scraper import NaukriScraper
from utils.excel_writer import ExcelWriter
print("  [PASS] All modules imported successfully")

# Test 2: JobListing dataclass
print("\n[Test 2] JobListing dataclass...")
job = JobListing(
    company="Google",
    job_role="Software Engineer",
    description="We are looking for a talented engineer",
    description_bullets=["Develop features", "Write clean code", "Collaborate"],
    source="Indeed"
)
assert job.company == "Google"
assert job.job_role == "Software Engineer"
assert len(job.description_bullets) == 3
print("  [PASS] JobListing dataclass works correctly")

# Test 3: Deduplication
print("\n[Test 3] Deduplication...")
BaseScraper.reset_duplicates()
scraper = IndeedScraper()
assert not scraper.is_duplicate("unique description")
assert scraper.is_duplicate("unique description")
assert not scraper.is_duplicate("another unique description")
print("  [PASS] Deduplication works correctly")

# Test 4: Bullet point extraction
print("\n[Test 4] Bullet point extraction...")
text = """
We are looking for a software engineer to join our team!
- Develop new features
- Write clean, maintainable code
- Collaborate with cross-functional teams
- Participate in code reviews
"""
bullets = scraper._extract_bullet_points(text)
print(f"  Extracted {len(bullets)} bullet points")
assert len(bullets) >= 3, f"Expected at least 3 bullets, got {len(bullets)}"
print("  [PASS] Bullet extraction works correctly")

# Test 5: Text cleaning
print("\n[Test 5] Text cleaning...")
cleaned = scraper._clean_text("  Hello   World  ")
assert cleaned == "Hello World"
cleaned2 = scraper._clean_text("  ")
assert cleaned2 == ""
print("  [PASS] Text cleaning works correctly")

# Test 6: URL detection
print("\n[Test 6] URL detection...")
assert scraper._is_indeed_url("https://www.indeed.com/jobs?q=it")
assert not scraper._is_indeed_url("https://www.google.com")

linkedin_scraper = LinkedInScraper()
assert linkedin_scraper._is_linkedin_url("https://www.linkedin.com/jobs/search/?keywords=it")
assert not linkedin_scraper._is_linkedin_url("https://www.indeed.com")

naukri_scraper = NaukriScraper()
assert naukri_scraper._is_naukri_url("https://www.naukri.com/it-jobs")
assert not naukri_scraper._is_naukri_url("https://www.indeed.com")
print("  [PASS] URL detection works correctly")

# Test 7: Excel writer
print("\n[Test 7] Excel writer...")
jobs = [
    JobListing(company="Google", job_role="SWE",
               description="Develop software", description_bullets=["Develop", "Write code"],
               source="Indeed"),
    JobListing(company="Meta", job_role="ML Engineer",
               description="Build ML models", description_bullets=["Build ML models"],
               source="LinkedIn"),
]
writer = ExcelWriter()
path = writer.write_jobs(jobs, filename="test_output.xlsx")
assert os.path.exists(path), f"Excel file not found: {path}"
print(f"  [PASS] Excel file created: {path}")

# Clean up
os.remove(path)
print(f"  [PASS] Test file cleaned up")

# Test 8: Description fingerprint
print("\n[Test 8] Description fingerprint...")
fp1 = scraper._generate_description_fingerprint("Hello World")
fp2 = scraper._generate_description_fingerprint("Hello  World  ")
assert fp1 == fp2, "Fingerprints should match (normalized)"
print("  [PASS] Fingerprint generation works correctly")

print("\n" + "=" * 60)
print("All 8 tests passed successfully!")
print("=" * 60)
