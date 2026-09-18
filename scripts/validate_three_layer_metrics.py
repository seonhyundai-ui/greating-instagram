from __future__ import annotations

import json
from pprint import pprint

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

from src.sheets_client import (
    get_gspread_client,
)


VERSION = "0.4.0-validation"


# ============================================================
# Validation target
# ============================================================

# 캡처의 "노오븐, 노밀가루, 노슈가" 콘텐츠 광고
TEST_AD_ID = "120249306264160599"


# Business Suite 화면에서 직접 확인한 값
BUSINESS_SUITE_REFERENCE = {
    "reach_total": 4924,
    "reach_organic": 1014,
    "reach_paid": 3941,

    "views_organic": 2091,
    "views_paid": 3799,
}


# ============================================================
# Helpers
# ============================================================

def act_id(
    ad_account_id: str,
) -> str:

    value = str(ad_account_id)

    if value.startswith("act_"):
        return value

    return f"act_{value}"


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


def metric_value(
    payload: dict,
    metric_name: str,
):
    """
    Supports both formats:

    values: [{"value": 123}]

    and

    total_value: {"value": 123}
    """

    for item in payload.get(
        "data",
        []
    ):

        if item.get("name") != metric_name:
            continue

        total_value = item.get(
            "total_value"
        )

        if isinstance(
            total_value,
            dict
        ):
            return total_value.get(
                "value"
            )

        values = item.get(
            "values",
            []
        )

        if values:
            return values[0].get(
                "value"
            )

    return None


def safe_media_insight(
    meta: MetaClient,
    media_id: str,
    metric: str,
):
    """
    Test one metric at a time so an unsupported
    metric does not break the entire validation.
    """

    try:

        payload = meta.get_instagram(
            f"{media_id}/insights",
            params={
                "metric": metric,
            },
        )

        return {
            "supported": True,
            "value": metric_value(
                payload,
                metric,
            ),
            "error": None,
        }

    except MetaAPIError as exc:

        return {
            "supported": False,
            "value": None,
            "error": str(exc),
        }


def safe_media_field(
    meta: MetaClient,
    media_id: str,
    field: str,
):
    try:

        payload = meta.get_instagram(
            media_id,
            params={
                "fields": (
                    f"id,{field}"
                ),
            },
        )

        return {
            "supported": True,
            "value": payload.get(
                field
            ),
            "error": None,
        }

    except MetaAPIError as exc:

        return {
            "supported": False,
            "value": None,
            "error": str(exc),
        }


def print_metric(
    name: str,
    result: dict,
) -> None:

    if result.get(
        "supported"
    ):

        print(
            f"      {name:<24}"
            f" = {result.get('value')}"
        )

    else:

        print(
            f"      {name:<24}"
            " = UNSUPPORTED"
        )


def extract_action_map(
    row: dict,
) -> dict[str, float]:

    output = {}

    for item in (
        row.get("actions")
        or []
    ):

        action_type = item.get(
            "action_type"
        )

        value = item.get(
            "value"
        )

        if (
            not action_type
            or value in (None, "")
        ):
            continue

        try:
            output[
                action_type
            ] = float(value)

        except (
            TypeError,
            ValueError,
        ):
            pass

    return output


# ============================================================
# CONTENT_MASTER
# ============================================================

def load_content_master() -> tuple[
    dict[str, dict],
    dict[str, dict],
]:

    google = get_gspread_client()

    spreadsheet = google.open_by_key(
        GOOGLE_SPREADSHEET_ID
    )

    worksheet = spreadsheet.worksheet(
        "CONTENT_MASTER"
    )

    rows = worksheet.get_all_records()

    by_id = {}
    by_permalink = {}

    for row in rows:

        media_id = str(
            row.get(
                "media_id",
                ""
            )
        ).strip()

        if media_id:

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
        by_id,
        by_permalink,
    )


# ============================================================
# Ad -> original Instagram post
# ============================================================

