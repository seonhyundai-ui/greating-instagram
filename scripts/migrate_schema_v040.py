from __future__ import annotations

from datetime import datetime
from zoneinfo import ZoneInfo

from config.settings import (
    GOOGLE_SPREADSHEET_ID,
)

from src.sheets_client import (
    get_gspread_client,
)


VERSION = "0.4.0"
KST = ZoneInfo("Asia/Seoul")


# ============================================================
# CONTENT_MASTER
# ============================================================

CONTENT_MASTER_HEADERS = [
    # ----------------------------------------
    # Meta original
    # ----------------------------------------
    "media_id",
    "posted_at",
    "media_type",
    "media_product_type",
    "permalink",
    "media_url",
    "thumbnail_url",
    "caption",

    # ----------------------------------------
    # AI classification
    # ----------------------------------------
    "ai_title",
    "content_category",
    "content_subcategory",
    "content_theme",
    "product_name",
    "campaign_name",
    "creative_format",

    # ----------------------------------------
    # System-derived
    # ----------------------------------------
    "has_paid",

    # ----------------------------------------
    # Manual override
    # ----------------------------------------
    "manual_title",
    "manual_category",

    # ----------------------------------------
    # Audit
    # ----------------------------------------
    "created_at",
    "updated_at",
]


# ============================================================
# MEDIA_SNAPSHOT
# ============================================================

MEDIA_SNAPSHOT_HEADERS = [
    "snapshot_date",
    "media_id",
    "posted_at",
    "media_type",
    "media_product_type",

    # ========================================
    # Views
    # ========================================
    "views_total",
    "views_organic",
    "views_paid",

    # ========================================
    # Reach
    #
    # total = organic + paid
    # duplicated users may exist.
    # ========================================
    "reach_total_gross",
    "reach_organic",
    "reach_paid",

    # ========================================
    # Likes
    # ========================================
    "likes_total",
    "likes_organic",
    "likes_paid",

    # ========================================
    # Comments
    # ========================================
    "comments_total",
    "comments_organic",
    "comments_paid",

    # ========================================
    # Saved
    # ========================================
    "saved_total",
    "saved_organic",
    "saved_paid",

    # ========================================
    # Shares
    # ========================================
    "shares_total",
    "shares_organic",
    "shares_paid",

    # ========================================
    # Interactions
    # ========================================
    "interactions_total",
    "interactions_organic",
    "interactions_paid",

    # ========================================
    # Reels organic watch metrics
    # ========================================
    "avg_watch_time_ms_organic",
    "total_watch_time_ms_organic",

    # ========================================
    # QA
    # ========================================
    "metric_qa_status",

    "collected_at",
]


# ============================================================
# AD_MASTER
# ============================================================

AD_MASTER_HEADERS = [
    "ad_id",
    "ad_name",

    "campaign_id",
    "campaign_name",

    "adset_id",
    "adset_name",

    "creative_id",
    "creative_name",

    # Original published Instagram media
    "source_instagram_media_id",

    # Effective ad-side Instagram media
    "effective_instagram_media_id",

    "instagram_permalink_url",

    # Final matched CONTENT_MASTER media_id
    "content_media_id",

    # PUBLISHED_CONTENT / AD_ONLY
    "creative_source",

    # SOURCE_MEDIA_ID / PERMALINK /
    # EFFECTIVE_MEDIA_ID / UNMATCHED
    "match_method",

    "status",
    "effective_status",

    "created_time",
    "updated_time",

    "first_seen_at",
    "last_seen_at",
]


# ============================================================
# ADS_DAILY
# ============================================================

ADS_DAILY_HEADERS = [
    "date",

    "ad_id",
    "ad_name",

    "campaign_id",
    "campaign_name",

    "adset_id",
    "adset_name",

    "creative_id",

    "source_instagram_media_id",
    "effective_instagram_media_id",
    "content_media_id",
    "creative_source",

    # ========================================
    # Paid delivery
    # ========================================
    "spend",
    "impressions",
    "reach_paid",
    "frequency",

    # ========================================
    # Paid traffic
    # ========================================
    "clicks",
    "ctr",
    "cpc",
    "cpm",

    # ========================================
    # Paid engagement
    # ========================================
    "paid_likes",
    "paid_comments",
    "paid_saved",
    "paid_shares",
    "paid_interactions",

    # Instagram only
    "publisher_platform",

    # Raw Marketing API actions for audit
    "actions_json",

    "collected_at",
]


# ============================================================
# Helpers
# ============================================================

def now_text() -> str:
    return datetime.now(
        KST
    ).strftime(
        "%Y-%m-%d %H:%M:%S"
    )


def get_existing_sheet_names(
    spreadsheet,
) -> set[str]:

    return {
        ws.title
        for ws in spreadsheet.worksheets()
    }


