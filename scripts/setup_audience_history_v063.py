from __future__ import annotations

from config.settings import (
    GOOGLE_SPREADSHEET_ID,
)

from src.sheets_client import (
    get_gspread_client,
)


VERSION = "0.6.3"

SHEET_NAME = (
    "AUDIENCE_HISTORY"
)


HEADERS = [
    "snapshot_date",
    "dimension",
    "segment",
    "value",

    # IMPORTANT:
    # denominator is dimension_total,
    # NOT followers_count.
    "percentage",
    "dimension_total",

    # account context only
    "followers_count",

    "collected_at",
]


def main() -> None:

    print("=" * 78)
    print(
        "Greating Instagram "
        f"Audience History Setup v{VERSION}"
    )
    print("=" * 78)

    client = get_gspread_client()

    spreadsheet = client.open_by_key(
        GOOGLE_SPREADSHEET_ID
    )

    sheet_names = {
        ws.title
        for ws
        in spreadsheet.worksheets()
    }

    if SHEET_NAME in sheet_names:

        worksheet = (
            spreadsheet.worksheet(
                SHEET_NAME
            )
        )

        values = (
            worksheet.get_all_values()
        )

        if values:

            existing_headers = (
                values[0]
            )

            if (
                existing_headers
                != HEADERS
            ):

                raise RuntimeError(
                    "AUDIENCE_HISTORY exists "
                    "but schema does not match."
                )

        print(
            "[SKIP] AUDIENCE_HISTORY "
            "already exists"
        )

    else:

        worksheet = (
            spreadsheet.add_worksheet(
                title=SHEET_NAME,
                rows=2000,
                cols=len(HEADERS),
            )
        )

        worksheet.update(
            range_name="A1",
            values=[
                HEADERS
            ],
            value_input_option="RAW",
        )

        worksheet.freeze(
            rows=1
        )

        print(
            "[CREATE] AUDIENCE_HISTORY"
        )

    print()
    print(
        "Headers:"
    )

    for header in HEADERS:

        print(
            f"      {header}"
        )

    print()
    print("=" * 78)
    print(
        "AUDIENCE HISTORY SETUP COMPLETED"
    )
    print("=" * 78)


if __name__ == "__main__":
    main()