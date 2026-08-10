from __future__ import annotations

import io
import json

from openpyxl import Workbook
from openpyxl.styles import Alignment, Font, PatternFill
from openpyxl.utils import get_column_letter

import case_store
from check_result import CheckResult

HEADER_FILL = PatternFill(start_color="12161F", end_color="12161F", fill_type="solid")
HEADER_FONT = Font(color="FFFFFF", bold=True, size=10)
TITLE_FONT = Font(bold=True, size=14, color="0F1420")
SECTION_FONT = Font(bold=True, size=11, color="0F1420")
LABEL_FONT = Font(bold=True, size=9, color="6B7280")
STATUS_FILL = {
    "PASS": PatternFill(start_color="E7F6ED", end_color="E7F6ED", fill_type="solid"),
    "FAIL": PatternFill(start_color="FCEAE9", end_color="FCEAE9", fill_type="solid"),
    "REVIEW": PatternFill(start_color="FBF1DE", end_color="FBF1DE", fill_type="solid"),
    "N/A": PatternFill(start_color="EEF0F3", end_color="EEF0F3", fill_type="solid"),
}
STATUS_FONT = {
    "PASS": Font(color="146C3A", bold=True),
    "FAIL": Font(color="B3261E", bold=True),
    "REVIEW": Font(color="91600A", bold=True),
    "N/A": Font(color="5B6472", bold=True),
}
WRAP = Alignment(wrap_text=True, vertical="top")


def _autosize(ws, widths: dict[int, int]) -> None:
    for col, width in widths.items():
        ws.column_dimensions[get_column_letter(col)].width = width


def _line_items_sheet(wb: Workbook, results: list[CheckResult], left_label: str, right_label: str) -> None:
    ws = wb.create_sheet("Line Items")
    headers = ["KCT", "Check", "Status", "Confidence", left_label, f"Source ({left_label})", right_label, f"Source ({right_label})", "Note"]
    ws.append(headers)
    for col in range(1, len(headers) + 1):
        cell = ws.cell(row=1, column=col)
        cell.fill = HEADER_FILL
        cell.font = HEADER_FONT
        cell.alignment = Alignment(vertical="center")
    ws.freeze_panes = "A2"

    for r in results:
        row = [
            r.kct, r.check, r.status,
            f"{r.confidence:.0f}%" if r.confidence is not None else "",
            r.left_value, r.source_left, r.right_value, r.source_right, r.note,
        ]
        ws.append(row)
        row_idx = ws.max_row
        status_cell = ws.cell(row=row_idx, column=3)
        status_cell.fill = STATUS_FILL.get(r.status, STATUS_FILL["N/A"])
        status_cell.font = STATUS_FONT.get(r.status, STATUS_FONT["N/A"])
        for col in (2, 5, 6, 7, 8, 9):
            ws.cell(row=row_idx, column=col).alignment = WRAP

    _autosize(ws, {1: 14, 2: 34, 3: 10, 4: 12, 5: 36, 6: 30, 7: 36, 8: 30, 9: 48})


def _full_report_sheet(
    wb: Workbook,
    case_meta: dict,
    results: list[CheckResult],
    remarks: str,
    left_label: str,
    right_label: str,
) -> None:
    ws = wb.create_sheet("Full Report", 0)
    row = 1

    ws.cell(row=row, column=1, value=case_meta.get("title", "Control Testing Report")).font = TITLE_FONT
    row += 2

    meta_fields = [
        ("Case ID", case_meta.get("case_id", "")),
        ("Module", case_meta.get("module", "")),
        ("Processed At", case_meta.get("processed_at", "")),
        ("Processing Time", case_meta.get("processing_time", "")),
        ("Documents", case_meta.get("documents", "")),
        ("Overall Status", case_meta.get("overall_status", "")),
    ]
    for label, value in meta_fields:
        ws.cell(row=row, column=1, value=label).font = LABEL_FONT
        cell = ws.cell(row=row, column=2, value=str(value))
        cell.alignment = WRAP
        row += 1
    row += 1

    ws.cell(row=row, column=1, value="AI Remarks").font = SECTION_FONT
    row += 1
    ws.cell(row=row, column=1, value=remarks or "Not generated.")
    ws.cell(row=row, column=1).alignment = WRAP
    ws.merge_cells(start_row=row, start_column=1, end_row=row, end_column=6)
    ws.row_dimensions[row].height = 80
    row += 2

    ws.cell(row=row, column=1, value="Detailed Findings").font = SECTION_FONT
    row += 2

    for r in results:
        header_cell = ws.cell(row=row, column=1, value=f"{r.kct} — {r.check}")
        header_cell.font = Font(bold=True, size=10.5, color="0F1420")
        ws.merge_cells(start_row=row, start_column=1, end_row=row, end_column=5)
        status_cell = ws.cell(row=row, column=6, value=r.status)
        status_cell.fill = STATUS_FILL.get(r.status, STATUS_FILL["N/A"])
        status_cell.font = STATUS_FONT.get(r.status, STATUS_FONT["N/A"])
        conf_cell = ws.cell(row=row, column=7, value=f"{r.confidence:.0f}%" if r.confidence is not None else "N/A")
        conf_cell.font = Font(size=9, color="6B7280")
        row += 1

        ws.cell(row=row, column=1, value=r.note).alignment = WRAP
        ws.merge_cells(start_row=row, start_column=1, end_row=row, end_column=7)
        row += 1

        ws.cell(row=row, column=1, value=f"{left_label}:").font = LABEL_FONT
        ws.cell(row=row, column=2, value=r.left_value).alignment = WRAP
        ws.merge_cells(start_row=row, start_column=2, end_row=row, end_column=4)
        ws.cell(row=row, column=5, value=r.source_left).font = Font(size=8, italic=True, color="98A2B3")
        ws.merge_cells(start_row=row, start_column=5, end_row=row, end_column=7)
        row += 1

        ws.cell(row=row, column=1, value=f"{right_label}:").font = LABEL_FONT
        ws.cell(row=row, column=2, value=r.right_value).alignment = WRAP
        ws.merge_cells(start_row=row, start_column=2, end_row=row, end_column=4)
        ws.cell(row=row, column=5, value=r.source_right).font = Font(size=8, italic=True, color="98A2B3")
        ws.merge_cells(start_row=row, start_column=5, end_row=row, end_column=7)
        row += 2

    _autosize(ws, {1: 16, 2: 22, 3: 16, 4: 16, 5: 22, 6: 12, 7: 16})