def make_backup(
    spreadsheet,
    source_sheet_name: str,
    backup_sheet_name: str,
) -> None:
    """
    Create a one-time backup sheet.
    Does nothing if backup already exists.
    """

    existing = get_existing_sheet_names(
        spreadsheet
    )

    if backup_sheet_name in existing:

        print(
            f"[SKIP] Backup already exists: "
            f"{backup_sheet_name}"
        )
        return

    source = spreadsheet.worksheet(
        source_sheet_name
    )

    values = source.get_all_values()

    rows = max(
        len(values) + 100,
        1000,
    )

    cols = max(
        max(
            (
                len(row)
                for row in values
            ),
            default=1,
        ),
        20,
    )

    backup = spreadsheet.add_worksheet(
        title=backup_sheet_name,
        rows=rows,
        cols=cols,
    )

    if values:

        backup.update(
            range_name="A1",
            values=values,
            value_input_option="RAW",
        )

    print(
        f"[OK] Backup created: "
        f"{backup_sheet_name}"
        f" | rows={max(len(values) - 1, 0)}"
    )


def replace_sheet(
    worksheet,
    headers: list[str],
    rows: list[list],
) -> None:

    matrix = [
        headers,
        *rows,
    ]

    required_rows = max(
        len(matrix) + 100,
        1000,
    )

    required_cols = max(
        len(headers),
        20,
    )

    worksheet.resize(
        rows=required_rows,
        cols=required_cols,
    )

    worksheet.clear()

    worksheet.update(
        range_name="A1",
        values=matrix,
        value_input_option="RAW",
    )


def ensure_empty_schema(
    spreadsheet,
    sheet_name: str,
    headers: list[str],
) -> None:

    existing = get_existing_sheet_names(
        spreadsheet
    )

    if sheet_name not in existing:

        worksheet = spreadsheet.add_worksheet(
            title=sheet_name,
            rows=2000,
            cols=max(
                len(headers),
                20,
            ),
        )

        worksheet.update(
            range_name="A1",
            values=[headers],
            value_input_option="RAW",
        )

        print(
            f"[CREATE] {sheet_name}"
        )

        return

    worksheet = spreadsheet.worksheet(
        sheet_name
    )

    values = worksheet.get_all_values()

    # Existing data should never be destroyed here.
    if len(values) > 1:

        print(
            f"[FOUND] {sheet_name}"
            f" | existing rows={len(values) - 1:,}"
            " | data preserved"
        )

        return

    worksheet.resize(
        rows=2000,
        cols=max(
            len(headers),
            20,
        ),
    )

    worksheet.clear()

    worksheet.update(
        range_name="A1",
        values=[headers],
        value_input_option="RAW",
    )

    print(
        f"[OK] Schema refreshed: {sheet_name}"
    )


# ============================================================
# CONTENT_MASTER migration
# ============================================================

