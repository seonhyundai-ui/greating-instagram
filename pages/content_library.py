from __future__ import annotations

import math
from datetime import datetime, timedelta

import pandas as pd
import streamlit as st

from dashboard.config import APP_VERSION, COLORS, KST
from dashboard.core import get_tables, metric_column, filter_performance_scope, fmt_int


# ============================================================
# Page: Content Library
# ============================================================

SORT_OPTIONS = {
    "최신 게시일": ("posted_at", False),
    "조회수 높은순": ("sort_views", False),
    "도달수 높은순": ("sort_reach", False),
    "인터랙션 높은순": ("sort_interactions", False),
    "저장 높은순": ("sort_saved", False),
}

STATUS_LABELS = {
    "AI_SEEDED": "AI 분류",
    "PENDING": "미분류",
    "MANUAL_DONE": "수동 완료",
    "NEED_REVIEW": "검토 필요",
}

STATUS_COLORS = {
    "AI_SEEDED": ("#EFF6FF", "#1D4ED8"),
    "PENDING": ("#FFF7ED", "#C2410C"),
    "MANUAL_DONE": ("#ECFDF5", "#047857"),
    "NEED_REVIEW": ("#FEF2F2", "#B91C1C"),
}


def resolve_title(row: pd.Series) -> str:
    for column in ["manual_title", "ai_title"]:
        value = str(row.get(column, "") or "").strip()
        if value:
            return value

    caption = str(row.get("caption", "") or "").strip().replace("\n", " ")
    if caption:
        return caption[:56] + ("…" if len(caption) > 56 else "")

    return "제목 미입력"


def resolve_thumbnail(row: pd.Series) -> str:
    for column in ["thumbnail_url", "media_url"]:
        value = str(row.get(column, "") or "").strip()
        if value and value.lower() not in {"nan", "none"}:
            return value
    return ""


def clean_text(value) -> str:
    text = str(value or "").strip()
    if text.lower() in {"nan", "none"}:
        return ""
    return text


def unique_values(df: pd.DataFrame, column: str) -> list[str]:
    if df.empty or column not in df.columns:
        return []
    values = df[column].fillna("").astype(str).str.strip()
    return sorted([value for value in values.unique().tolist() if value and value.lower() != "nan"])


def compact_metric(label: str, value) -> str:
    try:
        number = float(value)
    except (TypeError, ValueError):
        return f"{label} -"

    if pd.isna(number):
        return f"{label} -"

    return f"{label} {int(round(number)):,}"


def status_badge_html(status: str) -> str:
    normalized = str(status or "").strip().upper()
    label = STATUS_LABELS.get(normalized, normalized or "상태 없음")
    bg, fg = STATUS_COLORS.get(normalized, ("#F1F5F9", "#475569"))
    return (
        f'<span style="display:inline-flex;align-items:center;padding:3px 7px;border-radius:999px;'
        f'background:{bg};color:{fg};font-size:0.68rem;font-weight:800;">{label}</span>'
    )


