from __future__ import annotations

import json


# ============================================================
# Fields
# ============================================================

ADS_ACCOUNT_FIELDS = [
    "id",
    "name",
    "account_status",
    "currency",
    "timezone_name",
]


ADS_DAILY_FIELDS = [
    "date_start",
    "date_stop",
    "spend",
    "impressions",
    "reach",
    "frequency",
    "clicks",
    "ctr",
    "cpc",
    "cpm",
]


AD_MAPPING_FIELDS = ",".join(
    [
        "id",
        "name",
        "status",
        "effective_status",
        "created_time",
        "updated_time",

        "campaign{id,name}",
        "adset{id,name}",

        (
            "creative{"
            "id,"
            "name,"
            "source_instagram_media_id,"
            "effective_instagram_media_id,"
            "instagram_permalink_url"
            "}"
        ),
    ]
)


# ============================================================
# Helpers
# ============================================================

def _act_id(
    ad_account_id: str,
) -> str:

    value = str(
        ad_account_id
    )

    if value.startswith(
        "act_"
    ):
        return value

    return (
        f"act_{value}"
    )


def _to_int(
    value,
) -> int | None:

    if value in (
        None,
        "",
    ):
        return None

    return int(
        float(value)
    )


def _to_float(
    value,
) -> float | None:

    if value in (
        None,
        "",
    ):
        return None

    return float(
        value
    )


def extract_actions(
    actions: list[dict] | None,
) -> dict[str, float]:

    output = {}

    for item in (
        actions
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
            or value in (
                None,
                "",
            )
        ):
            continue

        try:
            output[
                action_type
            ] = float(
                value
            )

        except (
            TypeError,
            ValueError,
        ):
            continue

    return output


def find_action_value(
    action_map: dict[str, float],
    candidates: list[str],
):
    for name in candidates:

        if name in action_map:
            return action_map[
                name
            ]

    return None


# ============================================================
# Existing account functions
# ============================================================

def fetch_ad_account(
    client,
    ad_account_id: str,
) -> dict:

    return client.get_ads(
        _act_id(
            ad_account_id
        ),
        params={
            "fields": ",".join(
                ADS_ACCOUNT_FIELDS
            ),
        },
    )


def fetch_ads_daily(
    client,
    ad_account_id: str,
    *,
    date_preset: str = "last_7d",
    since: str | None = None,
    until: str | None = None,
) -> list[dict]:

    params = {
        "fields": ",".join(
            ADS_DAILY_FIELDS
        ),
        "time_increment": 1,
        "limit": 500,
    }

    if (
        since
        and until
    ):

        params[
            "time_range"
        ] = json.dumps(
            {
                "since": since,
                "until": until,
            }
        )

    else:

        params[
            "date_preset"
        ] = date_preset

    rows = client.get_ads_all(
        (
            f"{_act_id(ad_account_id)}"
            "/insights"
        ),
        params=params,
    )

    result = []

    for row in rows:

        result.append(
            {
                "date_start": row.get(
                    "date_start"
                ),

                "date_stop": row.get(
                    "date_stop"
                ),

                "spend": _to_float(
                    row.get(
                        "spend"
                    )
                ),

                "impressions": _to_int(
                    row.get(
                        "impressions"
                    )
                ),

                "reach": _to_int(
                    row.get(
                        "reach"
                    )
                ),

                "frequency": _to_float(
                    row.get(
                        "frequency"
                    )
                ),

                "clicks": _to_int(
                    row.get(
                        "clicks"
                    )
                ),

                "ctr": _to_float(
                    row.get(
                        "ctr"
                    )
                ),

                "cpc": _to_float(
                    row.get(
                        "cpc"
                    )
                ),

                "cpm": _to_float(
                    row.get(
                        "cpm"
                    )
                ),
            }
        )

    return result


# ============================================================
# Ads + Creative mapping
# ============================================================

def fetch_ads_with_content_mapping(
    client,
    ad_account_id: str,
) -> list[dict]:

    rows = client.get_ads_all(
        (
            f"{_act_id(ad_account_id)}"
            "/ads"
        ),
        params={
            "fields": (
                AD_MAPPING_FIELDS
            ),
            "limit": 100,
        },
    )

    result = []

    for row in rows:

        campaign = (
            row.get(
                "campaign"
            )
            or {}
        )

        adset = (
            row.get(
                "adset"
            )
            or {}
        )

        creative = (
            row.get(
                "creative"
            )
            or {}
        )

        result.append(
            {
                "ad_id": row.get(
                    "id"
                ),

                "ad_name": row.get(
                    "name"
                ),

                "campaign_id": (
                    campaign.get(
                        "id"
                    )
                ),

                "campaign_name": (
                    campaign.get(
                        "name"
                    )
                ),

                "adset_id": (
                    adset.get(
                        "id"
                    )
                ),

                "adset_name": (
                    adset.get(
                        "name"
                    )
                ),

                "creative_id": (
                    creative.get(
                        "id"
                    )
                ),

                "creative_name": (
                    creative.get(
                        "name"
                    )
                ),

                "source_instagram_media_id": (
                    creative.get(
                        "source_instagram_media_id"
                    )
                ),

                "effective_instagram_media_id": (
                    creative.get(
                        "effective_instagram_media_id"
                    )
                ),

                "instagram_permalink_url": (
                    creative.get(
                        "instagram_permalink_url"
                    )
                ),

                "status": row.get(
                    "status"
                ),

                "effective_status": row.get(
                    "effective_status"
                ),

                "created_time": row.get(
                    "created_time"
                ),

                "updated_time": row.get(
                    "updated_time"
                ),
            }
        )

    return result


# ============================================================
# Paid aggregate for one published content
# ============================================================

