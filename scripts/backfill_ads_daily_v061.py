from __future__ import annotations

import calendar
import time

from datetime import (
    date,
    datetime,
    timedelta,
)
from zoneinfo import ZoneInfo

from config.settings import (
    META_API_VERSION,
    META_AD_ACCOUNT_ID,
    META_IG_ACCESS_TOKEN,
    META_ADS_ACCESS_TOKEN,
    GOOGLE_SPREADSHEET_ID,
)

from src.meta_client import (
    MetaClient,
)

from src.fetch_ads import (
    fetch_instagram_ads_daily,
)

from src.sheets_client import (
    get_gspread_client,
)


VERSION = "0.6.1"

KST = ZoneInfo(
    "Asia/Seoul"
)

BACKFILL_START = date(
    2025,
    1,
    1,
)


# ============================================================
# Helpers
# ============================================================

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


def parse_date(
    value: str,
) -> date | None:

    if not value:
        return None

    try:
        return datetime.strptime(
            value,
            "%Y-%m-%d",
        ).date()

    except ValueError:
        return None


def numeric(value):

    if value in (
        None,
        "",
    ):
        return 0

    try:
        return float(value)

    except (
        TypeError,
        ValueError,
    ):
        return 0


def month_ranges(
    start_date: date,
    end_date: date,
):

    current = date(
        start_date.year,
        start_date.month,
        1,
    )

    while current <= end_date:

        last_day = calendar.monthrange(
            current.year,
            current.month,
        )[1]

        month_end = date(
            current.year,
            current.month,
            last_day,
        )

        since = max(
            current,
            start_date,
        )

        until = min(
            month_end,
            end_date,
        )

        yield (
            since,
            until,
        )

        if current.month == 12:

            current = date(
                current.year + 1,
                1,
                1,
            )

        else:

            current = date(
                current.year,
                current.month + 1,
                1,
            )


# ============================================================
# Main
# ============================================================

