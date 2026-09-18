from __future__ import annotations

from datetime import (
    datetime,
    timedelta,
)
from zoneinfo import ZoneInfo

from gspread.utils import (
    rowcol_to_a1,
)

from config.settings import (
    META_API_VERSION,
    INSTAGRAM_ACCOUNT_ID,
    META_AD_ACCOUNT_ID,
    META_IG_ACCESS_TOKEN,
    META_ADS_ACCESS_TOKEN,
    GOOGLE_SPREADSHEET_ID,
)

from src.meta_client import (
    MetaClient,
    MetaAPIError,
)

from src.fetch_account import (
    fetch_account,
)

from src.fetch_audience import (
    fetch_audience_demographics,
)

from src.fetch_media import (
    fetch_media,
)

from src.fetch_media_insights import (
    fetch_media_insights,
)

from src.fetch_stories import (
    fetch_stories,
    fetch_story_insights,
)

from src.fetch_ads import (
    fetch_ads_with_content_mapping,
    fetch_paid_content_aggregate,
    fetch_instagram_ads_daily,
)

from src.sheets_repository import (
    SheetsRepository,
)


# ============================================================
# Version
# ============================================================

VERSION = "0.6.4"

KST = ZoneInfo(
    "Asia/Seoul"
)


# ============================================================
# Policy
# ============================================================

LIFETIME_UPDATE_MAX_DAYS = 30

SNAPSHOT_DAYS = {
    0,
    1,
    3,
    7,
    14,
    30,
}


# ============================================================
# Clients
# ============================================================

meta = MetaClient(
    api_version=META_API_VERSION,
    ig_access_token=META_IG_ACCESS_TOKEN,
    ads_access_token=META_ADS_ACCESS_TOKEN,
)

sheets = SheetsRepository(
    GOOGLE_SPREADSHEET_ID
)


# ============================================================
# Helpers
# ============================================================

