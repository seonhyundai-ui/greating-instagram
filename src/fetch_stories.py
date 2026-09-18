from __future__ import annotations

from src.meta_client import (
    MetaClient,
    MetaAPIError,
)


# ============================================
# Story fields
# ============================================

STORY_FIELDS = [
    "id",
    "caption",
    "media_type",
    "media_url",
    "permalink",
    "timestamp",
]


# ============================================
# Story insight metrics
# ============================================

STORY_BASE_METRICS = [
    "views",
    "reach",
    "shares",
    "replies",
    "total_interactions",
    "follows",
    "profile_visits",
]


# ============================================
# Error helpers
# ============================================

def _is_low_volume_error(
    exc: MetaAPIError,
) -> bool:
    """
    Detect Meta Story insight suppression caused
    by an insufficient number of viewers.
    """

    code = getattr(
        exc,
        "code",
        None,
    )

    message = str(exc)

    return (
        code in (10, "10")
        and "Not enough viewers" in message
    )


# ============================================
# Metric response parser
# ============================================

def _metric_value_map(
    payload: dict,
) -> dict:
    """
    Convert Meta Insights response into:

    {
        "views": 100,
        "reach": 80,
        ...
    }
    """

    result = {}

    for row in payload.get("data", []):

        name = row.get("name")

        value = None

        # ------------------------------------
        # Standard lifetime metric response
        # ------------------------------------

        values = row.get(
            "values",
            [],
        )

        if values:
            value = values[0].get(
                "value"
            )

        # ------------------------------------
        # total_value response
        # ------------------------------------

        if value is None:

            total_value = row.get(
                "total_value"
            )

            if isinstance(
                total_value,
                dict,
            ):
                value = total_value.get(
                    "value"
                )

        result[name] = value

    return result


# ============================================
# Fetch active Stories
# ============================================

def fetch_stories(
    client: MetaClient,
    instagram_account_id: str,
) -> list[dict]:
    """
    Fetch currently active Instagram Stories.

    Important:
    Stories disappear from this endpoint
    after they expire, so historical Story
    data must be stored separately.
    """

    return client.get_instagram_all(
        f"{instagram_account_id}/stories",
        {
            "fields": ",".join(
                STORY_FIELDS
            ),
            "limit": 100,
        },
    )


# ============================================
# Base Story insights
# ============================================

def fetch_story_base_insights(
    client: MetaClient,
    story_id: str,
) -> tuple[dict, str]:
    """
    Fetch standard Story metrics.

    Returns:
        (
            metrics_dict,
            insight_status
        )

    insight_status:
        OK
        LOW_VOLUME
    """

    try:

        payload = client.get_instagram(
            f"{story_id}/insights",
            {
                "metric": ",".join(
                    STORY_BASE_METRICS
                ),
            },
        )

    except MetaAPIError as exc:

        # ------------------------------------
        # Story is too new / viewer count low
        # ------------------------------------

        if _is_low_volume_error(exc):

            return (
                {
                    metric: None
                    for metric
                    in STORY_BASE_METRICS
                },
                "LOW_VOLUME",
            )

        # ------------------------------------
        # Real API error
        # ------------------------------------

        raise

    return (
        _metric_value_map(
            payload
        ),
        "OK",
    )


# ============================================
# Story link clicks
# ============================================

def fetch_story_link_clicks(
    client: MetaClient,
    story_id: str,
) -> int | float | None:
    """
    Fetch Story link-click metric.

    Some Stories may not have an eligible
    link-click metric, so unsupported or
    unavailable responses are returned as None.
    """

    try:

        payload = client.get_instagram(
            f"{story_id}/insights",
            {
                "metric": "link_clicks",
            },
        )

    except MetaAPIError as exc:

        if _is_low_volume_error(exc):
            return None

        # A Story may not contain a link sticker,
        # or Meta may not expose this metric
        # for the Story.
        return None

    values = _metric_value_map(
        payload
    )

    return values.get(
        "link_clicks"
    )


# ============================================
# Story navigation
# ============================================

def fetch_story_navigation(
    client: MetaClient,
    story_id: str,
) -> dict:
    """
    Fetch Story navigation breakdown.

    Expected action types may include:

    TAP_FORWARD
    TAP_BACK
    TAP_EXIT
    SWIPE_FORWARD
    """

    try:

        payload = client.get_instagram(
            f"{story_id}/insights",
            {
                "metric": "navigation",
                "breakdown": (
                    "story_navigation_action_type"
                ),
            },
        )

    except MetaAPIError as exc:

        if _is_low_volume_error(exc):
            return {}

        raise

    result = {}

    for metric in payload.get(
        "data",
        [],
    ):

        total_value = metric.get(
            "total_value",
            {},
        )

        breakdowns = total_value.get(
            "breakdowns",
            [],
        )

        for breakdown in breakdowns:

            rows = breakdown.get(
                "results",
                [],
            )

            for row in rows:

                dimension_values = row.get(
                    "dimension_values",
                    [],
                )

                if not dimension_values:
                    continue

                action = (
                    dimension_values[0]
                )

                result[action] = row.get(
                    "value",
                    0,
                )

    return result


# ============================================
# Combined Story insights
# ============================================

def fetch_story_insights(
    client: MetaClient,
    story: dict,
) -> dict:
    """
    Fetch all supported Story insights.

    LOW_VOLUME is treated as a valid state,
    not as an exception.

    Important:
    LOW_VOLUME metrics remain None.
    They must NOT be converted to zero.
    """

    story_id = story["id"]

    # ----------------------------------------
    # Base metrics
    # ----------------------------------------

    base, insight_status = (
        fetch_story_base_insights(
            client,
            story_id,
        )
    )

    # ----------------------------------------
    # Not enough viewers yet
    # ----------------------------------------

    if insight_status == "LOW_VOLUME":

        return {
            "story_id": story_id,
            "media_type": story.get(
                "media_type"
            ),
            "timestamp": story.get(
                "timestamp"
            ),
            "insight_status": (
                "LOW_VOLUME"
            ),

            **base,

            "link_clicks": None,
            "tap_forward": None,
            "tap_back": None,
            "tap_exit": None,
            "swipe_forward": None,
        }

    # ----------------------------------------
    # Navigation
    # ----------------------------------------

    navigation = (
        fetch_story_navigation(
            client,
            story_id,
        )
    )

    # ----------------------------------------
    # Link clicks
    # ----------------------------------------

    link_clicks = (
        fetch_story_link_clicks(
            client,
            story_id,
        )
    )

    # ----------------------------------------
    # Final normalized result
    # ----------------------------------------

    return {
        "story_id": story_id,
        "media_type": story.get(
            "media_type"
        ),
        "timestamp": story.get(
            "timestamp"
        ),
        "insight_status": "OK",

        **base,

        "link_clicks": link_clicks,

        "tap_forward": navigation.get(
            "TAP_FORWARD"
        ),

        "tap_back": navigation.get(
            "TAP_BACK"
        ),

        "tap_exit": navigation.get(
            "TAP_EXIT"
        ),

        "swipe_forward": navigation.get(
            "SWIPE_FORWARD"
        ),
    }