def fetch_paid_content_aggregate(
    client,
    ad_account_id: str,
    ad_ids: list[str],
) -> dict | None:
    """
    Aggregate ALL matched ads before returning.

    Important:
    Reach should be aggregated by Meta rather than
    summing individual ad reach values ourselves.
    """

    clean_ids = [
        str(ad_id)
        for ad_id in ad_ids
        if ad_id
    ]

    if not clean_ids:
        return None

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
                    "value": clean_ids,
                }
            ]
        ),

        "limit": 100,
    }

    rows = client.get_ads_all(
        (
            f"{_act_id(ad_account_id)}"
            "/insights"
        ),
        params=params,
    )

    instagram_rows = [
        row
        for row in rows
        if row.get(
            "publisher_platform"
        ) == "instagram"
    ]

    if not instagram_rows:
        return None

    # publisher_platform breakdown should result
    # in one Instagram aggregate row.
    row = instagram_rows[0]

    action_map = extract_actions(
        row.get(
            "actions"
        )
    )

    return {
        "reach": _to_int(
            row.get(
                "reach"
            )
        ),

        "impressions": _to_int(
            row.get(
                "impressions"
            )
        ),

        "spend": _to_float(
            row.get(
                "spend"
            )
        ),

        "clicks": _to_int(
            row.get(
                "clicks"
            )
        ),

        "ctr": _to_float(
            row.get(
                "ctr"
            )
        ),

        "cpc": _to_float(
            row.get(
                "cpc"
            )
        ),

        "cpm": _to_float(
            row.get(
                "cpm"
            )
        ),

        "paid_likes": (
            find_action_value(
                action_map,
                [
                    (
                        "onsite_conversion."
                        "post_net_like"
                    ),
                ],
            )
        ),

        "paid_saved": (
            find_action_value(
                action_map,
                [
                    (
                        "onsite_conversion."
                        "post_net_save"
                    ),
                    (
                        "onsite_conversion."
                        "post_save"
                    ),
                ],
            )
        ),

        "paid_interactions": (
            find_action_value(
                action_map,
                [
                    "post_interaction_net",
                ],
            )
        ),

        "actions": action_map,
    }


# ============================================================
# Instagram paid daily by ad
# ============================================================

def fetch_instagram_ads_daily(
    client,
    ad_account_id: str,
    *,
    date_preset: str = "last_7d",
    since: str | None = None,
    until: str | None = None,
) -> list[dict]:

    params = {
        "fields": (
            "date_start,"
            "date_stop,"
            "campaign_id,"
            "campaign_name,"
            "adset_id,"
            "adset_name,"
            "ad_id,"
            "ad_name,"
            "spend,"
            "impressions,"
            "reach,"
            "frequency,"
            "clicks,"
            "ctr,"
            "cpc,"
            "cpm,"
            "actions"
        ),

        "level": "ad",
        "time_increment": 1,

        "breakdowns": (
            "publisher_platform"
        ),

        "limit": 500,
    }

    if (
        since
        and until
    ):

        params[
            "time_range"
        ] = json.dumps(
            {
                "since": since,
                "until": until,
            }
        )

    else:

        params[
            "date_preset"
        ] = date_preset

    rows = client.get_ads_all(
        (
            f"{_act_id(ad_account_id)}"
            "/insights"
        ),
        params=params,
    )

    result = []

    for row in rows:

        publisher_platform = (
            row.get(
                "publisher_platform"
            )
        )

        if (
            publisher_platform
            != "instagram"
        ):
            continue

        action_map = extract_actions(
            row.get(
                "actions"
            )
        )

        result.append(
            {
                "date": row.get(
                    "date_start"
                ),

                "campaign_id": row.get(
                    "campaign_id"
                ),

                "campaign_name": row.get(
                    "campaign_name"
                ),

                "adset_id": row.get(
                    "adset_id"
                ),

                "adset_name": row.get(
                    "adset_name"
                ),

                "ad_id": row.get(
                    "ad_id"
                ),

                "ad_name": row.get(
                    "ad_name"
                ),

                "spend": _to_float(
                    row.get(
                        "spend"
                    )
                ),

                "impressions": _to_int(
                    row.get(
                        "impressions"
                    )
                ),

                "reach_paid": _to_int(
                    row.get(
                        "reach"
                    )
                ),

                "frequency": _to_float(
                    row.get(
                        "frequency"
                    )
                ),

                "clicks": _to_int(
                    row.get(
                        "clicks"
                    )
                ),

                "ctr": _to_float(
                    row.get(
                        "ctr"
                    )
                ),

                "cpc": _to_float(
                    row.get(
                        "cpc"
                    )
                ),

                "cpm": _to_float(
                    row.get(
                        "cpm"
                    )
                ),

                "paid_likes": (
                    find_action_value(
                        action_map,
                        [
                            (
                                "onsite_conversion."
                                "post_net_like"
                            ),
                        ],
                    )
                ),

                "paid_saved": (
                    find_action_value(
                        action_map,
                        [
                            (
                                "onsite_conversion."
                                "post_net_save"
                            ),
                            (
                                "onsite_conversion."
                                "post_save"
                            ),
                        ],
                    )
                ),

                "paid_interactions": (
                    find_action_value(
                        action_map,
                        [
                            "post_interaction_net",
                        ],
                    )
                ),

                # We intentionally do not guess these
                # from ambiguous Marketing API actions.
                "paid_comments": None,
                "paid_shares": None,

                "publisher_platform": (
                    publisher_platform
                ),

                "actions_json": (
                    json.dumps(
                        action_map,
                        ensure_ascii=False,
                        separators=(
                            ",",
                            ":",
                        ),
                    )
                ),
            }
        )

    return result