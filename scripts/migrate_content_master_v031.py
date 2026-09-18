from __future__ import annotations

from datetime import datetime
from zoneinfo import ZoneInfo

from config.settings import GOOGLE_SPREADSHEET_ID
from src.sheets_client import get_gspread_client


VERSION = "0.3.1"
KST = ZoneInfo("Asia/Seoul")


NEW_HEADERS = [
    "media_id",
    "posted_at",
    "media_type",
    "media_product_type",
    "permalink",
    "media_url",
    "thumbnail_url",
    "caption",

    "ai_title",
    "content_category",
    "content_subcategory",
    "product_name",
    "campaign_name",
    "is_paid",

    "manual_title",
    "manual_category",

    "created_at",
    "updated_at",
]


def main() -> None:
    print("=" * 72)
    print(f"CONTENT_MASTER Migration v{VERSION}")
    print("=" * 72)

    client = get_gspread_client()

    spreadsheet = client.open_by_key(
        GOOGLE_SPREADSHEET_ID
    )

    worksheet = spreadsheet.worksheet(
        "CONTENT_MASTER"
    )

    values = worksheet.get_all_values()

    if not values:
        raise RuntimeError(
            "CONTENT_MASTER is empty."
        )

    old_headers = values[0]
    old_rows = values[1:]

    print(
        f"[INFO] Existing rows: {len(old_rows)}"
    )

    migrated_rows = []

    for raw_row in old_rows:

        padded = (
            raw_row
            + [""] * (
                len(old_headers)
                - len(raw_row)
            )
        )

        old = dict(
            zip(
                old_headers,
                padded,
            )
        )

        # 기존 updated_at을 최초 생성 시각으로 활용
        old_updated_at = old.get(
            "updated_at",
            "",
        )

        new_row = []

        for header in NEW_HEADERS:

            if header == "created_at":
                value = (
                    old.get("created_at")
                    or old_updated_at
                )

            elif header == "updated_at":
                value = old_updated_at

            else:
                value = old.get(
                    header,
                    "",
                )

            new_row.append(
                value
            )

        migrated_rows.append(
            new_row
        )

    required_rows = max(
        len(migrated_rows) + 100,
        1000,
    )

    worksheet.resize(
        rows=required_rows,
        cols=len(NEW_HEADERS),
    )

    worksheet.clear()

    matrix = [
        NEW_HEADERS,
        *migrated_rows,
    ]

    worksheet.update(
        range_name="A1",
        values=matrix,
        value_input_option="RAW",
    )

    print(
        f"[OK] Migrated rows: "
        f"{len(migrated_rows)}"
    )

    print(
        f"[OK] Columns: "
        f"{len(NEW_HEADERS)}"
    )

    print()
    print("=" * 72)
    print(
        "CONTENT_MASTER MIGRATION COMPLETED"
    )
    print("=" * 72)


if __name__ == "__main__":
    main()