from __future__ import annotations

from collections import Counter

from config.settings import (
    GOOGLE_SPREADSHEET_ID,
)

from src.sheets_client import (
    get_gspread_client,
)


VERSION = "0.4.1-audit"


def to_number(value):
    if value in (None, ""):
        return None

    try:
        return float(value)

    except (TypeError, ValueError):
        return None


def fmt_number(value):
    if value is None:
        return "-"

    if float(value).is_integer():
        return f"{int(value):,}"

    return f"{value:,.2f}"


def main() -> None:

    print("=" * 90)
    print(
        "Greating Instagram "
        f"CONTENT_LIFETIME QA Audit v{VERSION}"
    )
    print("=" * 90)

    client = get_gspread_client()

    spreadsheet = client.open_by_key(
        GOOGLE_SPREADSHEET_ID
    )

    worksheet = spreadsheet.worksheet(
        "CONTENT_LIFETIME"
    )

    rows = worksheet.get_all_records()

    print(
        f"[INFO] rows={len(rows):,}"
    )

    # ========================================================
    # QA status distribution
    # ========================================================

    status_counter = Counter(
        str(
            row.get(
                "metric_qa_status",
                ""
            )
        )
        for row in rows
    )

    print()
    print("[1/5] QA status distribution")

    for status, count in (
        status_counter.most_common()
    ):
        print(
            f"      {status or '(blank)':<60}"
            f"{count:>6,}"
        )

    # ========================================================
    # Detailed mismatch analysis
    # ========================================================

    organic_mismatch = []
    paid_mismatch = []

    for row in rows:

        # ----------------------------------------------------
        # Organic
        # ----------------------------------------------------

        ol = to_number(
            row.get("likes_organic")
        )

        oc = to_number(
            row.get("comments_organic")
        )

        os = to_number(
            row.get("saved_organic")
        )

        osh = to_number(
            row.get("shares_organic")
        )

        oi = to_number(
            row.get(
                "interactions_organic"
            )
        )

        if all(
            x is not None
            for x in [
                ol,
                oc,
                os,
                osh,
                oi,
            ]
        ):

            component_sum = (
                ol
                + oc
                + os
                + osh
            )

            diff = (
                oi
                - component_sum
            )

            if diff != 0:

                organic_mismatch.append(
                    {
                        "media_id": row.get(
                            "media_id"
                        ),
                        "posted_at": row.get(
                            "posted_at"
                        ),
                        "media_type": row.get(
                            "media_type"
                        ),
                        "media_product_type": row.get(
                            "media_product_type"
                        ),
                        "likes": ol,
                        "comments": oc,
                        "saved": os,
                        "shares": osh,
                        "component_sum": (
                            component_sum
                        ),
                        "interactions": oi,
                        "diff": diff,
                    }
                )

        # ----------------------------------------------------
        # Paid
        # ----------------------------------------------------

        pl = to_number(
            row.get("likes_paid")
        )

        pc = to_number(
            row.get("comments_paid")
        )

        ps = to_number(
            row.get("saved_paid")
        )

        psh = to_number(
            row.get("shares_paid")
        )

        pi = to_number(
            row.get(
                "interactions_paid"
            )
        )

        if all(
            x is not None
            for x in [
                pl,
                pc,
                ps,
                psh,
                pi,
            ]
        ):

            component_sum = (
                pl
                + pc
                + ps
                + psh
            )

            diff = (
                pi
                - component_sum
            )

            if diff != 0:

                paid_mismatch.append(
                    {
                        "media_id": row.get(
                            "media_id"
                        ),
                        "posted_at": row.get(
                            "posted_at"
                        ),
                        "likes": pl,
                        "comments": pc,
                        "saved": ps,
                        "shares": psh,
                        "component_sum": (
                            component_sum
                        ),
                        "interactions": pi,
                        "diff": diff,
                    }
                )

    print()
    print("[2/5] Interaction mismatch counts")

    print(
        f"      Organic mismatch = "
        f"{len(organic_mismatch):,}"
    )

    print(
        f"      Paid mismatch    = "
        f"{len(paid_mismatch):,}"
    )

    # ========================================================
    # Organic mismatch by media type
    # ========================================================

    print()
    print(
        "[3/5] Organic mismatch "
        "by media type"
    )

    media_type_counter = Counter(
        (
            str(
                row.get(
                    "media_type"
                )
            ),
            str(
                row.get(
                    "media_product_type"
                )
            ),
        )
        for row in organic_mismatch
    )

    for (
        media_key,
        count,
    ) in media_type_counter.most_common():

        media_type, product_type = (
            media_key
        )

        print(
            f"      "
            f"{media_type:<12}"
            f"{product_type:<12}"
            f"{count:>6,}"
        )

    # ========================================================
    # Difference distribution
    # ========================================================

    print()
    print(
        "[4/5] Organic interaction "
        "difference distribution"
    )

    diff_counter = Counter(
        row["diff"]
        for row in organic_mismatch
    )

    for diff, count in (
        diff_counter.most_common(20)
    ):

        print(
            f"      diff={fmt_number(diff):>10}"
            f" | rows={count:>6,}"
        )

    # ========================================================
    # Samples
    # ========================================================

    print()
    print(
        "[5/5] Organic mismatch samples"
    )

    for row in organic_mismatch[:30]:

        print(
            "      "
            f"{row['posted_at']} "
            f"| {row['media_product_type']} "
            f"| {row['media_id']} "
            f"| L={fmt_number(row['likes'])} "
            f"C={fmt_number(row['comments'])} "
            f"S={fmt_number(row['saved'])} "
            f"Sh={fmt_number(row['shares'])} "
            f"| SUM={fmt_number(row['component_sum'])} "
            f"| INTER={fmt_number(row['interactions'])} "
            f"| DIFF={fmt_number(row['diff'])}"
        )

    print()
    print("=" * 90)
    print(
        "QA AUDIT COMPLETED"
    )
    print("=" * 90)


if __name__ == "__main__":
    main()