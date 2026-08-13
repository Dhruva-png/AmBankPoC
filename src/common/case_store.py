from __future__ import annotations

import json
import re
import shutil
import sqlite3
from dataclasses import asdict
from datetime import datetime
from pathlib import Path

import pandas as pd

from check_result import CheckResult, compute_accuracy

REPO_ROOT = Path(__file__).resolve().parents[2]
DB_PATH = REPO_ROOT / "data" / "kct_cases.db"
DOCS_DIR = REPO_ROOT / "data" / "documents"

_PREFIX = {"case1": "CF", "case2": "AO"}

STATUS_COMPLETE = "complete"
STATUS_NEEDS_REVIEW = "needs_review"
STATUS_ERROR = "error"


def document_dir(case_id: str) -> Path:
    return DOCS_DIR / case_id


def store_documents(case_id: str, source_paths: list[str]) -> None:
    dest_dir = document_dir(case_id)
    dest_dir.mkdir(parents=True, exist_ok=True)
    for src in source_paths:
        shutil.copyfile(src, dest_dir / Path(src).name)


def document_path(case_id: str, filename: str) -> Path | None:
    path = document_dir(case_id) / filename
    return path if path.exists() else None


def _connect() -> sqlite3.Connection:
    DB_PATH.parent.mkdir(parents=True, exist_ok=True)
    return sqlite3.connect(str(DB_PATH))


def init_db() -> None:
    with _connect() as conn:
        conn.execute(
            """
            CREATE TABLE IF NOT EXISTS cases (
                case_id TEXT PRIMARY KEY,
                case_type TEXT NOT NULL,
                created_at TEXT NOT NULL,
                documents TEXT NOT NULL,
                pass_count INTEGER NOT NULL,
                fail_count INTEGER NOT NULL,
                review_count INTEGER NOT NULL,
                na_count INTEGER NOT NULL,
                flagged INTEGER NOT NULL,
                processing_seconds REAL,
                remarks TEXT,
                results_json TEXT NOT NULL,
                markdown_report TEXT
            )
            """
        )
        existing_cols = {row[1] for row in conn.execute("PRAGMA table_info(cases)").fetchall()}
        migrations = {
            "markdown_report": "ALTER TABLE cases ADD COLUMN markdown_report TEXT",
            "customer_name": "ALTER TABLE cases ADD COLUMN customer_name TEXT",
            "status": "ALTER TABLE cases ADD COLUMN status TEXT",
            "accuracy": "ALTER TABLE cases ADD COLUMN accuracy REAL",
            "error_message": "ALTER TABLE cases ADD COLUMN error_message TEXT",
        }
        for col, ddl in migrations.items():
            if col not in existing_cols:
                conn.execute(ddl)
        # Backfill rows created before status/accuracy existed, from their existing counts.
        conn.execute(
            f"UPDATE cases SET status = CASE WHEN flagged = 1 THEN '{STATUS_NEEDS_REVIEW}' "
            f"ELSE '{STATUS_COMPLETE}' END WHERE status IS NULL"
        )
        # Recompute accuracy for every non-error case with the current formula. This needs
        # per-check confidence values from results_json, so it has to happen in Python rather
        # than SQL -- also means it stays correct if the formula changes again later. Error
        # cases legitimately have no accuracy (no results were produced); the status backfill
        # above already ran, so every row now has a real status to exclude on.
        rows = conn.execute(
            f"SELECT case_id, results_json FROM cases WHERE status != '{STATUS_ERROR}'"
        ).fetchall()
        for case_id, results_json in rows:
            try:
                results = [CheckResult(**d) for d in json.loads(results_json)]
            except (TypeError, ValueError, json.JSONDecodeError):
                continue
            conn.execute(
                "UPDATE cases SET accuracy = ? WHERE case_id = ?", (compute_accuracy(results), case_id)
            )


def _slugify(name: str, max_len: int = 40) -> str:
    slug = re.sub(r"[^A-Za-z0-9]+", "-", (name or "").strip()).strip("-").upper()
    return slug[:max_len] or "UNKNOWN"


def combine_document_names(*names: str, part_len: int = 20) -> str:
    """Builds an identifying slug from multiple documents' identity fields (e.g. a Credit
    Paper's customer name and a Letter of Offer's addressee name). Near-duplicate names
    (the common case, when the documents agree) collapse to one instead of repeating; genuinely
    different names (e.g. a customer-name mismatch between two sources) both appear, which
    surfaces the discrepancy right in the case ID."""
    seen: set[str] = set()
    parts: list[str] = []
    for name in names:
        name = (name or "").strip()
        # Strip a trailing "(...)" qualifier -- e.g. a Credit Paper's customer field often
        # reads "Hadyan Sdn Bhd (200101007110 / 542866W)", registration numbers appended.
        # Without this, that name never dedupes against a cleaner "Hadyan Sdn Bhd" from
        # another document, and the truncated registration digits leak into the case ID.
        name = re.sub(r"\s*\([^)]*\)\s*$", "", name).strip()
        if not name:
            continue
        key = re.sub(r"[^A-Z0-9]", "", name.upper())
        if key and key not in seen:
            seen.add(key)
            parts.append(_slugify(name, max_len=part_len))
    return "-".join(parts)


