from __future__ import annotations

from pprint import pprint

from config.settings import (
    META_API_VERSION,
    META_IG_ACCESS_TOKEN,
    META_ADS_ACCESS_TOKEN,
)

from src.meta_client import (
    MetaClient,
    MetaAPIError,
)


VERSION = "0.4.0-validation-2"

TEST_AD_ID = "120249306264160599"


def metric_value(
    payload: dict,
    metric_name: str,
):
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


def get_media_insight(
    meta: MetaClient,
    media_id: str,
    metric: str,
):
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
        }

    except MetaAPIError as exc:

        return {
            "supported": False,
            "value": None,
            "error": str(exc),
        }


def get_media_field(
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
        }

    except MetaAPIError as exc:

        return {
            "supported": False,
            "value": None,
            "error": str(exc),
        }


def extract_actions(
    actions: list[dict],
) -> dict[str, float]:

    output = {}

    for item in actions:

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


def find_action(
    actions: dict[str, float],
    candidates: list[str],
):
    for key in candidates:

        if key in actions:
            return (
                key,
                actions[key],
            )

    return (
        None,
        None,
    )


def main() -> None:

    print("=" * 78)
    print(
        "Greating Instagram "
        f"Saved / Interactions Validation v{VERSION}"
    )
    print("=" * 78)

    meta = MetaClient(
        api_version=META_API_VERSION,
        ig_access_token=META_IG_ACCESS_TOKEN,
        ads_access_token=META_ADS_ACCESS_TOKEN,
    )

    # ========================================================
    # 1. Resolve original media
    # ========================================================

    print()
    print(
        "[1/5] Resolve source Instagram media"
    )

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
                "source_instagram_media_id,"
                "effective_instagram_media_id"
            ),
        },
    )

    media_id = str(
        creative.get(
            "source_instagram_media_id"
        )
        or ""
    )

    if not media_id:
        raise RuntimeError(
            "source_instagram_media_id not found."
        )

    print(
        f"      ad_id      = {TEST_AD_ID}"
    )

    print(
        f"      media_id   = {media_id}"
    )

    # ========================================================
    # 2. Organic Instagram metrics
    # ========================================================

    print()
    print(
        "[2/5] Organic Instagram metrics"
    )

    organic_metric_names = [
        "likes",
        "comments",
        "saved",
        "shares",
        "total_interactions",
    ]

    organic = {}

    for metric in organic_metric_names:

        result = get_media_insight(
            meta,
            media_id,
            metric,
        )

        organic[
            metric
        ] = result.get(
            "value"
        )

        if result.get(
            "supported"
        ):

            print(
                f"      {metric:<20}"
                f" = {result.get('value')}"
            )

        else:

            print(
                f"      {metric:<20}"
                " = UNSUPPORTED"
            )

    organic_component_sum = sum(
        value or 0
        for value in [
            organic.get("likes"),
            organic.get("comments"),
            organic.get("saved"),
            organic.get("shares"),
        ]
    )

    print()
    print(
        f"      component sum        "
        f" = {organic_component_sum}"
    )

    print(
        f"      total_interactions   "
        f" = {organic.get('total_interactions')}"
    )

    print(
        "      component check     "
        f" = "
        f"{organic_component_sum == organic.get('total_interactions')}"
    )

    # ========================================================
    # 3. Total field candidates
    # ========================================================

    print()
    print(
        "[3/5] Total field candidates"
    )

    candidate_fields = [
        "saved_count",
        "shares_count",
        "total_like_count",
        "total_comments_count",
    ]

    total_fields = {}

    for field in candidate_fields:

        result = get_media_field(
            meta,
            media_id,
            field,
        )

        total_fields[
            field
        ] = result.get(
            "value"
        )

        if result.get(
            "supported"
        ):

            print(
                f"      {field:<24}"
                f" = {result.get('value')}"
            )

        else:

            print(
                f"      {field:<24}"
                " = UNSUPPORTED"
            )

    # ========================================================
    # 4. Paid actions
    # ========================================================

    print()
    print(
        "[4/5] Paid Instagram actions"
    )

    paid_rows = meta.get_ads_all(
        f"{TEST_AD_ID}/insights",
        params={
            "fields": (
                "reach,"
                "impressions,"
                "spend,"
                "actions"
            ),
            "date_preset": "maximum",
            "breakdowns": (
                "publisher_platform"
            ),
        },
    )

    instagram_rows = [
        row
        for row in paid_rows
        if row.get(
            "publisher_platform"
        ) == "instagram"
    ]

    if len(
        instagram_rows
    ) != 1:

        print(
            f"      [WARN] rows="
            f"{len(instagram_rows)}"
        )

        pprint(
            instagram_rows
        )

    paid = (
        instagram_rows[0]
        if instagram_rows
        else {}
    )

    actions = extract_actions(
        paid.get(
            "actions"
        )
        or []
    )

    interesting_actions = {
        key: value
        for key, value
        in actions.items()
        if any(
            word in key.lower()
            for word in [
                "save",
                "like",
                "comment",
                "share",
                "interaction",
                "reaction",
            ]
        )
    }

    print(
        "      Relevant actions"
    )

    for (
        key,
        value,
    ) in sorted(
        interesting_actions.items()
    ):

        print(
            f"      {key:<45}"
            f" = {value}"
        )

    (
        paid_saved_key,
        paid_saved,
    ) = find_action(
        actions,
        [
            "onsite_conversion.post_save",
            "onsite_conversion.post_net_save",
        ],
    )

    (
        paid_like_key,
        paid_likes,
    ) = find_action(
        actions,
        [
            "onsite_conversion.post_net_like",
        ],
    )

    (
        paid_interaction_key,
        paid_interactions,
    ) = find_action(
        actions,
        [
            "post_interaction_net",
        ],
    )

    print()
    print(
        "      Selected Paid metrics"
    )

    print(
        f"      saved        = "
        f"{paid_saved}"
        f" [{paid_saved_key}]"
    )

    print(
        f"      likes        = "
        f"{paid_likes}"
        f" [{paid_like_key}]"
    )

    print(
        f"      interactions = "
        f"{paid_interactions}"
        f" [{paid_interaction_key}]"
    )

    # ========================================================
    # 5. Three-layer candidates
    # ========================================================

    print()
    print("=" * 78)
    print(
        "[5/5] THREE-LAYER CANDIDATES"
    )
    print("=" * 78)

    organic_saved = (
        organic.get(
            "saved"
        )
    )

    organic_interactions = (
        organic.get(
            "total_interactions"
        )
    )

    # --------------------------------------------------------
    # Saved
    # --------------------------------------------------------

    saved_total_calculated = None

    if (
        organic_saved is not None
        and paid_saved is not None
    ):

        saved_total_calculated = (
            float(organic_saved)
            + float(paid_saved)
        )

    print()
    print(
        "SAVED"
    )

    print(
        f"      TOTAL calculated = "
        f"{saved_total_calculated}"
    )

    print(
        f"      ORGANIC          = "
        f"{organic_saved}"
    )

    print(
        f"      PAID             = "
        f"{paid_saved}"
    )

    print(
        f"      saved_count field= "
        f"{total_fields.get('saved_count')}"
    )

    # --------------------------------------------------------
    # Interactions
    # --------------------------------------------------------

    interactions_total_calculated = None

    if (
        organic_interactions is not None
        and paid_interactions is not None
    ):

        interactions_total_calculated = (
            float(
                organic_interactions
            )
            + float(
                paid_interactions
            )
        )

    print()
    print(
        "INTERACTIONS"
    )

    print(
        f"      TOTAL calculated = "
        f"{interactions_total_calculated}"
    )

    print(
        f"      ORGANIC          = "
        f"{organic_interactions}"
    )

    print(
        f"      PAID             = "
        f"{paid_interactions}"
    )

    # --------------------------------------------------------
    # Paid component sanity check
    # --------------------------------------------------------

    print()
    print(
        "PAID SANITY CHECK"
    )

    print(
        f"      paid likes       = "
        f"{paid_likes}"
    )

    print(
        f"      paid saved       = "
        f"{paid_saved}"
    )

    print(
        f"      paid interactions= "
        f"{paid_interactions}"
    )

    if (
        paid_likes is not None
        and paid_saved is not None
        and paid_interactions is not None
    ):

        known_paid_components = (
            float(paid_likes)
            + float(paid_saved)
        )

        remainder = (
            float(paid_interactions)
            - known_paid_components
        )

        print(
            f"      interaction remainder"
            f" = {remainder}"
        )

        print(
            "      → remainder should roughly "
            "correspond to shares/comments/"
            "other post interactions."
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