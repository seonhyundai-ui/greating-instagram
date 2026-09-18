from __future__ import annotations

import base64
import json
from pathlib import Path

import gspread
from google.auth.transport.requests import Request
from google.oauth2.credentials import Credentials
from google_auth_oauthlib.flow import InstalledAppFlow


# ============================================================
# Paths
# ============================================================

ROOT_DIR = Path(__file__).resolve().parents[1]

CREDENTIALS_DIR = (
    ROOT_DIR
    / "credentials"
)

OAUTH_CLIENT_FILE = (
    CREDENTIALS_DIR
    / "google_oauth_client.json"
)

OAUTH_TOKEN_FILE = (
    CREDENTIALS_DIR
    / "google_token.json"
)


# ============================================================
# Scopes
# ============================================================

SCOPES = [
    "https://www.googleapis.com/auth/spreadsheets",
]


# ============================================================
# Helpers
# ============================================================

def _streamlit_secret(
    *keys: str,
):
    """
    Return the first non-empty Streamlit secret among keys.
    Safe outside Streamlit.
    """

    try:
        import streamlit as st

        for key in keys:

            if key in st.secrets:

                value = st.secrets[
                    key
                ]

                if value not in (
                    None,
                    "",
                ):
                    return str(
                        value
                    )

    except Exception:
        pass

    return None


def _decode_base64_json(
    value: str,
    *,
    label: str,
) -> dict:

    try:
        decoded = base64.b64decode(
            value
        ).decode(
            "utf-8"
        )

        return json.loads(
            decoded
        )

    except Exception as exc:

        raise RuntimeError(
            f"Failed to decode {label}."
        ) from exc


def _load_cloud_token_info():
    """
    Streamlit Cloud secrets.

    Supported token key:
    - GOOGLE_TOKEN_B64
    """

    token_b64 = _streamlit_secret(
        "GOOGLE_TOKEN_B64",
    )

    if not token_b64:
        return None

    return _decode_base64_json(
        token_b64,
        label="GOOGLE_TOKEN_B64",
    )


def _load_cloud_client_info():
    """
    Supports both names so existing secrets do not need
    to be renamed.

    - GOOGLE_CREDENTIALS_B64
    - GOOGLE_OAUTH_CLIENT_B64
    """

    client_b64 = _streamlit_secret(
        "GOOGLE_CREDENTIALS_B64",
        "GOOGLE_OAUTH_CLIENT_B64",
    )

    if not client_b64:
        return None

    return _decode_base64_json(
        client_b64,
        label="Google OAuth client Base64 secret",
    )


# ============================================================
# Streamlit Cloud OAuth
# ============================================================

def _get_streamlit_cloud_credentials():
    token_info = (
        _load_cloud_token_info()
    )

    if not token_info:
        return None

    credentials = (
        Credentials.from_authorized_user_info(
            token_info,
            SCOPES,
        )
    )

    if (
        credentials.expired
        and credentials.refresh_token
    ):

        credentials.refresh(
            Request()
        )

    if not credentials.valid:
        raise RuntimeError(
            "Google OAuth token in Streamlit Secrets "
            "is invalid or cannot be refreshed. "
            "Refresh credentials/google_token.json locally "
            "and replace GOOGLE_TOKEN_B64 in Streamlit Secrets."
        )

    return credentials


# ============================================================
# Local / GitHub Actions OAuth
# ============================================================

def _get_local_oauth_credentials():

    credentials = None

    if OAUTH_TOKEN_FILE.exists():

        credentials = (
            Credentials.from_authorized_user_file(
                str(
                    OAUTH_TOKEN_FILE
                ),
                SCOPES,
            )
        )

    if (
        credentials
        and credentials.expired
        and credentials.refresh_token
    ):

        credentials.refresh(
            Request()
        )

        # Keep refreshed local token for subsequent runs.
        try:
            OAUTH_TOKEN_FILE.write_text(
                credentials.to_json(),
                encoding="utf-8",
            )

        except OSError:
            pass

    if (
        credentials
        and credentials.valid
    ):
        return credentials

    if not OAUTH_CLIENT_FILE.exists():
        raise FileNotFoundError(
            "Google OAuth credentials not found. "
            f"Expected {OAUTH_CLIENT_FILE} and/or "
            "Streamlit secret GOOGLE_TOKEN_B64."
        )

    flow = (
        InstalledAppFlow
        .from_client_secrets_file(
            str(
                OAUTH_CLIENT_FILE
            ),
            SCOPES,
        )
    )

    credentials = (
        flow.run_local_server(
            port=0
        )
    )

    CREDENTIALS_DIR.mkdir(
        parents=True,
        exist_ok=True,
    )

    OAUTH_TOKEN_FILE.write_text(
        credentials.to_json(),
        encoding="utf-8",
    )

    return credentials


# ============================================================
# Public
# ============================================================

def get_gspread_client():
    """
    Authentication priority:

    1. Streamlit Cloud
       GOOGLE_TOKEN_B64 in st.secrets

    2. Local / GitHub Actions
       credentials/google_token.json

    GitHub Actions already reconstructs the credential files,
    so its current workflow remains unchanged.
    """

    cloud_credentials = (
        _get_streamlit_cloud_credentials()
    )

    if cloud_credentials:

        return gspread.authorize(
            cloud_credentials
        )

    local_credentials = (
        _get_local_oauth_credentials()
    )

    return gspread.authorize(
        local_credentials
    )
