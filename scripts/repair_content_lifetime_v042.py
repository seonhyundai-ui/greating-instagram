from __future__ import annotations

from config.settings import (
    GOOGLE_SPREADSHEET_ID,
)

from src.sheets_client import (
    get_gspread_client,
)


VERSION = "0.4.2"


PAID_FIELDS = [
    "views_paid",
    "reach_paid",
    "likes_paid",
    "comments_paid",
    "saved_paid",
    "shares_paid",
    "interactions_paid",
]


def to_number(value):

    if value in (
        None,
        "",
    ):
        return None

    try:
        return float(value)

    except (
        TypeError,
        ValueError,
    ):
        return None


def is_true(value) -> bool:

    return str(
        value
    ).strip().upper() == "TRUE"


def main() -> None:

    print("=" * 78)
    print(
        "Greating Instagram "
        f"CONTENT_LIFETIME Repair v{VERSION}"
    )
    print("=" * 78)

    client = get_gspread_client()

    spreadsheet = client.open_by_key(
        GOOGLE_SPREADSHEET_ID
    )

    worksheet = spreadsheet.worksheet(
        "CONTENT_LIFETIME"
    )

    values = worksheet.get_all_values()

    if not values:
        raise RuntimeError(
            "CONTENT_LIFETIME is empty."
        )

    headers = values[0]
    raw_rows = values[1:]

    repaired = []

    organic_count = 0
    paid_count = 0
    qa_ok = 0
    qa_check = 0

    for raw_row in raw_rows:

        padded = (
            raw_row
            + [""] * (
                len(headers)
                - len(raw_row)
            )
        )

        row = dict(
            zip(
                headers,
                padded,
            )
        )

        has_paid = is_true(
            row.get(
                "has_paid"
            )
        )

        issues = []

        # ====================================
        # No advertising
        # ====================================

        if not has_paid:

            organic_count += 1

            for field in PAID_FIELDS:
                row[field] = 0

            # Gross reach definition:
            # organic + paid
            reach_organic = to_number(
                row.get(
                    "reach_organic"
                )
            )

            if reach_organic is not None:
                row[
                    "reach_total_gross"
                ] = reach_organic

        # ====================================
        # Advertising content
        # ====================================

        else:

            paid_count += 1

            if to_number(
                row.get(
                    "reach_paid"
                )
            ) is None:

                issues.append(
                    "PAID_REACH_MISSING"
                )

            if to_number(
                row.get(
                    "interactions_paid"
                )
            ) is None:

                issues.append(
                    "PAID_INTERACTIONS_MISSING"
                )

            for field in [
                "views_paid",
                "likes_paid",
                "comments_paid",
                "shares_paid",
            ]:

                value = to_number(
                    row.get(
                        field
                    )
                )

                if (
                    value is not None
                    and value < 0
                ):

                    issues.append(
                        f"NEGATIVE_{field.upper()}"
                    )

        # ====================================
        # Organic core validation
        # ====================================

        for field in [
            "views_organic",
            "reach_organic",
            "interactions_organic",
        ]:

            if to_number(
                row.get(
                    field
                )
            ) is None:

                issues.append(
                    f"MISSING_{field.upper()}"
                )

        # ====================================
        # QA result
        # ====================================

        if issues:

            row[
                "metric_qa_status"
            ] = (
                "CHECK:"
                + ",".join(
                    sorted(
                        set(issues)
                    )
                )
            )

            qa_check += 1

        else:

            row[
                "metric_qa_status"
            ] = "OK"

            qa_ok += 1

        repaired.append(
            [
                row.get(
                    header,
                    ""
                )
                for header in headers
            ]
        )

    # ========================================
    # Bulk write
    # ========================================

    matrix = [
        headers,
        *repaired,
    ]

    worksheet.update(
        range_name="A1",
        values=matrix,
        value_input_option="RAW",
    )

    print(
        f"[OK] rows={len(repaired):,}"
    )

    print(
        f"     non-paid={organic_count:,}"
    )

    print(
        f"     paid={paid_count:,}"
    )

    print(
        f"     QA OK={qa_ok:,}"
    )

    print(
        f"     QA CHECK={qa_check:,}"
    )

    print()
    print("=" * 78)
    print(
        "CONTENT_LIFETIME REPAIR COMPLETED"
    )
    print("=" * 78)


if __name__ == "__main__":
    main()