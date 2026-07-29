"""
Job Scraper Pro - Streamlit Web Application
Scrapes job listings from LinkedIn, Indeed, and Naukri.com
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

from scrapers.base_scraper import BaseScraper
from scrapers.indeed_scraper import IndeedScraper
from scrapers.linkedin_scraper import LinkedInScraper
from scrapers.naukri_scraper import NaukriScraper
from utils.excel_writer import ExcelWriter


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
    return "Unknown"


def get_scraper(source: str):
    """Get the appropriate scraper instance for the given source."""
    if source == "Indeed":
        return IndeedScraper()
    elif source == "LinkedIn":
        return LinkedInScraper()
    elif source == "Naukri":
        return NaukriScraper()
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
            'Scrape job listings from LinkedIn, Indeed & Naukri — '
            'export to Excel with bullet-pointed descriptions & deduplication'
            '</div>',
            unsafe_allow_html=True
        )

    with col2:
        st.markdown(
            f'<div style="text-align:right;padding-top:0.8rem;color:#999;">'
            f'<small>v1.0 • {datetime.now().strftime("%b %Y")}</small>'
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
        """)

        # Sample URLs
        st.markdown("### 📌 Sample URLs")
        st.markdown("""
        ```
        Indeed:
        https://www.indeed.com/jobs?q=software+engineer

        LinkedIn:
        https://www.linkedin.com/jobs/search/
          ?keywords=software+engineer

        Naukri:
        https://www.naukri.com/
          software-engineer-jobs
        ```
        """)

        st.divider()

        # About
        st.markdown("### ℹ️ About")
        st.markdown(
            "Enter a job search URL, select the source, and scrape "
            "job listings to an Excel file with deduplication."
        )

    # ── Main Content ────────────────────────────────────────────────────
    tab1, tab2 = st.tabs(["🔍 Scrape Jobs", "📋 How to Use"])

    # ── Tab 1: Scrape ───────────────────────────────────────────────────
    with tab1:
        col1, col2 = st.columns([2, 1])

        with col1:
            url = st.text_input(
                "**Job Search URL**",
                placeholder="https://www.indeed.com/jobs?q=software+engineer",
                help="Paste the URL of a job search results page",
            )

        with col2:
            # Auto-detect source, but let user override
            detected_source = detect_source(url) if url else "Unknown"
            source_options = ["Auto-Detect", "Indeed", "LinkedIn", "Naukri"]
            default_idx = 0
            if detected_source != "Unknown":
                try:
                    default_idx = source_options.index(detected_source)
                except ValueError:
                    default_idx = 0

            selected_source = st.selectbox(
                "**Job Source**",
                options=source_options,
                index=0,
                help="Select the job site to scrape (Auto-Detect recommended)",
            )

        # Advanced options
        with st.expander("⚡ Advanced Options"):
            col1, col2, col3 = st.columns(3)
            with col1:
                use_playwright = st.checkbox(
                    "Use Playwright (Browser)",
                    value=True,
                    help="Enables JavaScript rendering for LinkedIn. Requires Playwright to be installed.",
                )
            with col2:
                max_pages = st.number_input(
                    "Max pages to scrape",
                    min_value=1,
                    max_value=10,
                    value=1,
                    help="Number of pages of results to scrape (1 page ≈ 15-20 jobs)",
                )
            with col3:
                dedup_enabled = st.checkbox(
                    "Enable Deduplication",
                    value=True,
                    help="Skip job descriptions that have already been scraped in this session",
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
                if source == "Unknown":
                    st.error(
                        "❌ Could not auto-detect the job source. "
                        "Please select the source manually."
                    )
                    st.stop()

            # Reset deduplication if enabled
            if dedup_enabled:
                BaseScraper.reset_duplicates()

            # Get the scraper
            scraper = get_scraper(source)
            if not scraper:
                st.error(f"❌ No scraper available for {source}")
                st.stop()

            # Validate URL matches source
            if source == "Indeed" and "indeed.com" not in url.lower():
                st.warning("⚠️ URL doesn't look like an Indeed domain. Proceeding anyway...")
            elif source == "LinkedIn" and "linkedin.com" not in url.lower():
                st.warning("⚠️ URL doesn't look like a LinkedIn domain. Proceeding anyway...")
            elif source == "Naukri" and "naukri.com" not in url.lower():
                st.warning("⚠️ URL doesn't look like a Naukri domain. Proceeding anyway...")

            # Progress indicators
            progress_bar = st.progress(0, text="Initializing scraper...")
            status_placeholder = st.empty()

            all_jobs = []

            try:
                # Scrape (with pagination support)
                current_url = url
                for page_num in range(max_pages):
                    status_placeholder.info(
                        f"🔄 Scraping page {page_num + 1} of {max_pages}..."
                    )
                    progress_bar.progress(
                        (page_num) / max_pages,
                        text=f"Scraping page {page_num + 1}..."
                    )

                    if source == "LinkedIn":
                        result = scraper.scrape(current_url, use_playwright=use_playwright)
                    else:
                        result = scraper.scrape(current_url)

                    if result.success:
                        all_jobs.extend(result.jobs)
                        st.toast(f"✅ Found {result.total_new} jobs on page {page_num + 1}")

                    # For multi-page support, try to find next page URL
                    # (simplified - in production, you'd parse for "Next" links)
                    if page_num + 1 < max_pages:
                        # Add page parameter to URL
                        if "start=" in current_url:
                            current_url = re.sub(r'start=\d+', f'start={(page_num + 1) * 10}', current_url)
                        elif "page=" in current_url:
                            current_url = re.sub(r'page=\d+', f'page={page_num + 2}', current_url)
                        else:
                            # Try appending page parameter
                            separator = "&" if "?" in current_url else "?"
                            if source == "Indeed":
                                current_url = f"{current_url}{separator}start={10}"
                            else:
                                break  # Can't paginate, stop here

                progress_bar.progress(100, text="Scraping complete!")

                if not all_jobs:
                    status_placeholder.error(
                        f"❌ No jobs found. The site may have blocked the scraper or "
                        f"the page structure may have changed.\n\n"
                        f"**Tips:**\n"
                        f"- Try using a different job search URL\n"
                        f"- For LinkedIn, make sure Playwright is installed "
                        f"(run: `playwright install chromium`)\n"
                        f"- Some sites require browser automation to bypass anti-bot protections"
                    )
                    st.stop()

                # ── Display Results ────────────────────────────────────
                status_placeholder.success(
                    f"✅ Successfully scraped **{len(all_jobs)}** job listings!"
                )

                # Stats row
                st.markdown("### 📊 Summary")
                stats_cols = st.columns(4)

                companies = set(j.company for j in all_jobs)
                roles = set(j.job_role for j in all_jobs)
                sources = set(j.source for j in all_jobs)

                stats_data = [
                    ("📋 Total Jobs", len(all_jobs)),
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
                st.markdown(f"Showing first 10 of {len(all_jobs)} jobs:")

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
                    st.markdown(f"... and {len(all_jobs) - 10} more jobs")

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

            except Exception as e:
                progress_bar.empty()
                status_placeholder.error(f"❌ An error occurred during scraping:")
                st.exception(e)
                st.markdown(
                    "**Possible fixes:**\n"
                    "- Check your internet connection\n"
                    "- Make sure the URL is correct and accessible\n"
                    "- For LinkedIn, install Playwright browsers: run `playwright install`\n"
                    "- The website may have blocked automated requests"
                )

    # ── Tab 2: How to Use ──────────────────────────────────────────────
    with tab2:
        st.markdown("## 📋 How to Use Job Scraper Pro")

        steps = [
            ("1️⃣ Find Job Listings",
             "Go to LinkedIn Jobs, Indeed, or Naukri.com and search for the "
             "type of jobs you want. Copy the URL from your browser's address bar."),
            ("2️⃣ Paste the URL",
             "Paste the job search URL into the input field. The app will "
             "auto-detect which site it's from."),
            ("3️⃣ Select Source",
             "Choose the correct job site. 'Auto-Detect' works for most URLs."),
            ("4️⃣ Start Scraping",
             "Click 'Start Scraping' and wait for the results. The app will "
             "extract job titles, company names, and descriptions."),
            ("5️⃣ Download Excel",
             "Preview the results, then click 'Download Excel File' to save "
             "everything to a formatted spreadsheet."),
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
            ("🔍 Multi-Site", "Scrape from LinkedIn, Indeed, and Naukri.com"),
            ("📄 Excel Export", "Well-formatted Excel with bullet points"),
            ("🔄 Dedup", "Automatic duplicate detection"),
            ("⚡ Playwright", "Browser automation for JS-heavy sites"),
            ("📊 Preview", "See results before downloading"),
            ("🆓 Free & Open", "No API keys required"),
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

        st.markdown("## 🔧 Requirements")
        st.info(
            "📌 **Playwright Browsers:** For LinkedIn scraping, you may need to install "
            "Playwright browsers. Run this command in your terminal:\n\n"
            "`playwright install chromium`\n\n"
            "Without this, some features may be limited."
        )

    # ── Footer ─────────────────────────────────────────────────────────
    st.markdown(
        '<div class="footer">'
        'Job Scraper Pro • Built with ❤️ using Streamlit & Python<br>'
        'Please respect websites\' terms of service and robots.txt'
        '</div>',
        unsafe_allow_html=True,
    )


if __name__ == "__main__":
    main()
