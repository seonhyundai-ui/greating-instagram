from __future__ import annotations

import html
from datetime import date, datetime, timedelta

import pandas as pd
import plotly.graph_objects as go
import streamlit as st
from plotly.subplots import make_subplots

from dashboard.config import APP_VERSION, COLORS, KST
from dashboard.core import (
    chart_layout,
    fmt_int,
    fmt_period,
    fmt_won,
    get_tables,
    plot_config,
    previous_month_same_period,
    previous_year_same_period,
    render_section_title,
    safe_pct_change,
)


# ============================================================
# Page: Ads
# ============================================================

ADS_METRICS = {
    "광고비": "spend",
    "노출수": "impressions",
    "클릭수": "clicks",
    "CTR": "ctr_calc",
    "CPC": "cpc_calc",
    "Paid 인터랙션": "paid_interactions",
}

CAMPAIGN_CHART_METRICS = {
    "광고비": "spend",
    "클릭수": "clicks",
    "CTR": "ctr_calc",
    "Paid 인터랙션": "paid_interactions",
}

CONTENT_TOP_METRICS = {
    "광고비": "spend",
    "클릭수": "clicks",
    "Paid 인터랙션": "paid_interactions",
    "CTR": "ctr_calc",
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


def _safe_div(numerator: float, denominator: float, multiplier: float = 1.0) -> float:
    if denominator == 0:
        return 0.0
    return numerator / denominator * multiplier


def _period_filter(df: pd.DataFrame, start: date, end: date) -> pd.DataFrame:
    if df.empty or "ad_date" not in df.columns:
        return df.iloc[0:0].copy()
    mask = (df["ad_date"] >= start) & (df["ad_date"] <= end)
    return df.loc[mask].copy()


def _shift_year_safe(value: date, years: int = -1) -> date:
    target_year = value.year + years
    try:
        return value.replace(year=target_year)
    except ValueError:
        return value.replace(year=target_year, day=28)


def _comparison_periods(
    preset: str,
    current_start: date,
    current_end: date,
) -> tuple[tuple[date, date], tuple[date, date], str, str]:
    if preset == "이번달":
        prev_start, prev_end = previous_month_same_period(current_start, current_end)
        yoy_start, yoy_end = previous_year_same_period(current_start, current_end)
        return (prev_start, prev_end), (yoy_start, yoy_end), "전월동기", "전년동기"

    days = (current_end - current_start).days + 1
    prev_end = current_start - timedelta(days=1)
    prev_start = prev_end - timedelta(days=days - 1)
    yoy_start = _shift_year_safe(current_start, -1)
    yoy_end = _shift_year_safe(current_end, -1)
    return (prev_start, prev_end), (yoy_start, yoy_end), "직전동기간", "전년동기간"


def _apply_ads_filters(
    df: pd.DataFrame,
    campaign_names: list[str],
    creative_scope: str,
) -> pd.DataFrame:
    result = df.copy()

    if campaign_names and "campaign_name" in result.columns:
        result = result[result["campaign_name"].astype(str).isin(campaign_names)].copy()

    if creative_scope != "전체" and "creative_source" in result.columns:
        if creative_scope == "게시물 연결":
            result = result[result["creative_source"].astype(str).eq("PUBLISHED_CONTENT")].copy()
        elif creative_scope == "광고 전용":
            result = result[result["creative_source"].astype(str).eq("AD_ONLY")].copy()

    return result


def _ads_summary(df: pd.DataFrame) -> dict[str, float]:
    spend = _sum(df, "spend")
    impressions = _sum(df, "impressions")
    clicks = _sum(df, "clicks")
    interactions = _sum(df, "paid_interactions")
    saved = _sum(df, "paid_saved")
    gross_reach = _sum(df, "reach_paid")

    return {
        "spend": spend,
        "impressions": impressions,
        "clicks": clicks,
        "paid_interactions": interactions,
        "paid_saved": saved,
        "reach_paid_gross": gross_reach,
        "ctr_calc": _safe_div(clicks, impressions, 100.0),
        "cpc_calc": _safe_div(spend, clicks),
        "cpm_calc": _safe_div(spend, impressions, 1000.0),
        "ad_count": float(df["ad_id"].astype(str).nunique()) if not df.empty and "ad_id" in df.columns else 0.0,
        "content_count": float(
            df.loc[df.get("content_media_id", pd.Series(index=df.index, dtype=str)).astype(str).str.strip().ne(""), "content_media_id"]
            .astype(str)
            .nunique()
        ) if not df.empty and "content_media_id" in df.columns else 0.0,
    }


def _fmt_metric(metric: str, value: float) -> str:
    if metric in {"spend", "cpc_calc", "cpm_calc"}:
        return fmt_won(value)
    if metric == "ctr_calc":
        return f"{value:.2f}%"
    return fmt_int(value)


def _delta_style(value: float | None, direction: str = "higher") -> tuple[str, str]:
    if value is None or pd.isna(value):
        return "#64748B", "#F1F5F9"

    value_f = float(value)
    if abs(value_f) < 1e-12:
        return "#64748B", "#F1F5F9"

    if direction == "neutral":
        return COLORS["primary"], COLORS["primary_soft"]

    good = value_f > 0 if direction == "higher" else value_f < 0
    if good:
        return "#047857", "#ECFDF5"
    return "#DC2626", "#FEF2F2"


def _delta_text(value: float | None) -> str:
    if value is None or pd.isna(value):
        return "-"
    arrow = "↑" if value > 0 else "↓" if value < 0 else "•"
    sign = "+" if value > 0 else ""
    return f"{arrow} {sign}{value:.1f}%"


def _render_ads_kpi(
    *,
    label: str,
    value: str,
    accent: str,
    prev_delta: float | None,
    yoy_delta: float | None,
    prev_label: str,
    yoy_label: str,
    direction: str,
    subline: str,
) -> None:
    prev_color, prev_bg = _delta_style(prev_delta, direction)
    yoy_color, yoy_bg = _delta_style(yoy_delta, direction)

    st.markdown(
        (
            f'<div class="kpi-card" style="--accent:{accent};min-height:148px">'
            f'<div class="kpi-label">{html.escape(label)}</div>'
            f'<div class="kpi-value-row"><div class="kpi-value">{html.escape(value)}</div></div>'
            f'<div class="kpi-compare-row">'
            f'<span class="delta-pill" style="color:{prev_color};background:{prev_bg}">{html.escape(prev_label)} {_delta_text(prev_delta)}</span>'
            f'<span class="delta-pill" style="color:{yoy_color};background:{yoy_bg}">{html.escape(yoy_label)} {_delta_text(yoy_delta)}</span>'
            f'</div>'
            f'<div class="kpi-subline">{html.escape(subline)}</div>'
            f'</div>'
        ),
        unsafe_allow_html=True,
    )


def _aggregate_campaign(df: pd.DataFrame) -> pd.DataFrame:
    if df.empty:
        return pd.DataFrame()

    rows = []
    for campaign_name, group in df.groupby("campaign_name", dropna=False):
        summary = _ads_summary(group)
        rows.append(
            {
                "campaign_name": str(campaign_name or "(캠페인명 없음)"),
                **summary,
            }
        )

    result = pd.DataFrame(rows)
    if not result.empty:
        result = result.sort_values("spend", ascending=False)
    return result


def _aggregate_ads(df: pd.DataFrame) -> pd.DataFrame:
    if df.empty:
        return pd.DataFrame()

    rows = []
    group_cols = [c for c in ["ad_id", "ad_name", "campaign_name", "content_media_id", "creative_source"] if c in df.columns]
    for keys, group in df.groupby(group_cols, dropna=False):
        if not isinstance(keys, tuple):
            keys = (keys,)
        key_map = dict(zip(group_cols, keys))
        summary = _ads_summary(group)
        rows.append({**key_map, **summary})

    result = pd.DataFrame(rows)
    if not result.empty:
        result = result.sort_values("spend", ascending=False)
    return result


def _content_lookup(master: pd.DataFrame) -> pd.DataFrame:
    if master.empty:
        return pd.DataFrame(columns=["media_id"])

    keep = [
        c for c in [
            "media_id",
            "ai_title",
            "manual_title",
            "caption",
            "content_category",
            "content_subcategory",
            "content_type",
            "thumbnail_url",
            "media_url",
            "permalink",
        ]
        if c in master.columns
    ]
    return master[keep].drop_duplicates(subset=["media_id"]).copy()


def _display_title(row: pd.Series) -> str:
    for column in ["manual_title", "ai_title", "caption", "ad_name"]:
        value = str(row.get(column, "") or "").strip()
        if value:
            return value.splitlines()[0][:70]
    return "제목 없음"


def _safe_image_url(row: pd.Series) -> str:
    for column in ["thumbnail_url", "media_url"]:
        value = str(row.get(column, "") or "").strip()
        if value:
            return value
    return ""


# ============================================================
# Page renderer
# ============================================================


def render_ads(tables: dict[str, pd.DataFrame]) -> None:
    ads = tables.get("ads", pd.DataFrame()).copy()
    master = tables.get("master", pd.DataFrame()).copy()

    st.title("Ads")

    if ads.empty:
        st.info("아직 ADS_DAILY에 광고 데이터가 없습니다.")
        return

    ads = ads.dropna(subset=["date"]).copy()
    if ads.empty:
        st.info("날짜를 확인할 수 있는 광고 데이터가 없습니다.")
        return

    latest_date = ads["ad_date"].max()
    earliest_date = ads["ad_date"].min()

    st.markdown(
        f'<div class="dashboard-subtitle">Instagram 광고 성과 분석 · v{APP_VERSION} · 데이터 기준일 {latest_date:%Y.%m.%d}</div>',
        unsafe_allow_html=True,
    )

    # --------------------------------------------------------
    # Filters
    # --------------------------------------------------------
    filter_cols = st.columns([1.2, 2.2, 1.3], gap="medium")

    with filter_cols[0]:
        period_preset = st.selectbox(
            "분석 기간",
            ["이번달", "최근 30일", "최근 90일", "올해", "직접 선택"],
            index=0,
            key="ads_period",
        )

    if period_preset == "이번달":
        period_start = latest_date.replace(day=1)
        period_end = latest_date
    elif period_preset == "최근 30일":
        period_end = latest_date
        period_start = max(earliest_date, period_end - timedelta(days=29))
    elif period_preset == "최근 90일":
        period_end = latest_date
        period_start = max(earliest_date, period_end - timedelta(days=89))
    elif period_preset == "올해":
        period_end = latest_date
        period_start = max(earliest_date, date(latest_date.year, 1, 1))
    else:
        picked = st.date_input(
            "직접 기간 선택",
            value=(latest_date.replace(day=1), latest_date),
            min_value=earliest_date,
            max_value=latest_date,
            key="ads_custom_period",
        )
        if isinstance(picked, (tuple, list)) and len(picked) == 2:
            period_start, period_end = picked
        else:
            period_start, period_end = latest_date.replace(day=1), latest_date

    all_campaigns = sorted(
        [
            value
            for value in ads.get("campaign_name", pd.Series(dtype=str)).astype(str).str.strip().unique().tolist()
            if value
        ]
    )

    with filter_cols[1]:
        campaign_filter = st.multiselect(
            "캠페인",
            options=all_campaigns,
            default=[],
            placeholder="전체 캠페인",
            key="ads_campaign_filter",
        )

    with filter_cols[2]:
        creative_scope = st.selectbox(
            "광고 유형",
            ["전체", "게시물 연결", "광고 전용"],
            index=0,
            key="ads_creative_scope",
        )

    (prev_start, prev_end), (yoy_start, yoy_end), prev_label, yoy_label = _comparison_periods(
        period_preset,
        period_start,
        period_end,
    )

    current_df = _apply_ads_filters(_period_filter(ads, period_start, period_end), campaign_filter, creative_scope)
    prev_df = _apply_ads_filters(_period_filter(ads, prev_start, prev_end), campaign_filter, creative_scope)
    yoy_df = _apply_ads_filters(_period_filter(ads, yoy_start, yoy_end), campaign_filter, creative_scope)

    if current_df.empty:
        st.warning("선택한 조건에 해당하는 광고 데이터가 없습니다.")
        return

    current = _ads_summary(current_df)
    prev = _ads_summary(prev_df)
    yoy = _ads_summary(yoy_df)

    st.markdown(
        (
            '<div class="dynamic-note">'
            f'현재 <strong>{fmt_period(period_start, period_end)}</strong> · '
            f'{html.escape(prev_label)} <strong>{fmt_period(prev_start, prev_end)}</strong> · '
            f'{html.escape(yoy_label)} <strong>{fmt_period(yoy_start, yoy_end)}</strong> · '
            f'캠페인 <strong>{"전체" if not campaign_filter else f"{len(campaign_filter):,}개 선택"}</strong> · '
            f'광고 유형 <strong>{html.escape(creative_scope)}</strong>'
            '</div>'
        ),
        unsafe_allow_html=True,
    )

    # --------------------------------------------------------
    # KPI
    # --------------------------------------------------------
    render_section_title(
        "광고 핵심 성과",
        "CTR·CPC·CPM은 기간 합산값으로 다시 계산합니다. 단순 일별 평균이 아닙니다.",
    )

    kpis = [
        ("광고비", "spend", COLORS["pink"], "neutral"),
        ("노출수", "impressions", COLORS["purple"], "higher"),
        ("클릭수", "clicks", COLORS["primary"], "higher"),
        ("CTR", "ctr_calc", COLORS["cyan"], "higher"),
        ("CPC", "cpc_calc", COLORS["orange"], "lower"),
        ("Paid 인터랙션", "paid_interactions", COLORS["green"], "higher"),
    ]

    kpi_cols = st.columns(3, gap="medium")
    for idx, (label, metric, accent, direction) in enumerate(kpis):
        with kpi_cols[idx % 3]:
            _render_ads_kpi(
                label=label,
                value=_fmt_metric(metric, current[metric]),
                accent=accent,
                prev_delta=safe_pct_change(current[metric], prev[metric]),
                yoy_delta=safe_pct_change(current[metric], yoy[metric]),
                prev_label=f"{prev_label} 대비",
                yoy_label=f"{yoy_label} 대비",
                direction=direction,
                subline=(
                    f"광고 {int(current['ad_count']):,}개 · 연결 콘텐츠 {int(current['content_count']):,}개"
                    if idx == 0
                    else f"기간 합산 기준 · CPM {_fmt_metric('cpm_calc', current['cpm_calc'])}" if idx == 3
                    else "선택 조건 기준"
                ),
            )

    st.markdown(
        '<div class="section-note" style="margin-top:4px">※ 기간 도달수는 ADS_DAILY의 일별 Reach를 합치면 동일 사용자가 중복될 수 있어 핵심 KPI에서 제외했습니다. 상세표의 도달수는 “일별 합산·중복 포함” 값입니다.</div>',
        unsafe_allow_html=True,
    )

    # --------------------------------------------------------
    # Period comparison + trend
    # --------------------------------------------------------
    render_section_title("기간 비교 & 일별 추이")
    left, right = st.columns([0.95, 1.45], gap="large")

    with left:
        compare_rows = []
        for label, metric in [
            ("광고비", "spend"),
            ("노출수", "impressions"),
            ("클릭수", "clicks"),
            ("CTR", "ctr_calc"),
            ("CPC", "cpc_calc"),
            ("Paid 인터랙션", "paid_interactions"),
        ]:
            compare_rows.append(
                {
                    "지표": label,
                    "현재": _fmt_metric(metric, current[metric]),
                    prev_label: _fmt_metric(metric, prev[metric]),
                    yoy_label: _fmt_metric(metric, yoy[metric]),
                }
            )
        compare_df = pd.DataFrame(compare_rows)
        st.dataframe(compare_df, hide_index=True, use_container_width=True, height=285)

    with right:
        daily = (
            current_df.groupby("ad_date", as_index=False)
            .agg(
                spend=("spend", "sum"),
                impressions=("impressions", "sum"),
                clicks=("clicks", "sum"),
            )
            .sort_values("ad_date")
        )
        daily["ctr_calc"] = daily.apply(
            lambda r: _safe_div(float(r["clicks"]), float(r["impressions"]), 100.0),
            axis=1,
        )

        fig = make_subplots(specs=[[{"secondary_y": True}]])
        fig.add_trace(
            go.Bar(
                x=daily["ad_date"],
                y=daily["spend"],
                name="광고비",
                marker_color=COLORS["primary"],
                hovertemplate="%{x|%m/%d}<br>광고비 ₩%{y:,.0f}<extra></extra>",
            ),
            secondary_y=False,
        )
        fig.add_trace(
            go.Scatter(
                x=daily["ad_date"],
                y=daily["ctr_calc"],
                name="CTR",
                mode="lines+markers",
                line=dict(color=COLORS["orange"], width=2.5),
                marker=dict(size=6),
                hovertemplate="%{x|%m/%d}<br>CTR %{y:.2f}%<extra></extra>",
            ),
            secondary_y=True,
        )
        fig.update_layout(**chart_layout(285, showlegend=True))
        fig.update_layout(legend=dict(orientation="h", y=1.12, x=0))
        fig.update_yaxes(title_text="광고비", tickprefix="₩", tickformat=",.0f", secondary_y=False)
        fig.update_yaxes(title_text="CTR", ticksuffix="%", secondary_y=True)
        st.plotly_chart(fig, use_container_width=True, config=plot_config())

    # --------------------------------------------------------
    # Campaign performance
    # --------------------------------------------------------
    render_section_title(
        "캠페인 성과",
        "선택 기간 캠페인별 합산 성과입니다. CTR·CPC·CPM은 캠페인 합산값에서 재계산합니다.",
    )

    campaign_df = _aggregate_campaign(current_df)
    if campaign_df.empty:
        st.info("표시할 캠페인 데이터가 없습니다.")
    else:
        control_cols = st.columns([1.1, 3.2], gap="medium")
        with control_cols[0]:
            campaign_metric_label = st.selectbox(
                "대표 지표",
                list(CAMPAIGN_CHART_METRICS.keys()),
                index=0,
                key="ads_campaign_metric",
            )
        campaign_metric = CAMPAIGN_CHART_METRICS[campaign_metric_label]

        top_campaign = campaign_df.nlargest(10, campaign_metric).sort_values(campaign_metric)
        campaign_colors = [
            COLORS["primary"], COLORS["purple"], COLORS["cyan"], COLORS["green"],
            COLORS["orange"], COLORS["pink"], COLORS["blue_2"], "#14B8A6", "#8B5CF6", "#F97316",
        ]
        fig = go.Figure(
            go.Bar(
                x=top_campaign[campaign_metric],
                y=top_campaign["campaign_name"],
                orientation="h",
                marker_color=campaign_colors[-len(top_campaign):],
                text=[_fmt_metric(campaign_metric, v) for v in top_campaign[campaign_metric]],
                textposition="outside",
                cliponaxis=False,
                hovertemplate="%{y}<br>%{text}<extra></extra>",
            )
        )
        fig.update_layout(**chart_layout(max(280, 42 * len(top_campaign)), showlegend=False))
        fig.update_xaxes(title=campaign_metric_label)
        fig.update_yaxes(title=None)
        st.plotly_chart(fig, use_container_width=True, config=plot_config())

        campaign_display = campaign_df.copy()
        campaign_display = campaign_display.rename(
            columns={
                "campaign_name": "캠페인",
                "spend": "광고비",
                "impressions": "노출수",
                "clicks": "클릭수",
                "ctr_calc": "CTR",
                "cpc_calc": "CPC",
                "cpm_calc": "CPM",
                "paid_interactions": "Paid 인터랙션",
                "ad_count": "광고수",
                "content_count": "연결 콘텐츠수",
            }
        )
        campaign_display["광고비"] = campaign_display["광고비"].map(lambda v: f"₩{v:,.0f}")
        campaign_display["노출수"] = campaign_display["노출수"].map(lambda v: f"{v:,.0f}")
        campaign_display["클릭수"] = campaign_display["클릭수"].map(lambda v: f"{v:,.0f}")
        campaign_display["CTR"] = campaign_display["CTR"].map(lambda v: f"{v:.2f}%")
        campaign_display["CPC"] = campaign_display["CPC"].map(lambda v: f"₩{v:,.0f}")
        campaign_display["CPM"] = campaign_display["CPM"].map(lambda v: f"₩{v:,.0f}")
        campaign_display["Paid 인터랙션"] = campaign_display["Paid 인터랙션"].map(lambda v: f"{v:,.0f}")
        campaign_display["광고수"] = campaign_display["광고수"].map(lambda v: f"{int(v):,}")
        campaign_display["연결 콘텐츠수"] = campaign_display["연결 콘텐츠수"].map(lambda v: f"{int(v):,}")
        st.dataframe(
            campaign_display[[
                "캠페인", "광고비", "노출수", "클릭수", "CTR", "CPC", "CPM",
                "Paid 인터랙션", "광고수", "연결 콘텐츠수",
            ]],
            hide_index=True,
            use_container_width=True,
            height=min(460, 70 + 35 * len(campaign_display)),
        )

    # --------------------------------------------------------
    # Paid content top
    # --------------------------------------------------------
    render_section_title(
        "Paid Content Top",
        "광고가 연결된 Instagram 게시물 기준입니다. 광고 전용 소재는 아래 광고 상세표에서 확인합니다.",
    )

    content_rows = current_df.copy()
    if "content_media_id" in content_rows.columns:
        content_rows = content_rows[content_rows["content_media_id"].astype(str).str.strip().ne("")].copy()
    else:
        content_rows = content_rows.iloc[0:0].copy()

    top_control = st.columns([1.1, 3.2], gap="medium")
    with top_control[0]:
        content_metric_label = st.selectbox(
            "정렬 기준",
            list(CONTENT_TOP_METRICS.keys()),
            index=0,
            key="ads_content_top_metric",
        )
    content_metric = CONTENT_TOP_METRICS[content_metric_label]

    if content_rows.empty:
        st.info("선택 기간에 연결된 게시물 광고가 없습니다.")
    else:
        grouped = []
        for media_id, group in content_rows.groupby("content_media_id", dropna=False):
            summary = _ads_summary(group)
            grouped.append({"media_id": str(media_id), **summary})
        content_agg = pd.DataFrame(grouped)

        lookup = _content_lookup(master)
        content_agg = content_agg.merge(lookup, on="media_id", how="left")
        content_agg = content_agg.sort_values(content_metric, ascending=False).head(5)

        cards = st.columns(5, gap="medium")
        for rank, (_, row) in enumerate(content_agg.iterrows(), start=1):
            with cards[rank - 1]:
                st.markdown(
                    f'<span style="display:inline-flex;background:{COLORS["primary"]};color:#fff;border-radius:999px;padding:4px 10px;font-weight:800;font-size:12px;margin-bottom:8px">TOP {rank}</span>',
                    unsafe_allow_html=True,
                )
                image_url = _safe_image_url(row)
                if image_url:
                    st.image(image_url, use_container_width=True)
                else:
                    st.markdown(
                        '<div style="height:180px;border-radius:12px;background:#F1F5F9;display:flex;align-items:center;justify-content:center;color:#94A3B8;font-size:12px">이미지 없음</div>',
                        unsafe_allow_html=True,
                    )
                st.markdown(f"**{html.escape(_display_title(row))}**")
                category = str(row.get("content_category", "") or "미분류")
                content_type = str(row.get("content_type", "") or "-")
                st.caption(f"{category} · {content_type}")
                st.markdown(
                    f'<div style="color:{COLORS["primary"]};font-size:18px;font-weight:800">{html.escape(content_metric_label)} {_fmt_metric(content_metric, float(row[content_metric]))}</div>',
                    unsafe_allow_html=True,
                )
                st.caption(f"광고비 {_fmt_metric('spend', float(row['spend']))} · 클릭 {fmt_int(row['clicks'])}")
                permalink = str(row.get("permalink", "") or "").strip()
                if permalink:
                    st.link_button("Instagram 열기", permalink, use_container_width=True)

    # --------------------------------------------------------
    # Detailed ads table + CSV
    # --------------------------------------------------------
    render_section_title(
        "광고 상세",
        "현재 필터 결과를 광고 단위로 합산합니다.",
    )

    ad_agg = _aggregate_ads(current_df)
    if ad_agg.empty:
        st.info("표시할 광고 상세 데이터가 없습니다.")
        return

    lookup = _content_lookup(master)
    ad_agg = ad_agg.merge(
        lookup.rename(columns={"media_id": "content_media_id"}),
        on="content_media_id",
        how="left",
    )

    detail_controls = st.columns([2.0, 1.0, 1.0], gap="medium")
    with detail_controls[0]:
        search = st.text_input(
            "광고 검색",
            placeholder="광고명, 캠페인명, 콘텐츠 제목 검색",
            key="ads_detail_search",
        )
    with detail_controls[1]:
        sort_label = st.selectbox(
            "정렬 기준",
            ["광고비", "클릭수", "CTR", "Paid 인터랙션"],
            index=0,
            key="ads_detail_sort",
        )
    with detail_controls[2]:
        display_count = st.selectbox(
            "표시 개수",
            [20, 50, 100, "전체"],
            index=0,
            key="ads_detail_count",
        )

    ad_agg["콘텐츠 제목"] = ad_agg.apply(_display_title, axis=1)
    if search.strip():
        needle = search.strip().lower()
        searchable = (
            ad_agg.get("ad_name", pd.Series(index=ad_agg.index, dtype=str)).astype(str)
            + " "
            + ad_agg.get("campaign_name", pd.Series(index=ad_agg.index, dtype=str)).astype(str)
            + " "
            + ad_agg["콘텐츠 제목"].astype(str)
        ).str.lower()
        ad_agg = ad_agg[searchable.str.contains(needle, na=False)].copy()

    sort_metric = {
        "광고비": "spend",
        "클릭수": "clicks",
        "CTR": "ctr_calc",
        "Paid 인터랙션": "paid_interactions",
    }[sort_label]
    ad_agg = ad_agg.sort_values(sort_metric, ascending=False)

    csv_df = ad_agg.copy()
    export_columns = [
        "ad_id", "ad_name", "campaign_name", "creative_source", "content_media_id", "콘텐츠 제목",
        "spend", "impressions", "reach_paid_gross", "clicks", "ctr_calc", "cpc_calc", "cpm_calc",
        "paid_interactions", "paid_saved",
    ]
    export_columns = [c for c in export_columns if c in csv_df.columns]
    csv_bytes = csv_df[export_columns].to_csv(index=False, encoding="utf-8-sig").encode("utf-8-sig")
    st.download_button(
        "CSV 다운로드",
        data=csv_bytes,
        file_name=f"greating_ads_{period_start:%Y%m%d}_{period_end:%Y%m%d}.csv",
        mime="text/csv",
        use_container_width=False,
    )

    display_df = ad_agg.copy()
    display_df["광고명"] = display_df.get("ad_name", "")
    display_df["캠페인"] = display_df.get("campaign_name", "")
    display_df["유형"] = display_df.get("creative_source", "").map(
        {"PUBLISHED_CONTENT": "게시물 연결", "AD_ONLY": "광고 전용"}
    ).fillna(display_df.get("creative_source", ""))
    display_df["광고비"] = display_df["spend"].map(lambda v: f"₩{v:,.0f}")
    display_df["노출수"] = display_df["impressions"].map(lambda v: f"{v:,.0f}")
    display_df["도달수(중복 포함)"] = display_df["reach_paid_gross"].map(lambda v: f"{v:,.0f}")
    display_df["클릭수"] = display_df["clicks"].map(lambda v: f"{v:,.0f}")
    display_df["CTR"] = display_df["ctr_calc"].map(lambda v: f"{v:.2f}%")
    display_df["CPC"] = display_df["cpc_calc"].map(lambda v: f"₩{v:,.0f}")
    display_df["CPM"] = display_df["cpm_calc"].map(lambda v: f"₩{v:,.0f}")
    display_df["Paid 인터랙션"] = display_df["paid_interactions"].map(lambda v: f"{v:,.0f}")
    display_df["저장"] = display_df["paid_saved"].map(lambda v: f"{v:,.0f}")
    display_df["Instagram"] = display_df.get("permalink", "")

    if display_count != "전체":
        display_df = display_df.head(int(display_count))

    st.dataframe(
        display_df[[
            "광고명", "캠페인", "유형", "콘텐츠 제목", "광고비", "노출수", "도달수(중복 포함)",
            "클릭수", "CTR", "CPC", "CPM", "Paid 인터랙션", "저장", "Instagram",
        ]],
        hide_index=True,
        use_container_width=True,
        height=min(700, 80 + 35 * len(display_df)),
        column_config={
            "Instagram": st.column_config.LinkColumn("Instagram", display_text="열기"),
        },
    )


# Streamlit st.Page execution entry point
render_ads(get_tables())
