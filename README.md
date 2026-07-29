# 💼 Job Scraper Pro

A powerful web scraping tool that extracts job listings from **Indeed**, **LinkedIn Jobs**, and **Naukri.com** and exports them to a beautifully formatted Excel file with deduplication.

![Python](https://img.shields.io/badge/Python-3.14-blue)
![Streamlit](https://img.shields.io/badge/Streamlit-1.40-red)
![License](https://img.shields.io/badge/License-MIT-green)

---

## ✨ Features

- 🔍 **Multi-site scraping** — Supports Indeed, LinkedIn Jobs, and Naukri.com
- 📄 **Excel Export** — Clean, formatted Excel with Company Name, Job Role, and bullet-pointed descriptions
- 🚫 **Deduplication** — Automatically detects and skips duplicate job descriptions
- 🌐 **Playwright integration** — Handles JavaScript-heavy sites like LinkedIn
- 📊 **Live Preview** — See scraped results before downloading
- ⚡ **One-click download** — Exports directly from the browser

## 📋 Requirements

- Python 3.10+
- pip

## 🚀 Installation

```bash
# 1. Clone the repository
git clone https://github.com/NandanSV2005/Jd_scrapper.git
cd Jd_scrapper

# 2. Install Python dependencies
pip install -r requirements.txt

# 3. Install Playwright browsers (required for LinkedIn scraping)
playwright install chromium
```

## 🎮 Usage

```bash
# Launch the Streamlit web app
streamlit run app.py
```

Then:
1. Open the URL shown in terminal (usually `http://localhost:8501`)
2. Paste a job search URL (e.g., `https://www.indeed.com/jobs?q=software+engineer`)
3. Select the job source (Auto-Detect works for most URLs)
4. Click **"Start Scraping"**
5. Preview the results
6. Click **"Download Excel File"**

### 📌 Sample URLs

| Site | Sample URL |
|------|-----------|
| **Indeed** | `https://www.indeed.com/jobs?q=software+engineer` |
| **LinkedIn** | `https://www.linkedin.com/jobs/search/?keywords=software+engineer` |
| **Naukri** | `https://www.naukri.com/software-engineer-jobs` |

## 🏗️ Project Structure

```
Jd_scrapper/
├── app.py                   # Streamlit web application
├── requirements.txt         # Python dependencies
├── test_project.py          # Test suite (8 tests)
├── .gitignore               # Git ignore rules
├── scrapers/
│   ├── __init__.py
│   ├── base_scraper.py      # Shared scraping utilities & deduplication
│   ├── indeed_scraper.py    # Indeed.com scraper
│   ├── linkedin_scraper.py  # LinkedIn Jobs scraper (requests + Playwright)
│   └── naukri_scraper.py    # Naukri.com scraper
├── utils/
│   ├── __init__.py
│   └── excel_writer.py      # Formatted Excel export with styling
└── output/                  # Generated Excel files
```

## 🧪 Running Tests

```bash
python test_project.py
```

## ⚠️ Important Notes

- **Respect robots.txt**: This tool is for personal/educational use. Always check the website's `robots.txt` and terms of service.
- **Rate limiting**: The scraper includes random delays between requests to be respectful to servers.
- **LinkedIn scraping**: LinkedIn heavily relies on JavaScript. For best results, ensure Playwright browsers are installed (`playwright install chromium`).

## 📝 Output Format

The Excel file contains:

| Column | Content |
|--------|---------|
| S.No | Serial number |
| Company Name | Name of the hiring company |
| Job Role | Job title/position |
| Job Description | Bullet-pointed description |
| Source | Website origin (Indeed/LinkedIn/Naukri) |

## 🤝 Contributing

Pull requests are welcome! Feel free to add support for more job sites or improve existing scrapers.

## 📄 License

This project is open source and available under the [MIT License](LICENSE).

---

<div align="center">
Made with ❤️ using Python & Streamlit
</div>
