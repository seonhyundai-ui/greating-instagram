from __future__ import annotations

import csv
from collections import Counter
from datetime import datetime
from pathlib import Path
from zoneinfo import ZoneInfo

from gspread.utils import rowcol_to_a1

from config.settings import GOOGLE_SPREADSHEET_ID
from src.sheets_client import get_gspread_client


VERSION = "0.5.0"
KST = ZoneInfo("Asia/Seoul")

INPUT_CANDIDATES = [
    Path("out/greating_content_ai_enriched_v050_ready.csv"),
    Path("greating_content_ai_enriched_v050_ready.csv"),
    Path("input/greating_content_ai_enriched_v050_ready.csv"),
]

BACKUP_SHEET = "BAK_CONTENT_MASTER_PRE_AI_v050"

AI_FIELDS = [
    "ai_title",
    "content_category",
    "content_subcategory",
    "content_theme",
    "product_name",
    "campaign_name",
    "creative_format",
]

REQUIRED_NONBLANK_FIELDS = [
    "ai_title",
    "content_category",
    "content_subcategory",
    "content_theme",
    "creative_format",
    "ai_status",
]

ALLOWED_AI_STATUS = {
    "OK",
    "NEED_REVIEW",
    "NEED_IMAGE",
}


def now_text() -> str:
    return datetime.now(KST).strftime("%Y-%m-%d %H:%M:%S")


def resolve_input_file() -> Path:
    for path in INPUT_CANDIDATES:
        if path.exists():
            return path

    searched = "\n".join(f"  - {p}" for p in INPUT_CANDIDATES)
    raise FileNotFoundError(
        "AI enrichment CSV not found. Place the file in one of:\n"
        + searched
    )


def load_csv(path: Path) -> tuple[list[str], list[dict[str, str]]]:
    with path.open("r", encoding="utf-8-sig", newline="") as f:
        reader = csv.DictReader(f)
        headers = reader.fieldnames or []
        rows = list(reader)

    required_columns = {
        "media_id",
        *AI_FIELDS,
        "ai_status",
    }

    missing_columns = sorted(required_columns - set(headers))
    if missing_columns:
        raise RuntimeError(
            "CSV missing required columns: " + ", ".join(missing_columns)
        )

    return headers, rows


def validate_csv(rows: list[dict[str, str]]) -> dict[str, dict[str, str]]:
    if not rows:
        raise RuntimeError("AI enrichment CSV has no data rows.")

    by_id: dict[str, dict[str, str]] = {}
    duplicate_ids: list[str] = []
    blank_issues: list[str] = []
    status_issues: list[str] = []

    for row_num, row in enumerate(rows, start=2):
        media_id = str(row.get("media_id", "")).strip()

        if not media_id:
            raise RuntimeError(f"Blank media_id at CSV row {row_num}.")

        if media_id in by_id:
            duplicate_ids.append(media_id)
        else:
            by_id[media_id] = row

        for field in REQUIRED_NONBLANK_FIELDS:
            value = str(row.get(field, "")).strip()
            if not value:
                blank_issues.append(f"row={row_num} media_id={media_id} field={field}")

        status = str(row.get("ai_status", "")).strip()
        if status and status not in ALLOWED_AI_STATUS:
            status_issues.append(
                f"row={row_num} media_id={media_id} ai_status={status}"
            )

    if duplicate_ids:
        sample = ", ".join(sorted(set(duplicate_ids))[:10])
        raise RuntimeError(
            f"Duplicate media_id found: {len(duplicate_ids):,} duplicates. Sample: {sample}"
        )

    if blank_issues:
        sample = "\n".join(blank_issues[:20])
        raise RuntimeError(
            f"Required AI fields contain blanks: {len(blank_issues):,}\n{sample}"
        )

    if status_issues:
        sample = "\n".join(status_issues[:20])
        raise RuntimeError(
            f"Invalid ai_status values: {len(status_issues):,}\n{sample}"
        )

    return by_id


