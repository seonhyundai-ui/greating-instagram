from __future__ import annotations

import hmac
from pathlib import Path

import streamlit as st


AUTH_SESSION_KEY = "authenticated"
PASSWORD_SECRET_KEY = "APP_PASSWORD"


def _read_app_password() -> str:
    """Read the dashboard password from Streamlit Secrets."""
    try:
        value = str(st.secrets[PASSWORD_SECRET_KEY]).strip()
    except Exception as exc:  # pragma: no cover - runtime environment dependent
        raise RuntimeError(
            "Streamlit Secrets에 APP_PASSWORD가 없습니다. "
            ".streamlit/secrets.toml 또는 Streamlit Cloud Secrets에 APP_PASSWORD를 설정해주세요."
        ) from exc

    if not value:
        raise RuntimeError("APP_PASSWORD 값이 비어 있습니다.")

    return value


def _logo_path() -> Path | None:
    candidates = [
        Path("assets/greating_logo.png"),
        Path("assets/logo.png"),
    ]
    for path in candidates:
        if path.exists():
            return path
    return None


def _render_login_css() -> None:
    st.markdown(
        """
        <style>
        [data-testid="stSidebar"] { display: none; }
        [data-testid="stHeader"] { background: transparent; }

        .block-container {
            max-width: 520px;
            padding-top: 9vh;
            padding-bottom: 5rem;
        }

        .login-shell {
            text-align: center;
            margin-bottom: 1.4rem;
        }

        .login-kicker {
            display: inline-block;
            padding: .34rem .72rem;
            border-radius: 999px;
            background: #eef4ff;
            color: #2563eb;
            font-size: .78rem;
            font-weight: 700;
            margin-bottom: .9rem;
        }

        .login-title {
            font-size: 2rem;
            line-height: 1.15;
            font-weight: 800;
            letter-spacing: -.04em;
            color: #15213a;
            margin-bottom: .55rem;
        }

        .login-subtitle {
            color: #7b8495;
            font-size: .93rem;
            margin-bottom: 1.2rem;
        }

        div[data-testid="stForm"] {
            border: 1px solid #e5e9f2;
            border-radius: 18px;
            padding: 1.4rem 1.4rem 1.15rem 1.4rem;
            background: #ffffff;
            box-shadow: 0 12px 34px rgba(31, 41, 55, .07);
        }

        div[data-testid="stTextInput"] input {
            border-radius: 10px;
        }

        div[data-testid="stFormSubmitButton"] button {
            width: 100%;
            border-radius: 10px;
            min-height: 2.85rem;
            font-weight: 700;
            background: #2563eb;
            color: white;
            border: 0;
        }

        div[data-testid="stFormSubmitButton"] button:hover {
            background: #1d4ed8;
            color: white;
            border: 0;
        }

        .login-footnote {
            text-align: center;
            color: #9aa2b1;
            font-size: .76rem;
            margin-top: 1rem;
        }
        </style>
        """,
        unsafe_allow_html=True,
    )


def check_login() -> bool:
    """
    App-level password gate.

    Returns True only after successful authentication.
    Authentication is kept in st.session_state for the current browser session.
    """
    if st.session_state.get(AUTH_SESSION_KEY, False):
        return True

    _render_login_css()

    logo = _logo_path()
    if logo is not None:
        left, center, right = st.columns([1.15, 1, 1.15])
        with center:
            st.image(str(logo), use_container_width=True)

    st.markdown(
        """
        <div class="login-shell">
            <div class="login-kicker">GREATING SOCIAL ANALYTICS</div>
            <div class="login-title">Greating Instagram Dashboard</div>
            <div class="login-subtitle">대시보드 접근 비밀번호를 입력해주세요.</div>
        </div>
        """,
        unsafe_allow_html=True,
    )

    with st.form("login_form", clear_on_submit=False):
        password = st.text_input(
            "비밀번호",
            type="password",
            placeholder="비밀번호 입력",
            autocomplete="current-password",
        )
        submitted = st.form_submit_button("로그인", use_container_width=True)

    if submitted:
        try:
            expected = _read_app_password()
        except RuntimeError as exc:
            st.error(str(exc))
            return False

        if hmac.compare_digest(password, expected):
            st.session_state[AUTH_SESSION_KEY] = True
            st.session_state.pop("login_error", None)
            st.rerun()
        else:
            st.session_state["login_error"] = True

    if st.session_state.get("login_error"):
        st.error("비밀번호가 올바르지 않습니다.")

    st.markdown(
        '<div class="login-footnote">Hyundai Green Food · Greating Marketing</div>',
        unsafe_allow_html=True,
    )

    return False


def render_logout_button() -> None:
    """Render a logout button in the sidebar for authenticated sessions."""
    if not st.session_state.get(AUTH_SESSION_KEY, False):
        return

    with st.sidebar:
        st.markdown("---")
        if st.button("로그아웃", use_container_width=True, key="logout_button"):
            st.session_state[AUTH_SESSION_KEY] = False
            st.session_state.pop("login_error", None)
            st.rerun()