def migrate_content_master(
    spreadsheet,
) -> None:

    print()
    print(
        "[1/4] CONTENT_MASTER migration"
    )

    make_backup(
        spreadsheet,
        "CONTENT_MASTER",
        "BAK_CONTENT_MASTER_v031",
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

    # Already migrated
    if old_headers == CONTENT_MASTER_HEADERS:

        print(
            "[SKIP] CONTENT_MASTER "
            "already v0.4.0"
        )
        return

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

        migrated = {}

        for header in CONTENT_MASTER_HEADERS:

            # Rename is_paid -> has_paid
            if header == "has_paid":

                migrated[
                    header
                ] = (
                    old.get(
                        "has_paid"
                    )
                    or old.get(
                        "is_paid"
                    )
                    or ""
                )

            else:

                migrated[
                    header
                ] = old.get(
                    header,
                    "",
                )

        migrated_rows.append(
            [
                migrated.get(
                    header,
                    "",
                )
                for header
                in CONTENT_MASTER_HEADERS
            ]
        )

    replace_sheet(
        worksheet,
        CONTENT_MASTER_HEADERS,
        migrated_rows,
    )

    print(
        f"[OK] CONTENT_MASTER migrated"
        f" | rows={len(migrated_rows):,}"
        f" | columns={len(CONTENT_MASTER_HEADERS)}"
    )


# ============================================================
# MEDIA_SNAPSHOT migration
# ============================================================

def migrate_media_snapshot(
    spreadsheet,
) -> None:

    print()
    print(
        "[2/4] MEDIA_SNAPSHOT migration"
    )

    make_backup(
        spreadsheet,
        "MEDIA_SNAPSHOT",
        "BAK_MEDIA_SNAPSHOT_v030",
    )

    worksheet = spreadsheet.worksheet(
        "MEDIA_SNAPSHOT"
    )

    values = worksheet.get_all_values()

    if not values:
        raise RuntimeError(
            "MEDIA_SNAPSHOT is empty."
        )

    old_headers = values[0]
    old_rows = values[1:]

    # Already migrated
    if old_headers == MEDIA_SNAPSHOT_HEADERS:

        print(
            "[SKIP] MEDIA_SNAPSHOT "
            "already v0.4.0"
        )
        return

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

        migrated = {
            "snapshot_date": old.get(
                "snapshot_date",
                "",
            ),

            "media_id": old.get(
                "media_id",
                "",
            ),

            "posted_at": old.get(
                "posted_at",
                "",
            ),

            "media_type": old.get(
                "media_type",
                "",
            ),

            "media_product_type": old.get(
                "media_product_type",
                "",
            ),

            # --------------------------------
            # Existing v0.3 values were
            # Instagram native/organic values.
            # --------------------------------

            "views_organic": (
                old.get(
                    "views_organic"
                )
                or old.get(
                    "views"
                )
                or ""
            ),

            "reach_organic": (
                old.get(
                    "reach_organic"
                )
                or old.get(
                    "reach"
                )
                or ""
            ),

            "saved_organic": (
                old.get(
                    "saved_organic"
                )
                or old.get(
                    "saved"
                )
                or ""
            ),

            "shares_organic": (
                old.get(
                    "shares_organic"
                )
                or old.get(
                    "shares"
                )
                or ""
            ),

            "interactions_organic": (
                old.get(
                    "interactions_organic"
                )
                or old.get(
                    "total_interactions"
                )
                or ""
            ),

            "avg_watch_time_ms_organic": (
                old.get(
                    "avg_watch_time_ms_organic"
                )
                or old.get(
                    "avg_watch_time_ms"
                )
                or ""
            ),

            "total_watch_time_ms_organic": (
                old.get(
                    "total_watch_time_ms_organic"
                )
                or old.get(
                    "total_watch_time_ms"
                )
                or ""
            ),

            # --------------------------------
            # v0.3 did not collect TOTAL / PAID
            # --------------------------------

            "views_total": old.get(
                "views_total",
                "",
            ),

            "views_paid": old.get(
                "views_paid",
                "",
            ),

            "reach_total_gross": old.get(
                "reach_total_gross",
                "",
            ),

            "reach_paid": old.get(
                "reach_paid",
                "",
            ),

            "likes_total": old.get(
                "likes_total",
                "",
            ),

            "likes_organic": old.get(
                "likes_organic",
                "",
            ),

            "likes_paid": old.get(
                "likes_paid",
                "",
            ),

            "comments_total": old.get(
                "comments_total",
                "",
            ),

            "comments_organic": old.get(
                "comments_organic",
                "",
            ),

            "comments_paid": old.get(
                "comments_paid",
                "",
            ),

            "saved_total": old.get(
                "saved_total",
                "",
            ),

            "saved_paid": old.get(
                "saved_paid",
                "",
            ),

            "shares_total": old.get(
                "shares_total",
                "",
            ),

            "shares_paid": old.get(
                "shares_paid",
                "",
            ),

            "interactions_total": old.get(
                "interactions_total",
                "",
            ),

            "interactions_paid": old.get(
                "interactions_paid",
                "",
            ),

            "metric_qa_status": (
                old.get(
                    "metric_qa_status"
                )
                or "LEGACY_ORGANIC_ONLY"
            ),

            "collected_at": old.get(
                "collected_at",
                "",
            ),
        }

        migrated_rows.append(
            [
                migrated.get(
                    header,
                    "",
                )
                for header
                in MEDIA_SNAPSHOT_HEADERS
            ]
        )

    replace_sheet(
        worksheet,
        MEDIA_SNAPSHOT_HEADERS,
        migrated_rows,
    )

    print(
        f"[OK] MEDIA_SNAPSHOT migrated"
        f" | rows={len(migrated_rows):,}"
        f" | columns={len(MEDIA_SNAPSHOT_HEADERS)}"
    )

    if migrated_rows:

        print(
            "[INFO] Existing rows marked "
            "LEGACY_ORGANIC_ONLY"
        )


# ============================================================
# Main
# ============================================================

def main() -> None:

    print("=" * 78)
    print(
        "Greating Instagram Schema Migration "
        f"v{VERSION}"
    )
    print(
        f"Started at: {now_text()} KST"
    )
    print("=" * 78)

    client = get_gspread_client()

    spreadsheet = client.open_by_key(
        GOOGLE_SPREADSHEET_ID
    )

    print(
        f"[OK] Spreadsheet: "
        f"{spreadsheet.title}"
    )

    # ========================================================
    # 1. Content master
    # ========================================================

    migrate_content_master(
        spreadsheet
    )

    # ========================================================
    # 2. Media snapshot
    # ========================================================

    migrate_media_snapshot(
        spreadsheet
    )

    # ========================================================
    # 3. AD_MASTER
    # ========================================================

    print()
    print(
        "[3/4] AD_MASTER schema"
    )

    ensure_empty_schema(
        spreadsheet,
        "AD_MASTER",
        AD_MASTER_HEADERS,
    )

    # ========================================================
    # 4. ADS_DAILY
    # ========================================================

    print()
    print(
        "[4/4] ADS_DAILY schema"
    )

    ensure_empty_schema(
        spreadsheet,
        "ADS_DAILY",
        ADS_DAILY_HEADERS,
    )

    # ========================================================
    # Complete
    # ========================================================

    print()
    print("=" * 78)
    print(
        "SCHEMA MIGRATION COMPLETED "
        f"| VERSION={VERSION}"
    )
    print("=" * 78)


if __name__ == "__main__":
    main()