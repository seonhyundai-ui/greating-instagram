from __future__ import annotations

import html
from datetime import datetime, timedelta

import pandas as pd
import plotly.express as px
import plotly.graph_objects as go
import streamlit as st

from dashboard.config import APP_VERSION, COLORS, KST
from dashboard.core import *  # shared dashboard metrics/filter/UI helpers

def render_overview(tables: dict[str, pd.DataFrame]) -> None:
    account = tables["account"]
    audience = tables["audience"]
    content = tables["content"]
    ads = tables["ads"]

    # --------------------------------------------------------
    # Periods
    # --------------------------------------------------------
    today = datetime.now(KST).date()
    current_end = today - timedelta(days=1)
    current_start = current_end.replace(day=1)
    prev_start, prev_end = previous_month_same_period(current_start, current_end)
    yoy_start, yoy_end = previous_year_same_period(current_start, current_end)

    st.title("Greating Instagram Dashboard")
    st.markdown(
        f'<div class="dashboard-subtitle">Overview · v{APP_VERSION} · 전일 종료 기준 ({current_end:%Y.%m.%d})</div>',
        unsafe_allow_html=True,
    )

    st.markdown(
        f"""
        <div class="period-row">
            <span class="period-chip"><strong>이번달</strong> {fmt_period(current_start, current_end)}</span>
            <span class="period-chip"><strong>전월동기</strong> {fmt_period(prev_start, prev_end)}</span>
            <span class="period-chip"><strong>전년동기</strong> {fmt_period(yoy_start, yoy_end)}</span>
        </div>
        """,
        unsafe_allow_html=True,
    )

    filter_col1, filter_col2, filter_col3 = st.columns([1.55, 1.55, 4.9])

    with filter_col1:
        content_type_filter = st.radio(
            "콘텐츠 유형",
            ["전체", "Feed", "Reels"],
            horizontal=True,
            key="overview_content_type",
        )

    with filter_col2:
        performance_filter = st.radio(
            "성과 기준",
            ["전체", "Organic", "Paid"],
            horizontal=True,
            key="overview_performance_layer",
        )

    with filter_col3:
        st.markdown(
            '<div class="filter-note">성과 비교는 <strong>CONTENT_LIFETIME 현재 누적값</strong> 기준입니다. '
            'D+7 / D+14 / D+30 비교는 Snapshot 데이터가 충분히 축적되면 활성화합니다.</div>',
            unsafe_allow_html=True,
        )

    # --------------------------------------------------------
    # Period subsets
    # --------------------------------------------------------
    current_type_df = filter_content_type(filter_by_period(content, current_start, current_end), content_type_filter)
    prev_type_df = filter_content_type(filter_by_period(content, prev_start, prev_end), content_type_filter)
    yoy_type_df = filter_content_type(filter_by_period(content, yoy_start, yoy_end), content_type_filter)

    # Performance scope policy:
    # 전체/Organic = all selected contents, Paid = paid contents only.
    current_df = filter_performance_scope(current_type_df, performance_filter)
    prev_df = filter_performance_scope(prev_type_df, performance_filter)
    yoy_df = filter_performance_scope(yoy_type_df, performance_filter)

    current_summary = period_summary(current_df, performance_filter)
    prev_summary = period_summary(prev_df, performance_filter)
    yoy_summary = period_summary(yoy_df, performance_filter)

    # --------------------------------------------------------
    # Top KPIs
    # --------------------------------------------------------
    render_section_title("핵심 현황")

    latest_followers = 0.0
    follower_delta_abs = None
    follower_delta_direction = None
    follower_spark_values: list[float] = []

    if not account.empty:
        latest_followers = float(account.iloc[-1]["followers_count"])
        follower_spark_values = (
            account.tail(14)["followers_count"]
            .dropna()
            .astype(float)
            .tolist()
        )
        if len(account) >= 2:
            previous_followers = float(account.iloc[-2]["followers_count"])
            follower_delta_abs = latest_followers - previous_followers
            follower_delta_direction = follower_delta_abs

    current_reels = int((current_df["content_type"] == "Reels").sum()) if not current_df.empty else 0
    current_feed = int((current_df["content_type"] == "Feed").sum()) if not current_df.empty else 0

    # Ad-running content KPI is an operational KPI, so it is independent of
    # the Total/Organic/Paid metric-layer selection. It still respects the
    # selected content type and period.
    current_paid_content = int(current_type_df["has_paid_bool"].sum()) if not current_type_df.empty else 0
    prev_paid_content = int(prev_type_df["has_paid_bool"].sum()) if not prev_type_df.empty else 0
    yoy_paid_content = int(yoy_type_df["has_paid_bool"].sum()) if not yoy_type_df.empty else 0

    def ads_spend_between(start: date, end: date) -> float:
        if ads.empty or "ad_date" not in ads.columns or "spend" not in ads.columns:
            return 0.0
        subset = ads[(ads["ad_date"] >= start) & (ads["ad_date"] <= end)]
        return float(subset["spend"].sum())

    current_spend = ads_spend_between(current_start, current_end)
    prev_spend = ads_spend_between(prev_start, prev_end)
    yoy_spend = ads_spend_between(yoy_start, yoy_end)

    row1 = st.columns(4)

    with row1[0]:
        follower_text = "-"
        if follower_delta_abs is not None and not pd.isna(follower_delta_abs):
            follower_text = f"{int(follower_delta_abs):+,}명"
        render_kpi_card(
            label="누적 팔로워",
            value=f"{fmt_int(latest_followers)}명",
            accent=COLORS["purple"],
            direct_delta_text=follower_text,
            direct_delta_value=follower_delta_direction,
            direct_delta_label="직전 수집일 대비",
            subline="최근 수집일 기준 · 우측 미니 추이는 최근 최대 14일",
            spark_values=follower_spark_values,
        )

    with row1[1]:
        render_kpi_card(
            label="콘텐츠수",
            value=f"{len(current_df):,}개",
            accent=COLORS["primary"],
            prev_delta=safe_pct_change(len(current_df), len(prev_df)),
            yoy_delta=safe_pct_change(len(current_df), len(yoy_df)),
            subline=f"{performance_filter} 기준 구성 · Reels {current_reels}개 · Feed {current_feed}개",
        )

    with row1[2]:
        render_kpi_card(
            label="광고 집행 콘텐츠",
            value=f"{current_paid_content:,}개",
            accent=COLORS["orange"],
            prev_delta=safe_pct_change(current_paid_content, prev_paid_content),
            yoy_delta=safe_pct_change(current_paid_content, yoy_paid_content),
            subline=f"선택 콘텐츠 유형: {content_type_filter}",
        )

    with row1[3]:
        render_kpi_card(
            label="광고비",
            value=fmt_won(current_spend),
            accent=COLORS["pink"],
            prev_delta=safe_pct_change(current_spend, prev_spend),
            yoy_delta=safe_pct_change(current_spend, yoy_spend),
            subline="Instagram Ads · D-1 누적",
        )

    st.write("")

    row2 = st.columns(4)
    metric_accents = {
        "조회수": COLORS["cyan"],
        "도달수": COLORS["primary"],
        "인터랙션": COLORS["green"],
        "저장": COLORS["orange"],
    }

    for column, metric_label in zip(row2, ["조회수", "도달수", "인터랙션", "저장"]):
        current_value = current_summary[f"sum_{metric_label}"]
        prev_value = prev_summary[f"sum_{metric_label}"]
        yoy_value = yoy_summary[f"sum_{metric_label}"]

        display_label = metric_label
        if metric_label == "도달수" and performance_filter == "전체":
            display_label = "도달수*"

        with column:
            render_kpi_card(
                label=f"{display_label} · {performance_filter}",
                value=fmt_int(current_value),
                accent=metric_accents[metric_label],
                prev_delta=safe_pct_change(current_value, prev_value),
                yoy_delta=safe_pct_change(current_value, yoy_value),
                subline=f"콘텐츠 유형: {content_type_filter}",
            )

    if performance_filter == "전체":
        st.caption("* 전체 도달수는 Organic Reach + Paid Reach이며 동일 사용자가 중복 포함될 수 있습니다.")

    # --------------------------------------------------------
    # Comparison table + stacked charts on right
    # --------------------------------------------------------
    st.divider()
    render_section_title(
        "기간 비교 & 콘텐츠 성과",
        "왼쪽은 기간 비교표, 오른쪽은 Feed/Reels와 카테고리별 성과를 함께 봅니다.",
    )

    st.markdown(
        f"""
        <div class="dynamic-note">
            현재 기준: <strong>콘텐츠 유형 = {html.escape(content_type_filter)}</strong> ·
            <strong>성과 기준 = {html.escape(performance_filter)}</strong> ·
            콘텐츠별 <strong>현재 누적 Lifetime 평균</strong>을 이번달 / 전월동기 / 전년동기로 비교합니다.<br>
            <span style="color:#64748B;">전체·Organic은 선택 콘텐츠 전체를 포함하고, Paid는 광고 집행 콘텐츠만 포함합니다.</span>
        </div>
        """,
        unsafe_allow_html=True,
    )

    compare_left, compare_right = st.columns([1.02, 0.98], gap="large")

    comparison_specs = [
        ("콘텐츠수", "contents"),
        ("평균 조회수", "mean_조회수"),
        ("평균 도달수", "mean_도달수"),
        ("평균 인터랙션", "mean_인터랙션"),
        ("평균 저장", "mean_저장"),
    ]

    with compare_left:
        comparison_rows = []
        for metric_name, summary_key in comparison_specs:
            current_value = current_summary[summary_key]
            prev_value = prev_summary[summary_key]
            yoy_value = yoy_summary[summary_key]

            comparison_rows.append(
                {
                    "지표": metric_name,
                    "이번달": format_table_value(metric_name, current_value),
                    "전월동기": format_table_value(metric_name, prev_value),
                    "전년동기": format_table_value(metric_name, yoy_value),
                    "전월동기 대비": safe_pct_change(current_value, prev_value),
                    "전년동기 대비": safe_pct_change(current_value, yoy_value),
                }
            )

        render_comparison_table(comparison_rows)

    with compare_right:
        chart_col1, chart_col2 = st.columns(2, gap="medium")

        # Feed vs Reels
        with chart_col1:
            st.markdown('<div class="mini-chart-label">Feed vs Reels</div>', unsafe_allow_html=True)
            format_metric = st.selectbox(
                "비교 지표",
                ["조회수", "도달수", "인터랙션", "저장"],
                key="format_metric",
                label_visibility="collapsed",
            )

            format_col = metric_column(format_metric, performance_filter)
            format_rows = []
            format_source = filter_performance_scope(filter_by_period(content, current_start, current_end), performance_filter)
            for content_type in ["Feed", "Reels"]:
                subset = format_source[format_source["content_type"] == content_type]
                format_rows.append(
                    {
                        "콘텐츠 유형": content_type,
                        "metric": mean_metric(subset, format_col),
                        "contents": len(subset),
                    }
                )

            format_df = pd.DataFrame(format_rows)
            fig_format = px.bar(
                format_df,
                x="콘텐츠 유형",
                y="metric",
                text="metric",
                color="콘텐츠 유형",
                color_discrete_map={
                    "Feed": "#2563EB",
                    "Reels": "#8B5CF6",
                },
                hover_data={"contents": True, "metric": ":,.0f"},
            )
            fig_format.update_traces(
                texttemplate="%{text:,.0f}",
                textposition="outside",
                cliponaxis=False,
            )
            fig_format.update_layout(**chart_layout(190, showlegend=False))
            fig_format.update_layout(xaxis_title=None, yaxis_title=None)
            fig_format.update_xaxes(showgrid=False)
            fig_format.update_yaxes(gridcolor="#EEF2F7", zeroline=False, showticklabels=False)
            st.plotly_chart(fig_format, use_container_width=True, config=plot_config())

        # Category performance
        with chart_col2:
            st.markdown('<div class="mini-chart-label">카테고리별 성과</div>', unsafe_allow_html=True)
            category_metric = st.selectbox(
                "카테고리 지표",
                ["인터랙션", "조회수", "도달수", "저장"],
                key="category_metric",
                label_visibility="collapsed",
            )

            category_col = metric_column(category_metric, performance_filter)
            category_df = current_df.copy()
            if not category_df.empty:
                category_df["content_category"] = category_df["content_category"].fillna("").astype(str).str.strip()
                category_df.loc[category_df["content_category"] == "", "content_category"] = "미분류"
                grouped = (
                    category_df.groupby("content_category", as_index=False)
                    .agg(metric=(category_col, "mean"), contents=("media_id", "count"))
                    .sort_values("metric", ascending=True)
                )
            else:
                grouped = pd.DataFrame(columns=["content_category", "metric", "contents"])

            category_palette = [
                "#2563EB",
                "#06B6D4",
                "#10B981",
                "#F59E0B",
                "#EC4899",
                "#8B5CF6",
                "#64748B",
            ]
            category_names = grouped["content_category"].astype(str).tolist()
            category_color_map = {
                name: category_palette[i % len(category_palette)]
                for i, name in enumerate(category_names)
            }

            fig_category = px.bar(
                grouped,
                x="metric",
                y="content_category",
                orientation="h",
                text="metric",
                color="content_category",
                color_discrete_map=category_color_map,
                hover_data={"contents": True, "metric": ":,.0f"},
            )
            fig_category.update_traces(
                texttemplate="%{text:,.0f}",
                textposition="outside",
                cliponaxis=False,
            )
            fig_category.update_layout(**chart_layout(190, showlegend=False))
            fig_category.update_layout(xaxis_title=None, yaxis_title=None)
            fig_category.update_xaxes(gridcolor="#EEF2F7", zeroline=False, showticklabels=False)
            fig_category.update_yaxes(showgrid=False, tickfont=dict(size=10))
            st.plotly_chart(fig_category, use_container_width=True, config=plot_config())

    # --------------------------------------------------------
    # Top content: large-thumbnail horizontal cards
    # --------------------------------------------------------
    st.divider()

    top_header, top_filter = st.columns([5, 1.25])
    with top_header:
        render_section_title("Top Content", "현재 기간 내 게시 콘텐츠를 선택한 지표 기준으로 정렬합니다.")
    with top_filter:
        top_metric = st.selectbox(
            "정렬 기준",
            ["조회수", "도달수", "인터랙션"],
            key="top_content_metric",
        )

    st.markdown(
        f"""
        <div class="dynamic-note">
            Top Content 기준: <strong>{html.escape(top_metric)}</strong> ·
            콘텐츠 유형 <strong>{html.escape(content_type_filter)}</strong> ·
            성과 기준 <strong>{html.escape(performance_filter)}</strong>
        </div>
        """,
        unsafe_allow_html=True,
    )

    top_col = metric_column(top_metric, performance_filter)
    top_df = current_df.copy()

    if not top_df.empty and top_col in top_df.columns:
        top_df[top_col] = to_numeric_series(top_df[top_col])
        top_df = top_df.sort_values(top_col, ascending=False).head(5).reset_index(drop=True)

        top_columns = st.columns(5, gap="small")

        for idx, row in top_df.iterrows():
            with top_columns[idx]:
                with st.container(border=True):
                    st.markdown(f'<span class="top-rank">TOP {idx + 1}</span>', unsafe_allow_html=True)

                    image_url = str(row.get("thumbnail_url", "") or "").strip()
                    if not image_url:
                        image_url = str(row.get("media_url", "") or "").strip()

                    if image_url:
                        st.image(image_url, use_container_width=True)
                    else:
                        st.markdown(
                            '<div style="height:150px;background:#F1F5F9;border-radius:10px;display:flex;align-items:center;justify-content:center;color:#94A3B8;font-size:0.8rem;">이미지 없음</div>',
                            unsafe_allow_html=True,
                        )

                    title = str(row.get("ai_title", "") or "").strip() or "제목 미입력"
                    category = str(row.get("content_category", "") or "").strip() or "미분류"
                    content_type = str(row.get("content_type", "") or "").strip()
                    score = row.get(top_col)

                    st.markdown(f'<div class="top-title">{html.escape(title)}</div>', unsafe_allow_html=True)
                    st.markdown(
                        f'<div class="top-meta">{html.escape(category)} · {html.escape(content_type)}</div>',
                        unsafe_allow_html=True,
                    )
                    st.markdown(
                        f'<div class="top-score">{html.escape(top_metric)} {fmt_int(score)}</div>',
                        unsafe_allow_html=True,
                    )

                    permalink = str(row.get("permalink", "") or "").strip()
                    if permalink:
                        st.link_button("Instagram 열기", permalink, use_container_width=True)
    else:
        st.info("현재 조건에 해당하는 콘텐츠가 없습니다.")

    # --------------------------------------------------------
    # Compact operations + Audience
    # --------------------------------------------------------
    st.divider()
    render_section_title("운영 흐름 & Audience", "하단 정보는 한 화면 안에서 빠르게 훑을 수 있도록 compact하게 구성했습니다.")

    if audience.empty:
        latest_audience = pd.DataFrame()
        gender = pd.DataFrame()
        age = pd.DataFrame()
    else:
        latest_audience_date = audience["snapshot_date"].max()
        latest_audience = audience[audience["snapshot_date"] == latest_audience_date].copy()
        gender = latest_audience[latest_audience["dimension"] == "gender"].copy()
        age = latest_audience[latest_audience["dimension"] == "age"].copy()

    bottom_cols = st.columns([1.2, 0.9, 1.25, 0.65], gap="medium")

    # Recent 4 weeks
    with bottom_cols[0]:
        st.markdown("#### 최근 4주 콘텐츠")
        window_start = current_end - timedelta(days=27)
        trend_source = content[(content["posted_date"] >= window_start) & (content["posted_date"] <= current_end)].copy()
        trend_source = filter_content_type(trend_source, content_type_filter)
        trend_source = filter_performance_scope(trend_source, performance_filter)

        buckets = []
        for i in range(4):
            start = window_start + timedelta(days=i * 7)
            end = start + timedelta(days=6)
            label = f"{start.month}/{start.day}-{end.month}/{end.day}"
            bucket = trend_source[(trend_source["posted_date"] >= start) & (trend_source["posted_date"] <= end)]
            buckets.append(
                {
                    "주간": label,
                    "Feed": int((bucket["content_type"] == "Feed").sum()),
                    "Reels": int((bucket["content_type"] == "Reels").sum()),
                }
            )

        weekly_df = pd.DataFrame(buckets)
        fig_week = go.Figure()
        fig_week.add_bar(x=weekly_df["주간"], y=weekly_df["Feed"], name="Feed", marker_color=COLORS["primary"])
        fig_week.add_bar(x=weekly_df["주간"], y=weekly_df["Reels"], name="Reels", marker_color=COLORS["cyan"])
        fig_week.update_layout(**chart_layout(235, showlegend=True))
        fig_week.update_layout(
            barmode="stack",
            xaxis_title=None,
            yaxis_title="게시수",
            legend=dict(orientation="h", yanchor="bottom", y=1.02, xanchor="right", x=1),
        )
        fig_week.update_xaxes(showgrid=False)
        fig_week.update_yaxes(gridcolor="#EEF2F7", zeroline=False, dtick=1)
        st.plotly_chart(fig_week, use_container_width=True, config=plot_config())

    # Gender
    with bottom_cols[1]:
        st.markdown("#### 성별 비중")
        if not gender.empty:
            gender_map = {"F": "여성", "M": "남성", "U": "Unknown"}
            gender_order = ["F", "M", "U"]
            gender["segment"] = pd.Categorical(gender["segment"], categories=gender_order, ordered=True)
            gender = gender.sort_values("segment")
            gender["label"] = gender["segment"].astype(str).map(gender_map).fillna(gender["segment"].astype(str))

            fig_gender = px.pie(
                gender,
                names="label",
                values="value",
                hole=0.58,
                color="label",
                color_discrete_map={
                    "여성": COLORS["pink"],
                    "남성": COLORS["primary"],
                    "Unknown": COLORS["slate_2"],
                },
            )
            fig_gender.update_traces(textposition="inside", textinfo="percent", textfont_size=10)
            fig_gender.update_layout(**chart_layout(235, showlegend=True))
            fig_gender.update_layout(
                legend=dict(orientation="h", yanchor="top", y=-0.05, xanchor="center", x=0.5),
            )
            st.plotly_chart(fig_gender, use_container_width=True, config=plot_config())
        else:
            st.info("성별 데이터 없음")

    # Age
    with bottom_cols[2]:
        st.markdown("#### 연령별 비중")
        if not age.empty:
            age_order = ["13-17", "18-24", "25-34", "35-44", "45-54", "55-64", "65+"]
            age["segment"] = pd.Categorical(age["segment"], categories=age_order, ordered=True)
            age = age.sort_values("segment")

            fig_age = px.bar(
                age,
                x="percentage",
                y="segment",
                orientation="h",
                text="percentage",
            )
            fig_age.update_traces(
                marker_color=COLORS["primary"],
                texttemplate="%{text:.1f}%",
                textposition="outside",
                cliponaxis=False,
            )
            fig_age.update_layout(**chart_layout(235, showlegend=False))
            fig_age.update_layout(xaxis_title=None, yaxis_title=None)
            fig_age.update_xaxes(gridcolor="#EEF2F7", zeroline=False)
            fig_age.update_yaxes(showgrid=False)
            st.plotly_chart(fig_age, use_container_width=True, config=plot_config())
        else:
            st.info("연령 데이터 없음")

    # Target share
    with bottom_cols[3]:
        st.markdown("#### 핵심 타깃")
        target_share = 0.0
        counted_value = 0

        if not age.empty:
            age_for_calc = latest_audience[latest_audience["dimension"] == "age"].copy()
            target_share = float(
                age_for_calc[age_for_calc["segment"].astype(str).isin(["25-34", "35-44"])]["percentage"].sum()
            )

        if not latest_audience.empty:
            counted_total = latest_audience["dimension_total"].dropna()
            counted_value = int(counted_total.iloc[0]) if not counted_total.empty else 0

        st.markdown(
            f"""
            <div class="kpi-card" style="--accent:{COLORS['green']};min-height:188px;">
                <div class="kpi-label">25-44 비중</div>
                <div class="kpi-value">{target_share:.1f}%</div>
                <div class="kpi-subline">Demographic 집계 대상<br><strong>{counted_value:,}명</strong></div>
                <div class="kpi-subline">Meta 연령구간상 정확한 30-49세 분리는 불가합니다.</div>
            </div>
            """,
            unsafe_allow_html=True,
        )



with st.spinner("Google Sheets 데이터를 불러오는 중..."):
    _tables = get_tables()
render_overview(_tables)
