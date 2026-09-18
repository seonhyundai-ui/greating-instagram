from pathlib import Path
import os

from dotenv import load_dotenv


# ============================================
# Project paths
# ============================================

PROJECT_ROOT = Path(__file__).resolve().parents[1]

ENV_PATH = PROJECT_ROOT / ".env"

load_dotenv(ENV_PATH)


# ============================================
# Meta API configuration
# ============================================

META_API_VERSION = os.getenv("META_API_VERSION", "v26.0")

INSTAGRAM_ACCOUNT_ID = os.getenv("INSTAGRAM_ACCOUNT_ID")
FACEBOOK_PAGE_ID = os.getenv("FACEBOOK_PAGE_ID")
META_AD_ACCOUNT_ID = os.getenv("META_AD_ACCOUNT_ID")

META_IG_ACCESS_TOKEN = os.getenv("META_IG_ACCESS_TOKEN")
META_ADS_ACCESS_TOKEN = os.getenv("META_ADS_ACCESS_TOKEN")


# ============================================
# Validation
# ============================================

_REQUIRED_VALUES = {
    "INSTAGRAM_ACCOUNT_ID": INSTAGRAM_ACCOUNT_ID,
    "FACEBOOK_PAGE_ID": FACEBOOK_PAGE_ID,
    "META_AD_ACCOUNT_ID": META_AD_ACCOUNT_ID,
    "META_IG_ACCESS_TOKEN": META_IG_ACCESS_TOKEN,
    "META_ADS_ACCESS_TOKEN": META_ADS_ACCESS_TOKEN,
}

_missing = [
    key
    for key, value in _REQUIRED_VALUES.items()
    if not value
]

if _missing:
    raise RuntimeError(
        "Missing required environment variables: "
        + ", ".join(_missing)
    )

GOOGLE_SPREADSHEET_ID = os.getenv(
    "GOOGLE_SPREADSHEET_ID"
)

if not GOOGLE_SPREADSHEET_ID:
    raise RuntimeError(
        "Missing required environment variable: "
        "GOOGLE_SPREADSHEET_ID"
    )