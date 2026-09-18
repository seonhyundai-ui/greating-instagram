from __future__ import annotations

from typing import Any

import requests


# ============================================
# Exceptions
# ============================================

class MetaAPIError(RuntimeError):
    """
    Raised when Meta Graph API returns an error.

    Meta error information is stored separately
    so callers can distinguish expected API states
    such as Story LOW_VOLUME from real failures.
    """

    def __init__(
        self,
        message: str,
        *,
        http_status: int | None = None,
        code: int | None = None,
        subcode: int | None = None,
    ):
        super().__init__(message)

        self.http_status = http_status
        self.code = code
        self.subcode = subcode


# ============================================
# Meta Graph API Client
# ============================================

class MetaClient:
    def __init__(
        self,
        api_version: str,
        ig_access_token: str,
        ads_access_token: str,
        timeout: int = 30,
    ):
        self.api_version = api_version
        self.ig_access_token = ig_access_token
        self.ads_access_token = ads_access_token
        self.timeout = timeout

        self.base_url = (
            f"https://graph.facebook.com/"
            f"{self.api_version}"
        )

        self.session = requests.Session()

    # ========================================
    # Base GET request
    # ========================================

    def _get(
        self,
        path: str,
        params: dict[str, Any] | None = None,
        *,
        access_token: str,
    ) -> dict[str, Any]:

        url = (
            f"{self.base_url}/"
            f"{path.lstrip('/')}"
        )

        # Do not expose the access token
        # in query strings or error URLs.
        headers = {
            "Authorization": (
                f"Bearer {access_token}"
            ),
        }

        request_params = dict(
            params or {}
        )

        try:

            response = self.session.get(
                url,
                params=request_params,
                headers=headers,
                timeout=self.timeout,
            )

        except requests.RequestException as exc:

            raise MetaAPIError(
                (
                    "Meta API network error: "
                    f"{exc.__class__.__name__}: "
                    f"{exc}"
                )
            ) from exc

        # ====================================
        # Parse JSON
        # ====================================

        try:

            payload = response.json()

        except ValueError as exc:

            raise MetaAPIError(
                (
                    "Meta API returned "
                    "non-JSON response. "
                    f"HTTP={response.status_code}"
                ),
                http_status=response.status_code,
            ) from exc

        # ====================================
        # Meta API error
        # ====================================

        if (
            not response.ok
            or "error" in payload
        ):

            error = payload.get(
                "error",
                {},
            )

            message = error.get(
                "message",
                "Unknown Meta API error",
            )

            code = error.get(
                "code"
            )

            subcode = error.get(
                "error_subcode"
            )

            error_type = error.get(
                "type"
            )

            fbtrace_id = error.get(
                "fbtrace_id"
            )

            parts = [
                "Meta API error",
                (
                    f"HTTP="
                    f"{response.status_code}"
                ),
                f"code={code}",
                f"subcode={subcode}",
            ]

            if error_type:
                parts.append(
                    f"type={error_type}"
                )

            if fbtrace_id:
                parts.append(
                    f"fbtrace_id={fbtrace_id}"
                )

            error_prefix = (
                "("
                + ", ".join(parts[1:])
                + ")"
            )

            raise MetaAPIError(
                (
                    f"{parts[0]} "
                    f"{error_prefix}: "
                    f"{message}"
                ),
                http_status=(
                    response.status_code
                ),
                code=code,
                subcode=subcode,
            )

        return payload

    # ========================================
    # Pagination
    # ========================================

    def _get_all(
        self,
        path: str,
        params: dict[str, Any] | None = None,
        *,
        access_token: str,
        max_items: int | None = None,
    ) -> list[dict[str, Any]]:
        """
        Fetch all pages using Meta cursor pagination.

        Access tokens are not read from Meta's
        paging.next URL. Only the 'after' cursor
        is reused so the token remains protected.
        """

        rows: list[dict[str, Any]] = []

        base_params = dict(
            params or {}
        )

        after: str | None = None

        while True:

            page_params = dict(
                base_params
            )

            if after:
                page_params["after"] = after

            payload = self._get(
                path,
                page_params,
                access_token=access_token,
            )

            page_rows = payload.get(
                "data",
                [],
            )

            if isinstance(
                page_rows,
                list,
            ):
                rows.extend(
                    page_rows
                )

            if (
                max_items is not None
                and len(rows) >= max_items
            ):
                return rows[
                    :max_items
                ]

            paging = payload.get(
                "paging",
                {},
            )

            cursors = paging.get(
                "cursors",
                {},
            )

            next_url = paging.get(
                "next"
            )

            next_after = cursors.get(
                "after"
            )

            if (
                not next_url
                or not next_after
            ):
                break

            after = next_after

        return rows

    # ========================================
    # Instagram API
    # ========================================

    def get_instagram(
        self,
        path: str,
        params: dict[str, Any] | None = None,
    ) -> dict[str, Any]:

        return self._get(
            path,
            params,
            access_token=(
                self.ig_access_token
            ),
        )

    def get_instagram_all(
        self,
        path: str,
        params: dict[str, Any] | None = None,
        *,
        max_items: int | None = None,
    ) -> list[dict[str, Any]]:

        return self._get_all(
            path,
            params,
            access_token=(
                self.ig_access_token
            ),
            max_items=max_items,
        )

    # ========================================
    # Meta Marketing API
    # ========================================

    def get_ads(
        self,
        path: str,
        params: dict[str, Any] | None = None,
    ) -> dict[str, Any]:

        return self._get(
            path,
            params,
            access_token=(
                self.ads_access_token
            ),
        )

    def get_ads_all(
        self,
        path: str,
        params: dict[str, Any] | None = None,
        *,
        max_items: int | None = None,
    ) -> list[dict[str, Any]]:

        return self._get_all(
            path,
            params,
            access_token=(
                self.ads_access_token
            ),
            max_items=max_items,
        )