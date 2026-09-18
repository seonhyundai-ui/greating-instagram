from __future__ import annotations

import time

from datetime import datetime
from zoneinfo import ZoneInfo

from gspread.utils import rowcol_to_a1

from config.settings import (
    META_API_VERSION,
    META_AD_ACCOUNT_ID,
    META_IG_ACCESS_TOKEN,
    META_ADS_ACCESS_TOKEN,
    GOOGLE_SPREADSHEET_ID,
)

from src.meta_client import (
    MetaClient,
    MetaAPIError,
)

from src.fetch_media_insights import (
    fetch_media_insights,
)

from src.fetch_ads import (
    fetch_ads_with_content_mapping,
    fetch_paid_content_aggregate,
)

from src.sheets_client import (
    get_gspread_client,
)


VERSION = "0.4.1"

KST = ZoneInfo(
    "Asia/Seoul"
)


HEADERS = [
    "media_id",
    "posted_at",
    "media_type",
    "media_product_type",
    "has_paid",

    "views_total",
    "views_organic",
    "views_paid",

    "reach_total_gross",
    "reach_organic",
    "reach_paid",

    "likes_total",
    "likes_organic",
    "likes_paid",

    "comments_total",
    "comments_organic",
    "comments_paid",

    "saved_total",
    "saved_organic",
    "saved_paid",

    "shares_total",
    "shares_organic",
    "shares_paid",

    "interactions_total",
    "interactions_organic",
    "interactions_paid",

    "avg_watch_time_ms_organic",
    "total_watch_time_ms_organic",

    "metric_qa_status",
    "updated_at",
]


def now_kst() -> datetime:
    return datetime.now(KST)


def format_datetime(
    value: datetime,
) -> str:

    return value.strftime(
        "%Y-%m-%d %H:%M:%S"
    )


def normalize_url(
    value: str | None,
) -> str:

    if not value:
        return ""

    return (
        str(value)
        .split("?")[0]
        .rstrip("/")
        .strip()
    )


def numeric(value):

    if value in (
        None,
        "",
    ):
        return None

    try:
        result = float(value)

    except (
        TypeError,
        ValueError,
    ):
        return None

    if result.is_integer():
        return int(result)

    return result


def subtract(
    total,
    organic,
):

    total = numeric(total)
    organic = numeric(organic)

    if (
        total is None
        or organic is None
    ):
        return None

    return total - organic


def add(
    first,
    second,
):

    first = numeric(first)
    second = numeric(second)

    if (
        first is None
        or second is None
    ):
        return None

    return first + second


def build_qa(
    *,
    likes_organic,
    comments_organic,
    saved_organic,
    shares_organic,
    interactions_organic,

    likes_paid,
    comments_paid,
    saved_paid,
    shares_paid,
    interactions_paid,

    views_total,
    views_organic,
):

    issues = []

    organic_parts = [
        numeric(likes_organic),
        numeric(comments_organic),
        numeric(saved_organic),
        numeric(shares_organic),
    ]

    if (
        all(
            x is not None
            for x in organic_parts
        )
        and numeric(
            interactions_organic
        ) is not None
    ):

        if (
            sum(organic_parts)
            != numeric(
                interactions_organic
            )
        ):
            issues.append(
                "ORGANIC_INTERACTION_MISMATCH"
            )

    paid_parts = [
        numeric(likes_paid),
        numeric(comments_paid),
        numeric(saved_paid),
        numeric(shares_paid),
    ]

    if (
        all(
            x is not None
            for x in paid_parts
        )
        and numeric(
            interactions_paid
        ) is not None
    ):

        if (
            sum(paid_parts)
            != numeric(
                interactions_paid
            )
        ):
            issues.append(
                "PAID_INTERACTION_MISMATCH"
            )

    paid_views = subtract(
        views_total,
        views_organic,
    )

    if (
        paid_views is not None
        and paid_views < 0
    ):
        issues.append(
            "NEGATIVE_PAID_VIEWS"
        )

    if issues:
        return (
            "CHECK:"
            + ",".join(issues)
        )

    return "OK"


