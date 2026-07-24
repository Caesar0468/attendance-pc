from __future__ import annotations

from datetime import date, datetime, timedelta
from pathlib import Path

from openpyxl import Workbook
from openpyxl.styles import Font, PatternFill
from openpyxl.utils import get_column_letter

from app.config import REPORTS_DIR
from app.database import get_connection


def _status(morning: bool, evening: bool) -> str:
    if morning and evening:
        return "Full Day"
    if morning or evening:
        return "Half Day"
    return "Absent"


def generate_report(start_date: str, end_date: str, daily_wage: float | None = None) -> Path:
    start = datetime.strptime(start_date, "%Y-%m-%d").date()
    end = datetime.strptime(end_date, "%Y-%m-%d").date()
    if start > end:
        raise ValueError("Start date must be before end date.")

    with get_connection() as conn:
        if daily_wage is None:
            row = conn.execute("SELECT value FROM settings WHERE key = 'daily_wage'").fetchone()
            wage = float(row["value"]) if row else 500.0
        else:
            wage = daily_wage

        workers = conn.execute("SELECT id, name FROM workers ORDER BY name").fetchall()
        attendance = conn.execute(
            """
            SELECT worker_id, date, morning_present, evening_present
            FROM attendance
            WHERE date >= ? AND date <= ?
            """,
            (start_date, end_date),
        ).fetchall()

    att_map: dict[tuple[int, str], dict] = {}
    for row in attendance:
        att_map[(row["worker_id"], row["date"])] = dict(row)

    wb = Workbook()
    ws = wb.active
    ws.title = "Daily Attendance"

    headers = ["Worker Name", "Date", "Morning", "Evening", "Status"]
    header_fill = PatternFill(start_color="4472C4", end_color="4472C4", fill_type="solid")
    header_font = Font(color="FFFFFF", bold=True)
    for col, header in enumerate(headers, 1):
        cell = ws.cell(row=1, column=col, value=header)
        cell.fill = header_fill
        cell.font = header_font

    row_idx = 2
    summary: dict[int, dict[str, int]] = {
        w["id"]: {"full": 0, "half": 0, "absent": 0} for w in workers
    }

    current = start
    while current <= end:
        day_str = current.isoformat()
        for worker in workers:
            att = att_map.get((worker["id"], day_str), {})
            morning = bool(att.get("morning_present", 0))
            evening = bool(att.get("evening_present", 0))
            status = _status(morning, evening)

            ws.cell(row=row_idx, column=1, value=worker["name"])
            ws.cell(row=row_idx, column=2, value=day_str)
            ws.cell(row=row_idx, column=3, value="Yes" if morning else "No")
            ws.cell(row=row_idx, column=4, value="Yes" if evening else "No")
            ws.cell(row=row_idx, column=5, value=status)

            if status == "Full Day":
                summary[worker["id"]]["full"] += 1
            elif status == "Half Day":
                summary[worker["id"]]["half"] += 1
            else:
                summary[worker["id"]]["absent"] += 1

            row_idx += 1
        current += timedelta(days=1)

    for col in ws.columns:
        max_len = max(len(str(cell.value or "")) for cell in col)
        col_letter = get_column_letter(col[0].column)
        ws.column_dimensions[col_letter].width = min(max_len + 2, 30)

    summary_ws = wb.create_sheet("Monthly Summary")
    sum_headers = [
        "Worker Name",
        "Full Days",
        "Half Days",
        "Absent Days",
        "Daily Wage",
        "Total Payment",
    ]
    for col, header in enumerate(sum_headers, 1):
        cell = summary_ws.cell(row=1, column=col, value=header)
        cell.fill = header_fill
        cell.font = header_font

    for i, worker in enumerate(workers, 2):
        stats = summary[worker["id"]]
        payment = stats["full"] * wage + stats["half"] * (wage * 0.5)
        summary_ws.cell(row=i, column=1, value=worker["name"])
        summary_ws.cell(row=i, column=2, value=stats["full"])
        summary_ws.cell(row=i, column=3, value=stats["half"])
        summary_ws.cell(row=i, column=4, value=stats["absent"])
        summary_ws.cell(row=i, column=5, value=wage)
        summary_ws.cell(row=i, column=6, value=payment)

    for col in summary_ws.columns:
        max_len = max(len(str(cell.value or "")) for cell in col)
        col_letter = get_column_letter(col[0].column)
        summary_ws.column_dimensions[col_letter].width = min(max_len + 2, 25)

    REPORTS_DIR.mkdir(parents=True, exist_ok=True)
    filename = f"attendance_{start_date}_to_{end_date}.xlsx"
    out_path = REPORTS_DIR / filename
    wb.save(out_path)
    return out_path