def build_workbook(
    case_meta: dict,
    results: list[CheckResult],
    remarks: str,
    left_label: str,
    right_label: str,
) -> bytes:
    wb = Workbook()
    wb.remove(wb.active)
    _full_report_sheet(wb, case_meta, results, remarks, left_label, right_label)
    _line_items_sheet(wb, results, left_label, right_label)
    buffer = io.BytesIO()
    wb.save(buffer)
    return buffer.getvalue()


def build_consolidated_workbook(case_type: str, module_name: str) -> bytes:
    df = case_store.list_cases(case_type)
    wb = Workbook()
    wb.properties.title = f"{module_name} Cases"
    ws = wb.active
    ws.title = "Cases"
    headers = ["Case ID", "Processed At", "Status", "Pass", "Fail", "Review", "N/A", "Processing Time (s)", "Remarks"]
    ws.append(headers)
    for col in range(1, len(headers) + 1):
        cell = ws.cell(row=1, column=col)
        cell.fill = HEADER_FILL
        cell.font = HEADER_FONT
    ws.freeze_panes = "A2"
    for _, row in df.iterrows():
        ws.append([
            row["case_id"], row["created_at"], "FLAGGED" if row["flagged"] else "CLEAR",
            row["pass_count"], row["fail_count"], row["review_count"], row["na_count"],
            row["processing_seconds"], row["remarks"],
        ])
        status_cell = ws.cell(row=ws.max_row, column=3)
        status_cell.fill = STATUS_FILL["FAIL" if row["flagged"] else "PASS"]
        status_cell.font = STATUS_FONT["FAIL" if row["flagged"] else "PASS"]
        ws.cell(row=ws.max_row, column=9).alignment = WRAP
    _autosize(ws, {1: 22, 2: 20, 3: 12, 4: 8, 5: 8, 6: 8, 7: 8, 8: 16, 9: 60})

    ws2 = wb.create_sheet("All Line Items")
    headers2 = ["Case ID", "KCT", "Check", "Status", "Confidence", "Note"]
    ws2.append(headers2)
    for col in range(1, len(headers2) + 1):
        cell = ws2.cell(row=1, column=col)
        cell.fill = HEADER_FILL
        cell.font = HEADER_FONT
    ws2.freeze_panes = "A2"
    for _, row in df.iterrows():
        for r in json.loads(row["results_json"]):
            ws2.append([
                row["case_id"], r.get("kct"), r.get("check"), r.get("status"),
                f"{r['confidence']:.0f}%" if r.get("confidence") is not None else "",
                r.get("note"),
            ])
            status_cell = ws2.cell(row=ws2.max_row, column=4)
            status_cell.fill = STATUS_FILL.get(r.get("status"), STATUS_FILL["N/A"])
            status_cell.font = STATUS_FONT.get(r.get("status"), STATUS_FONT["N/A"])
            ws2.cell(row=ws2.max_row, column=6).alignment = WRAP
    _autosize(ws2, {1: 22, 2: 14, 3: 34, 4: 10, 5: 12, 6: 48})

    buffer = io.BytesIO()
    wb.save(buffer)
    return buffer.getvalue()
