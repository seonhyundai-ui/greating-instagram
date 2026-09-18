from __future__ import annotations

from typing import Iterable

from gspread.utils import rowcol_to_a1

from src.sheets_client import (
    get_gspread_client,
)


class SheetsRepository:
    """
    Small repository layer for Google Sheets.

    Supports:
    - append
    - update
    - composite-key upsert
    - insert-only rows
    """

    def __init__(
        self,
        spreadsheet_id: str,
    ):
        client = get_gspread_client()

        self.spreadsheet = client.open_by_key(
            spreadsheet_id
        )

    # ========================================
    # Helpers
    # ========================================

    def _worksheet(
        self,
        sheet_name: str,
    ):
        return self.spreadsheet.worksheet(
            sheet_name
        )

    @staticmethod
    def _sheet_value(
        value,
    ):
        """
        Convert Python None to blank cell.

        Important:
        None != 0

        This preserves the distinction between
        unavailable data and a real zero.
        """

        if value is None:
            return ""

        return value

    @staticmethod
    def _key_tuple(
        row: dict,
        key_fields: Iterable[str],
    ) -> tuple[str, ...]:

        return tuple(
            str(
                row.get(
                    field,
                    "",
                )
            )
            for field in key_fields
        )

    # ========================================
    # Generic upsert
    # ========================================

    def upsert_rows(
        self,
        sheet_name: str,
        rows: list[dict],
        *,
        key_fields: list[str],
        update_existing: bool = True,
        preserve_existing_on_none: bool = False,
        preserve_existing_fields: set[str] | None = None,
    ) -> dict:
        """
        Bulk upsert.

        v0.6.1:
        기존 방식의 row-by-row Google Sheets write를 제거하고
        전체 결과를 메모리에서 만든 뒤 한 번의 update 요청으로 저장한다.

        Google Sheets API write quota 초과 방지 목적.
        """

        preserve_existing_fields = (
            preserve_existing_fields
            or set()
        )

        result = {
            "inserted": 0,
            "updated": 0,
            "skipped": 0,
        }

        # ----------------------------------------------------
        # Nothing to do
        # ----------------------------------------------------

        if not rows:
            return result

        worksheet = (
            self.spreadsheet.worksheet(
                sheet_name
            )
        )

        values = (
            worksheet.get_all_values()
        )

        if not values:
            raise RuntimeError(
                f"{sheet_name}: header row missing."
            )

        headers = values[0]

        if not headers:
            raise RuntimeError(
                f"{sheet_name}: empty header row."
            )

        # ----------------------------------------------------
        # Validate key fields
        # ----------------------------------------------------

        missing_key_headers = [
            field
            for field in key_fields
            if field not in headers
        ]

        if missing_key_headers:

            raise RuntimeError(
                f"{sheet_name}: "
                f"key columns missing: "
                f"{missing_key_headers}"
            )

        # ----------------------------------------------------
        # Validate incoming fields
        # ----------------------------------------------------

        incoming_fields = set()

        for row in rows:
            incoming_fields.update(
                row.keys()
            )

        unknown_fields = (
            incoming_fields
            - set(headers)
        )

        if unknown_fields:

            raise RuntimeError(
                f"{sheet_name}: "
                f"incoming columns not in sheet: "
                f"{sorted(unknown_fields)}"
            )

        # ----------------------------------------------------
        # Normalize existing data
        # ----------------------------------------------------

        data_rows = []

        for raw_row in values[1:]:

            normalized = (
                list(raw_row)
                + [""] * (
                    len(headers)
                    - len(raw_row)
                )
            )

            normalized = (
                normalized[
                    :len(headers)
                ]
            )

            data_rows.append(
                normalized
            )

        # ----------------------------------------------------
        # Header position map
        # ----------------------------------------------------

        header_index = {
            header: index
            for index, header
            in enumerate(headers)
        }

        # ----------------------------------------------------
        # Existing key -> row index
        # ----------------------------------------------------

        def build_key_from_list(
            row_values: list,
        ) -> tuple:

            key = []

            for field in key_fields:

                value = row_values[
                    header_index[
                        field
                    ]
                ]

                key.append(
                    str(value).strip()
                )

            return tuple(key)

        def build_key_from_dict(
            row_dict: dict,
        ) -> tuple:

            key = []

            for field in key_fields:

                value = row_dict.get(
                    field,
                    "",
                )

                if value is None:
                    value = ""

                key.append(
                    str(value).strip()
                )

            return tuple(key)

        existing_index = {}

        for index, row_values in enumerate(
            data_rows
        ):

            key = build_key_from_list(
                row_values
            )

            # Empty keys should not participate
            # in upsert matching.
            if all(
                value == ""
                for value in key
            ):
                continue

            existing_index[
                key
            ] = index

        # ----------------------------------------------------
        # Apply incoming rows in memory
        # ----------------------------------------------------

        for incoming in rows:

            key = build_key_from_dict(
                incoming
            )

            if all(
                value == ""
                for value in key
            ):

                raise ValueError(
                    f"{sheet_name}: "
                    f"empty upsert key: "
                    f"{key_fields}"
                )

            # =================================================
            # Existing row
            # =================================================

            if key in existing_index:

                if not update_existing:

                    result[
                        "skipped"
                    ] += 1

                    continue

                row_index = (
                    existing_index[
                        key
                    ]
                )

                existing_row = (
                    data_rows[
                        row_index
                    ]
                )

                new_row = list(
                    existing_row
                )

                for header, value in (
                    incoming.items()
                ):

                    col_index = (
                        header_index[
                            header
                        ]
                    )

                    existing_value = (
                        existing_row[
                            col_index
                        ]
                    )

                    # -----------------------------------------
                    # Preserve explicit fields
                    # e.g. first_collected_at
                    # -----------------------------------------

                    if (
                        header
                        in preserve_existing_fields
                        and existing_value
                        not in (
                            None,
                            "",
                        )
                    ):

                        continue

                    # -----------------------------------------
                    # Preserve existing if incoming is None
                    # -----------------------------------------

                    if (
                        preserve_existing_on_none
                        and value is None
                    ):

                        continue

                    # -----------------------------------------
                    # Google Sheet blank
                    # -----------------------------------------

                    if value is None:
                        value = ""

                    new_row[
                        col_index
                    ] = value

                data_rows[
                    row_index
                ] = new_row

                result[
                    "updated"
                ] += 1

            # =================================================
            # New row
            # =================================================

            else:

                new_row = [
                    ""
                    for _ in headers
                ]

                for header, value in (
                    incoming.items()
                ):

                    if value is None:
                        value = ""

                    new_row[
                        header_index[
                            header
                        ]
                    ] = value

                data_rows.append(
                    new_row
                )

                new_index = (
                    len(data_rows)
                    - 1
                )

                existing_index[
                    key
                ] = new_index

                result[
                    "inserted"
                ] += 1

        # ----------------------------------------------------
        # Build complete matrix
        # ----------------------------------------------------

        matrix = [
            headers,
            *data_rows,
        ]

        required_rows = (
            len(matrix)
        )

        required_cols = (
            len(headers)
        )

        # ----------------------------------------------------
        # Resize only when actually necessary.
        # Resize itself is another API write request,
        # so avoid it during normal runs.
        # ----------------------------------------------------

        if (
            worksheet.row_count
            < required_rows
            or worksheet.col_count
            < required_cols
        ):

            worksheet.resize(
                rows=max(
                    worksheet.row_count,
                    required_rows + 100,
                ),
                cols=max(
                    worksheet.col_count,
                    required_cols,
                ),
            )

        # ----------------------------------------------------
        # ONE bulk write request
        # ----------------------------------------------------

        worksheet.update(
            range_name="A1",
            values=matrix,
            value_input_option="RAW",
        )

        return result