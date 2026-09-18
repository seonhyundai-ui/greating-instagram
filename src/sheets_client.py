from __future__ import annotations

from pathlib import Path

import gspread

from google.auth.transport.requests import Request
from google.oauth2.credentials import Credentials
from google_auth_oauthlib.flow import InstalledAppFlow


SCOPES = [
    "https://www.googleapis.com/auth/spreadsheets",
]


PROJECT_ROOT = Path(__file__).resolve().parents[1]

CREDENTIALS_DIR = PROJECT_ROOT / "credentials"

CLIENT_SECRET_PATH = (
    CREDENTIALS_DIR
    / "google_oauth_client.json"
)

TOKEN_PATH = (
    CREDENTIALS_DIR
    / "google_token.json"
)


def get_google_credentials() -> Credentials:
    """
    Load Google OAuth credentials.

    First execution:
        Browser login -> consent -> token saved.

    Following executions:
        Stored refresh token is used automatically.
    """

    creds = None

    if TOKEN_PATH.exists():
        creds = Credentials.from_authorized_user_file(
            TOKEN_PATH,
            SCOPES,
        )

    if not creds or not creds.valid:

        if (
            creds
            and creds.expired
            and creds.refresh_token
        ):
            creds.refresh(
                Request()
            )

        else:
            flow = (
                InstalledAppFlow
                .from_client_secrets_file(
                    CLIENT_SECRET_PATH,
                    SCOPES,
                )
            )

            creds = flow.run_local_server(
                port=0,
            )

        TOKEN_PATH.parent.mkdir(
            parents=True,
            exist_ok=True,
        )

        TOKEN_PATH.write_text(
            creds.to_json(),
            encoding="utf-8",
        )

    return creds


def get_gspread_client() -> gspread.Client:
    """
    Return authenticated gspread client.
    """

    creds = get_google_credentials()

    return gspread.authorize(
        creds
    )