def main() -> None:

    started_at = now_kst()

    end_date = (
        started_at.date()
        - timedelta(days=1)
    )

    collected_text = format_datetime(
        started_at
    )

    print("=" * 82)
    print(
        "Greating Instagram "
        f"ADS_DAILY Backfill v{VERSION}"
    )

    print(
        f"Range: "
        f"{BACKFILL_START.isoformat()}"
        f" ~ "
        f"{end_date.isoformat()}"
    )

    print("=" * 82)

    # ========================================================
    # Clients
    # ========================================================

    meta = MetaClient(
        api_version=META_API_VERSION,
        ig_access_token=META_IG_ACCESS_TOKEN,
        ads_access_token=META_ADS_ACCESS_TOKEN,
    )

    google = get_gspread_client()

    spreadsheet = google.open_by_key(
        GOOGLE_SPREADSHEET_ID
    )

    # ========================================================
    # 1. AD_MASTER
    # ========================================================

    print()
    print(
        "[1/4] Load AD_MASTER"
    )

    ad_ws = spreadsheet.worksheet(
        "AD_MASTER"
    )

    ad_values = ad_ws.get_all_values()

    if not ad_values:

        raise RuntimeError(
            "AD_MASTER is empty."
        )

    ad_headers = ad_values[0]

    ad_lookup = {}

    for raw_row in ad_values[1:]:

        padded = (
            raw_row
            + [""] * (
                len(ad_headers)
                - len(raw_row)
            )
        )

        row = dict(
            zip(
                ad_headers,
                padded,
            )
        )

        ad_id = str(
            row.get(
                "ad_id",
                ""
            )
        ).strip()

        if ad_id:

            ad_lookup[
                ad_id
            ] = row

    print(
        f"      AD_MASTER rows="
        f"{len(ad_lookup):,}"
    )

    # ========================================================
    # 2. Existing ADS_DAILY
    # ========================================================

    print()
    print(
        "[2/4] Load existing ADS_DAILY"
    )

    daily_ws = spreadsheet.worksheet(
        "ADS_DAILY"
    )

    daily_values = daily_ws.get_all_values()

    if not daily_values:

        raise RuntimeError(
            "ADS_DAILY header missing."
        )

    headers = daily_values[0]

    # Rows outside the backfill period are preserved.
    preserved_rows = []

    for raw_row in daily_values[1:]:

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

        row_date = parse_date(
            str(
                row.get(
                    "date",
                    ""
                )
            )
        )

        if (
            row_date is None
            or row_date < BACKFILL_START
            or row_date > end_date
        ):

            preserved_rows.append(
                row
            )

    print(
        f"      existing rows="
        f"{max(len(daily_values) - 1, 0):,}"
    )

    print(
        f"      preserved outside range="
        f"{len(preserved_rows):,}"
    )

    # ========================================================
    # 3. Fetch monthly chunks
    # ========================================================

    print()
    print(
        "[3/4] Meta Ads historical fetch"
    )

    backfill_by_key = {}

    unknown_ad_ids = set()

    total_source_rows = 0

    month_list = list(
        month_ranges(
            BACKFILL_START,
            end_date,
        )
    )

    for index, (
        since,
        until,
    ) in enumerate(
        month_list,
        start=1,
    ):

        print(
            f"      [{index:02d}/{len(month_list):02d}] "
            f"{since.isoformat()} "
            f"~ {until.isoformat()}",
            end="",
            flush=True,
        )

        source_rows = (
            fetch_instagram_ads_daily(
                meta,
                META_AD_ACCOUNT_ID,
                since=since.isoformat(),
                until=until.isoformat(),
            )
        )

        total_source_rows += len(
            source_rows
        )

        month_spend = 0

        for source in source_rows:

            ad_id = str(
                source.get(
                    "ad_id"
                )
                or ""
            )

            master = (
                ad_lookup.get(
                    ad_id
                )
            )

            if master is None:

                master = {}
                unknown_ad_ids.add(
                    ad_id
                )

            row = {
                "date": source.get(
                    "date"
                ),

                "ad_id": ad_id,

                "ad_name": source.get(
                    "ad_name"
                ),

                "campaign_id": (
                    source.get(
                        "campaign_id"
                    )
                ),

                "campaign_name": (
                    source.get(
                        "campaign_name"
                    )
                ),

                "adset_id": (
                    source.get(
                        "adset_id"
                    )
                ),

                "adset_name": (
                    source.get(
                        "adset_name"
                    )
                ),

                "creative_id": (
                    master.get(
                        "creative_id",
                        ""
                    )
                ),

                "source_instagram_media_id": (
                    master.get(
                        "source_instagram_media_id",
                        ""
                    )
                ),

                "effective_instagram_media_id": (
                    master.get(
                        "effective_instagram_media_id",
                        ""
                    )
                ),

                "content_media_id": (
                    master.get(
                        "content_media_id",
                        ""
                    )
                ),

                "creative_source": (
                    master.get(
                        "creative_source",
                        "UNKNOWN"
                    )
                ),

                "spend": source.get(
                    "spend"
                ),

                "impressions": (
                    source.get(
                        "impressions"
                    )
                ),

                "reach_paid": (
                    source.get(
                        "reach_paid"
                    )
                ),

                "frequency": (
                    source.get(
                        "frequency"
                    )
                ),

                "clicks": source.get(
                    "clicks"
                ),

                "ctr": source.get(
                    "ctr"
                ),

                "cpc": source.get(
                    "cpc"
                ),

                "cpm": source.get(
                    "cpm"
                ),

                "paid_likes": (
                    source.get(
                        "paid_likes"
                    )
                ),

                "paid_comments": (
                    source.get(
                        "paid_comments"
                    )
                ),

                "paid_saved": (
                    source.get(
                        "paid_saved"
                    )
                ),

                "paid_shares": (
                    source.get(
                        "paid_shares"
                    )
                ),

                "paid_interactions": (
                    source.get(
                        "paid_interactions"
                    )
                ),

                "publisher_platform": (
                    source.get(
                        "publisher_platform"
                    )
                ),

                "actions_json": (
                    source.get(
                        "actions_json"
                    )
                ),

                "collected_at": (
                    collected_text
                ),
            }

            key = (
                str(
                    row.get(
                        "date",
                        ""
                    )
                ),
                ad_id,
            )

            backfill_by_key[
                key
            ] = row

            month_spend += numeric(
                source.get(
                    "spend"
                )
            )

        print(
            f" | rows={len(source_rows):,}"
            f" | spend={month_spend:,.0f}"
        )

        # Light pacing between monthly requests
        time.sleep(
            0.3
        )

    print()
    print(
        f"      fetched rows="
        f"{total_source_rows:,}"
    )

    print(
        f"      unique date+ad="
        f"{len(backfill_by_key):,}"
    )

    print(
        f"      unknown ad IDs="
        f"{len(unknown_ad_ids):,}"
    )

    # ========================================================
    # 4. ONE bulk write
    # ========================================================

    print()
    print(
        "[4/4] Bulk write ADS_DAILY"
    )

    final_rows = (
        list(
            backfill_by_key.values()
        )
        + preserved_rows
    )

    final_rows.sort(
        key=lambda row: (
            str(
                row.get(
                    "date",
                    ""
                )
            ),
            str(
                row.get(
                    "ad_id",
                    ""
                )
            ),
        )
    )

    matrix = [
        headers
    ]

    for row in final_rows:

        matrix.append(
            [
                (
                    ""
                    if row.get(
                        header
                    ) is None
                    else row.get(
                        header,
                        ""
                    )
                )
                for header
                in headers
            ]
        )

    required_rows = len(
        matrix
    )

    required_cols = len(
        headers
    )

    if (
        daily_ws.row_count
        < required_rows
        or daily_ws.col_count
        < required_cols
    ):

        daily_ws.resize(
            rows=max(
                required_rows + 100,
                daily_ws.row_count,
            ),
            cols=max(
                required_cols,
                daily_ws.col_count,
            ),
        )

    daily_ws.clear()

    daily_ws.update(
        range_name="A1",
        values=matrix,
        value_input_option="RAW",
    )

    # ========================================================
    # Verification
    # ========================================================

    total_spend = sum(
        numeric(
            row.get(
                "spend"
            )
        )
        for row in backfill_by_key.values()
    )

    min_date = min(
        (
            row.get(
                "date"
            )
            for row
            in backfill_by_key.values()
            if row.get(
                "date"
            )
        ),
        default="-",
    )

    max_date = max(
        (
            row.get(
                "date"
            )
            for row
            in backfill_by_key.values()
            if row.get(
                "date"
            )
        ),
        default="-",
    )

    elapsed = (
        now_kst()
        - started_at
    )

    print(
        f"      rows written="
        f"{len(final_rows):,}"
    )

    print(
        f"      backfill range="
        f"{min_date} ~ {max_date}"
    )

    print(
        f"      total spend="
        f"{total_spend:,.0f}"
    )

    print(
        f"      unknown ads="
        f"{len(unknown_ad_ids):,}"
    )

    print()
    print("=" * 82)
    print(
        "ADS_DAILY BACKFILL COMPLETED "
        f"| VERSION={VERSION}"
    )

    print(
        f"Elapsed: {elapsed}"
    )

    print("=" * 82)

    if unknown_ad_ids:

        print()
        print(
            "[NOTICE] Ads not found in AD_MASTER:"
        )

        for ad_id in sorted(
            unknown_ad_ids
        )[:30]:

            print(
                f"      {ad_id}"
            )

        if (
            len(unknown_ad_ids)
            > 30
        ):

            print(
                f"      ... +"
                f"{len(unknown_ad_ids) - 30:,}"
            )


if __name__ == "__main__":
    main()