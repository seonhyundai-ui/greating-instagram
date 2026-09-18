from __future__ import annotations

from dataclasses import dataclass
from urllib.parse import quote

import requests
import streamlit as st


@dataclass(frozen=True)
class GithubDispatchConfig:
    owner: str
    repo: str
    workflow: str
    token: str
    ref: str = "main"


def _secret(name: str, default: str = "") -> str:
    """Read a Streamlit secret without leaking the value."""
    try:
        value = st.secrets.get(name, default)
    except Exception:
        return default

    if value is None:
        return default

    return str(value).strip()


def get_github_dispatch_config() -> GithubDispatchConfig | None:
    owner = _secret("GITHUB_OWNER")
    repo = _secret("GITHUB_REPO")
    workflow = _secret("GITHUB_WORKFLOW")
    token = _secret("GITHUB_TOKEN")
    ref = _secret("GITHUB_REF", "main") or "main"

    if not all([owner, repo, workflow, token]):
        return None

    return GithubDispatchConfig(
        owner=owner,
        repo=repo,
        workflow=workflow,
        token=token,
        ref=ref,
    )


def github_dispatch_configured() -> bool:
    return get_github_dispatch_config() is not None


def dispatch_github_workflow(
    source: str = "streamlit_overview",
) -> dict:
    """
    Trigger the existing GitHub Actions workflow via workflow_dispatch.

    The GitHub PAT stays in Streamlit Secrets and is never sent to the
    browser. A normal GitHub workflow_dispatch response is HTTP 204.
    """
    config = get_github_dispatch_config()

    if config is None:
        raise RuntimeError(
            "GitHub 수동 수집 설정이 없습니다. "
            "Streamlit Secrets에 GITHUB_OWNER, GITHUB_REPO, "
            "GITHUB_WORKFLOW, GITHUB_TOKEN을 설정해주세요."
        )

    workflow = quote(config.workflow, safe="")
    url = (
        f"https://api.github.com/repos/{config.owner}/{config.repo}"
        f"/actions/workflows/{workflow}/dispatches"
    )

    response = requests.post(
        url,
        headers={
            "Authorization": f"Bearer {config.token}",
            "Accept": "application/vnd.github+json",
            "X-GitHub-Api-Version": "2022-11-28",
            "User-Agent": "greating-instagram-dashboard",
        },
        json={
            "ref": config.ref,
            "inputs": {
                "source": str(source)[:100],
            },
        },
        timeout=20,
    )

    if response.status_code != 204:
        detail = response.text.strip()
        if len(detail) > 500:
            detail = detail[:500] + "..."

        raise RuntimeError(
            "GitHub Actions 실행 요청 실패 "
            f"(HTTP {response.status_code})"
            + (f": {detail}" if detail else "")
        )

    return {
        "ok": True,
        "status_code": 204,
        "owner": config.owner,
        "repo": config.repo,
        "workflow": config.workflow,
        "ref": config.ref,
        "source": source,
    }
