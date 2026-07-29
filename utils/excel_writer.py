"""
Excel Writer Utility - handles exporting scraped job data to Excel files
with deduplication and proper formatting.
"""

import os
from datetime import datetime
from typing import List

from openpyxl import Workbook
from openpyxl.styles import Font, Alignment, PatternFill, Border, Side
from openpyxl.utils import get_column_letter

from scrapers.base_scraper import JobListing


class ExcelWriter:
    """Handles writing scraped job data to formatted Excel files."""

    # Styles
    HEADER_FILL = PatternFill(start_color="1F4E79", end_color="1F4E79", fill_type="solid")
    HEADER_FONT = Font(name="Calibri", size=12, bold=True, color="FFFFFF")
    HEADER_ALIGNMENT = Alignment(horizontal="center", vertical="center", wrap_text=True)

    CELL_FONT = Font(name="Calibri", size=11)
    CELL_ALIGNMENT = Alignment(vertical="top", wrap_text=True)
    BULLET_ALIGNMENT = Alignment(vertical="top", wrap_text=True)

    THIN_BORDER = Border(
        left=Side(style="thin", color="D9D9D9"),
        right=Side(style="thin", color="D9D9D9"),
        top=Side(style="thin", color="D9D9D9"),
        bottom=Side(style="thin", color="D9D9D9"),
    )

    ALT_ROW_FILL = PatternFill(start_color="F2F7FB", end_color="F2F7FB", fill_type="solid")

    def __init__(self, output_dir: str = "output"):
        self.output_dir = output_dir
        os.makedirs(output_dir, exist_ok=True)

    def _generate_filename(self, source: str = "") -> str:
        """Generate a timestamped filename for the output Excel file."""
        timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
        if source:
            clean_source = "".join(c for c in source if c.isalnum() or c in " _-").strip()
            return f"jobs_{clean_source}_{timestamp}.xlsx"
        return f"jobs_scraped_{timestamp}.xlsx"

    def write_jobs(self, jobs: List[JobListing], filename: str = "") -> str:
        """
        Write job listings to an Excel file with proper formatting.

        Args:
            jobs: List of JobListing objects to write
            filename: Optional filename (auto-generated if not provided)

        Returns:
            Path to the generated Excel file
        """
        if not filename:
            sources = set(j.source for j in jobs)
            source_str = "_".join(filter(None, sources)) if sources else ""
            filename = self._generate_filename(source_str)

        filepath = os.path.join(self.output_dir, filename)

        wb = Workbook()
        ws = wb.active
        ws.title = "Job Listings"

        # Set column widths
        col_widths = {
            "A": 8,    # S.No
            "B": 30,   # Company
            "C": 35,   # Job Role
            "D": 80,   # Job Description (Bullet Points)
            "E": 15,   # Source
        }
        for col, width in col_widths.items():
            ws.column_dimensions[col].width = width

        # Headers
        headers = ["S.No", "Company Name", "Job Role", "Job Description (Bullet Points)", "Source"]
        for col_idx, header in enumerate(headers, 1):
            cell = ws.cell(row=1, column=col_idx, value=header)
            cell.fill = self.HEADER_FILL
            cell.font = self.HEADER_FONT
            cell.alignment = self.HEADER_ALIGNMENT
            cell.border = self.THIN_BORDER

        # Freeze header row
        ws.freeze_panes = "A2"

        # Write data
        for row_idx, job in enumerate(jobs, 2):
            # Format bullet points as a nice text block
            if job.description_bullets:
                bullets_text = "\n".join(f"• {bullet}" for bullet in job.description_bullets)
            elif job.description:
                bullets_text = f"• {job.description}"
            else:
                bullets_text = "No description available"

            row_data = [
                row_idx - 1,           # S.No
                job.company,           # Company Name
                job.job_role,          # Job Role
                bullets_text,          # Job Description (Bullet Points)
                job.source,            # Source
            ]

            for col_idx, value in enumerate(row_data, 1):
                cell = ws.cell(row=row_idx, column=col_idx, value=value)
                cell.font = self.CELL_FONT
                cell.border = self.THIN_BORDER

                if col_idx in (2, 3, 5):  # Company, Role, Source
                    cell.alignment = Alignment(vertical="top", wrap_text=True)
                elif col_idx == 4:  # Description bullets
                    cell.alignment = self.BULLET_ALIGNMENT
                elif col_idx == 1:  # S.No
                    cell.alignment = Alignment(horizontal="center", vertical="top")

            # Alternate row coloring
            if row_idx % 2 == 0:
                for col_idx in range(1, 6):
                    ws.cell(row=row_idx, column=col_idx).fill = self.ALT_ROW_FILL

        # Set row heights for better readability
        for row_idx in range(2, len(jobs) + 2):
            # Calculate estimated row height based on bullet points
            job = jobs[row_idx - 2]
            num_bullets = len(job.description_bullets) if job.description_bullets else 1
            estimated_height = max(30, num_bullets * 20)
            ws.row_dimensions[row_idx].height = min(estimated_height, 400)

        # Header row height
        ws.row_dimensions[1].height = 30

        wb.save(filepath)
        print(f"[Excel] Saved {len(jobs)} job listings to: {filepath}")
        return filepath

    def write_summary_sheet(self, wb: Workbook, jobs: List[JobListing]):
        """Write a summary sheet with statistics about the scraped jobs."""
        ws = wb.create_sheet("Summary")

        # Title
        ws.merge_cells("A1:D1")
        title_cell = ws.cell(row=1, column=1, value="Scraping Summary")
        title_cell.font = Font(name="Calibri", size=16, bold=True, color="1F4E79")

        # Stats
        sources = {}
        for job in jobs:
            sources[job.source] = sources.get(job.source, 0) + 1

        stats = [
            ("Total Jobs Scraped", len(jobs)),
            ("Unique Companies", len(set(j.company for j in jobs))),
            ("Unique Job Roles", len(set(j.job_role for j in jobs))),
            ("Sources", ", ".join(sources.keys())),
        ]

        for idx, (label, value) in enumerate(stats, 3):
            ws.cell(row=idx, column=1, value=label).font = Font(bold=True)
            ws.cell(row=idx, column=2, value=value)

        # Per-source breakdown
        row = len(stats) + 5
        ws.cell(row=row, column=1, value="Per-Source Breakdown").font = Font(bold=True, size=12)
        row += 1
        for source, count in sources.items():
            ws.cell(row=row, column=1, value=source)
            ws.cell(row=row, column=2, value=f"{count} jobs")
            row += 1

        # Timestamp
        row += 1
        ws.cell(row=row, column=1, value="Generated:").font = Font(bold=True)
        ws.cell(row=row, column=2, value=datetime.now().strftime("%Y-%m-%d %H:%M:%S"))

        ws.column_dimensions["A"].width = 25
        ws.column_dimensions["B"].width = 20
