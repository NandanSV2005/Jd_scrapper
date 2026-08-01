"""
Job Scraper Pro - Streamlit Web Application
Scrapes job listings from LinkedIn, Indeed, Naukri.com, and any generic page
and exports them to Excel.
"""

import os
import re
import traceback
from datetime import datetime

import streamlit as st

# Page config MUST be the first Streamlit command
st.set_page_config(
    page_title="Job Scraper Pro",
    page_icon="💼",
    layout="wide",
    initial_sidebar_state="expanded",
)

from scrapers.base_scraper import BaseScraper, JobListing
from scrapers.indeed_scraper import IndeedScraper
from scrapers.linkedin_scraper import LinkedInScraper
from scrapers.generic_scraper import GenericScraper
from utils.excel_writer import ExcelWriter
from scrapling_scraper import NaukriScraper as ScraplingNaukriScraper


# ─── Styling ────────────────────────────────────────────────────────────────

def apply_custom_styles():
    st.markdown("""
        <style>
        /* Main container */
        .main > div {
            padding: 1rem 2rem;
        }

        /* Title */
        .app-title {
            font-size: 2.5rem;
            font-weight: 800;
            background: linear-gradient(135deg, #1F4E79 0%, #4A90D9 100%);
            -webkit-background-clip: text;
            -webkit-text-fill-color: transparent;
            margin-bottom: 0.2rem;
        }
        .app-subtitle {
            color: #666;
            font-size: 1.1rem;
            margin-bottom: 2rem;
        }

        /* Cards */
        .card {
            background: white;
            border-radius: 12px;
            padding: 1.5rem;
            box-shadow: 0 2px 8px rgba(0,0,0,0.08);
            border: 1px solid #f0f0f0;
            margin-bottom: 1rem;
        }
        .card h3 {
            margin-top: 0;
            color: #1F4E79;
        }

        /* Results */
        .result-card {
            background: white;
            border-radius: 10px;
            padding: 1rem 1.5rem;
            box-shadow: 0 1px 4px rgba(0,0,0,0.06);
            border-left: 4px solid #4A90D9;
            margin-bottom: 0.8rem;
        }
        .result-card .company {
            font-weight: 700;
            color: #1F4E79;
            font-size: 1.1rem;
        }
        .result-card .role {
            color: #333;
            font-size: 0.95rem;
        }
        .result-card .source-badge {
            display: inline-block;
            padding: 0.15rem 0.6rem;
            border-radius: 12px;
            font-size: 0.75rem;
            font-weight: 600;
            color: white;
            margin-left: 0.5rem;
        }
        .badge-indeed { background: #003D9E; }
        .badge-linkedin { background: #0077B5; }
        .badge-naukri { background: #E9542A; }
        .badge-generic { background: #6B3FA0; }

        /* Stats */
        .stat-box {
            background: linear-gradient(135deg, #f8faff 0%, #eef4fb 100%);
            border-radius: 10px;
            padding: 1.2rem;
            text-align: center;
            border: 1px solid #e0e8f0;
        }
        .stat-number {
            font-size: 2rem;
            font-weight: 800;
            color: #1F4E79;
        }
        .stat-label {
            font-size: 0.85rem;
            color: #666;
            margin-top: 0.2rem;
        }

        /* Info box */
        .info-box {
            background: #FFF8E1;
            border-left: 4px solid #FFA000;
            padding: 1rem 1.5rem;
            border-radius: 8px;
            margin: 1rem 0;
        }

        /* Footer */
        .footer {
            text-align: center;
            color: #999;
            font-size: 0.8rem;
            margin-top: 3rem;
            padding: 1rem;
            border-top: 1px solid #f0f0f0;
        }
        </style>
    """, unsafe_allow_html=True)


# ─── Helper Functions ───────────────────────────────────────────────────────

def detect_source(url: str) -> str:
    """Automatically detect which job site the URL belongs to."""
    url_lower = url.lower()
    if "indeed.com" in url_lower:
        return "Indeed"
    elif "linkedin.com" in url_lower and "jobs" in url_lower:
        return "LinkedIn"
    elif "naukri.com" in url_lower:
        return "Naukri"
    return "Generic"


