from __future__ import annotations

from src.meta_client import MetaClient


ACCOUNT_FIELDS = [
    "id",
    "username",
    "name",
    "followers_count",
    "follows_count",
    "media_count",
    "profile_picture_url",
]


def fetch_account(
    client: MetaClient,
    instagram_account_id: str,
) -> dict:

    return client.get_instagram(
        instagram_account_id,
        {
            "fields": ",".join(ACCOUNT_FIELDS),
        },
    )