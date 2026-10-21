"""Export the screening-cleared candidates of a job as CSV or XLSX.

One-click download for recruiters: every application on the job whose status
is screening_cleared (or the legacy alias "selected"), with the scores the
recruiter dashboard shows.
"""

import csv
import datetime
import io

CLEARED_STATUSES = ["screening_cleared", "selected"]  # "selected" = legacy alias

COLUMNS = [
    ("Candidate Name", "student_name"),
    ("Email", "student_email"),
    ("CV Score", "cv_score"),
    ("Interview Score", "interview_score"),
    ("Proctoring Score", "proctoring_score"),
    ("Applied At", "applied_at"),
    ("Status", "status"),
]


def fetch_cleared_rows(applications_collection, job_id):
    """All screening-cleared applications for the job, newest first."""
    cursor = applications_collection.find(
        {"job_id": str(job_id), "status": {"$in": CLEARED_STATUSES}}
    ).sort("applied_at", -1)

    rows = []
    for doc in cursor:
        row = {}
        for _, field in COLUMNS:
            value = doc.get(field)
            if isinstance(value, datetime.datetime):
                value = value.strftime("%Y-%m-%d %H:%M")
            if field == "status" and value == "selected":
                value = "screening_cleared"
            row[field] = value if value is not None else ""
        rows.append(row)
    return rows


def spreadsheet_cell(value):
    """Keep untrusted strings as text in Excel, including whitespace prefixes."""
    if value is None:
        return ''
    if isinstance(value, str) and (value.startswith(('\t', '\r', '\n')) or value.lstrip().startswith(('=', '+', '-', '@'))):
        return "'" + value
    return value


def build_csv(rows):
    """CSV bytes (UTF-8 with BOM so Excel renders names correctly)."""
    buffer = io.StringIO()
    writer = csv.writer(buffer, lineterminator="\r\n")
    writer.writerow([header for header, _ in COLUMNS])
    for row in rows:
        writer.writerow([spreadsheet_cell(row.get(field)) for _, field in COLUMNS])
    return ("﻿" + buffer.getvalue()).encode("utf-8")


def build_xlsx(rows, job_title):
    """XLSX bytes via openpyxl (already a project dependency)."""
    from openpyxl import Workbook
    from openpyxl.styles import Font

    workbook = Workbook()
    sheet = workbook.active
    sheet.title = "Screening Cleared"

    sheet.append([header for header, _ in COLUMNS])
    for cell in sheet[1]:
        cell.font = Font(bold=True)

    for row in rows:
        sheet.append([spreadsheet_cell(row.get(field)) for _, field in COLUMNS])

    # Readable column widths
    for index, (header, field) in enumerate(COLUMNS, start=1):
        letter = sheet.cell(row=1, column=index).column_letter
        longest = max([len(header)] + [len(str(row[field])) for row in rows])
        sheet.column_dimensions[letter].width = min(max(longest + 2, 12), 45)

    buffer = io.BytesIO()
    workbook.save(buffer)
    return buffer.getvalue()


def safe_filename(job_title, extension):
    stem = "".join(c for c in (job_title or "job") if c.isalnum() or c in (" ", "-", "_")).strip()
    stem = (stem or "job").replace(" ", "_")[:60]
    date = datetime.datetime.utcnow().strftime("%Y-%m-%d")
    return f"screening_cleared_{stem}_{date}.{extension}"


def build_stage_export(rows, extension):
    """Explicit owner-facing fields, with spreadsheet formula injection blocked."""
    columns = [('Application ID', 'application_id'), ('Candidate', 'name'), ('Email', 'email'),
        ('Current stage', 'stage'), ('State', 'state'), ('Lifecycle', 'lifecycle'), ('Status', 'label'),
        ('CV score', 'cv_score'), ('Screening score', 'interview_score'), ('Screening proctoring score', 'screening_proctoring_score'),
        ('OA score', 'oa_score'), ('Objective recommendation', 'oa_recommendation'), ('Integrity review pending', 'integrity_hold'),
        ('Recruiter OA decision', 'recruiter_decision'), ('Result released', 'result_released')]
    data = [[header for header, _ in columns]] + [[spreadsheet_cell(row.get(field)) for _, field in columns] for row in rows]
    if extension == 'csv':
        buffer = io.StringIO(); writer = csv.writer(buffer, lineterminator='\r\n'); writer.writerows(data)
        return ('\ufeff'+buffer.getvalue()).encode('utf-8')
    from openpyxl import Workbook
    from openpyxl.styles import Font
    workbook = Workbook(); sheet = workbook.active; sheet.title = 'Company candidates'
    for row in data: sheet.append(row)
    for header in sheet[1]: header.font = Font(bold=True)
    sheet.freeze_panes = 'A2'; sheet.auto_filter.ref = sheet.dimensions
    for index, (header, _) in enumerate(columns, 1): sheet.column_dimensions[sheet.cell(1, index).column_letter].width = min(45, max(15, len(header)+2))
    buffer = io.BytesIO(); workbook.save(buffer); return buffer.getvalue()