def get_scraper(source: str):
    """Get the appropriate scraper instance for the given source."""
    if source == "Indeed":
        return IndeedScraper()
    elif source == "LinkedIn":
        return LinkedInScraper()
    elif source in ("Generic", "Auto-Detect", "Naukri"):
        # Naukri uses Scrapling engine (handled separately in scrape flow)
        return GenericScraper()
    return None


def is_valid_url(url: str) -> bool:
    """Basic URL validation."""
    return url.startswith(("http://", "https://"))


# ─── Main App ───────────────────────────────────────────────────────────────

def main():
    apply_custom_styles()

    # ── Header ──────────────────────────────────────────────────────────
    col1, col2 = st.columns([3, 1])
    with col1:
        st.markdown('<div class="app-title">💼 Job Scraper Pro</div>',
                    unsafe_allow_html=True)
        st.markdown(
            '<div class="app-subtitle">'
            'Scrape job listings from LinkedIn, Indeed, Naukri (🦀 Scrapling anti-bot) & any website — '
            'export to Excel with bullet-pointed descriptions & deduplication'
            '</div>',
            unsafe_allow_html=True
        )

    with col2:
        st.markdown(
            f'<div style="text-align:right;padding-top:0.8rem;color:#999;">'
            f'<small>v3.0 • Scrapling Engine • {datetime.now().strftime("%b %Y")}</small>'
            f'</div>',
            unsafe_allow_html=True
        )

    # ── Sidebar ─────────────────────────────────────────────────────────
    with st.sidebar:
        st.markdown("## ⚙️ Settings")

        # Source info
        st.markdown("### Supported Sites")
        st.markdown("""
        - 🔵 **LinkedIn Jobs**
        - 🔵 **Indeed**
        - 🔵 **Naukri.com**
        - 🟣 **Any Website** (Generic)
        """)

        # Sample URLs
        st.markdown("### 📌 Sample URLs")
        st.markdown("""
        ```
        Naukri (🦀 Scrapling):
        https://www.naukri.com/ai-jobs

        Indeed:
        https://www.indeed.com/jobs?q=software+engineer

        LinkedIn:
        https://www.linkedin.com/jobs/search/
          ?keywords=software+engineer

        Any Page (Generic):
        https://example.com/companies
        ```
        """)

        st.divider()

        # About
        st.markdown("### ℹ️ About")
        st.markdown(
            "Enter any URL containing company/job listings, "
            "select the source, and scrape data to an Excel file."
        )

    # ── Main Content ────────────────────────────────────────────────────
    tab1, tab2 = st.tabs(["🔍 Scrape Jobs", "📋 How to Use"])

    # ── Tab 1: Scrape ───────────────────────────────────────────────────
    with tab1:
        col1, col2 = st.columns([2, 1])

        with col1:
            url = st.text_input(
                "**Enter URL**",
                placeholder="https://www.naukri.com/it-companies-in-india-cat116",
                help="Paste the URL of a job search page, company directory, or any page with listings",
            )

        with col2:
            # Auto-detect source, but let user override
            detected_source = detect_source(url) if url else "Unknown"
            source_options = ["Auto-Detect", "Indeed", "LinkedIn", "Naukri", "Generic"]
            default_idx = 0
            if detected_source != "Unknown":
                try:
                    default_idx = source_options.index(detected_source)
                except ValueError:
                    default_idx = 0

            selected_source = st.selectbox(
                "**Source**",
                options=source_options,
                index=default_idx if url and detected_source != "Unknown" else 0,
                help="Select the website type (Auto-Detect recommended)",
            )

        # ── Advanced Options ────────────────────────────────────────────
        with st.expander("⚡ Advanced Options"):
            col1, col2 = st.columns(2)

            with col1:
                use_playwright = st.checkbox(
                    "Use Playwright Browser",
                    value=True,
                    help="Enables JavaScript rendering. Required for most modern sites.",
                )
                dedup_enabled = st.checkbox(
                    "Enable Deduplication",
                    value=True,
                    help="Skip duplicate entries found in this session",
                )

            with col2:
                max_pages = st.number_input(
                    "Max pages to scrape",
                    min_value=1,
                    max_value=10,
                    value=1,
                    help="Only works with Indeed/LinkedIn/Naukri (not Generic)",
                )

            # ── Custom CSS Selectors (only shown for Generic mode) ────
            css_company = ""
            css_role = ""
            css_desc = ""

            show_css_selectors = (
                selected_source == "Generic" or
                (selected_source == "Auto-Detect" and detected_source in ("Unknown", "Generic")) or
                (selected_source == "Auto-Detect" and not url)
            )

            if show_css_selectors:
                st.markdown("---")
                st.markdown("#### 🎯 Custom CSS Selectors (for Generic mode)")

                st.markdown(
                    '<div class="info-box">'
                    '💡 <b>Don\'t know CSS selectors?</b> Just leave these blank — '
                    'the scraper will try to detect data automatically.<br>'
                    'If auto-detection fails, right-click an element on the page → '
                    '"Inspect" → copy the CSS selector and paste it below.'
                    '</div>',
                    unsafe_allow_html=True
                )

                cols = st.columns(3)
                with cols[0]:
                    css_company = st.text_input(
                        "Company CSS Selector",
                        placeholder="e.g., .company-name, td:nth-child(1) a",
                        help="CSS selector for company name elements",
                    )
                with cols[1]:
                    css_role = st.text_input(
                        "Job Role CSS Selector",
                        placeholder="e.g., .job-title, td:nth-child(2)",
                        help="CSS selector for job title/role elements",
                    )
                with cols[2]:
                    css_desc = st.text_input(
                        "Description CSS Selector",
                        placeholder="e.g., .description, td:nth-child(3)",
                        help="CSS selector for job description elements",
                    )

        # Scrape button
        col1, col2, col3 = st.columns([1, 2, 1])
        with col2:
            scrape_button = st.button(
                "🚀 Start Scraping",
                type="primary",
                use_container_width=True,
                disabled=not url,
            )

        # ── Results Area ────────────────────────────────────────────────
        if scrape_button:
            if not is_valid_url(url):
                st.error("❌ Please enter a valid URL starting with http:// or https://")
                st.stop()

            # Determine which source to use
            source = selected_source
            if source == "Auto-Detect":
                source = detect_source(url)

            # Reset deduplication if enabled
            if dedup_enabled:
                BaseScraper.reset_duplicates()

            # Get the scraper
            scraper = get_scraper(source)
            if not scraper:
                st.error(f"❌ No scraper available for {source}")
                st.stop()

            # Apply custom CSS selectors for Generic scraper
            if isinstance(scraper, GenericScraper):
                scraper.set_custom_selectors(
                    company_selector=css_company,
                    role_selector=css_role,
                    desc_selector=css_desc,
                )

            # Validate URL matches source (for known sites)
            if source == "Indeed" and "indeed.com" not in url.lower():
                st.warning("⚠️ URL doesn't look like an Indeed domain. Proceeding anyway...")
            elif source == "LinkedIn" and "linkedin.com" not in url.lower():
                st.warning("⚠️ URL doesn't look like a LinkedIn domain. Proceeding anyway...")
            elif source == "Naukri" and "naukri.com" not in url.lower():
                st.warning("⚠️ URL doesn't look like a Naukri domain. Proceeding anyway...")

            # Generic mode info
            if source == "Generic":
                st.info(
                    "🔄 **Generic Mode** — The scraper will try to automatically detect "
                    "company names and job roles on this page using multiple strategies "
                    "(JSON-LD, HTML tables, card patterns, text analysis).\n\n"
                    "If results are incomplete, try adding **Custom CSS Selectors** "
                    "in Advanced Options above."
                )

            # Progress indicators
            progress_bar = st.progress(0, text="Initializing scraper...")
            status_placeholder = st.empty()

            all_jobs = []

            try:
                # ── Naukri: Use Scrapling engine ────────────────────────
                if source == "Naukri":
                    status_placeholder.info(
                        "🦀 **Scrapling Engine Active** — Bypassing anti-bot & visiting each job page..."
                    )
                    progress_bar.progress(10, text="Initializing Scrapling (anti-bot bypass)...")

                    serial_scraper = ScraplingNaukriScraper(
                        headless=not use_playwright,
                        verbose=False
                    )

                    job_dicts = serial_scraper.scrape_listing(url, max_jobs=max_pages * 20)

                    if job_dicts:
                        seen = set()
                        for jd in job_dicts:
                            fp = f"{jd.get('company','')}|{jd.get('role','')}|{jd.get('description','')[:100]}"
                            if fp not in seen:
                                seen.add(fp)
                                all_jobs.append(JobListing(
                                    company=jd.get('company', ''),
                                    job_role=jd.get('role', ''),
                                    description=jd.get('description', ''),
                                    description_bullets=jd.get('descriptionBullets', []),
                                    source='Scrapling-Naukri',
                                ))
                        progress_bar.progress(100, text=f"Scraped {len(all_jobs)} jobs!")
                        st.success(f"✅ Scrapling extracted **{len(all_jobs)}** jobs!")
                    else:
                        progress_bar.empty()
                        status_placeholder.error(
                            "❌ Scrapling couldn't find any jobs on this page.\n\n"
                            "**Possible reasons:**\n"
                            "- The URL might not be a valid Naukri search results page\n"
                            "- The site structure may have changed\n"
                            "- Anti-bot protection may be blocking the request\n\n"
                            "Try with a different Naukri search URL."
                        )
                        st.stop()

                else:
                    # ── Other sources: use old scrapers ─────────────────
                    current_url = url
                    for page_num in range(max_pages):
                        status_placeholder.info(
                            f"🔄 Scraping page {page_num + 1} of {max_pages}..."
                        )
                        progress_bar.progress(
                            (page_num) / max_pages,
                            text=f"Scraping page {page_num + 1}..."
                        )

                        result = scraper.scrape(current_url, use_playwright=use_playwright)

                        if result.success:
                            all_jobs.extend(result.jobs)
                            st.toast(f"✅ Found {result.total_new} entries on page {page_num + 1}")

                        if page_num + 1 < max_pages:
                            if "start=" in current_url:
                                current_url = re.sub(r'start=\d+', f'start={(page_num + 1) * 10}', current_url)
                            elif "page=" in current_url:
                                current_url = re.sub(r'page=\d+', f'page={page_num + 2}', current_url)
                            else:
                                sep = "&" if "?" in current_url else "?"
                                if source == "Indeed":
                                    current_url = f"{current_url}{sep}start={10}"
                                else:
                                    break

                    progress_bar.progress(100, text="Scraping complete!")

                if not all_jobs:
                    status_placeholder.error(
                        f"❌ No data found on this page.\n\n"
                        f"**Possible reasons:**\n"
                        f"- The site uses strong anti-bot protection (Cloudflare, Akamai)\n"
                        f"- The page doesn't contain company/job listings\n"
                        f"- The data is loaded dynamically via JavaScript\n\n"
                        f"**Suggestions:**\n"
                        f"- Try selecting a different source type\n"
                        f"- Try with an Indeed job search URL instead\n"
                        f"- Use Custom CSS Selectors in Advanced Options"
                    )
                    st.stop()

                # ── Display Results ────────────────────────────────────
                status_placeholder.success(
                    f"✅ Successfully scraped **{len(all_jobs)}** entries!"
                )

                # Stats row
                st.markdown("### 📊 Summary")
                stats_cols = st.columns(4)

                companies = set(j.company for j in all_jobs)
                roles = set(j.job_role for j in all_jobs)
                sources = set(j.source for j in all_jobs)

                stats_data = [
                    ("📋 Total Entries", len(all_jobs)),
                    ("🏢 Companies", len(companies)),
                    ("💼 Job Roles", len(roles)),
                    ("🌐 Sources", ", ".join(sources)),
                ]

                for idx, (label, value) in enumerate(stats_data):
                    with stats_cols[idx]:
                        st.markdown(
                            f'<div class="stat-box">'
                            f'<div class="stat-number">{value}</div>'
                            f'<div class="stat-label">{label}</div>'
                            f'</div>',
                            unsafe_allow_html=True,
                        )

                # ── Preview Results ────────────────────────────────────
                st.markdown("### 👁️ Preview Results")
                st.markdown(f"Showing first 10 of {len(all_jobs)} entries:")

                for job in all_jobs[:10]:
                    badge_class = f"badge-{job.source.lower()}"
                    st.markdown(
                        f'<div class="result-card">'
                        f'<div class="company">{job.company}</div>'
                        f'<div class="role">{job.job_role} '
                        f'<span class="source-badge {badge_class}">{job.source}</span>'
                        f'</div>'
                        f'</div>',
                        unsafe_allow_html=True,
                    )

                if len(all_jobs) > 10:
                    st.markdown(f"... and {len(all_jobs) - 10} more entries")

                # ── Export to Excel ─────────────────────────────────────
                st.markdown("### 📥 Export to Excel")

                excel_writer = ExcelWriter()
                filepath = excel_writer.write_jobs(all_jobs)

                with open(filepath, "rb") as f:
                    excel_data = f.read()

                st.download_button(
                    label="📥 Download Excel File",
                    data=excel_data,
                    file_name=os.path.basename(filepath),
                    mime="application/vnd.openxmlformats-officedocument.spreadsheetml.sheet",
                    type="primary",
                    use_container_width=True,
                )

                st.success(f"✅ File saved: `{filepath}`")
                st.info("📁 **NextBuild Integration**: Scraped jobs have also been automatically exported as JSON into the `scraped_jds/` folder for instant fallback selection on the NextBuild website!")

            except Exception as e:
                progress_bar.empty()
                status_placeholder.error(f"❌ An error occurred during scraping:")
                st.exception(e)
                st.markdown(
                    "**Possible fixes:**\n"
                    "- Check your internet connection\n"
                    "- Make sure the URL is correct and accessible\n"
                    "- The website may have blocked automated requests\n"
                    "- Try using a different source type"
                )

    # ── Tab 2: How to Use ──────────────────────────────────────────────
    with tab2:
        st.markdown("## 📋 How to Use Job Scraper Pro")

        steps = [
            ("1️⃣ Find a URL",
             "Go to any job site, company directory, or page with listings. "
             "Copy the URL from your browser's address bar."),
            ("2️⃣ Paste the URL",
             "Paste the URL into the input field. The app will auto-detect "
             "the source type."),
            ("3️⃣ Select Source",
             "Choose the correct source. 'Auto-Detect' works for most URLs. "
             "Use 'Generic' for any other website."),
            ("4️⃣ Custom Selectors (Optional)",
             "If auto-detection doesn't find anything, use 'Advanced Options' "
             "to specify CSS selectors. Right-click an element → Inspect → "
             "copy the CSS selector."),
            ("5️⃣ Start Scraping",
             "Click 'Start Scraping' and wait for results."),
            ("6️⃣ Download Excel",
             "Preview results, then click 'Download Excel File'."),
        ]

        for title, desc in steps:
            st.markdown(
                f'<div class="card">'
                f'<h3>{title}</h3>'
                f'<p>{desc}</p>'
                f'</div>',
                unsafe_allow_html=True,
            )

        st.markdown("## 🎯 Features")
        features_cols = st.columns(3)
        features = [
            ("🔍 Multi-Site", "Scrape from LinkedIn, Indeed, Naukri & more"),
            ("🔄 Generic Mode", "Scrape company info from ANY website"),
            ("📄 Excel Export", "Formatted Excel with bullet points"),
            ("🚫 Dedup", "Automatic duplicate detection"),
            ("⚡ Playwright", "Browser automation for JS-heavy sites"),
            ("🎯 Custom Selectors", "Fine-tune extraction with CSS selectors"),
        ]
        for idx, (title, desc) in enumerate(features):
            with features_cols[idx % 3]:
                st.markdown(
                    f'<div class="result-card">'
                    f'<div style="font-weight:700;">{title}</div>'
                    f'<div style="color:#666;font-size:0.9rem;">{desc}</div>'
                    f'</div>',
                    unsafe_allow_html=True,
                )

        st.markdown("## 🎯 Tips for Generic Mode")
        st.markdown("""
        - **Company Directories** — Works well with sites listing company names
        - **Job Boards** — Works with most job board search results
        - **Tables** — Automatically detects data in HTML tables
        - **If nothing is found** — Use Custom CSS Selectors:
          1. Right-click a company name on the page → "Inspect"
          2. Copy the CSS selector (e.g., `.company-name`)
          3. Paste it in Advanced Options
          4. Do the same for job role and description
        """)

        st.markdown("## 🔧 Requirements")
        st.info(
            "📌 **Playwright Browsers:** For best results, install Playwright:\n\n"
            "`playwright install chromium`\n\n"
            "Without Playwright, some JavaScript-heavy sites may not work."
        )

    # ── Footer ─────────────────────────────────────────────────────────
    st.markdown(
        '<div class="footer">'
        'Job Scraper Pro v3.0 • 🦀 Scrapling Engine • Built with ❤️ using Streamlit & Python<br>'
        'Please respect websites\' terms of service and robots.txt'
        '</div>',
        unsafe_allow_html=True,
    )


if __name__ == "__main__":
    main()