def main() -> None:

    started_at = now_kst()
    updated_text = format_datetime(
        started_at
    )

    print("=" * 78)
    print(
        "Greating Instagram "
        f"CONTENT_LIFETIME Backfill v{VERSION}"
    )
    print(
        f"Started at: {updated_text} KST"
    )
    print("=" * 78)

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
    # 1. CONTENT_MASTER
    # ========================================================

    print()
    print(
        "[1/5] Load CONTENT_MASTER"
    )

    content_ws = spreadsheet.worksheet(
        "CONTENT_MASTER"
    )

    content_values = (
        content_ws.get_all_values()
    )

    if not content_values:
        raise RuntimeError(
            "CONTENT_MASTER is empty."
        )

    content_headers = (
        content_values[0]
    )

    contents = []

    content_by_id = {}
    content_by_permalink = {}

    for raw_row in content_values[1:]:

        padded = (
            raw_row
            + [""] * (
                len(content_headers)
                - len(raw_row)
            )
        )

        row = dict(
            zip(
                content_headers,
                padded,
            )
        )

        media_id = str(
            row.get(
                "media_id",
                ""
            )
        ).strip()

        if not media_id:
            continue

        contents.append(row)

        content_by_id[
            media_id
        ] = row

        permalink = normalize_url(
            row.get("permalink")
        )

        if permalink:
            content_by_permalink[
                permalink
            ] = row

    print(
        f"      contents="
        f"{len(contents):,}"
    )

    # ========================================================
    # 2. Ads -> content mapping
    # ========================================================

    print()
    print(
        "[2/5] Build Ads -> Content mapping"
    )

    ads = fetch_ads_with_content_mapping(
        meta,
        META_AD_ACCOUNT_ID,
    )

    content_to_ad_ids = {}

    source_match = 0
    permalink_match = 0
    effective_match = 0
    unmatched = 0

    for ad in ads:

        ad_id = str(
            ad.get("ad_id")
            or ""
        )

        source_id = str(
            ad.get(
                "source_instagram_media_id"
            )
            or ""
        )

        effective_id = str(
            ad.get(
                "effective_instagram_media_id"
            )
            or ""
        )

        permalink = normalize_url(
            ad.get(
                "instagram_permalink_url"
            )
        )

        content_media_id = None

        if (
            source_id
            and source_id in content_by_id
        ):

            content_media_id = (
                source_id
            )

            source_match += 1

        elif (
            permalink
            and permalink
            in content_by_permalink
        ):

            content_media_id = str(
                content_by_permalink[
                    permalink
                ].get(
                    "media_id"
                )
            )

            permalink_match += 1

        elif (
            effective_id
            and effective_id
            in content_by_id
        ):

            content_media_id = (
                effective_id
            )

            effective_match += 1

        else:
            unmatched += 1

        if (
            content_media_id
            and ad_id
        ):

            content_to_ad_ids.setdefault(
                content_media_id,
                [],
            ).append(
                ad_id
            )

    print(
        f"      ads={len(ads):,}"
    )

    print(
        f"      source={source_match:,}"
        f" | permalink={permalink_match:,}"
        f" | effective={effective_match:,}"
        f" | unmatched={unmatched:,}"
    )

    print(
        f"      paid contents="
        f"{len(content_to_ad_ids):,}"
    )

    # ========================================================
    # 3. Update CONTENT_MASTER.has_paid
    # ========================================================

    print()
    print(
        "[3/5] Update CONTENT_MASTER.has_paid"
    )

    try:
        has_paid_col = (
            content_headers.index(
                "has_paid"
            )
            + 1
        )

    except ValueError as exc:
        raise RuntimeError(
            "CONTENT_MASTER has no has_paid column."
        ) from exc

    paid_ids = set(
        content_to_ad_ids.keys()
    )

    has_paid_values = []

    for raw_row in content_values[1:]:

        padded = (
            raw_row
            + [""] * (
                len(content_headers)
                - len(raw_row)
            )
        )

        row = dict(
            zip(
                content_headers,
                padded,
            )
        )

        media_id = str(
            row.get(
                "media_id",
                ""
            )
        )

        has_paid_values.append(
            [
                (
                    "TRUE"
                    if media_id in paid_ids
                    else "FALSE"
                )
            ]
        )

    start_cell = rowcol_to_a1(
        2,
        has_paid_col,
    )

    end_cell = rowcol_to_a1(
        len(has_paid_values) + 1,
        has_paid_col,
    )

    content_ws.update(
        range_name=(
            f"{start_cell}:{end_cell}"
        ),
        values=has_paid_values,
        value_input_option="RAW",
    )

    print(
        f"      paid TRUE="
        f"{len(paid_ids):,}"
    )

    # ========================================================
    # 4. Backfill
    # ========================================================

    print()
    print(
        "[4/5] Backfill lifetime insights"
    )

    output = []

    total_count = len(contents)

    error_count = 0
    qa_check_count = 0
    paid_count = 0

    for index, content in enumerate(
        contents,
        start=1,
    ):

        media_id = str(
            content.get(
                "media_id"
            )
        )

        media = {
            "id": media_id,

            "media_type": content.get(
                "media_type"
            ),

            "media_product_type": (
                content.get(
                    "media_product_type"
                )
            ),
        }

        try:

            insight = (
                fetch_media_insights(
                    meta,
                    media,
                )
            )

            views_organic = numeric(
                insight.get("views")
            )

            reach_organic = numeric(
                insight.get("reach")
            )

            likes_organic = numeric(
                insight.get("likes")
            )

            comments_organic = numeric(
                insight.get("comments")
            )

            saved_organic = numeric(
                insight.get("saved")
            )

            shares_organic = numeric(
                insight.get("shares")
            )

            interactions_organic = numeric(
                insight.get(
                    "total_interactions"
                )
            )

            has_paid = (
                media_id
                in content_to_ad_ids
            )

            # ================================================
            # Paid
            # ================================================

            paid = None

            if has_paid:

                paid_count += 1

                paid = (
                    fetch_paid_content_aggregate(
                        meta,
                        META_AD_ACCOUNT_ID,
                        content_to_ad_ids[
                            media_id
                        ],
                    )
                )

            if has_paid:

                reach_paid = numeric(
                    (
                        paid
                        or {}
                    ).get("reach")
                )

                saved_paid = numeric(
                    (
                        paid
                        or {}
                    ).get(
                        "paid_saved"
                    )
                )

                interactions_paid = numeric(
                    (
                        paid
                        or {}
                    ).get(
                        "paid_interactions"
                    )
                )

            else:

                reach_paid = 0
                saved_paid = 0
                interactions_paid = 0

            # ================================================
            # Views
            # ================================================

            views_total = numeric(
                insight.get(
                    "total_views"
                )
            )

            if (
                not has_paid
                and views_total is None
            ):
                views_total = (
                    views_organic
                )

            views_paid = subtract(
                views_total,
                views_organic,
            )

            if (
                not has_paid
                and views_paid is None
            ):
                views_paid = 0

            # ================================================
            # Reach
            # ================================================

            reach_total_gross = add(
                reach_organic,
                reach_paid,
            )

            # ================================================
            # Likes
            # ================================================

            likes_total = numeric(
                insight.get(
                    "total_like_count"
                )
            )

            if (
                not has_paid
                and likes_total is None
            ):
                likes_total = likes_organic

            likes_paid = subtract(
                likes_total,
                likes_organic,
            )

            if (
                not has_paid
                and likes_paid is None
            ):
                likes_paid = 0

            # ================================================
            # Comments
            # ================================================

            comments_total = numeric(
                insight.get(
                    "total_comments_count"
                )
            )

            if (
                not has_paid
                and comments_total is None
            ):
                comments_total = (
                    comments_organic
                )

            comments_paid = subtract(
                comments_total,
                comments_organic,
            )

            if (
                not has_paid
                and comments_paid is None
            ):
                comments_paid = 0

            # ================================================
            # Shares
            # ================================================

            shares_total = numeric(
                insight.get(
                    "shares_count"
                )
            )

            if (
                not has_paid
                and shares_total is None
            ):
                shares_total = shares_organic

            shares_paid = subtract(
                shares_total,
                shares_organic,
            )

            if (
                not has_paid
                and shares_paid is None
            ):
                shares_paid = 0

            # ================================================
            # Saved
            # ================================================

            if has_paid:

                saved_total = add(
                    saved_organic,
                    saved_paid,
                )

            else:

                saved_total = (
                    saved_organic
                )

            # ================================================
            # Interactions
            # ================================================

            if has_paid:

                interactions_total = add(
                    interactions_organic,
                    interactions_paid,
                )

            else:

                interactions_total = (
                    interactions_organic
                )

            # ================================================
            # QA
            # ================================================

            qa_status = build_qa(
                likes_organic=likes_organic,
                comments_organic=comments_organic,
                saved_organic=saved_organic,
                shares_organic=shares_organic,
                interactions_organic=(
                    interactions_organic
                ),

                likes_paid=likes_paid,
                comments_paid=comments_paid,
                saved_paid=saved_paid,
                shares_paid=shares_paid,
                interactions_paid=(
                    interactions_paid
                ),

                views_total=views_total,
                views_organic=views_organic,
            )

            if qa_status != "OK":
                qa_check_count += 1

            row = {
                "media_id": media_id,

                "posted_at": content.get(
                    "posted_at"
                ),

                "media_type": content.get(
                    "media_type"
                ),

                "media_product_type": (
                    content.get(
                        "media_product_type"
                    )
                ),

                "has_paid": (
                    "TRUE"
                    if has_paid
                    else "FALSE"
                ),

                "views_total": views_total,
                "views_organic": views_organic,
                "views_paid": views_paid,

                "reach_total_gross": (
                    reach_total_gross
                ),
                "reach_organic": (
                    reach_organic
                ),
                "reach_paid": reach_paid,

                "likes_total": likes_total,
                "likes_organic": (
                    likes_organic
                ),
                "likes_paid": likes_paid,

                "comments_total": (
                    comments_total
                ),
                "comments_organic": (
                    comments_organic
                ),
                "comments_paid": (
                    comments_paid
                ),

                "saved_total": saved_total,
                "saved_organic": (
                    saved_organic
                ),
                "saved_paid": saved_paid,

                "shares_total": shares_total,
                "shares_organic": (
                    shares_organic
                ),
                "shares_paid": shares_paid,

                "interactions_total": (
                    interactions_total
                ),
                "interactions_organic": (
                    interactions_organic
                ),
                "interactions_paid": (
                    interactions_paid
                ),

                "avg_watch_time_ms_organic": (
                    insight.get(
                        "ig_reels_avg_watch_time"
                    )
                ),

                "total_watch_time_ms_organic": (
                    insight.get(
                        "ig_reels_video_view_total_time"
                    )
                ),

                "metric_qa_status": (
                    qa_status
                ),

                "updated_at": (
                    updated_text
                ),
            }

            output.append(row)

        except Exception as exc:

            error_count += 1

            print(
                f"\n[ERROR] "
                f"media_id={media_id}"
                f" | {exc}"
            )

            output.append(
                {
                    "media_id": media_id,
                    "posted_at": content.get(
                        "posted_at"
                    ),
                    "media_type": content.get(
                        "media_type"
                    ),
                    "media_product_type": (
                        content.get(
                            "media_product_type"
                        )
                    ),
                    "has_paid": (
                        "TRUE"
                        if media_id
                        in paid_ids
                        else "FALSE"
                    ),
                    "metric_qa_status": (
                        "ERROR"
                    ),
                    "updated_at": (
                        updated_text
                    ),
                }
            )

        # ------------------------------------
        # Progress
        # ------------------------------------

        if (
            index == 1
            or index % 25 == 0
            or index == total_count
        ):

            print(
                f"      "
                f"{index:,}/{total_count:,}"
                f" | paid={paid_count:,}"
                f" | QA_CHECK={qa_check_count:,}"
                f" | errors={error_count:,}",
                flush=True,
            )

        # Meta를 너무 세게 두드리지 않음
        time.sleep(0.10)

    # ========================================================
    # 5. Bulk write
    # ========================================================

    print()
    print(
        "[5/5] Write CONTENT_LIFETIME"
    )

    existing_sheet_names = {
        ws.title
        for ws
        in spreadsheet.worksheets()
    }

    if (
        "CONTENT_LIFETIME"
        not in existing_sheet_names
    ):

        lifetime_ws = (
            spreadsheet.add_worksheet(
                title="CONTENT_LIFETIME",
                rows=max(
                    len(output) + 200,
                    2000,
                ),
                cols=len(HEADERS),
            )
        )

        print(
            "      [CREATE] CONTENT_LIFETIME"
        )

    else:

        lifetime_ws = (
            spreadsheet.worksheet(
                "CONTENT_LIFETIME"
            )
        )

    # 최신 게시순
    output.sort(
        key=lambda x: str(
            x.get(
                "posted_at",
                ""
            )
        ),
        reverse=True,
    )

    matrix = [
        HEADERS
    ]

    for row in output:

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
                for header in HEADERS
            ]
        )

    lifetime_ws.resize(
        rows=max(
            len(matrix) + 100,
            2000,
        ),
        cols=len(HEADERS),
    )

    lifetime_ws.clear()

    lifetime_ws.update(
        range_name="A1",
        values=matrix,
        value_input_option="RAW",
    )

    print(
        f"      rows={len(output):,}"
    )

    print(
        f"      paid contents={paid_count:,}"
    )

    print(
        f"      QA_CHECK={qa_check_count:,}"
    )

    print(
        f"      errors={error_count:,}"
    )

    elapsed = (
        now_kst()
        - started_at
    )

    print()
    print("=" * 78)
    print(
        "CONTENT_LIFETIME BACKFILL COMPLETED "
        f"| VERSION={VERSION}"
    )
    print(
        f"Elapsed: {elapsed}"
    )
    print("=" * 78)


if __name__ == "__main__":

    try:
        main()

    except MetaAPIError as exc:

        print()
        print("=" * 78)
        print("[META API ERROR]")
        print(exc)
        print("=" * 78)

        raise