def render_card(row: pd.Series, performance_label: str) -> None:
    title = resolve_title(row)
    thumb = resolve_thumbnail(row)
    permalink = clean_text(row.get("permalink", ""))
    category = clean_text(row.get("content_category", "")) or "미분류"
    subcategory = clean_text(row.get("content_subcategory", ""))
    content_type = clean_text(row.get("content_type", "")) or "-"
    product_name = clean_text(row.get("product_name", ""))
    campaign_name = clean_text(row.get("campaign_name", ""))
    status = clean_text(row.get("classification_status", ""))
    paid = bool(row.get("has_paid_bool", False))

    posted_at = row.get("posted_at")
    posted_text = posted_at.strftime("%Y.%m.%d") if pd.notna(posted_at) else "-"

    views_col = metric_column("조회수", performance_label)
    reach_col = metric_column("도달수", performance_label)
    interaction_col = metric_column("인터랙션", performance_label)
    saved_col = metric_column("저장", performance_label)

    with st.container(border=True):
        if thumb:
            st.image(thumb, use_container_width=True)
        else:
            st.markdown(
                """
                <div style="height:190px;border-radius:10px;background:#F1F5F9;display:flex;align-items:center;justify-content:center;color:#94A3B8;font-weight:700;">
                    이미지 없음
                </div>
                """,
                unsafe_allow_html=True,
            )

        paid_html = (
            '<span style="display:inline-flex;padding:3px 7px;border-radius:999px;background:#FFF7ED;color:#C2410C;font-size:0.68rem;font-weight:800;">Paid</span>'
            if paid
            else '<span style="display:inline-flex;padding:3px 7px;border-radius:999px;background:#F8FAFC;color:#64748B;font-size:0.68rem;font-weight:800;">Organic</span>'
        )

        st.markdown(
            f"""
            <div style="display:flex;justify-content:space-between;align-items:center;gap:6px;margin:3px 0 7px 0;">
                <div style="font-size:0.73rem;color:#64748B;font-weight:700;">{posted_text} · {content_type}</div>
                <div style="display:flex;gap:5px;align-items:center;">{paid_html}{status_badge_html(status)}</div>
            </div>
            <div style="font-size:0.94rem;line-height:1.4;font-weight:850;color:#0F172A;min-height:2.65rem;margin-bottom:6px;">{title}</div>
            <div style="font-size:0.74rem;color:#64748B;min-height:1.25rem;margin-bottom:8px;">{category}{' · ' + subcategory if subcategory else ''}</div>
            """,
            unsafe_allow_html=True,
        )

        m1, m2 = st.columns(2, gap="small")
        with m1:
            st.caption(compact_metric("조회", row.get(views_col)))
            st.caption(compact_metric("인터랙션", row.get(interaction_col)))
        with m2:
            st.caption(compact_metric("도달", row.get(reach_col)))
            st.caption(compact_metric("저장", row.get(saved_col)))

        extra = []
        if product_name:
            extra.append(f"상품: {product_name}")
        if campaign_name:
            extra.append(f"캠페인: {campaign_name}")
        if extra:
            st.caption(" · ".join(extra))

        if permalink:
            st.link_button("Instagram 열기", permalink, use_container_width=True)
        else:
            st.button("Instagram 링크 없음", disabled=True, use_container_width=True, key=f"no_link_{row.get('media_id','')}")


