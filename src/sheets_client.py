from __future__ import annotations

import base64
import json
import os
from pathlib import Path

import gspread
from google.oauth2 import service_account


ROOT_DIR = Path(__file__).resolve().parents[1]
CREDENTIALS_DIR = ROOT_DIR / "credentials"
SERVICE_ACCOUNT_FILE = CREDENTIALS_DIR / "google_service_account.json"

SCOPES = [
    "https://www.googleapis.com/auth/spreadsheets",
    "https://www.googleapis.com/auth/drive",
]


def _streamlit_secret(key: str) -> str | None:
    try:
        import streamlit as st

        if key in st.secrets:
            value = st.secrets[key]
            if value not in (None, ""):
                return str(value)
    except Exception:
        pass

    return None


def _decode_base64_json(value: str, *, label: str) -> dict:
    try:
        decoded = base64.b64decode(value).decode("utf-8")
        return json.loads(decoded)
    except Exception as exc:
        raise RuntimeError(
            f"Failed to decode {label}."
        ) from exc


def _load_service_account_info() -> dict:
    """
    Credential priority:
    1. Streamlit Cloud secret: GOOGLE_SERVICE_ACCOUNT_B64
    2. Environment variable: GOOGLE_SERVICE_ACCOUNT_B64
    3. Local file: credentials/google_service_account.json
    """
    encoded = (
        _streamlit_secret("GOOGLE_SERVICE_ACCOUNT_B64")
        or os.getenv("GOOGLE_SERVICE_ACCOUNT_B64")
    )

    if encoded:
        info = _decode_base64_json(
            encoded,
            label="GOOGLE_SERVICE_ACCOUNT_B64",
        )
    elif SERVICE_ACCOUNT_FILE.exists():
        try:
            info = json.loads(
                SERVICE_ACCOUNT_FILE.read_text(encoding="utf-8")
            )
        except Exception as exc:
            raise RuntimeError(
                f"Failed to read {SERVICE_ACCOUNT_FILE}."
            ) from exc
    else:
        raise RuntimeError(
            "Google Service Account credentials not found. "
            "Configure GOOGLE_SERVICE_ACCOUNT_B64 or "
            "credentials/google_service_account.json."
        )

    if info.get("type") != "service_account":
        raise RuntimeError(
            "Configured Google credential is not a service-account JSON key."
        )

    if not info.get("client_email") or not info.get("private_key"):
        raise RuntimeError(
            "Service-account JSON is missing client_email/private_key."
        )

    return info


def get_gspread_client():
    """Create a gspread client using only the production service account."""
    info = _load_service_account_info()

    try:
        credentials = service_account.Credentials.from_service_account_info(
            info,
            scopes=SCOPES,
        )
    except Exception as exc:
        raise RuntimeError(
            "Google Service Account credentials are invalid."
        ) from exc

    return gspread.authorize(credentials)
