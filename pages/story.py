from __future__ import annotations

import html
from datetime import date, datetime, timedelta

import pandas as pd
import plotly.express as px
import plotly.graph_objects as go
import streamlit as st
from plotly.subplots import make_subplots

from dashboard.config import APP_VERSION, COLORS, KST
from dashboard.core import chart_layout, fmt_int, get_tables, plot_config, render_section_title


# ============================================================
# Page: Story
# ============================================================

STORY_METRICS = {
    "조회수": "views",
    "도달수": "reach",
    "인터랙션": "total_interactions",
    "링크 클릭": "link_clicks",
}

ACTION_LABELS = {
    "shares": "공유",
    "replies": "답장",
    "link_clicks": "링크 클릭",
    "profile_visits": "프로필 방문",
    "follows": "팔로우",
}

NAVIGATION_LABELS = {
    "tap_forward": "앞으로 탭",
    "tap_back": "뒤로 탭",
    "tap_exit": "종료 탭",
    "swipe_forward": "다음 스토리 이동",
}


# ============================================================
# Helpers
# ============================================================


def _numeric(df: pd.DataFrame, column: str) -> pd.Series:
    if column not in df.columns:
        return pd.Series(index=df.index, dtype="float64")
    return pd.to_numeric(df[column], errors="coerce")


def _sum(df: pd.DataFrame, column: str) -> float:
    values = _numeric(df, column)
    if values.notna().any():
        return float(values.sum(min_count=1))
    return 0.0


def _mean(df: pd.DataFrame, column: str) -> float:
    values = _numeric(df, column)
    if values.notna().any():
        return float(values.mean())
    return 0.0


def _period_filter(df: pd.DataFrame, start: date, end: date) -> pd.DataFrame:
    if df.empty or "posted_date" not in df.columns:
        return df.iloc[0:0].copy()
    mask = (df["posted_date"] >= start) & (df["posted_date"] <= end)
    return df.loc[mask].copy()


def _render_story_kpi(*, label: str, value: str, accent: str, subline: str) -> None:
    st.markdown(
        (
            f'<div class="kpi-card" style="--accent:{accent};min-height:126px">'
            f'<div class="kpi-label">{html.escape(label)}</div>'
            f'<div class="kpi-value-row"><div class="kpi-value">{html.escape(value)}</div></div>'
            f'<div class="kpi-subline" style="margin-top:13px">{html.escape(subline)}</div>'
            f'</div>'
        ),
        unsafe_allow_html=True,
    )


def _safe_image_url(row: pd.Series) -> str:
    """Return a still image URL suitable for Story cards/tables.

    VIDEO stories use Meta's thumbnail_url. IMAGE stories fall back to
    media_url. We intentionally do not send a VIDEO media_url (MP4) to
    st.image(), because that renders as a broken image.
    """
    thumbnail_url = str(row.get("thumbnail_url", "") or "").strip()
    if thumbnail_url:
        return thumbnail_url

    media_type = str(row.get("media_type", "") or "").strip().upper()
    media_url = str(row.get("media_url", "") or "").strip()

    if media_type == "IMAGE" and media_url:
        return media_url

    return ""


def _latest_collected_text(story: pd.DataFrame) -> str:
    if story.empty or "last_collected_at" not in story.columns:
        return "-"
    values = pd.to_datetime(story["last_collected_at"], errors="coerce").dropna()
    if values.empty:
        return "-"
    latest = values.max()
    return latest.strftime("%Y.%m.%d %H:%M")


def _story_type_label(value: object) -> str:
    raw = str(value or "").strip().upper()
    if raw == "VIDEO":
        return "Video"
    if raw == "IMAGE":
        return "Image"
    return raw.title() if raw else "Unknown"


# ============================================================
# Page renderer
# ============================================================