def resolve_original_media(
    meta: MetaClient,
    content_by_id: dict[str, dict],
    content_by_permalink: dict[str, dict],
) -> tuple[str, dict, dict]:

    ad = meta.get_ads(
        TEST_AD_ID,
        params={
            "fields": (
                "id,"
                "name,"
                "creative{id}"
            ),
        },
    )

    creative_id = (
        ad.get(
            "creative",
            {}
        )
        .get("id")
    )

    if not creative_id:
        raise RuntimeError(
            "Creative ID not found."
        )

    creative = meta.get_ads(
        creative_id,
        params={
            "fields": (
                "id,"
                "name,"
                "source_instagram_media_id,"
                "effective_instagram_media_id,"
                "instagram_permalink_url,"
                "effective_object_story_id"
            ),
        },
    )

    source_id = str(
        creative.get(
            "source_instagram_media_id"
        )
        or ""
    )

    effective_id = str(
        creative.get(
            "effective_instagram_media_id"
        )
        or ""
    )

    permalink = normalize_url(
        creative.get(
            "instagram_permalink_url"
        )
    )

    # --------------------------------------------------------
    # Priority 1: source_instagram_media_id
    # --------------------------------------------------------

    if (
        source_id
        and source_id in content_by_id
    ):

        return (
            source_id,
            content_by_id[source_id],
            {
                "method": (
                    "SOURCE_INSTAGRAM_MEDIA_ID"
                ),
                "ad": ad,
                "creative": creative,
            },
        )

    # --------------------------------------------------------
    # Priority 2: permalink
    # --------------------------------------------------------

    if (
        permalink
        and permalink
        in content_by_permalink
    ):

        content = (
            content_by_permalink[
                permalink
            ]
        )

        return (
            str(
                content.get(
                    "media_id"
                )
            ),
            content,
            {
                "method": "PERMALINK",
                "ad": ad,
                "creative": creative,
            },
        )

    # --------------------------------------------------------
    # Priority 3: effective ID
    # --------------------------------------------------------

    if (
        effective_id
        and effective_id in content_by_id
    ):

        return (
            effective_id,
            content_by_id[
                effective_id
            ],
            {
                "method": (
                    "EFFECTIVE_INSTAGRAM_MEDIA_ID"
                ),
                "ad": ad,
                "creative": creative,
            },
        )

    raise RuntimeError(
        "Could not match the test ad "
        "to CONTENT_MASTER."
    )


# ============================================================
# Find all ads using the original post
# ============================================================

def find_ads_for_media(
    meta: MetaClient,
    media_id: str,
) -> list[dict]:

    rows = meta.get_ads_all(
        (
            f"{act_id(META_AD_ACCOUNT_ID)}"
            "/ads"
        ),
        params={
            "fields": (
                "id,"
                "name,"
                "creative{"
                "id,"
                "source_instagram_media_id,"
                "effective_instagram_media_id"
                "}"
            ),
            "limit": 100,
        },
    )

    matches = []

    for row in rows:

        creative = (
            row.get(
                "creative"
            )
            or {}
        )

        source_id = str(
            creative.get(
                "source_instagram_media_id"
            )
            or ""
        )

        effective_id = str(
            creative.get(
                "effective_instagram_media_id"
            )
            or ""
        )

        # source ID is the primary match.
        if source_id == media_id:

            matches.append(
                {
                    "ad_id": row.get("id"),
                    "ad_name": row.get("name"),
                    "match_method": (
                        "SOURCE_MEDIA_ID"
                    ),
                }
            )

            continue

        # only diagnostic fallback
        if effective_id == media_id:

            matches.append(
                {
                    "ad_id": row.get("id"),
                    "ad_name": row.get("name"),
                    "match_method": (
                        "EFFECTIVE_MEDIA_ID"
                    ),
                }
            )

    return matches


# ============================================================
# Paid aggregate
# ============================================================

def fetch_paid_aggregate(
    meta: MetaClient,
    ad_ids: list[str],
) -> list[dict]:

    if not ad_ids:
        return []

    params = {
        "fields": (
            "reach,"
            "impressions,"
            "spend,"
            "clicks,"
            "ctr,"
            "cpc,"
            "cpm,"
            "actions"
        ),

        # We want Meta to aggregate before returning.
        # This is important for unique reach.
        "level": "account",

        "date_preset": "maximum",

        "breakdowns": (
            "publisher_platform"
        ),

        "filtering": json.dumps(
            [
                {
                    "field": "ad.id",
                    "operator": "IN",
                    "value": ad_ids,
                }
            ]
        ),

        "limit": 100,
    }

    rows = meta.get_ads_all(
        (
            f"{act_id(META_AD_ACCOUNT_ID)}"
            "/insights"
        ),
        params=params,
    )

    return [
        row
        for row in rows
        if row.get(
            "publisher_platform"
        ) == "instagram"
    ]


