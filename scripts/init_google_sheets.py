from __future__ import annotations

from config.settings import (
    GOOGLE_SPREADSHEET_ID,
)

from src.sheets_client import (
    get_gspread_client,
)


SHEETS = {

    "ACCOUNT_HISTORY": [
        "snapshot_date",
        "followers_count",
        "follows_count",
        "media_count",
        "collected_at",
    ],

    "MEDIA_SNAPSHOT": [
        "snapshot_date",
        "media_id",
        "posted_at",
        "media_type",
        "media_product_type",
        "views",
        "reach",
        "saved",
        "shares",
        "total_interactions",
        "avg_watch_time_ms",
        "total_watch_time_ms",
        "collected_at",
    ],

    "STORY_HISTORY": [
        "story_id",
        "posted_at",
        "media_type",
        "media_url",
        "permalink",
        "views",
        "reach",
        "shares",
        "replies",
        "total_interactions",
        "follows",
        "profile_visits",
        "link_clicks",
        "tap_forward",
        "tap_back",
        "tap_exit",
        "swipe_forward",
        "insight_status",
        "first_collected_at",
        "last_collected_at",
    ],

    "CONTENT_MASTER": [
        "media_id",
        "ai_title",
        "content_category",
        "content_subcategory",
        "product_name",
        "campaign_name",
        "is_paid",
        "manual_title",
        "manual_category",
        "updated_at",
    ],
}


def main() -> None:

    print("=" * 72)
    print("Greating Instagram Google Sheets Init v0.3.0")
    print("=" * 72)

    client = get_gspread_client()

    spreadsheet = client.open_by_key(
        GOOGLE_SPREADSHEET_ID
    )

    print(
        f"[OK] Spreadsheet connected: "
        f"{spreadsheet.title}"
    )

    existing = {
        ws.title
        for ws in spreadsheet.worksheets()
    }

    for sheet_name, headers in SHEETS.items():

        if sheet_name not in existing:

            worksheet = spreadsheet.add_worksheet(
                title=sheet_name,
                rows=1000,
                cols=max(
                    len(headers),
                    20,
                ),
            )

            print(
                f"[CREATE] {sheet_name}"
            )

        else:

            worksheet = spreadsheet.worksheet(
                sheet_name
            )

            print(
                f"[FOUND] {sheet_name}"
            )

        worksheet.update(
            range_name="A1",
            values=[headers],
        )

        print(
            f"[OK] Header: {sheet_name}"
        )

    print()
    print("=" * 72)
    print("GOOGLE SHEETS INIT COMPLETED")
    print("=" * 72)


if __name__ == "__main__":
    main()