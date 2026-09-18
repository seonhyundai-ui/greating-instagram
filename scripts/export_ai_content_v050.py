from __future__ import annotations

import csv
from pathlib import Path

from config.settings import (
    GOOGLE_SPREADSHEET_ID,
)

from src.sheets_client import (
    get_gspread_client,
)


VERSION = "0.5.0"

OUTPUT_DIR = Path("out")

OUTPUT_FILE = (
    OUTPUT_DIR
    / "greating_content_ai_input_v050.csv"
)


EXPORT_FIELDS = [
    "media_id",
    "posted_at",
    "media_type",
    "media_product_type",
    "caption",
    "permalink",
    "has_paid",

    # Existing values, if any
    "ai_title",
    "content_category",
    "content_subcategory",
    "content_theme",
    "product_name",
    "campaign_name",
    "creative_format",
]


def main() -> None:

    print("=" * 78)
    print(
        "Greating Instagram "
        f"AI Content Export v{VERSION}"
    )
    print("=" * 78)

    OUTPUT_DIR.mkdir(
        parents=True,
        exist_ok=True,
    )

    client = get_gspread_client()

    spreadsheet = client.open_by_key(
        GOOGLE_SPREADSHEET_ID
    )

    worksheet = spreadsheet.worksheet(
        "CONTENT_MASTER"
    )

    rows = worksheet.get_all_records()

    print(
        f"[INFO] CONTENT_MASTER rows="
        f"{len(rows):,}"
    )

    output_rows = []

    skipped_existing = 0
    blank_caption = 0

    for row in rows:

        media_id = str(
            row.get(
                "media_id",
                ""
            )
        ).strip()

        if not media_id:
            continue

        # ----------------------------------------
        # 이미 AI title이 있으면 재분류하지 않음
        # ----------------------------------------

        existing_title = str(
            row.get(
                "ai_title",
                ""
            )
        ).strip()

        if existing_title:
            skipped_existing += 1
            continue

        caption = str(
            row.get(
                "caption",
                ""
            )
        ).strip()

        if not caption:
            blank_caption += 1

        output = {}

        for field in EXPORT_FIELDS:

            value = row.get(
                field,
                ""
            )

            if value is None:
                value = ""

            output[
                field
            ] = value

        output_rows.append(
            output
        )

    # 최신 콘텐츠부터
    output_rows.sort(
        key=lambda x: str(
            x.get(
                "posted_at",
                ""
            )
        ),
        reverse=True,
    )

    with OUTPUT_FILE.open(
        "w",
        encoding="utf-8-sig",
        newline="",
    ) as f:

        writer = csv.DictWriter(
            f,
            fieldnames=EXPORT_FIELDS,
        )

        writer.writeheader()

        writer.writerows(
            output_rows
        )

    print()
    print(
        f"[OK] export rows="
        f"{len(output_rows):,}"
    )

    print(
        f"     skipped existing="
        f"{skipped_existing:,}"
    )

    print(
        f"     blank caption="
        f"{blank_caption:,}"
    )

    print()
    print(
        f"[FILE] {OUTPUT_FILE}"
    )

    print()
    print("=" * 78)
    print("AI CONTENT EXPORT COMPLETED")
    print("=" * 78)


if __name__ == "__main__":
    main()