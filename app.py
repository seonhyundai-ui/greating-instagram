from __future__ import annotations

import streamlit as st

from dashboard.auth import check_login, render_logout_button
from dashboard.config import APP_VERSION
from dashboard.core import get_tables, reload_data
from dashboard.styles import apply_styles


st.set_page_config(
    page_title="Greating Instagram Dashboard",
    page_icon="📊",
    layout="wide",
    initial_sidebar_state="expanded",
)


# ============================================================
# Login gate
# ============================================================

if not check_login():
    st.stop()


# IMPORTANT:
# The login page injects its own narrow-layout CSS and hides the sidebar.
# Apply the dashboard CSS only AFTER successful authentication so the
# normal wide dashboard layout and sidebar are restored.
apply_styles()


# ============================================================
# Sidebar / Navigation
# ============================================================

with st.sidebar:
    st.markdown("## Greating Instagram")
    st.caption(f"Dashboard v{APP_VERSION}")

pages = [
    st.Page(
        "pages/overview.py",
        title="Overview",
        icon=":material/home:",
        default=True,
    ),
    st.Page(
        "pages/content_performance.py",
        title="Content Performance",
        icon=":material/analytics:",
    ),
    st.Page(
        "pages/story.py",
        title="Story",
        icon=":material/auto_stories:",
    ),
    st.Page(
        "pages/ads.py",
        title="Ads",
        icon=":material/campaign:",
    ),
    st.Page(
        "pages/content_library.py",
        title="Content Library",
        icon=":material/grid_view:",
    ),
]

navigation = st.navigation(
    pages,
    position="sidebar",
)


with st.sidebar:
    st.divider()

    if st.button(
        "데이터 새로고침",
        use_container_width=True,
        key="refresh_dashboard_data",
    ):
        reload_data()
        st.rerun()

    st.caption("Google Sheets 데이터를 5분간 캐시합니다.")

    # CONTENT_MASTER manual-classification alert
    try:
        _tables = get_tables()
        _master = _tables["master"]

        if (
            not _master.empty
            and "classification_status" in _master.columns
        ):
            _pending = int(
                (
                    _master["classification_status"]
                    .astype(str)
                    .str.upper()
                    == "PENDING"
                ).sum()
            )

            if _pending > 0:
                st.warning(
                    f"미분류 콘텐츠 {_pending}건"
                )
            else:
                st.success(
                    "미분류 콘텐츠 없음"
                )

    except Exception:
        st.caption(
            "분류 상태를 확인하지 못했습니다."
        )

# Logout at the bottom of the authenticated sidebar
render_logout_button()


# ============================================================
# Run selected page
# ============================================================

try:
    navigation.run()

except Exception as exc:
    st.error(
        "대시보드 데이터를 불러오거나 계산하는 중 오류가 발생했습니다."
    )
    st.exception(exc)