def make_backup(spreadsheet, values: list[list[str]]) -> None:
    existing_titles = {ws.title for ws in spreadsheet.worksheets()}

    if BACKUP_SHEET in existing_titles:
        print(f"[SKIP] Backup already exists: {BACKUP_SHEET}")
        return

    max_cols = max((len(row) for row in values), default=1)

    backup = spreadsheet.add_worksheet(
        title=BACKUP_SHEET,
        rows=max(len(values) + 100, 1500),
        cols=max(max_cols, 20),
    )

    if values:
        backup.update(
            range_name="A1",
            values=values,
            value_input_option="RAW",
        )

    print(
        f"[OK] Backup created: {BACKUP_SHEET}"
        f" | rows={max(len(values) - 1, 0):,}"
    )


def range_a1(start_row: int, start_col: int, end_row: int, end_col: int) -> str:
    return (
        f"{rowcol_to_a1(start_row, start_col)}:"
        f"{rowcol_to_a1(end_row, end_col)}"
    )


def main() -> None:
    print("=" * 82)
    print(f"Greating Instagram AI Content Import v{VERSION}")
    print(f"Started at: {now_text()} KST")
    print("=" * 82)

    input_file = resolve_input_file()
    print(f"[INPUT] {input_file}")

    _, csv_rows = load_csv(input_file)
    csv_by_id = validate_csv(csv_rows)

    print(
        f"[OK] CSV validation"
        f" | rows={len(csv_rows):,}"
        f" | unique media_id={len(csv_by_id):,}"
    )

    print(
        "[AI STATUS] "
        + " | ".join(
            f"{status}={count:,}"
            for status, count in Counter(
                str(row.get("ai_status", "")).strip()
                for row in csv_rows
            ).most_common()
        )
    )

    client = get_gspread_client()
    spreadsheet = client.open_by_key(GOOGLE_SPREADSHEET_ID)
    worksheet = spreadsheet.worksheet("CONTENT_MASTER")

    values = worksheet.get_all_values()
    if not values:
        raise RuntimeError("CONTENT_MASTER is empty.")

    headers = list(values[0])
    raw_rows = values[1:]

    if "media_id" not in headers:
        raise RuntimeError("CONTENT_MASTER has no media_id column.")

    master_media_id_col = headers.index("media_id")
    master_ids: list[str] = []

    for raw_row in raw_rows:
        media_id = (
            str(raw_row[master_media_id_col]).strip()
            if len(raw_row) > master_media_id_col
            else ""
        )
        if media_id:
            master_ids.append(media_id)

    master_id_set = set(master_ids)
    csv_id_set = set(csv_by_id)

    missing_in_csv = sorted(master_id_set - csv_id_set)
    extra_in_csv = sorted(csv_id_set - master_id_set)

    print(
        f"[MASTER] rows={len(master_ids):,}"
        f" | unique media_id={len(master_id_set):,}"
    )

    if len(master_ids) != len(master_id_set):
        raise RuntimeError("CONTENT_MASTER contains duplicate media_id values.")

    if missing_in_csv or extra_in_csv:
        print(f"[STOP] missing in CSV={len(missing_in_csv):,}")
        print(f"[STOP] extra in CSV={len(extra_in_csv):,}")

        if missing_in_csv:
            print("       missing sample:", ", ".join(missing_in_csv[:10]))
        if extra_in_csv:
            print("       extra sample:", ", ".join(extra_in_csv[:10]))

        raise RuntimeError(
            "CSV and CONTENT_MASTER media_id sets do not match. No changes were made."
        )

    # Backup before any schema/data change.
    make_backup(spreadsheet, values)

    # Add ai_status once, without reshuffling existing columns.
    if "ai_status" not in headers:
        ai_status_col = len(headers) + 1

        # CONTENT_MASTER v0.4.0 has 20 grid columns.
        # ai_status is appended as column 21 (U), so expand
        # the sheet grid BEFORE writing U1.
        if worksheet.col_count < ai_status_col:
            old_col_count = worksheet.col_count
            worksheet.resize(cols=ai_status_col)
            print(
                f"[SCHEMA] Expanded CONTENT_MASTER columns "
                f"{old_col_count} -> {ai_status_col}"
            )

        worksheet.update_cell(1, ai_status_col, "ai_status")
        headers.append("ai_status")
        print(f"[SCHEMA] Added ai_status column at col={ai_status_col}")
    else:
        ai_status_col = headers.index("ai_status") + 1
        print(f"[SCHEMA] ai_status already exists at col={ai_status_col}")

    # All AI taxonomy fields must already exist from v0.4.0 migration.
    missing_master_fields = [field for field in AI_FIELDS if field not in headers]
    if missing_master_fields:
        raise RuntimeError(
            "CONTENT_MASTER missing AI columns: " + ", ".join(missing_master_fields)
        )

    if "updated_at" not in headers:
        raise RuntimeError("CONTENT_MASTER has no updated_at column.")

    # AI_FIELDS are contiguous in v0.4.0, but we still calculate positions dynamically.
    ai_cols = [headers.index(field) + 1 for field in AI_FIELDS]
    if ai_cols != list(range(min(ai_cols), max(ai_cols) + 1)):
        raise RuntimeError("AI fields are not contiguous in CONTENT_MASTER.")

    ai_start_col = min(ai_cols)
    ai_end_col = max(ai_cols)
    updated_at_col = headers.index("updated_at") + 1

    imported_at = now_text()

    ai_matrix: list[list[str]] = []
    status_matrix: list[list[str]] = []
    updated_matrix: list[list[str]] = []

    for media_id in master_ids:
        source = csv_by_id[media_id]

        ai_matrix.append([
            str(source.get(field, "")).strip()
            for field in AI_FIELDS
        ])

        status_matrix.append([
            str(source.get("ai_status", "")).strip()
        ])

        updated_matrix.append([imported_at])

    end_row = len(master_ids) + 1

    worksheet.update(
        range_name=range_a1(2, ai_start_col, end_row, ai_end_col),
        values=ai_matrix,
        value_input_option="RAW",
    )

    worksheet.update(
        range_name=range_a1(2, ai_status_col, end_row, ai_status_col),
        values=status_matrix,
        value_input_option="RAW",
    )

    worksheet.update(
        range_name=range_a1(2, updated_at_col, end_row, updated_at_col),
        values=updated_matrix,
        value_input_option="RAW",
    )

    print(
        f"[WRITE] AI fields={len(AI_FIELDS)}"
        f" | rows={len(master_ids):,}"
    )
    print("[WRITE] ai_status updated")
    print("[WRITE] updated_at updated")

    # Verification
    verify_rows = worksheet.get_all_records()

    ai_title_count = sum(
        1 for row in verify_rows
        if str(row.get("ai_title", "")).strip()
    )
    ai_status_count = sum(
        1 for row in verify_rows
        if str(row.get("ai_status", "")).strip()
    )

    status_counter = Counter(
        str(row.get("ai_status", "")).strip()
        for row in verify_rows
    )
    category_counter = Counter(
        str(row.get("content_category", "")).strip()
        for row in verify_rows
    )

    print()
    print("[VERIFY]")
    print(f"      CONTENT_MASTER rows={len(verify_rows):,}")
    print(f"      ai_title populated={ai_title_count:,}")
    print(f"      ai_status populated={ai_status_count:,}")
    print(
        "      status="
        + ", ".join(
            f"{key or '(blank)'}:{value:,}"
            for key, value in status_counter.most_common()
        )
    )
    print(
        "      categories="
        + ", ".join(
            f"{key or '(blank)'}:{value:,}"
            for key, value in category_counter.most_common()
        )
    )

    if ai_title_count != len(master_ids) or ai_status_count != len(master_ids):
        raise RuntimeError("Post-import verification failed: AI fields are not fully populated.")

    print()
    print("=" * 82)
    print(f"AI CONTENT IMPORT COMPLETED | VERSION={VERSION}")
    print("=" * 82)


if __name__ == "__main__":
    main()
