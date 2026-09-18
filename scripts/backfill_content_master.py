from __future__ import annotations

from datetime import datetime
from zoneinfo import ZoneInfo

from config.settings import (
    GOOGLE_SPREADSHEET_ID,
    META_API_VERSION,
    INSTAGRAM_ACCOUNT_ID,
    META_IG_ACCESS_TOKEN,
    META_ADS_ACCESS_TOKEN,
)

from src.meta_client import (
    MetaClient,
    MetaAPIError,
)

from src.fetch_account import (
    fetch_account,
)

from src.fetch_media import (
    fetch_media,
)

from src.sheets_client import (
    get_gspread_client,
)


VERSION = "0.3.1"

KST = ZoneInfo(
    "Asia/Seoul"
)


HEADERS = [
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


def now_kst() -> datetime:
    return datetime.now(
        KST
    )


def format_datetime(
    value: datetime,
) -> str:
    return value.strftime(
        "%Y-%m-%d %H:%M:%S"
    )


def parse_meta_datetime(
    value: str | None,
) -> str:

    if not value:
        return ""

    dt = datetime.strptime(
        value,
        "%Y-%m-%dT%H:%M:%S%z",
    )

    return format_datetime(
        dt.astimezone(KST)
    )


def main() -> None:

    collected_at = now_kst()
    collected_at_text = format_datetime(
        collected_at
    )

    print("=" * 72)
    print(
        "Greating Instagram "
        f"CONTENT_MASTER Backfill v{VERSION}"
    )
    print("=" * 72)

    # ========================================
    # Meta
    # ========================================

    meta = MetaClient(
        api_version=META_API_VERSION,
        ig_access_token=META_IG_ACCESS_TOKEN,
        ads_access_token=META_ADS_ACCESS_TOKEN,
    )

    account = fetch_account(
        meta,
        INSTAGRAM_ACCOUNT_ID,
    )

    expected_media_count = account.get(
        "media_count"
    )

    print(
        f"[INFO] Instagram media_count: "
        f"{expected_media_count}"
    )

    print(
        "[INFO] Loading all available media..."
    )

    media = fetch_media(
        meta,
        INSTAGRAM_ACCOUNT_ID,
        max_items=5000,
    )

    print(
        f"[OK] API media loaded: "
        f"{len(media)}"
    )

    # ========================================
    # Sheets
    # ========================================

    client = get_gspread_client()

    spreadsheet = client.open_by_key(
        GOOGLE_SPREADSHEET_ID
    )

    worksheet = spreadsheet.worksheet(
        "CONTENT_MASTER"
    )

    existing_values = (
        worksheet.get_all_values()
    )

    if not existing_values:
        raise RuntimeError(
            "CONTENT_MASTER has no header."
        )

    existing_headers = (
        existing_values[0]
    )

    if existing_headers != HEADERS:
        raise RuntimeError(
            "CONTENT_MASTER header does not "
            "match v0.3.1 schema. "
            "Run migrate_content_master_v031 first."
        )

    # ========================================
    # Existing rows by media_id
    # ========================================

    existing_by_id: dict[
        str,
        dict,
    ] = {}

    for raw_row in existing_values[1:]:

        padded = (
            raw_row
            + [""] * (
                len(HEADERS)
                - len(raw_row)
            )
        )

        row = dict(
            zip(
                HEADERS,
                padded,
            )
        )

        media_id = row.get(
            "media_id",
            "",
        )

        if media_id:
            existing_by_id[
                media_id
            ] = row

    print(
        f"[INFO] Existing master rows: "
        f"{len(existing_by_id)}"
    )

    # ========================================
    # Merge API metadata + existing AI/manual
    # ========================================

    merged_by_id = dict(
        existing_by_id
    )

    inserted = 0
    refreshed = 0

    for item in media:

        media_id = str(
            item.get(
                "id",
                "",
            )
        )

        if not media_id:
            continue

        existing = (
            existing_by_id.get(
                media_id,
                {}
            )
        )

        if existing:
            refreshed += 1
        else:
            inserted += 1

        created_at = (
            existing.get(
                "created_at"
            )
            or collected_at_text
        )

        merged = {
            # -------------------------------
            # Meta metadata
            # -------------------------------
            "media_id": media_id,

            "posted_at": (
                parse_meta_datetime(
                    item.get(
                        "timestamp"
                    )
                )
            ),

            "media_type": item.get(
                "media_type",
                "",
            ),

            "media_product_type": item.get(
                "media_product_type",
                "",
            ),

            "permalink": item.get(
                "permalink",
                "",
            ),

            "media_url": item.get(
                "media_url",
                "",
            ),

            "thumbnail_url": item.get(
                "thumbnail_url",
                "",
            ),

            "caption": item.get(
                "caption",
                "",
            ),

            # -------------------------------
            # Preserve AI fields
            # -------------------------------
            "ai_title": existing.get(
                "ai_title",
                "",
            ),

            "content_category": existing.get(
                "content_category",
                "",
            ),

            "content_subcategory": existing.get(
                "content_subcategory",
                "",
            ),

            "product_name": existing.get(
                "product_name",
                "",
            ),

            "campaign_name": existing.get(
                "campaign_name",
                "",
            ),

            "is_paid": existing.get(
                "is_paid",
                "",
            ),

            # -------------------------------
            # Preserve manual fields
            # -------------------------------
            "manual_title": existing.get(
                "manual_title",
                "",
            ),

            "manual_category": existing.get(
                "manual_category",
                "",
            ),

            # -------------------------------
            # Audit
            # -------------------------------
            "created_at": created_at,
            "updated_at": collected_at_text,
        }

        merged_by_id[
            media_id
        ] = merged

    # ========================================
    # Sort newest first
    # ========================================

    merged_rows = list(
        merged_by_id.values()
    )

    merged_rows.sort(
        key=lambda x: x.get(
            "posted_at",
            "",
        ),
        reverse=True,
    )

    matrix = [
        HEADERS
    ]

    for row in merged_rows:

        matrix.append(
            [
                row.get(
                    header,
                    "",
                )
                for header in HEADERS
            ]
        )

    # ========================================
    # Resize + single bulk write
    # ========================================

    required_rows = max(
        len(matrix) + 100,
        1000,
    )

    worksheet.resize(
        rows=required_rows,
        cols=len(HEADERS),
    )

    worksheet.clear()

    worksheet.update(
        range_name="A1",
        values=matrix,
        value_input_option="RAW",
    )

    # ========================================
    # Result
    # ========================================

    print()
    print(
        f"[OK] Existing refreshed: "
        f"{refreshed}"
    )

    print(
        f"[OK] Newly inserted: "
        f"{inserted}"
    )

    print(
        f"[OK] Final master rows: "
        f"{len(merged_rows)}"
    )

    if expected_media_count is not None:

        diff = (
            int(expected_media_count)
            - len(media)
        )

        print(
            f"[CHECK] account media_count="
            f"{expected_media_count}"
            f" | API fetched={len(media)}"
            f" | difference={diff}"
        )

    print()
    print("=" * 72)
    print(
        "CONTENT_MASTER BACKFILL COMPLETED "
        f"| VERSION={VERSION}"
    )
    print("=" * 72)


if __name__ == "__main__":

    try:
        main()

    except MetaAPIError as exc:

        print()
        print("=" * 72)
        print("[META API ERROR]")
        print(exc)
        print("=" * 72)

        raise