def render_story(tables: dict[str, pd.DataFrame]) -> None:
    story = tables.get("story", pd.DataFrame()).copy()

    st.title("Story")
    st.markdown(
        f'<div class="dashboard-subtitle">스토리 성과 분석 · v{APP_VERSION} · 최신 수집 {_latest_collected_text(story)}</div>',
        unsafe_allow_html=True,
    )

    if story.empty:
        st.info("아직 STORY_HISTORY에 수집된 스토리 데이터가 없습니다.")
        return

    story = story.dropna(subset=["posted_at"]).copy()
    if story.empty:
        st.info("게시일시가 확인되는 스토리 데이터가 없습니다.")
        return

    available_min = story["posted_date"].min()
    available_max = story["posted_date"].max()
    today = datetime.now(KST).date()

    # --------------------------------------------------------
    # Filters
    # --------------------------------------------------------
    filter_cols = st.columns([1.35, 1.1, 1.1, 1.35], gap="medium")

    with filter_cols[0]:
        period_preset = st.selectbox(
            "분석 기간",
            ["최근 7일", "최근 30일", "최근 90일", "전체", "직접 선택"],
            index=1,
            key="story_period",
        )

    with filter_cols[1]:
        type_options = ["전체"] + sorted(
            [_story_type_label(value) for value in story["media_type"].dropna().unique().tolist()]
        )
        type_options = list(dict.fromkeys(type_options))
        media_type_filter = st.selectbox("스토리 유형", type_options, key="story_media_type")

    with filter_cols[2]:
        top_metric_label = st.selectbox(
            "Top Story 기준",
            list(STORY_METRICS.keys()),
            index=1,
            key="story_top_metric",
        )

    with filter_cols[3]:
        st.markdown(
            '<div class="filter-note">Story는 24시간 콘텐츠이므로 전일 종료가 아니라 <strong>수집된 최신값</strong>을 기준으로 봅니다.</div>',
            unsafe_allow_html=True,
        )

    if period_preset == "최근 7일":
        period_end = min(today, available_max)
        period_start = max(available_min, period_end - timedelta(days=6))
    elif period_preset == "최근 30일":
        period_end = min(today, available_max)
        period_start = max(available_min, period_end - timedelta(days=29))
    elif period_preset == "최근 90일":
        period_end = min(today, available_max)
        period_start = max(available_min, period_end - timedelta(days=89))
    elif period_preset == "전체":
        period_start, period_end = available_min, available_max
    else:
        picked = st.date_input(
            "직접 기간 선택",
            value=(available_min, available_max),
            min_value=available_min,
            max_value=available_max,
            key="story_custom_period",
        )
        if isinstance(picked, (tuple, list)) and len(picked) == 2:
            period_start, period_end = picked
        else:
            period_start, period_end = available_min, available_max

    df = _period_filter(story, period_start, period_end)

    if media_type_filter != "전체":
        df = df[df["media_type"].apply(_story_type_label) == media_type_filter].copy()

    if df.empty:
        st.warning("선택한 조건에 해당하는 Story 데이터가 없습니다.")
        return

    low_volume_count = 0
    if "insight_status" in df.columns:
        low_volume_count = int(
            df["insight_status"].astype(str).str.upper().eq("LOW_VOLUME").sum()
        )

    st.markdown(
        (
            '<div class="dynamic-note">'
            f'분석 범위: <strong>{period_start:%Y.%m.%d} - {period_end:%Y.%m.%d}</strong> · '
            f'스토리 유형 <strong>{html.escape(media_type_filter)}</strong> · '
            f'수집 Story <strong>{len(df):,}개</strong>'
            + (f' · 저볼륨 {low_volume_count:,}개' if low_volume_count else "")
            + '</div>'
        ),
        unsafe_allow_html=True,
    )

    # --------------------------------------------------------
    # KPI
    # --------------------------------------------------------
    render_section_title(
        "Story 핵심 성과",
        "선택 기간 Story의 수집된 최신 누적값을 기준으로 계산합니다.",
    )

    kpi_cols = st.columns(5, gap="medium")
    with kpi_cols[0]:
        _render_story_kpi(
            label="스토리수",
            value=f"{len(df):,}개",
            accent=COLORS["purple"],
            subline=f"{period_start:%m.%d} - {period_end:%m.%d}",
        )
    with kpi_cols[1]:
        _render_story_kpi(
            label="평균 조회수",
            value=fmt_int(_mean(df, "views")),
            accent=COLORS["cyan"],
            subline="Story 1개당 평균",
        )
    with kpi_cols[2]:
        _render_story_kpi(
            label="평균 도달수",
            value=fmt_int(_mean(df, "reach")),
            accent=COLORS["primary"],
            subline="Story 1개당 평균",
        )
    with kpi_cols[3]:
        _render_story_kpi(
            label="평균 인터랙션",
            value=fmt_int(_mean(df, "total_interactions")),
            accent=COLORS["green"],
            subline="공유·답장 등 Meta 집계값",
        )
    with kpi_cols[4]:
        _render_story_kpi(
            label="링크 클릭",
            value=fmt_int(_sum(df, "link_clicks")),
            accent=COLORS["orange"],
            subline="선택 기간 합계",
        )

    st.write("")

    # --------------------------------------------------------
    # Trend + action mix
    # --------------------------------------------------------
    render_section_title(
        "발행 및 반응 흐름",
        "일별 발행수와 평균 도달, Story에서 발생한 주요 반응을 함께 봅니다.",
    )

    trend_col, action_col = st.columns([1.55, 1], gap="large")

    daily = (
        df.assign(day=pd.to_datetime(df["posted_at"]).dt.date)
        .groupby("day", dropna=False)
        .agg(
            stories=("story_id", "nunique"),
            avg_reach=("reach", "mean"),
        )
        .reset_index()
        .sort_values("day")
    )
    daily["day_label"] = pd.to_datetime(daily["day"]).dt.strftime("%m/%d")

    with trend_col:
        fig = make_subplots(specs=[[{"secondary_y": True}]])
        fig.add_trace(
            go.Bar(
                x=daily["day_label"],
                y=daily["stories"],
                name="발행수",
                marker_color=COLORS["purple"],
                hovertemplate="%{x}<br>발행 %{y:,.0f}개<extra></extra>",
            ),
            secondary_y=False,
        )
        fig.add_trace(
            go.Scatter(
                x=daily["day_label"],
                y=daily["avg_reach"],
                name="평균 도달",
                mode="lines+markers",
                line=dict(color=COLORS["cyan"], width=2.5),
                marker=dict(size=6),
                hovertemplate="%{x}<br>평균 도달 %{y:,.0f}<extra></extra>",
            ),
            secondary_y=True,
        )
        fig.update_layout(**chart_layout(285, showlegend=True))
        fig.update_layout(
            legend=dict(orientation="h", y=1.08, x=0),
            bargap=0.42,
        )
        fig.update_yaxes(title_text="발행수", secondary_y=False, showgrid=False, rangemode="tozero")
        fig.update_yaxes(title_text="평균 도달", secondary_y=True, showgrid=True, rangemode="tozero")
        st.plotly_chart(fig, use_container_width=True, config=plot_config())

    with action_col:
        action_rows = []
        action_colors = [
            COLORS["green"],
            COLORS["primary"],
            COLORS["orange"],
            COLORS["pink"],
            COLORS["purple"],
        ]
        for index, (column, label) in enumerate(ACTION_LABELS.items()):
            action_rows.append(
                {
                    "action": label,
                    "value": _sum(df, column),
                    "color": action_colors[index % len(action_colors)],
                }
            )
        action_df = pd.DataFrame(action_rows).sort_values("value", ascending=True)

        fig = go.Figure(
            go.Bar(
                x=action_df["value"],
                y=action_df["action"],
                orientation="h",
                marker_color=action_df["color"],
                text=[fmt_int(v) for v in action_df["value"]],
                textposition="outside",
                cliponaxis=False,
                hovertemplate="%{y}<br>%{x:,.0f}<extra></extra>",
            )
        )
        fig.update_layout(**chart_layout(285))
        fig.update_layout(margin=dict(l=8, r=45, t=18, b=8))
        fig.update_xaxes(title_text="합계", rangemode="tozero")
        fig.update_yaxes(title_text="")
        st.plotly_chart(fig, use_container_width=True, config=plot_config())

    # --------------------------------------------------------
    # Top stories
    # --------------------------------------------------------
    st.write("")
    render_section_title(
        "Top Story",
        "선택한 지표 기준 상위 Story를 빠르게 확인합니다.",
    )

    metric_col = STORY_METRICS[top_metric_label]
    ranked = df.copy()
    ranked[metric_col] = _numeric(ranked, metric_col)
    ranked = ranked.sort_values([metric_col, "posted_at"], ascending=[False, False]).head(5)

    card_cols = st.columns(5, gap="medium")
    for rank, ((_, row), col) in enumerate(zip(ranked.iterrows(), card_cols), start=1):
        with col:
            st.markdown(f'<span class="top-rank">TOP {rank}</span>', unsafe_allow_html=True)
            image_url = _safe_image_url(row)
            if image_url:
                try:
                    st.image(image_url, use_container_width=True)
                except Exception:
                    st.markdown("🖼️ 미리보기 만료")
            else:
                st.markdown("🖼️ 미리보기 없음")

            posted_at = pd.to_datetime(row.get("posted_at"), errors="coerce")
            posted_text = posted_at.strftime("%m.%d %H:%M") if not pd.isna(posted_at) else "-"
            st.markdown(
                f'<div class="top-title">{html.escape(posted_text)} · {html.escape(_story_type_label(row.get("media_type")))}</div>',
                unsafe_allow_html=True,
            )
            st.markdown(
                f'<div class="top-score">{html.escape(top_metric_label)} {fmt_int(row.get(metric_col))}</div>',
                unsafe_allow_html=True,
            )
            st.markdown(
                f'<div class="top-meta">도달 {fmt_int(row.get("reach"))} · 인터랙션 {fmt_int(row.get("total_interactions"))}</div>',
                unsafe_allow_html=True,
            )
            permalink = str(row.get("permalink", "") or "").strip()
            if permalink:
                st.link_button("Instagram 열기", permalink, use_container_width=True)

    # --------------------------------------------------------
    # Navigation signals
    # --------------------------------------------------------
    st.write("")
    render_section_title(
        "Story 이동 행동",
        "탭·이동 이벤트의 합계입니다. 비율이 아니라 이벤트 발생량이므로 방향성 확인용으로 봅니다.",
    )

    nav_rows = []
    nav_colors = [COLORS["cyan"], COLORS["green"], COLORS["orange"], COLORS["pink"]]
    for index, (column, label) in enumerate(NAVIGATION_LABELS.items()):
        nav_rows.append(
            {
                "action": label,
                "value": _sum(df, column),
                "color": nav_colors[index % len(nav_colors)],
            }
        )
    nav_df = pd.DataFrame(nav_rows).sort_values("value", ascending=False)

    fig = go.Figure(
        go.Bar(
            x=nav_df["action"],
            y=nav_df["value"],
            marker_color=nav_df["color"],
            text=[fmt_int(v) for v in nav_df["value"]],
            textposition="outside",
            cliponaxis=False,
            hovertemplate="%{x}<br>%{y:,.0f}<extra></extra>",
        )
    )
    fig.update_layout(**chart_layout(245))
    fig.update_layout(margin=dict(l=8, r=8, t=18, b=35))
    fig.update_yaxes(title_text="이벤트 수", rangemode="tozero")
    fig.update_xaxes(title_text="")
    st.plotly_chart(fig, use_container_width=True, config=plot_config())

    # --------------------------------------------------------
    # Detail table
    # --------------------------------------------------------
    st.write("")
    render_section_title(
        "Story 상세",
        "최신 게시순으로 상세 성과를 확인하고 현재 필터 결과를 CSV로 내려받을 수 있습니다.",
    )

    detail = df.copy().sort_values("posted_at", ascending=False)
    detail["썸네일"] = detail.apply(_safe_image_url, axis=1)
    detail["게시일시"] = pd.to_datetime(detail["posted_at"], errors="coerce").dt.strftime("%Y-%m-%d %H:%M")
    detail["유형"] = detail["media_type"].apply(_story_type_label)

    display_specs = [
        ("썸네일", "썸네일"),
        ("게시일시", "게시일시"),
        ("유형", "유형"),
        ("views", "조회수"),
        ("reach", "도달수"),
        ("total_interactions", "인터랙션"),
        ("shares", "공유"),
        ("replies", "답장"),
        ("link_clicks", "링크 클릭"),
        ("profile_visits", "프로필 방문"),
        ("follows", "팔로우"),
        ("tap_forward", "앞으로 탭"),
        ("tap_back", "뒤로 탭"),
        ("tap_exit", "종료 탭"),
        ("swipe_forward", "다음 스토리"),
        ("permalink", "Instagram"),
    ]

    table = pd.DataFrame(index=detail.index)
    for source, label in display_specs:
        if source in detail.columns:
            table[label] = detail[source]
        else:
            table[label] = ""

    numeric_labels = [
        "조회수", "도달수", "인터랙션", "공유", "답장", "링크 클릭",
        "프로필 방문", "팔로우", "앞으로 탭", "뒤로 탭", "종료 탭", "다음 스토리",
    ]
    for column in numeric_labels:
        table[column] = pd.to_numeric(table[column], errors="coerce")

    st.dataframe(
        table,
        use_container_width=True,
        hide_index=True,
        height=min(680, 92 + len(table) * 38),
        column_config={
            "썸네일": st.column_config.ImageColumn("썸네일", width="small"),
            "게시일시": st.column_config.TextColumn("게시일시", width="medium"),
            "유형": st.column_config.TextColumn("유형", width="small"),
            **{
                column: st.column_config.NumberColumn(column, format="%,.0f", width="small")
                for column in numeric_labels
            },
            "Instagram": st.column_config.LinkColumn("Instagram", display_text="열기", width="small"),
        },
    )

    csv_table = table.drop(columns=["썸네일"]).copy()
    csv_bytes = csv_table.to_csv(index=False).encode("utf-8-sig")
    st.download_button(
        "CSV 다운로드",
        data=csv_bytes,
        file_name=f"greating_story_{period_start:%Y%m%d}_{period_end:%Y%m%d}.csv",
        mime="text/csv",
        use_container_width=False,
    )

    st.caption(
        "IMAGE는 media_url, VIDEO는 Meta thumbnail_url을 대표 이미지로 사용합니다. "
        "Meta URL은 시간이 지나면 만료될 수 있어 과거 Story의 미리보기가 보이지 않을 수 있으며, "
        "성과 수치는 STORY_HISTORY에 저장된 값을 사용합니다."
    )


render_story(get_tables())