# ============================================================
# Main
# ============================================================

def main() -> None:

    print("=" * 78)
    print(
        "Greating Instagram "
        f"3-Layer Metric Validation v{VERSION}"
    )
    print("=" * 78)

    meta = MetaClient(
        api_version=META_API_VERSION,
        ig_access_token=META_IG_ACCESS_TOKEN,
        ads_access_token=META_ADS_ACCESS_TOKEN,
    )

    # ========================================================
    # 1. Master
    # ========================================================

    print()
    print(
        "[1/7] Load CONTENT_MASTER"
    )

    (
        content_by_id,
        content_by_permalink,
    ) = load_content_master()

    print(
        f"      contents="
        f"{len(content_by_id):,}"
    )

    # ========================================================
    # 2. Resolve test content
    # ========================================================

    print()
    print(
        "[2/7] Resolve Ad -> Published Content"
    )

    (
        media_id,
        content,
        resolution,
    ) = resolve_original_media(
        meta,
        content_by_id,
        content_by_permalink,
    )

    print(
        f"      test ad       = "
        f"{TEST_AD_ID}"
    )

    print(
        f"      content media = "
        f"{media_id}"
    )

    print(
        f"      match method  = "
        f"{resolution['method']}"
    )

    print(
        f"      posted_at     = "
        f"{content.get('posted_at')}"
    )

    print(
        f"      permalink     = "
        f"{content.get('permalink')}"
    )

    print()
    print(
        "      Creative IDs"
    )

    pprint(
        resolution[
            "creative"
        ]
    )

    # ========================================================
    # 3. Media node + boost ads
    # ========================================================

    print()
    print(
        "[3/7] Instagram Media aggregated fields"
    )

    node_fields = [
        "total_views_count",
        "total_like_count",
        "total_comments_count",
        "saved_count",
        "shares_count",
        "boost_ads_list",
    ]

    node_results = {}

    for field in node_fields:

        result = safe_media_field(
            meta,
            media_id,
            field,
        )

        node_results[
            field
        ] = result

        print_metric(
            field,
            result,
        )

    # ========================================================
    # 4. Organic media insights
    # ========================================================

    print()
    print(
        "[4/7] Organic / native media insights"
    )

    organic_metrics = [
        "reach",
        "views",
        "likes",
        "comments",
        "saved",
        "shares",
        "total_interactions",
    ]

    organic = {}

    for metric in organic_metrics:

        result = safe_media_insight(
            meta,
            media_id,
            metric,
        )

        organic[
            metric
        ] = result

        print_metric(
            metric,
            result,
        )

    # ========================================================
    # 5. Aggregated TOTAL candidates
    # ========================================================

    print()
    print(
        "[5/7] TOTAL metric candidates"
    )

    total_metrics = [
        "total_views",
        "total_likes",
        "total_comments",

        # We explicitly test this.
        # It may not be supported.
        "total_reach",
    ]

    totals = {}

    for metric in total_metrics:

        result = safe_media_insight(
            meta,
            media_id,
            metric,
        )

        totals[
            metric
        ] = result

        print_metric(
            metric,
            result,
        )

    # ========================================================
    # 6. Paid ads connected to this content
    # ========================================================

    print()
    print(
        "[6/7] Paid performance"
    )

    matched_ads = find_ads_for_media(
        meta,
        media_id,
    )

    print(
        f"      connected ads = "
        f"{len(matched_ads)}"
    )

    for row in matched_ads:

        print(
            "      "
            f"{row['ad_id']} "
            f"| {row['match_method']} "
            f"| {row['ad_name']}"
        )

    ad_ids = [
        str(
            row["ad_id"]
        )
        for row in matched_ads
        if row.get(
            "ad_id"
        )
    ]

    paid_rows = fetch_paid_aggregate(
        meta,
        ad_ids,
    )

    print()
    print(
        f"      paid aggregate rows = "
        f"{len(paid_rows)}"
    )

    paid_reach = None
    paid_impressions = None
    paid_spend = None
    paid_actions = {}

    if len(paid_rows) == 1:

        paid = paid_rows[0]

        paid_reach = (
            int(
                float(
                    paid.get(
                        "reach",
                        0,
                    )
                )
            )
        )

        paid_impressions = (
            int(
                float(
                    paid.get(
                        "impressions",
                        0,
                    )
                )
            )
        )

        paid_spend = (
            float(
                paid.get(
                    "spend",
                    0,
                )
            )
        )

        paid_actions = (
            extract_action_map(
                paid
            )
        )

        print(
            f"      reach        = "
            f"{paid_reach:,}"
        )

        print(
            f"      impressions  = "
            f"{paid_impressions:,}"
        )

        print(
            f"      spend        = "
            f"{paid_spend:,.0f}"
        )

        print()
        print(
            "      ---- actions ----"
        )

        for (
            action_type,
            value,
        ) in sorted(
            paid_actions.items()
        ):

            print(
                f"      {action_type:<40}"
                f" {value}"
            )

    else:

        print(
            "      [WARN] Expected one "
            "aggregated Instagram row."
        )

        pprint(
            paid_rows
        )

    # ========================================================
    # 7. Validation matrix
    # ========================================================

    print()
    print("=" * 78)
    print(
        "[7/7] THREE-LAYER VALIDATION"
    )
    print("=" * 78)

    organic_reach = (
        organic.get(
            "reach",
            {}
        ).get(
            "value"
        )
    )

    organic_views = (
        organic.get(
            "views",
            {}
        ).get(
            "value"
        )
    )

    total_views = (
        totals.get(
            "total_views",
            {}
        ).get(
            "value"
        )
    )

    total_reach = (
        totals.get(
            "total_reach",
            {}
        ).get(
            "value"
        )
    )

    print()
    print(
        "REACH"
    )

    print(
        f"      TOTAL API       = "
        f"{total_reach}"
    )

    print(
        f"      ORGANIC API     = "
        f"{organic_reach}"
    )

    print(
        f"      PAID API        = "
        f"{paid_reach}"
    )

    print(
        f"      Business Suite  = "
        f"{BUSINESS_SUITE_REFERENCE['reach_total']:,}"
        " | "
        f"{BUSINESS_SUITE_REFERENCE['reach_organic']:,}"
        " | "
        f"{BUSINESS_SUITE_REFERENCE['reach_paid']:,}"
    )

    print()
    print(
        "VIEWS"
    )

    print(
        f"      TOTAL API       = "
        f"{total_views}"
    )

    print(
        f"      ORGANIC API     = "
        f"{organic_views}"
    )

    print(
        f"      PAID impressions"
        f" = {paid_impressions}"
    )

    print(
        f"      Business Suite "
        f"Organic views = "
        f"{BUSINESS_SUITE_REFERENCE['views_organic']:,}"
    )

    print(
        f"      Business Suite "
        f"Paid views    = "
        f"{BUSINESS_SUITE_REFERENCE['views_paid']:,}"
    )

    print()
    print(
        "CHECKS"
    )

    print(
        "      Organic Reach match : "
        f"{organic_reach == BUSINESS_SUITE_REFERENCE['reach_organic']}"
    )

    print(
        "      Paid Reach match    : "
        f"{paid_reach == BUSINESS_SUITE_REFERENCE['reach_paid']}"
    )

    print(
        "      Paid Views candidate"
        " : "
        f"{paid_impressions == BUSINESS_SUITE_REFERENCE['views_paid']}"
    )

    if (
        organic_reach is not None
        and paid_reach is not None
    ):

        naive_reach_sum = (
            int(organic_reach)
            + int(paid_reach)
        )

        overlap = (
            naive_reach_sum
            - BUSINESS_SUITE_REFERENCE[
                "reach_total"
            ]
        )

        print()
        print(
            f"      Organic + Paid Reach = "
            f"{naive_reach_sum:,}"
        )

        print(
            f"      Actual Total Reach   = "
            f"{BUSINESS_SUITE_REFERENCE['reach_total']:,}"
        )

        print(
            f"      Duplicate audience   = "
            f"{overlap:,}"
        )

    print()
    print("=" * 78)
    print(
        "VALIDATION COMPLETED"
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