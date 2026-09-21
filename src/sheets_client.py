from __future__ import annotations

import base64
import json
import os
from pathlib import Path

import gspread
from google.auth.transport.requests import Request
from google.oauth2 import service_account
from google.oauth2.credentials import Credentials
from google_auth_oauthlib.flow import InstalledAppFlow


ROOT_DIR = Path(__file__).resolve().parents[1]
CREDENTIALS_DIR = ROOT_DIR / "credentials"

SERVICE_ACCOUNT_FILE = CREDENTIALS_DIR / "google_service_account.json"
OAUTH_CLIENT_FILE = CREDENTIALS_DIR / "google_oauth_client.json"
OAUTH_TOKEN_FILE = CREDENTIALS_DIR / "google_token.json"

SCOPES = [
    "https://www.googleapis.com/auth/spreadsheets",
    "https://www.googleapis.com/auth/drive",
]


def _streamlit_secret(key: str):
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
        raise RuntimeError(f"Failed to decode {label}.") from exc


def _get_service_account_info():
    secret_b64 = _streamlit_secret("GOOGLE_SERVICE_ACCOUNT_B64")
    env_b64 = os.getenv("GOOGLE_SERVICE_ACCOUNT_B64")
    encoded = secret_b64 or env_b64

    if encoded:
        return _decode_base64_json(
            encoded,
            label="GOOGLE_SERVICE_ACCOUNT_B64",
        )

    if SERVICE_ACCOUNT_FILE.exists():
        return json.loads(
            SERVICE_ACCOUNT_FILE.read_text(encoding="utf-8")
        )

    return None


def _get_service_account_credentials():
    info = _get_service_account_info()
    if not info:
        return None

    try:
        return service_account.Credentials.from_service_account_info(
            info,
            scopes=SCOPES,
        )
    except Exception as exc:
        raise RuntimeError(
            "Google Service Account credentials are invalid."
        ) from exc


def _get_oauth_credentials():
    """
    Temporary fallback during migration.
    Remove after service account is verified everywhere.
    """
    credentials = None

    if OAUTH_TOKEN_FILE.exists():
        credentials = Credentials.from_authorized_user_file(
            str(OAUTH_TOKEN_FILE),
            SCOPES,
        )

    if credentials and credentials.expired and credentials.refresh_token:
        credentials.refresh(Request())
        try:
            OAUTH_TOKEN_FILE.write_text(
                credentials.to_json(),
                encoding="utf-8",
            )
        except OSError:
            pass

    if credentials and credentials.valid:
        return credentials

    if not OAUTH_CLIENT_FILE.exists():
        return None

    flow = InstalledAppFlow.from_client_secrets_file(
        str(OAUTH_CLIENT_FILE),
        SCOPES,
    )
    credentials = flow.run_local_server(port=0)

    CREDENTIALS_DIR.mkdir(parents=True, exist_ok=True)
    OAUTH_TOKEN_FILE.write_text(
        credentials.to_json(),
        encoding="utf-8",
    )
    return credentials


def get_gspread_client():
    """
    Priority:
    1. Service Account
    2. Legacy OAuth fallback
    """
    credentials = _get_service_account_credentials()

    if credentials:
        return gspread.authorize(credentials)

    credentials = _get_oauth_credentials()

    if credentials:
        return gspread.authorize(credentials)

    raise RuntimeError(
        "Google credentials not found. Configure "
        "GOOGLE_SERVICE_ACCOUNT_B64 or "
        "credentials/google_service_account.json."
    )
