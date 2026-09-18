from __future__ import annotations

from src.meta_client import MetaAPIError


BASE_ORGANIC_METRICS = [
    "views",
    "reach",
    "likes",
    "comments",
    "saved",
    "shares",
    "total_interactions",
]

REELS_EXTRA_METRICS = [
    "ig_reels_avg_watch_time",
    "ig_reels_video_view_total_time",
]

TOTAL_INSIGHT_METRICS = [
    "total_views",
]

TOTAL_NODE_FIELDS = [
    "total_like_count",
    "total_comments_count",
    "shares_count",
    "boost_ads_list",
]


def _extract_metric_value(
    payload: dict,
    metric_name: str,
):
    for item in payload.get("data", []):
        if item.get("name") != metric_name:
            continue

        total_value = item.get("total_value")

        if isinstance(total_value, dict):
            return total_value.get("value")

        values = item.get("values", [])

        if values:
            return values[0].get("value")

    return None


def _fetch_metrics_safe(
    client,
    media_id: str,
    metrics: list[str],
) -> dict:

    output = {
        metric: None
        for metric in metrics
    }

    if not metrics:
        return output

    try:
        payload = client.get_instagram(
            f"{media_id}/insights",
            params={
                "metric": ",".join(metrics),
            },
        )

        for metric in metrics:
            output[metric] = (
                _extract_metric_value(
                    payload,
                    metric,
                )
            )

        return output

    except MetaAPIError:
        pass

    # 한 metric 때문에 전체가 실패하면 개별 재시도
    for metric in metrics:

        try:
            payload = client.get_instagram(
                f"{media_id}/insights",
                params={
                    "metric": metric,
                },
            )

            output[metric] = (
                _extract_metric_value(
                    payload,
                    metric,
                )
            )

        except MetaAPIError:
            output[metric] = None

    return output


def _fetch_node_fields_safe(
    client,
    media_id: str,
) -> dict:

    output = {
        field: None
        for field in TOTAL_NODE_FIELDS
    }

    try:
        payload = client.get_instagram(
            media_id,
            params={
                "fields": (
                    "id,"
                    + ",".join(
                        TOTAL_NODE_FIELDS
                    )
                ),
            },
        )

        for field in TOTAL_NODE_FIELDS:
            output[field] = (
                payload.get(field)
            )

    except MetaAPIError:
        pass

    return output


def fetch_media_insights(
    client,
    media: dict,
) -> dict:

    media_id = str(
        media.get("id", "")
    )

    if not media_id:
        raise ValueError(
            "media.id is required."
        )

    media_product_type = (
        media.get("media_product_type")
        or ""
    )

    organic_metrics = list(
        BASE_ORGANIC_METRICS
    )

    if (
        media_product_type.upper()
        == "REELS"
    ):
        organic_metrics.extend(
            REELS_EXTRA_METRICS
        )

    # Organic + total_views를 한 번에 시도
    insight_metrics = (
        organic_metrics
        + TOTAL_INSIGHT_METRICS
    )

    insights = _fetch_metrics_safe(
        client,
        media_id,
        insight_metrics,
    )

    # Node total fields는 한 API 호출
    node = _fetch_node_fields_safe(
        client,
        media_id,
    )

    return {
        "media_id": media_id,

        "media_type": media.get(
            "media_type"
        ),

        "media_product_type": (
            media_product_type
        ),

        # Organic
        "views": insights.get("views"),
        "reach": insights.get("reach"),
        "likes": insights.get("likes"),
        "comments": insights.get(
            "comments"
        ),
        "saved": insights.get("saved"),
        "shares": insights.get("shares"),

        "total_interactions": (
            insights.get(
                "total_interactions"
            )
        ),

        "ig_reels_avg_watch_time": (
            insights.get(
                "ig_reels_avg_watch_time"
            )
        ),

        "ig_reels_video_view_total_time": (
            insights.get(
                "ig_reels_video_view_total_time"
            )
        ),

        # Total
        "total_views": insights.get(
            "total_views"
        ),

        "total_like_count": node.get(
            "total_like_count"
        ),

        "total_comments_count": node.get(
            "total_comments_count"
        ),

        "shares_count": node.get(
            "shares_count"
        ),

        "boost_ads_list": node.get(
            "boost_ads_list"
        ),
    }