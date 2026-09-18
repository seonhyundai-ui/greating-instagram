from __future__ import annotations

from src.meta_client import MetaClient


MEDIA_FIELDS = [
    "id",
    "caption",
    "media_type",
    "media_product_type",
    "media_url",
    "thumbnail_url",
    "permalink",
    "timestamp",
]


CHILD_FIELDS = [
    "id",
    "media_type",
    "media_url",
    "thumbnail_url",
]


def fetch_media(
    client: MetaClient,
    instagram_account_id: str,
    *,
    max_items: int = 50,
) -> list[dict]:

    return client.get_instagram_all(
        f"{instagram_account_id}/media",
        {
            "fields": ",".join(MEDIA_FIELDS),
            "limit": min(max_items, 100),
        },
        max_items=max_items,
    )


def fetch_carousel_children(
    client: MetaClient,
    media_id: str,
) -> list[dict]:

    return client.get_instagram_all(
        f"{media_id}/children",
        {
            "fields": ",".join(CHILD_FIELDS),
        },
    )