from __future__ import annotations

from src.meta_client import MetaAPIError


# ============================================================
# Normalization
# ============================================================

GENDER_MAP = {
    "F": "F",
    "FEMALE": "F",
    "M": "M",
    "MALE": "M",
    "U": "U",
    "UNKNOWN": "U",
}


def _normalize_gender(value: str) -> str:

    raw = str(
        value or ""
    ).strip().upper()

    return GENDER_MAP.get(
        raw,
        raw,
    )


# ============================================================
# Parser
# ============================================================

def _parse_breakdown_results(
    payload: dict,
    *,
    dimension: str,
) -> list[dict]:

    rows = []

    for metric_item in payload.get(
        "data",
        [],
    ):

        total_value = (
            metric_item.get(
                "total_value"
            )
            or {}
        )

        breakdowns = (
            total_value.get(
                "breakdowns"
            )
            or []
        )

        for breakdown in breakdowns:

            results = (
                breakdown.get(
                    "results"
                )
                or []
            )

            for result in results:

                dimension_values = (
                    result.get(
                        "dimension_values"
                    )
                    or []
                )

                if not dimension_values:
                    continue

                segment = str(
                    dimension_values[0]
                ).strip()

                if (
                    dimension
                    == "gender"
                ):

                    segment = (
                        _normalize_gender(
                            segment
                        )
                    )

                value = result.get(
                    "value"
                )

                try:
                    value = int(
                        float(value)
                    )

                except (
                    TypeError,
                    ValueError,
                ):
                    continue

                rows.append(
                    {
                        "dimension": (
                            dimension
                        ),
                        "segment": (
                            segment
                        ),
                        "value": (
                            value
                        ),
                    }
                )

    return rows


# ============================================================
# One dimension
# ============================================================

def fetch_follower_demographic(
    client,
    instagram_account_id: str,
    *,
    breakdown: str,
) -> list[dict]:

    payload = client.get_instagram(
        f"{instagram_account_id}/insights",
        params={
            "metric": (
                "follower_demographics"
            ),
            "period": "lifetime",
            "metric_type": (
                "total_value"
            ),
            "breakdown": (
                breakdown
            ),
        },
    )

    return _parse_breakdown_results(
        payload,
        dimension=breakdown,
    )


# ============================================================
# Public
# ============================================================

def fetch_audience_demographics(
    client,
    instagram_account_id: str,
) -> list[dict]:
    """
    Fetch current follower demographics.

    Percentages are NOT calculated here.
    They must use the counted total of each
    demographic dimension, NOT followers_count.
    """

    rows = []

    for dimension in [
        "gender",
        "age",
    ]:

        try:

            part = (
                fetch_follower_demographic(
                    client,
                    instagram_account_id,
                    breakdown=dimension,
                )
            )

            rows.extend(
                part
            )

        except MetaAPIError as exc:

            print(
                f"[WARN] Audience "
                f"{dimension} fetch failed:"
                f" {exc}"
            )

    return rows