def new_case_id(case_type: str, customer_name: str = "") -> str:
    prefix = _PREFIX.get(case_type, "KC")
    slug = _slugify(customer_name)
    date_part = datetime.now().strftime("%Y%m%d")
    base = f"{prefix}-{slug}-{date_part}"
    with _connect() as conn:
        taken = {
            row[0] for row in conn.execute("SELECT case_id FROM cases WHERE case_id LIKE ?", (f"{base}%",)).fetchall()
        }
    if base not in taken:
        return base
    n = 2
    while f"{base}-{n}" in taken:
        n += 1
    return f"{base}-{n}"


def _status_and_accuracy(results: list[CheckResult]) -> tuple[str, float]:
    counts = {s: 0 for s in ("PASS", "FAIL", "REVIEW", "N/A")}
    for r in results:
        counts[r.status] = counts.get(r.status, 0) + 1
    status = STATUS_NEEDS_REVIEW if (counts["FAIL"] or counts["REVIEW"]) else STATUS_COMPLETE
    return status, compute_accuracy(results)


def save_case(
    case_type: str,
    documents: list[dict],
    results: list[CheckResult],
    processing_seconds: float,
    remarks: str,
    markdown_report: str = "",
    customer_name: str = "",
) -> str:
    init_db()
    case_id = new_case_id(case_type, customer_name)
    counts = {s: 0 for s in ("PASS", "FAIL", "REVIEW", "N/A")}
    for r in results:
        counts[r.status] = counts.get(r.status, 0) + 1
    status, accuracy = _status_and_accuracy(results)
    flagged = 1 if status == STATUS_NEEDS_REVIEW else 0
    with _connect() as conn:
        conn.execute(
            """
            INSERT INTO cases (
                case_id, case_type, created_at, documents, customer_name,
                pass_count, fail_count, review_count, na_count, flagged,
                processing_seconds, remarks, results_json, markdown_report,
                status, accuracy, error_message
            ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
            """,
            (
                case_id,
                case_type,
                datetime.now().isoformat(timespec="seconds"),
                json.dumps(documents, ensure_ascii=False),
                customer_name,
                counts["PASS"],
                counts["FAIL"],
                counts["REVIEW"],
                counts["N/A"],
                flagged,
                processing_seconds,
                remarks,
                json.dumps([asdict(r) for r in results], ensure_ascii=False, default=str),
                markdown_report,
                status,
                accuracy,
                None,
            ),
        )
    return case_id


def save_error_case(case_type: str, documents: list[dict], customer_name: str, error_message: str) -> str:
    """Persists a case whose extraction/comparison pipeline threw before producing results,
    so a failed run is still visible in Case Management instead of silently vanishing."""
    init_db()
    case_id = new_case_id(case_type, customer_name)
    with _connect() as conn:
        conn.execute(
            """
            INSERT INTO cases (
                case_id, case_type, created_at, documents, customer_name,
                pass_count, fail_count, review_count, na_count, flagged,
                processing_seconds, remarks, results_json, markdown_report,
                status, accuracy, error_message
            ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
            """,
            (
                case_id,
                case_type,
                datetime.now().isoformat(timespec="seconds"),
                json.dumps(documents, ensure_ascii=False),
                customer_name,
                0, 0, 0, 0, 1,
                0.0, "", "[]", "",
                STATUS_ERROR, None, error_message,
            ),
        )
    return case_id


def list_cases(case_type: str | None = None) -> pd.DataFrame:
    init_db()
    with _connect() as conn:
        if case_type:
            df = pd.read_sql_query(
                "SELECT * FROM cases WHERE case_type = ? ORDER BY created_at DESC", conn, params=(case_type,)
            )
        else:
            df = pd.read_sql_query("SELECT * FROM cases ORDER BY created_at DESC", conn)
    return df


def delete_case(case_id: str) -> None:
    init_db()
    with _connect() as conn:
        conn.execute("DELETE FROM cases WHERE case_id = ?", (case_id,))
    doc_dir = document_dir(case_id)
    if doc_dir.exists():
        shutil.rmtree(doc_dir, ignore_errors=True)


def get_case(case_id: str) -> dict | None:
    init_db()
    with _connect() as conn:
        conn.row_factory = sqlite3.Row
        row = conn.execute("SELECT * FROM cases WHERE case_id = ?", (case_id,)).fetchone()
    if not row:
        return None
    record = dict(row)
    record["documents"] = json.loads(record["documents"])
    record["results"] = [CheckResult(**d) for d in json.loads(record["results_json"])]
    return record