def section(
    title: str,
) -> None:

    print()
    print("=" * 78)
    print(title)
    print("=" * 78)


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
    value: str,
) -> datetime:

    parsed = datetime.strptime(
        value,
        "%Y-%m-%dT%H:%M:%S%z",
    )

    return parsed.astimezone(
        KST
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
        number = float(
            value
        )

    except (
        TypeError,
        ValueError,
    ):
        return None

    if number.is_integer():
        return int(number)

    return number


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


# ============================================================
# CONTENT_MASTER reader
# ============================================================

def load_content_master():

    worksheet = (
        sheets.spreadsheet.worksheet(
            "CONTENT_MASTER"
        )
    )

    values = worksheet.get_all_values()

    if not values:

        raise RuntimeError(
            "CONTENT_MASTER is empty."
        )

    headers = values[0]

    rows = []
    by_id = {}
    by_permalink = {}

    for raw_row in values[1:]:

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

        media_id = str(
            row.get(
                "media_id",
                ""
            )
        ).strip()

        if not media_id:
            continue

        rows.append(
            row
        )

        by_id[
            media_id
        ] = row

        permalink = normalize_url(
            row.get(
                "permalink"
            )
        )

        if permalink:

            by_permalink[
                permalink
            ] = row

    return (
        worksheet,
        headers,
        rows,
        by_id,
        by_permalink,
    )


# ============================================================
# QA
# ============================================================

def build_metric_qa_status(
    *,
    has_paid: bool,
    views_organic,
    reach_organic,
    interactions_organic,
    views_paid,
    reach_paid,
    likes_paid,
    comments_paid,
    saved_paid,
    shares_paid,
    interactions_paid,
) -> str:

    issues = []

    if numeric(
        views_organic
    ) is None:

        issues.append(
            "MISSING_VIEWS_ORGANIC"
        )

    if numeric(
        reach_organic
    ) is None:

        issues.append(
            "MISSING_REACH_ORGANIC"
        )

    if numeric(
        interactions_organic
    ) is None:

        issues.append(
            "MISSING_INTERACTIONS_ORGANIC"
        )

    if has_paid:

        if numeric(
            reach_paid
        ) is None:

            issues.append(
                "PAID_REACH_MISSING"
            )

        if numeric(
            interactions_paid
        ) is None:

            issues.append(
                "PAID_INTERACTIONS_MISSING"
            )

        negative_checks = {
            "VIEWS_PAID": views_paid,
            "LIKES_PAID": likes_paid,
            "COMMENTS_PAID": comments_paid,
            "SAVED_PAID": saved_paid,
            "SHARES_PAID": shares_paid,
        }

        for (
            metric_name,
            value,
        ) in negative_checks.items():

            value = numeric(value)

            if (
                value is not None
                and value < 0
            ):

                issues.append(
                    f"NEGATIVE_{metric_name}"
                )

    if issues:

        return (
            "CHECK:"
            + ",".join(
                sorted(
                    set(issues)
                )
            )
        )

    return "OK"


# ============================================================
# 1. ACCOUNT_HISTORY
# ============================================================

def collect_account(
    collected_at: datetime,
) -> dict:

    section(
        "[1/8] ACCOUNT_HISTORY"
    )

    account = fetch_account(
        meta,
        INSTAGRAM_ACCOUNT_ID,
    )

    row = {
        "snapshot_date": (
            collected_at
            .date()
            .isoformat()
        ),

        "followers_count": (
            account.get(
                "followers_count"
            )
        ),

        "follows_count": (
            account.get(
                "follows_count"
            )
        ),

        "media_count": (
            account.get(
                "media_count"
            )
        ),

        "collected_at": (
            format_datetime(
                collected_at
            )
        ),
    }

    result = sheets.upsert_rows(
        "ACCOUNT_HISTORY",
        [row],
        key_fields=[
            "snapshot_date",
        ],
    )

    followers = (
        row.get(
            "followers_count"
        )
    )

    print(
        f"[OK] followers="
        f"{followers:,}"
        f" | inserted="
        f"{result['inserted']}"
        f" | updated="
        f"{result['updated']}"
    )

    return account


# ============================================================
# 2. AUDIENCE_HISTORY
# ============================================================

def collect_audience(
    collected_at: datetime,
    followers_count,
) -> None:

    section(
        "[2/8] AUDIENCE_HISTORY"
    )

    source_rows = (
        fetch_audience_demographics(
            meta,
            INSTAGRAM_ACCOUNT_ID,
        )
    )

    if not source_rows:

        print(
            "[WARN] No audience rows returned."
        )
        return

    # --------------------------------------------------------
    # 각 dimension별 counted total
    # --------------------------------------------------------

    totals = {}

    for row in source_rows:

        dimension = (
            row.get(
                "dimension"
            )
        )

        value = (
            numeric(
                row.get(
                    "value"
                )
            )
            or 0
        )

        totals[
            dimension
        ] = (
            totals.get(
                dimension,
                0,
            )
            + value
        )

    snapshot_date = (
        collected_at
        .date()
        .isoformat()
    )

    collected_text = (
        format_datetime(
            collected_at
        )
    )

    output = []

    for row in source_rows:

        dimension = (
            row.get(
                "dimension"
            )
        )

        segment = (
            row.get(
                "segment"
            )
        )

        value = (
            numeric(
                row.get(
                    "value"
                )
            )
            or 0
        )

        dimension_total = (
            totals.get(
                dimension,
                0,
            )
        )

        percentage = None

        if dimension_total > 0:

            percentage = round(
                (
                    value
                    / dimension_total
                )
                * 100,
                2,
            )

        output.append(
            {
                "snapshot_date": (
                    snapshot_date
                ),

                "dimension": (
                    dimension
                ),

                "segment": (
                    segment
                ),

                "value": (
                    value
                ),

                "percentage": (
                    percentage
                ),

                "dimension_total": (
                    dimension_total
                ),

                "followers_count": (
                    followers_count
                ),

                "collected_at": (
                    collected_text
                ),
            }
        )

    result = sheets.upsert_rows(
        "AUDIENCE_HISTORY",
        output,
        key_fields=[
            "snapshot_date",
            "dimension",
            "segment",
        ],
    )

    print(
        f"[OK] rows="
        f"{len(output):,}"
        f" | inserted="
        f"{result['inserted']}"
        f" | updated="
        f"{result['updated']}"
    )

    for dimension in [
        "gender",
        "age",
    ]:

        print(
            f"      {dimension} "
            f"counted total="
            f"{totals.get(dimension, 0):,}"
        )

    # 25-44 핵심 비중
    age_total = (
        totals.get(
            "age",
            0,
        )
    )

    if age_total > 0:

        age_25_44 = sum(
            numeric(
                row.get(
                    "value"
                )
            )
            or 0
            for row
            in source_rows
            if (
                row.get(
                    "dimension"
                )
                == "age"
                and row.get(
                    "segment"
                )
                in {
                    "25-34",
                    "35-44",
                }
            )
        )

        share = (
            age_25_44
            / age_total
            * 100
        )

        print(
            f"      25-44 share="
            f"{share:.2f}%"
        )


# ============================================================
# 3. CONTENT_MASTER
# ============================================================

def collect_new_content(
    media: list[dict],
    collected_at: datetime,
) -> None:

    section(
        "[3/8] CONTENT_MASTER"
    )

    (
        _,
        _,
        _,
        existing_by_id,
        _,
    ) = load_content_master()

    collected_text = (
        format_datetime(
            collected_at
        )
    )

    rows = []

    for item in media:

        media_id = str(
            item.get(
                "id"
            )
            or ""
        )

        if (
            not media_id
            or media_id
            in existing_by_id
        ):

            continue

        timestamp = item.get(
            "timestamp"
        )

        posted_at = (
            parse_meta_datetime(
                timestamp
            )
            if timestamp
            else None
        )

        rows.append(
            {
                "media_id": media_id,

                "posted_at": (
                    format_datetime(
                        posted_at
                    )
                    if posted_at
                    else ""
                ),

                "media_type": (
                    item.get(
                        "media_type",
                        ""
                    )
                ),

                "media_product_type": (
                    item.get(
                        "media_product_type",
                        ""
                    )
                ),

                "permalink": (
                    item.get(
                        "permalink",
                        ""
                    )
                ),

                "media_url": (
                    item.get(
                        "media_url",
                        ""
                    )
                ),

                "thumbnail_url": (
                    item.get(
                        "thumbnail_url",
                        ""
                    )
                ),

                "caption": (
                    item.get(
                        "caption",
                        ""
                    )
                ),

                "ai_title": "",
                "content_category": "",
                "content_subcategory": "",
                "content_theme": "",
                "product_name": "",
                "campaign_name": "",
                "creative_format": "",

                "has_paid": "FALSE",

                "manual_title": "",
                "manual_category": "",

                "created_at": (
                    collected_text
                ),

                "updated_at": (
                    collected_text
                ),

                "classification_status": (
                    "PENDING"
                ),
            }
        )

    if not rows:

        print(
            "[OK] new contents=0"
        )
        return

    result = sheets.upsert_rows(
        "CONTENT_MASTER",
        rows,
        key_fields=[
            "media_id",
        ],
        update_existing=False,
    )

    print(
        f"[OK] new contents="
        f"{len(rows):,}"
        f" | inserted="
        f"{result['inserted']}"
    )


# ============================================================
# 4. AD_MASTER
# ============================================================

def refresh_ad_master(
    collected_at: datetime,
):

    section(
        "[4/8] AD_MASTER + CONTENT MAPPING"
    )

    (
        content_ws,
        content_headers,
        content_rows,
        content_by_id,
        content_by_permalink,
    ) = load_content_master()

    ads = (
        fetch_ads_with_content_mapping(
            meta,
            META_AD_ACCOUNT_ID,
        )
    )

    ad_ws = (
        sheets.spreadsheet.worksheet(
            "AD_MASTER"
        )
    )

    existing_values = (
        ad_ws.get_all_values()
    )

    existing_headers = (
        existing_values[0]
        if existing_values
        else []
    )

    existing_by_ad_id = {}

    if existing_values:

        for raw_row in (
            existing_values[1:]
        ):

            padded = (
                raw_row
                + [""] * (
                    len(
                        existing_headers
                    )
                    - len(raw_row)
                )
            )

            row = dict(
                zip(
                    existing_headers,
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

                existing_by_ad_id[
                    ad_id
                ] = row

    collected_text = (
        format_datetime(
            collected_at
        )
    )

    output = []

    source_count = 0
    permalink_count = 0
    effective_count = 0
    unmatched_count = 0

    for ad in ads:

        ad_id = str(
            ad.get(
                "ad_id"
            )
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

        content_media_id = ""
        match_method = "UNMATCHED"

        if (
            source_id
            and source_id
            in content_by_id
        ):

            content_media_id = (
                source_id
            )

            match_method = (
                "SOURCE_MEDIA_ID"
            )

            source_count += 1

        elif (
            permalink
            and permalink
            in content_by_permalink
        ):

            content_media_id = str(
                content_by_permalink[
                    permalink
                ].get(
                    "media_id",
                    ""
                )
            )

            match_method = (
                "PERMALINK"
            )

            permalink_count += 1

        elif (
            effective_id
            and effective_id
            in content_by_id
        ):

            content_media_id = (
                effective_id
            )

            match_method = (
                "EFFECTIVE_MEDIA_ID"
            )

            effective_count += 1

        else:

            unmatched_count += 1

        creative_source = (
            "PUBLISHED_CONTENT"
            if content_media_id
            else "AD_ONLY"
        )

        existing = (
            existing_by_ad_id.get(
                ad_id,
                {}
            )
        )

        output.append(
            {
                "ad_id": ad_id,
                "ad_name": ad.get(
                    "ad_name"
                ),

                "campaign_id": ad.get(
                    "campaign_id"
                ),
                "campaign_name": ad.get(
                    "campaign_name"
                ),

                "adset_id": ad.get(
                    "adset_id"
                ),
                "adset_name": ad.get(
                    "adset_name"
                ),

                "creative_id": ad.get(
                    "creative_id"
                ),
                "creative_name": ad.get(
                    "creative_name"
                ),

                "source_instagram_media_id": (
                    source_id
                ),

                "effective_instagram_media_id": (
                    effective_id
                ),

                "instagram_permalink_url": (
                    ad.get(
                        "instagram_permalink_url"
                    )
                ),

                "content_media_id": (
                    content_media_id
                ),

                "creative_source": (
                    creative_source
                ),

                "match_method": (
                    match_method
                ),

                "status": ad.get(
                    "status"
                ),

                "effective_status": (
                    ad.get(
                        "effective_status"
                    )
                ),

                "created_time": (
                    ad.get(
                        "created_time"
                    )
                ),

                "updated_time": (
                    ad.get(
                        "updated_time"
                    )
                ),

                "first_seen_at": (
                    existing.get(
                        "first_seen_at"
                    )
                    or collected_text
                ),

                "last_seen_at": (
                    collected_text
                ),
            }
        )

    result = sheets.upsert_rows(
        "AD_MASTER",
        output,
        key_fields=[
            "ad_id",
        ],
    )

    # --------------------------------------------------------
    # 전체 AD_MASTER 재조회
    # --------------------------------------------------------

    ad_values = (
        ad_ws.get_all_values()
    )

    if not ad_values:

        raise RuntimeError(
            "AD_MASTER became empty."
        )

    ad_headers = (
        ad_values[0]
    )

    content_to_ad_ids = {}
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

        content_media_id = str(
            row.get(
                "content_media_id",
                ""
            )
        ).strip()

        if ad_id:

            ad_lookup[
                ad_id
            ] = row

        if (
            ad_id
            and content_media_id
        ):

            content_to_ad_ids.setdefault(
                content_media_id,
                [],
            ).append(
                ad_id
            )

    # --------------------------------------------------------
    # CONTENT_MASTER.has_paid
    # --------------------------------------------------------

    if (
        "has_paid"
        not in content_headers
    ):

        raise RuntimeError(
            "CONTENT_MASTER.has_paid missing."
        )

    has_paid_col = (
        content_headers.index(
            "has_paid"
        )
        + 1
    )

    paid_content_ids = set(
        content_to_ad_ids.keys()
    )

    paid_values = []

    for row in content_rows:

        media_id = str(
            row.get(
                "media_id",
                ""
            )
        ).strip()

        paid_values.append(
            [
                (
                    "TRUE"
                    if media_id
                    in paid_content_ids
                    else "FALSE"
                )
            ]
        )

    if paid_values:

        start_cell = (
            rowcol_to_a1(
                2,
                has_paid_col,
            )
        )

        end_cell = (
            rowcol_to_a1(
                len(paid_values)
                + 1,
                has_paid_col,
            )
        )

        content_ws.update(
            range_name=(
                f"{start_cell}:"
                f"{end_cell}"
            ),
            values=paid_values,
            value_input_option="RAW",
        )

    print(
        f"[OK] fetched ads="
        f"{len(ads):,}"
        f" | inserted="
        f"{result['inserted']}"
        f" | updated="
        f"{result['updated']}"
    )

    print(
        "[MAP]"
        f" source={source_count:,}"
        f" | permalink={permalink_count:,}"
        f" | effective={effective_count:,}"
        f" | unmatched={unmatched_count:,}"
    )

    print(
        f"[OK] known paid contents="
        f"{len(paid_content_ids):,}"
    )

    return (
        content_to_ad_ids,
        ad_lookup,
    )


# ============================================================
# 3-Layer metrics
# ============================================================

def build_three_layer_metrics(
    item: dict,
    content_to_ad_ids: dict[
        str,
        list[str],
    ],
) -> dict:

    media_id = str(
        item.get(
            "id"
        )
        or ""
    )

    insight = (
        fetch_media_insights(
            meta,
            item,
        )
    )

    views_organic = numeric(
        insight.get(
            "views"
        )
    )

    reach_organic = numeric(
        insight.get(
            "reach"
        )
    )

    likes_organic = numeric(
        insight.get(
            "likes"
        )
    )

    comments_organic = numeric(
        insight.get(
            "comments"
        )
    )

    saved_organic = numeric(
        insight.get(
            "saved"
        )
    )

    shares_organic = numeric(
        insight.get(
            "shares"
        )
    )

    interactions_organic = numeric(
        insight.get(
            "total_interactions"
        )
    )

    ad_ids = (
        content_to_ad_ids.get(
            media_id,
            [],
        )
    )

    has_paid = bool(
        ad_ids
    )

    if not has_paid:

        views_total = (
            views_organic
        )
        views_paid = 0

        reach_total_gross = (
            reach_organic
        )
        reach_paid = 0

        likes_total = (
            likes_organic
        )
        likes_paid = 0

        comments_total = (
            comments_organic
        )
        comments_paid = 0

        saved_total = (
            saved_organic
        )
        saved_paid = 0

        shares_total = (
            shares_organic
        )
        shares_paid = 0

        interactions_total = (
            interactions_organic
        )
        interactions_paid = 0

    else:

        paid = (
            fetch_paid_content_aggregate(
                meta,
                META_AD_ACCOUNT_ID,
                ad_ids,
            )
        )

        views_total = numeric(
            insight.get(
                "total_views"
            )
        )

        views_paid = subtract(
            views_total,
            views_organic,
        )

        reach_paid = numeric(
            (
                paid
                or {}
            ).get(
                "reach"
            )
        )

        reach_total_gross = add(
            reach_organic,
            reach_paid,
        )

        likes_total = numeric(
            insight.get(
                "total_like_count"
            )
        )

        likes_paid = subtract(
            likes_total,
            likes_organic,
        )

        comments_total = numeric(
            insight.get(
                "total_comments_count"
            )
        )

        comments_paid = subtract(
            comments_total,
            comments_organic,
        )

        saved_paid = numeric(
            (
                paid
                or {}
            ).get(
                "paid_saved"
            )
        )

        saved_total = add(
            saved_organic,
            saved_paid,
        )

        shares_total = numeric(
            insight.get(
                "shares_count"
            )
        )

        shares_paid = subtract(
            shares_total,
            shares_organic,
        )

        interactions_paid = numeric(
            (
                paid
                or {}
            ).get(
                "paid_interactions"
            )
        )

        interactions_total = add(
            interactions_organic,
            interactions_paid,
        )

    qa_status = (
        build_metric_qa_status(
            has_paid=has_paid,

            views_organic=(
                views_organic
            ),

            reach_organic=(
                reach_organic
            ),

            interactions_organic=(
                interactions_organic
            ),

            views_paid=(
                views_paid
            ),

            reach_paid=(
                reach_paid
            ),

            likes_paid=(
                likes_paid
            ),

            comments_paid=(
                comments_paid
            ),

            saved_paid=(
                saved_paid
            ),

            shares_paid=(
                shares_paid
            ),

            interactions_paid=(
                interactions_paid
            ),
        )
    )

    return {
        "has_paid": (
            has_paid
        ),

        "views_total": (
            views_total
        ),
        "views_organic": (
            views_organic
        ),
        "views_paid": (
            views_paid
        ),

        "reach_total_gross": (
            reach_total_gross
        ),
        "reach_organic": (
            reach_organic
        ),
        "reach_paid": (
            reach_paid
        ),

        "likes_total": (
            likes_total
        ),
        "likes_organic": (
            likes_organic
        ),
        "likes_paid": (
            likes_paid
        ),

        "comments_total": (
            comments_total
        ),
        "comments_organic": (
            comments_organic
        ),
        "comments_paid": (
            comments_paid
        ),

        "saved_total": (
            saved_total
        ),
        "saved_organic": (
            saved_organic
        ),
        "saved_paid": (
            saved_paid
        ),

        "shares_total": (
            shares_total
        ),
        "shares_organic": (
            shares_organic
        ),
        "shares_paid": (
            shares_paid
        ),

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
    }


# ============================================================
# Metrics cache
# ============================================================

def get_metrics_cached(
    item: dict,
    content_to_ad_ids: dict[
        str,
        list[str],
    ],
    cache: dict[
        str,
        dict,
    ],
) -> dict:

    media_id = str(
        item.get(
            "id"
        )
        or ""
    )

    if (
        media_id
        in cache
    ):

        return cache[
            media_id
        ]

    metrics = (
        build_three_layer_metrics(
            item,
            content_to_ad_ids,
        )
    )

    cache[
        media_id
    ] = metrics

    return metrics


# ============================================================
# 5. CONTENT_LIFETIME
# ============================================================

def collect_recent_lifetime(
    media: list[dict],
    collected_at: datetime,
    content_to_ad_ids: dict[
        str,
        list[str],
    ],
    metrics_cache: dict[
        str,
        dict,
    ],
) -> None:

    section(
        "[5/8] CONTENT_LIFETIME D+0~D+30"
    )

    today = (
        collected_at.date()
    )

    rows = []

    for item in media:

        media_id = str(
            item.get(
                "id"
            )
            or ""
        )

        timestamp = (
            item.get(
                "timestamp"
            )
        )

        if (
            not media_id
            or not timestamp
        ):
            continue

        posted_at = (
            parse_meta_datetime(
                timestamp
            )
        )

        age_days = (
            today
            - posted_at.date()
        ).days

        if not (
            0
            <= age_days
            <= LIFETIME_UPDATE_MAX_DAYS
        ):
            continue

        metrics = (
            get_metrics_cached(
                item,
                content_to_ad_ids,
                metrics_cache,
            )
        )

        row = {
            "media_id": (
                media_id
            ),

            "posted_at": (
                format_datetime(
                    posted_at
                )
            ),

            "media_type": (
                item.get(
                    "media_type"
                )
            ),

            "media_product_type": (
                item.get(
                    "media_product_type"
                )
            ),

            "has_paid": (
                "TRUE"
                if metrics[
                    "has_paid"
                ]
                else "FALSE"
            ),

            "updated_at": (
                format_datetime(
                    collected_at
                )
            ),
        }

        for (
            key,
            value,
        ) in metrics.items():

            if key == "has_paid":
                continue

            row[
                key
            ] = value

        rows.append(
            row
        )

        print(
            f"[LIFETIME] "
            f"D+{age_days}"
            f" | {media_id}"
            f" | paid="
            f"{'Y' if metrics['has_paid'] else 'N'}"
            f" | QA="
            f"{metrics['metric_qa_status']}"
        )

    result = sheets.upsert_rows(
        "CONTENT_LIFETIME",
        rows,
        key_fields=[
            "media_id",
        ],
        preserve_existing_on_none=True,
    )

    print(
        f"[OK] targets="
        f"{len(rows):,}"
        f" | inserted="
        f"{result['inserted']}"
        f" | updated="
        f"{result['updated']}"
    )


# ============================================================
# 6. MEDIA_SNAPSHOT
# ============================================================

def collect_media_snapshots(
    media: list[dict],
    collected_at: datetime,
    content_to_ad_ids: dict[
        str,
        list[str],
    ],
    metrics_cache: dict[
        str,
        dict,
    ],
) -> None:

    section(
        "[6/8] MEDIA_SNAPSHOT"
    )

    today = (
        collected_at.date()
    )

    rows = []

    for item in media:

        media_id = str(
            item.get(
                "id"
            )
            or ""
        )

        timestamp = (
            item.get(
                "timestamp"
            )
        )

        if (
            not media_id
            or not timestamp
        ):
            continue

        posted_at = (
            parse_meta_datetime(
                timestamp
            )
        )

        age_days = (
            today
            - posted_at.date()
        ).days

        if (
            age_days
            not in SNAPSHOT_DAYS
        ):
            continue

        metrics = (
            get_metrics_cached(
                item,
                content_to_ad_ids,
                metrics_cache,
            )
        )

        row = {
            "snapshot_date": (
                today.isoformat()
            ),

            "media_id": (
                media_id
            ),

            "posted_at": (
                format_datetime(
                    posted_at
                )
            ),

            "media_type": (
                item.get(
                    "media_type"
                )
            ),

            "media_product_type": (
                item.get(
                    "media_product_type"
                )
            ),

            "collected_at": (
                format_datetime(
                    collected_at
                )
            ),
        }

        for (
            key,
            value,
        ) in metrics.items():

            if key == "has_paid":
                continue

            row[
                key
            ] = value

        rows.append(
            row
        )

        print(
            f"[SNAPSHOT] "
            f"D+{age_days}"
            f" | {media_id}"
            f" | QA="
            f"{metrics['metric_qa_status']}"
        )

    result = sheets.upsert_rows(
        "MEDIA_SNAPSHOT",
        rows,
        key_fields=[
            "snapshot_date",
            "media_id",
        ],
        preserve_existing_on_none=True,
    )

    print(
        f"[OK] targets="
        f"{len(rows):,}"
        f" | inserted="
        f"{result['inserted']}"
        f" | updated="
        f"{result['updated']}"
    )


# ============================================================
# 7. ADS_DAILY
# ============================================================

def collect_ads_daily(
    collected_at: datetime,
    ad_lookup: dict,
) -> None:

    section(
        "[7/8] ADS_DAILY D-1"
    )

    target_date = (
        collected_at.date()
        - timedelta(
            days=1
        )
    )

    target_text = (
        target_date.isoformat()
    )

    source_rows = (
        fetch_instagram_ads_daily(
            meta,
            META_AD_ACCOUNT_ID,
            since=target_text,
            until=target_text,
        )
    )

    collected_text = (
        format_datetime(
            collected_at
        )
    )

    rows = []

    for source in source_rows:

        ad_id = str(
            source.get(
                "ad_id"
            )
            or ""
        )

        master = (
            ad_lookup.get(
                ad_id,
                {}
            )
        )

        rows.append(
            {
                "date": (
                    source.get(
                        "date"
                    )
                ),

                "ad_id": (
                    ad_id
                ),

                "ad_name": (
                    source.get(
                        "ad_name"
                    )
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

                "spend": (
                    source.get(
                        "spend"
                    )
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

                "clicks": (
                    source.get(
                        "clicks"
                    )
                ),

                "ctr": (
                    source.get(
                        "ctr"
                    )
                ),

                "cpc": (
                    source.get(
                        "cpc"
                    )
                ),

                "cpm": (
                    source.get(
                        "cpm"
                    )
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
        )

    result = sheets.upsert_rows(
        "ADS_DAILY",
        rows,
        key_fields=[
            "date",
            "ad_id",
        ],
        preserve_existing_on_none=True,
    )

    total_spend = sum(
        numeric(
            row.get(
                "spend"
            )
        )
        or 0
        for row in rows
    )

    print(
        f"[OK] date="
        f"{target_text}"
        f" | ads="
        f"{len(rows):,}"
        f" | spend="
        f"{total_spend:,.0f}"
        f" | inserted="
        f"{result['inserted']}"
        f" | updated="
        f"{result['updated']}"
    )


# ============================================================
# 8. STORY_HISTORY
# ============================================================

def collect_stories(
    collected_at: datetime,
) -> None:

    section(
        "[8/8] STORY_HISTORY"
    )

    stories = fetch_stories(
        meta,
        INSTAGRAM_ACCOUNT_ID,
    )

    rows = []

    for story in stories:

        insight = (
            fetch_story_insights(
                meta,
                story,
            )
        )

        timestamp = (
            story.get(
                "timestamp"
            )
        )

        posted_at = (
            parse_meta_datetime(
                timestamp
            )
            if timestamp
            else None
        )

        story_id = str(story.get("id") or "").strip()
        media_type = str(story.get("media_type") or "").strip().upper()
        media_url = str(story.get("media_url") or "").strip()

        # Story representative still image
        # IMAGE: the media itself is already an image.
        # VIDEO: fetch Meta thumbnail_url once while the Story is active.
        thumbnail_url = str(story.get("thumbnail_url") or "").strip()

        if media_type == "IMAGE" and not thumbnail_url:
            thumbnail_url = media_url

        elif media_type == "VIDEO" and story_id and not thumbnail_url:
            try:
                detail = meta.get_instagram(
                    story_id,
                    params={
                        "fields": "thumbnail_url",
                    },
                )
                thumbnail_url = str(
                    detail.get("thumbnail_url") or ""
                ).strip()
            except MetaAPIError as exc:
                print(
                    f"[WARN] Story thumbnail fetch failed "
                    f"| story_id={story_id} | {exc}"
                )

        rows.append(
            {
                "story_id": (
                    story.get(
                        "id"
                    )
                ),

                "posted_at": (
                    format_datetime(
                        posted_at
                    )
                    if posted_at
                    else ""
                ),

                "media_type": (
                    story.get(
                        "media_type"
                    )
                ),

                "media_url": (
                    story.get(
                        "media_url"
                    )
                ),

                "thumbnail_url": (
                    thumbnail_url
                ),

                "permalink": (
                    story.get(
                        "permalink"
                    )
                ),

                "views": (
                    insight.get(
                        "views"
                    )
                ),

                "reach": (
                    insight.get(
                        "reach"
                    )
                ),

                "shares": (
                    insight.get(
                        "shares"
                    )
                ),

                "replies": (
                    insight.get(
                        "replies"
                    )
                ),

                "total_interactions": (
                    insight.get(
                        "total_interactions"
                    )
                ),

                "follows": (
                    insight.get(
                        "follows"
                    )
                ),

                "profile_visits": (
                    insight.get(
                        "profile_visits"
                    )
                ),

                "link_clicks": (
                    insight.get(
                        "link_clicks"
                    )
                ),

                "tap_forward": (
                    insight.get(
                        "tap_forward"
                    )
                ),

                "tap_back": (
                    insight.get(
                        "tap_back"
                    )
                ),

                "tap_exit": (
                    insight.get(
                        "tap_exit"
                    )
                ),

                "swipe_forward": (
                    insight.get(
                        "swipe_forward"
                    )
                ),

                "insight_status": (
                    insight.get(
                        "insight_status"
                    )
                ),

                "first_collected_at": (
                    format_datetime(
                        collected_at
                    )
                ),

                "last_collected_at": (
                    format_datetime(
                        collected_at
                    )
                ),
            }
        )

        print(
            f"[STORY] "
            f"{story.get('id')}"
            f" | "
            f"{insight.get('insight_status')}"
        )

    result = sheets.upsert_rows(
        "STORY_HISTORY",
        rows,
        key_fields=[
            "story_id",
        ],
        preserve_existing_on_none=True,
        preserve_existing_fields={
            "first_collected_at",
        },
    )

    print(
        f"[OK] active stories="
        f"{len(rows):,}"
        f" | inserted="
        f"{result['inserted']}"
        f" | updated="
        f"{result['updated']}"
    )


# ============================================================
# Main
# ============================================================

def main() -> None:

    collected_at = (
        now_kst()
    )

    print("=" * 78)
    print(
        "Greating Instagram "
        f"Daily Collector v{VERSION}"
    )

    print(
        f"Collected at: "
        f"{format_datetime(collected_at)} KST"
    )

    print("=" * 78)

    # ========================================================
    # 1. Account
    # ========================================================

    account = collect_account(
        collected_at
    )

    # ========================================================
    # 2. Audience
    # ========================================================

    collect_audience(
        collected_at,
        account.get(
            "followers_count"
        ),
    )

    # ========================================================
    # Recent media
    # ========================================================

    media = fetch_media(
        meta,
        INSTAGRAM_ACCOUNT_ID,
        max_items=200,
    )

    print()
    print(
        f"[INFO] Recent media loaded="
        f"{len(media):,}"
    )

    # ========================================================
    # 3. New content
    # ========================================================

    collect_new_content(
        media,
        collected_at,
    )

    # ========================================================
    # 4. Ads mapping
    # ========================================================

    (
        content_to_ad_ids,
        ad_lookup,
    ) = refresh_ad_master(
        collected_at
    )

    # ========================================================
    # Shared metric cache
    # ========================================================

    metrics_cache = {}

    # ========================================================
    # 5. Lifetime
    # ========================================================

    collect_recent_lifetime(
        media,
        collected_at,
        content_to_ad_ids,
        metrics_cache,
    )

    # ========================================================
    # 6. Snapshot
    # ========================================================

    collect_media_snapshots(
        media,
        collected_at,
        content_to_ad_ids,
        metrics_cache,
    )

    print()
    print(
        f"[INFO] Metric API cache="
        f"{len(metrics_cache):,} contents"
    )

    # ========================================================
    # 7. Ads daily
    # ========================================================

    collect_ads_daily(
        collected_at,
        ad_lookup,
    )

    # ========================================================
    # 8. Stories
    # ========================================================

    collect_stories(
        collected_at
    )

    print()
    print("=" * 78)
    print(
        "DAILY COLLECTION COMPLETED "
        f"| VERSION={VERSION}"
    )
    print("=" * 78)


if __name__ == "__main__":

    try:

        main()

    except MetaAPIError as exc:

        print()
        print("=" * 78)
        print(
            "[META API ERROR]"
        )
        print(exc)
        print("=" * 78)

        raise