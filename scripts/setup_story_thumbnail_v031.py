from __future__ import annotations

from gspread.utils import rowcol_to_a1

from config.settings import GOOGLE_SPREADSHEET_ID
from src.sheets_client import get_gspread_client


VERSION = "0.3.1"
SHEET_NAME = "STORY_HISTORY"
NEW_COLUMN = "thumbnail_url"


def main() -> None:
    print("=" * 78)
    print(f"Greating Instagram Story Thumbnail Schema Setup v{VERSION}")
    print("=" * 78)

    client = get_gspread_client()
    spreadsheet = client.open_by_key(GOOGLE_SPREADSHEET_ID)
    worksheet = spreadsheet.worksheet(SHEET_NAME)

    headers = worksheet.row_values(1)
    if not headers:
        raise RuntimeError("STORY_HISTORY header is empty.")

    if NEW_COLUMN in headers:
        print(f"[SKIP] {NEW_COLUMN} already exists at col={headers.index(NEW_COLUMN)+1}")
        print("=" * 78)
        print("SETUP COMPLETED")
        print("=" * 78)
        return

    new_col_index = len(headers) + 1
    if worksheet.col_count < new_col_index:
        worksheet.resize(cols=new_col_index)

    cell = rowcol_to_a1(1, new_col_index)
    worksheet.update(
        range_name=cell,
        values=[[NEW_COLUMN]],
        value_input_option="RAW",
    )

    print(f"[ADD] {NEW_COLUMN} -> col={new_col_index}")
    print("=" * 78)
    print("SETUP COMPLETED")
    print("=" * 78)


if __name__ == "__main__":
    main()
