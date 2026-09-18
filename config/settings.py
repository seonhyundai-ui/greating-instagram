from __future__ import annotations

import os
from pathlib import Path

from dotenv import load_dotenv


# ============================================================
# Project paths
# ============================================================

ROOT_DIR = Path(__file__).resolve().parents[1]
ENV_FILE = ROOT_DIR / ".env"

load_dotenv(ENV_FILE)


# ============================================================
# Secret / env helper
# ============================================================

def get_setting(
    key: str,
    default=None,
):
    """
    Priority:
    1. Streamlit secrets
    2. Environment variable / .env
    3. default

    This keeps the same code working in:
    - local development
    - GitHub Actions
    - Streamlit Community Cloud
    """

    try:
        import streamlit as st

        if key in st.secrets:
            value = st.secrets[key]

            if value not in (
                None,
                "",
            ):
                return value

    except Exception:
        # Streamlit may not be installed or may not be running.
        pass

    value = os.getenv(
        key
    )

    if value not in (
        None,
        "",
    ):
        return value

    return default


def require_setting(
    key: str,
):
    value = get_setting(
        key
    )

    if value in (
        None,
        "",
    ):
        raise RuntimeError(
            f"Missing required setting: {key}"
        )

    return value


# ============================================================
# Meta
# ============================================================

META_API_VERSION = get_setting(
    "META_API_VERSION",
    "v26.0",
)

INSTAGRAM_ACCOUNT_ID = require_setting(
    "INSTAGRAM_ACCOUNT_ID"
)

FACEBOOK_PAGE_ID = get_setting(
    "FACEBOOK_PAGE_ID",
    "",
)

META_AD_ACCOUNT_ID = require_setting(
    "META_AD_ACCOUNT_ID"
)

META_IG_ACCESS_TOKEN = require_setting(
    "META_IG_ACCESS_TOKEN"
)

META_ADS_ACCESS_TOKEN = get_setting(
    "META_ADS_ACCESS_TOKEN",
    META_IG_ACCESS_TOKEN,
)


# ============================================================
# Google Sheets
# ============================================================

GOOGLE_SPREADSHEET_ID = require_setting(
    "GOOGLE_SPREADSHEET_ID"
)