def render_content_library(tables: dict[str, pd.DataFrame]) -> None:
    content = tables["content"].copy()

    today = datetime.now(KST).date()
    current_end = today - timedelta(days=1)

    st.title("Content Library")
    st.markdown(
        f'<div class="dashboard-subtitle">그리팅 인스타그램 콘텐츠 아카이브 · v{APP_VERSION} · 데이터 기준일 {current_end:%Y.%m.%d}</div>',
        unsafe_allow_html=True,
    )

    if content.empty:
        st.warning("CONTENT_MASTER / CONTENT_LIFETIME 데이터가 없습니다.")
        return

    content["library_title"] = content.apply(resolve_title, axis=1)
    content["posted_year"] = content["posted_at"].dt.year
    content["posted_month"] = content["posted_at"].dt.month

    # --------------------------------------------------------
    # Search + primary controls
    # --------------------------------------------------------
    top_cols = st.columns([2.4, 1.0, 1.0, 1.0, 1.0], gap="medium")

    with top_cols[0]:
        search = st.text_input(
            "콘텐츠 검색",
            placeholder="제목, 캡션, 상품명, 캠페인명, 카테고리 검색",
            key="library_search",
        )

    with top_cols[1]:
        content_type = st.selectbox(
            "유형",
            ["전체", "Feed", "Reels"],
            key="library_content_type",
        )

    with top_cols[2]:
        performance_label = st.selectbox(
            "성과 기준",
            ["전체", "Organic", "Paid"],
            key="library_performance",
            help="Paid 선택 시 광고 집행 콘텐츠만 표시합니다.",
        )

    with top_cols[3]:
        years = sorted(
            [int(year) for year in content["posted_year"].dropna().unique().tolist()],
            reverse=True,
        )
        year_filter = st.selectbox(
            "연도",
            ["전체"] + years,
            key="library_year",
        )

    with top_cols[4]:
        month_filter = st.selectbox(
            "월",
            ["전체"] + list(range(1, 13)),
            key="library_month",
        )

    # --------------------------------------------------------
    # Detail filters
    # --------------------------------------------------------
    with st.expander("상세 분류 필터", expanded=False):
        cols = st.columns(6)

        with cols[0]:
            category = st.multiselect(
                "카테고리",
                unique_values(content, "content_category"),
                key="library_category",
            )
        with cols[1]:
            subcategory = st.multiselect(
                "서브카테고리",
                unique_values(content, "content_subcategory"),
                key="library_subcategory",
            )
        with cols[2]:
            creative_format = st.multiselect(
                "크리에이티브 포맷",
                unique_values(content, "creative_format"),
                key="library_format",
            )
        with cols[3]:
            classification_status = st.multiselect(
                "분류 상태",
                unique_values(content, "classification_status"),
                format_func=lambda x: STATUS_LABELS.get(str(x).upper(), x),
                key="library_status",
            )
        with cols[4]:
            products = st.multiselect(
                "상품",
                unique_values(content, "product_name"),
                key="library_product",
            )
        with cols[5]:
            campaigns = st.multiselect(
                "캠페인",
                unique_values(content, "campaign_name"),
                key="library_campaign",
            )

    # --------------------------------------------------------
    # Apply filters
    # --------------------------------------------------------
    df = content.copy()

    if content_type != "전체":
        df = df[df["content_type"] == content_type].copy()

    df = filter_performance_scope(df, performance_label)

    if year_filter != "전체":
        df = df[df["posted_year"] == int(year_filter)].copy()

    if month_filter != "전체":
        df = df[df["posted_month"] == int(month_filter)].copy()

    filter_specs = [
        ("content_category", category),
        ("content_subcategory", subcategory),
        ("creative_format", creative_format),
        ("classification_status", classification_status),
        ("product_name", products),
        ("campaign_name", campaigns),
    ]

    for column, selected in filter_specs:
        if selected and column in df.columns:
            normalized = df[column].fillna("").astype(str).str.strip()
            df = df[normalized.isin(selected)].copy()

    if search.strip():
        needle = search.strip().lower()
        search_columns = [
            "library_title",
            "caption",
            "content_category",
            "content_subcategory",
            "content_theme",
            "product_name",
            "campaign_name",
            "creative_format",
        ]
        mask = pd.Series(False, index=df.index)
        for column in search_columns:
            if column in df.columns:
                mask = mask | df[column].fillna("").astype(str).str.lower().str.contains(needle, regex=False)
        df = df[mask].copy()

    # --------------------------------------------------------
    # Metric sorting helpers
    # --------------------------------------------------------
    views_col = metric_column("조회수", performance_label)
    reach_col = metric_column("도달수", performance_label)
    interaction_col = metric_column("인터랙션", performance_label)
    saved_col = metric_column("저장", performance_label)

    df["sort_views"] = pd.to_numeric(df.get(views_col), errors="coerce")
    df["sort_reach"] = pd.to_numeric(df.get(reach_col), errors="coerce")
    df["sort_interactions"] = pd.to_numeric(df.get(interaction_col), errors="coerce")
    df["sort_saved"] = pd.to_numeric(df.get(saved_col), errors="coerce")

    # --------------------------------------------------------
    # Summary
    # --------------------------------------------------------
    feed_count = int((df["content_type"] == "Feed").sum()) if "content_type" in df.columns else 0
    reels_count = int((df["content_type"] == "Reels").sum()) if "content_type" in df.columns else 0
    paid_count = int(df["has_paid_bool"].sum()) if "has_paid_bool" in df.columns else 0
    pending_count = (
        int((df["classification_status"].fillna("").astype(str).str.upper() == "PENDING").sum())
        if "classification_status" in df.columns
        else 0
    )

    st.markdown(
        f"""
        <div style="border:1px solid #DBEAFE;border-left:3px solid {COLORS['primary']};border-radius:10px;background:#F8FBFF;padding:10px 13px;margin:4px 0 14px 0;color:#475569;font-size:0.78rem;">
            현재 필터 결과 <b>{len(df):,}개</b> · Feed <b>{feed_count:,}</b> · Reels <b>{reels_count:,}</b> · Paid <b>{paid_count:,}</b> · 미분류 <b>{pending_count:,}</b><br>
            성과 표시는 <b>{performance_label}</b> 기준입니다.
        </div>
        """,
        unsafe_allow_html=True,
    )

    # --------------------------------------------------------
    # Sort / pagination / export
    # --------------------------------------------------------
    render_cols = st.columns([1.3, 1.0, 1.0, 1.2], gap="medium")

    with render_cols[0]:
        sort_label = st.selectbox(
            "정렬 기준",
            list(SORT_OPTIONS.keys()),
            key="library_sort",
        )

    with render_cols[1]:
        page_size = st.selectbox(
            "페이지당 표시",
            [12, 24, 36, 48],
            index=0,
            key="library_page_size",
        )

    sort_column, ascending = SORT_OPTIONS[sort_label]
    df = df.sort_values(sort_column, ascending=ascending, na_position="last").copy()

    total_pages = max(1, math.ceil(len(df) / page_size))

    with render_cols[2]:
        page = st.number_input(
            "페이지",
            min_value=1,
            max_value=total_pages,
            value=min(st.session_state.get("library_page", 1), total_pages),
            step=1,
            key="library_page",
        )

    # CSV is full filtered result, not only current page.
    export_columns = [
        "posted_at",
        "library_title",
        "content_type",
        views_col,
        reach_col,
        interaction_col,
        saved_col,
        "has_paid_bool",
        "content_category",
        "content_subcategory",
        "creative_format",
        "product_name",
        "campaign_name",
        "classification_status",
        "permalink",
    ]
    export_columns = [column for column in export_columns if column in df.columns]
    export_df = df[export_columns].copy()
    export_df = export_df.rename(
        columns={
            "posted_at": "게시일",
            "library_title": "제목",
            "content_type": "유형",
            views_col: "조회수",
            reach_col: "도달수",
            interaction_col: "인터랙션",
            saved_col: "저장",
            "has_paid_bool": "Paid",
            "content_category": "카테고리",
            "content_subcategory": "서브카테고리",
            "creative_format": "크리에이티브 포맷",
            "product_name": "상품",
            "campaign_name": "캠페인",
            "classification_status": "분류상태",
            "permalink": "Instagram",
        }
    )
    if "게시일" in export_df.columns:
        export_df["게시일"] = pd.to_datetime(export_df["게시일"], errors="coerce").dt.strftime("%Y-%m-%d %H:%M")

    with render_cols[3]:
        st.markdown('<div style="height:1.72rem"></div>', unsafe_allow_html=True)
        st.download_button(
            "CSV 다운로드",
            data=export_df.to_csv(index=False).encode("utf-8-sig"),
            file_name=f"greating_content_library_{current_end:%Y%m%d}.csv",
            mime="text/csv",
            use_container_width=True,
            disabled=export_df.empty,
        )

    # --------------------------------------------------------
    # Card grid
    # --------------------------------------------------------
    if df.empty:
        st.info("현재 필터 조건에 해당하는 콘텐츠가 없습니다.")
        return

    start_index = (int(page) - 1) * page_size
    end_index = min(start_index + page_size, len(df))
    page_df = df.iloc[start_index:end_index].copy()

    st.caption(f"{start_index + 1:,} - {end_index:,} / 총 {len(df):,}개")

    rows = [page_df.iloc[i:i + 4] for i in range(0, len(page_df), 4)]
    for row_df in rows:
        columns = st.columns(4, gap="medium")
        for column, (_, row) in zip(columns, row_df.iterrows()):
            with column:
                render_card(row, performance_label)

    st.divider()
    st.caption(
        "신규 콘텐츠의 카테고리/서브카테고리/포맷은 CONTENT_MASTER의 드롭다운에서 관리합니다. "
        "미분류 콘텐츠는 classification_status=PENDING으로 표시됩니다."
    )


render_content_library(get_tables())
