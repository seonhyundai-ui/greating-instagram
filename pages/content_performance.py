from __future__ import annotations

import html
from datetime import date, datetime, timedelta

import pandas as pd
import plotly.express as px
import plotly.graph_objects as go
import streamlit as st

from dashboard.config import APP_VERSION, COLORS, KST
from dashboard.core import *  # shared dashboard metrics/filter/UI helpers

# ============================================================
# Page: Content Performance
# ============================================================

PERFORMANCE_TIMING = {
    "현재 누적": None,
    "D+7": 7,
    "D+14": 14,
    "D+30": 30,
}

ANALYSIS_AXES = {
    "카테고리": "content_category",
    "서브카테고리": "content_subcategory",
    "크리에이티브 포맷": "creative_format",
    "상품": "product_name",
    "캠페인": "campaign_name",
}


def resolve_content_title(row: pd.Series) -> str:
    for column in ["manual_title", "ai_title"]:
        value = str(row.get(column, "") or "").strip()
        if value:
            return value

    caption = str(row.get("caption", "") or "").strip().replace("\n", " ")
    if caption:
        return caption[:48] + ("…" if len(caption) > 48 else "")

    return "제목 미입력"


def build_performance_source(
    tables: dict[str, pd.DataFrame],
    timing_label: str,
) -> pd.DataFrame:
    """Return current lifetime metrics or exact D+N snapshot metrics."""
    if timing_label == "현재 누적":
        return tables["content"].copy()

    snapshot = tables["snapshot"].copy()
    master = tables["master"].copy()
    target_age = PERFORMANCE_TIMING[timing_label]

    if snapshot.empty or target_age is None:
        return pd.DataFrame()

    source = snapshot[snapshot["snapshot_age_days"] == target_age].copy()
    if source.empty:
        return source

    source = source.sort_values("snapshot_date").drop_duplicates("media_id", keep="last")

    meta_columns = [
        "media_id",
        "posted_at",
        "posted_date",
        "content_type",
        "has_paid_bool",
        "permalink",
        "thumbnail_url",
        "media_url",
        "caption",
        "ai_title",
        "manual_title",
        "content_category",
        "content_subcategory",
        "content_theme",
        "product_name",
        "campaign_name",
        "creative_format",
        "classification_status",
    ]
    meta_columns = [column for column in meta_columns if column in master.columns]

    return source.merge(
        master[meta_columns],
        on="media_id",
        how="left",
        suffixes=("", "_master"),
    )


def apply_detail_filters(
    df: pd.DataFrame,
    *,
    categories: list[str],
    subcategories: list[str],
    creative_formats: list[str],
    products: list[str],
    campaigns: list[str],
) -> pd.DataFrame:
    result = df.copy()

    specs = [
        ("content_category", categories),
        ("content_subcategory", subcategories),
        ("creative_format", creative_formats),
        ("product_name", products),
        ("campaign_name", campaigns),
    ]

    for column, selected in specs:
        if not selected or column not in result.columns:
            continue
        normalized = result[column].fillna("").astype(str).str.strip()
        result = result[normalized.isin(selected)].copy()

    return result


def render_content_performance(tables: dict[str, pd.DataFrame]) -> None:
    snapshot = tables["snapshot"]

    today = datetime.now(KST).date()
    current_end = today - timedelta(days=1)

    st.title("Content Performance")
    st.markdown(
        f'<div class="dashboard-subtitle">콘텐츠 성과 심층 분석 · v{APP_VERSION} · 데이터 기준일 {current_end:%Y.%m.%d}</div>',
        unsafe_allow_html=True,
    )

    # --------------------------------------------------------
    # Primary filters
    # --------------------------------------------------------
    filter_cols = st.columns([1.35, 1.15, 1.15, 1.15], gap="medium")

    with filter_cols[0]:
        period_preset = st.selectbox(
            "분석 기간",
            ["최근 30일", "최근 90일", "올해", "직접 선택"],
            index=1,
            key="cp_period_preset",
        )

    with filter_cols[1]:
        content_type_filter = st.radio(
            "콘텐츠 유형",
            ["전체", "Feed", "Reels"],
            horizontal=True,
            key="cp_content_type",
        )

    with filter_cols[2]:
        performance_filter = st.radio(
            "성과 기준",
            ["전체", "Organic", "Paid"],
            horizontal=True,
            key="cp_performance_layer",
        )

    with filter_cols[3]:
        timing_filter = st.selectbox(
            "성과 시점",
            list(PERFORMANCE_TIMING.keys()),
            key="cp_timing",
            help="현재 누적은 CONTENT_LIFETIME, D+7/14/30은 MEDIA_SNAPSHOT을 사용합니다.",
        )

    if period_preset == "최근 30일":
        period_start = current_end - timedelta(days=29)
        period_end = current_end
    elif period_preset == "최근 90일":
        period_start = current_end - timedelta(days=89)
        period_end = current_end
    elif period_preset == "올해":
        period_start = date(current_end.year, 1, 1)
        period_end = current_end
    else:
        picked = st.date_input(
            "직접 기간 선택",
            value=(current_end - timedelta(days=89), current_end),
            max_value=current_end,
            key="cp_custom_period",
        )
        if isinstance(picked, (tuple, list)) and len(picked) == 2:
            period_start, period_end = picked
        else:
            period_start = current_end - timedelta(days=89)
            period_end = current_end

    source = build_performance_source(tables, timing_filter)

    if source.empty:
        st.warning(
            f"{timing_filter} 성과 Snapshot이 아직 없습니다. 현재 누적을 선택하거나 Snapshot이 더 쌓인 뒤 다시 확인해주세요."
        )
        if not snapshot.empty:
            available = (
                snapshot["snapshot_age_days"]
                .dropna()
                .astype(int)
                .value_counts()
                .sort_index()
            )
            if not available.empty:
                available_text = " · ".join(f"D+{age} {count:,}개" for age, count in available.items())
                st.caption(f"현재 Snapshot 보유 현황: {available_text}")
        return

    df = filter_by_period(source, period_start, period_end)
    df = filter_content_type(df, content_type_filter)
    df = filter_performance_scope(df, performance_filter)

    # --------------------------------------------------------
    # Detail filters
    # --------------------------------------------------------
    with st.expander("상세 분류 필터", expanded=False):
        detail_cols = st.columns(5)

        def values_for(column: str) -> list[str]:
            if column not in df.columns:
                return []
            values = df[column].fillna("").astype(str).str.strip()
            return sorted([value for value in values.unique().tolist() if value])

        with detail_cols[0]:
            category_filter = st.multiselect(
                "카테고리",
                values_for("content_category"),
                key="cp_category_filter",
            )
        with detail_cols[1]:
            subcategory_filter = st.multiselect(
                "서브카테고리",
                values_for("content_subcategory"),
                key="cp_subcategory_filter",
            )
        with detail_cols[2]:
            format_filter = st.multiselect(
                "크리에이티브 포맷",
                values_for("creative_format"),
                key="cp_format_filter",
            )
        with detail_cols[3]:
            product_filter = st.multiselect(
                "상품",
                values_for("product_name"),
                key="cp_product_filter",
            )
        with detail_cols[4]:
            campaign_filter = st.multiselect(
                "캠페인",
                values_for("campaign_name"),
                key="cp_campaign_filter",
            )

    df = apply_detail_filters(
        df,
        categories=category_filter,
        subcategories=subcategory_filter,
        creative_formats=format_filter,
        products=product_filter,
        campaigns=campaign_filter,
    )

    layer_note = (
        "전체·Organic은 광고 집행 여부와 관계없이 선택 콘텐츠 전체를 포함하고, Paid는 광고 집행 콘텐츠만 포함합니다."
    )
    timing_note = "현재 누적 Lifetime" if timing_filter == "현재 누적" else f"게시 후 {timing_filter} Snapshot"

    note_html = (
        '<div class="dynamic-note">'
        f'분석 범위: <strong>{fmt_period(period_start, period_end)}</strong> · '
        f'콘텐츠 유형 <strong>{html.escape(content_type_filter)}</strong> · '
        f'성과 기준 <strong>{html.escape(performance_filter)}</strong> · '
        f'성과 시점 <strong>{html.escape(timing_note)}</strong> · '
        f'현재 표본 <strong>{len(df):,}개</strong><br>'
        f'<span style="color:#64748B;">{html.escape(layer_note)}</span>'
        '</div>'
    )
    st.markdown(note_html, unsafe_allow_html=True)

    if df.empty:
        st.info("현재 필터에 해당하는 콘텐츠가 없습니다.")
        return

    # --------------------------------------------------------
    # KPI
    # --------------------------------------------------------
    render_section_title("선택 콘텐츠 성과")

    kpi_cols = st.columns(5)
    kpi_specs = [
        ("콘텐츠수", None, COLORS["primary"]),
        ("평균 조회수", metric_column("조회수", performance_filter), COLORS["cyan"]),
        ("평균 도달수", metric_column("도달수", performance_filter), COLORS["primary"]),
        ("평균 인터랙션", metric_column("인터랙션", performance_filter), COLORS["green"]),
        ("평균 저장", metric_column("저장", performance_filter), COLORS["orange"]),
    ]

    for column, (label, metric_col, accent) in zip(kpi_cols, kpi_specs):
        with column:
            if metric_col is None:
                value = f"{len(df):,}개"
            else:
                value = fmt_int(mean_metric(df, metric_col))
            render_kpi_card(
                label=label,
                value=value,
                accent=accent,
                direct_delta_text=timing_filter,
                direct_delta_value=0,
                direct_delta_label="성과 시점",
                subline=f"{content_type_filter} · {performance_filter}",
            )

    if performance_filter == "전체":
        st.caption("* 전체 도달수는 Organic Reach + Paid Reach이며 동일 사용자가 중복 포함될 수 있습니다.")

    # --------------------------------------------------------
    # Analysis controls
    # --------------------------------------------------------
    st.divider()
    render_section_title(
        "성과 구조 분석",
        "분류축별 평균 성과와 콘텐츠별 Reach × Interaction 분포를 함께 봅니다.",
    )

    control_cols = st.columns([1.4, 1.2, 1.0, 3.4])
    with control_cols[0]:
        axis_label = st.selectbox(
            "분석 축",
            list(ANALYSIS_AXES.keys()),
            key="cp_analysis_axis",
        )
    with control_cols[1]:
        selected_metric = st.selectbox(
            "대표 지표",
            ["인터랙션", "조회수", "도달수", "저장"],
            key="cp_metric",
        )
    with control_cols[2]:
        min_sample = st.selectbox(
            "최소 콘텐츠수",
            [1, 2, 3, 5],
            index=1,
            key="cp_min_sample",
        )
    with control_cols[3]:
        st.markdown(
            '<div class="filter-note" style="padding-top:1.9rem;">표본이 너무 작은 분류의 평균값 과대해석을 막기 위해 최소 콘텐츠수를 적용할 수 있습니다.</div>',
            unsafe_allow_html=True,
        )

    axis_col = ANALYSIS_AXES[axis_label]
    selected_col = metric_column(selected_metric, performance_filter)
    views_col = metric_column("조회수", performance_filter)
    reach_col = metric_column("도달수", performance_filter)
    interactions_col = metric_column("인터랙션", performance_filter)
    saved_col = metric_column("저장", performance_filter)

    analysis_df = df.copy()
    if axis_col not in analysis_df.columns:
        analysis_df[axis_col] = "미분류"
    analysis_df[axis_col] = analysis_df[axis_col].fillna("").astype(str).str.strip()
    analysis_df.loc[analysis_df[axis_col] == "", axis_col] = "미분류"
    analysis_df["_title"] = analysis_df.apply(resolve_content_title, axis=1)

    chart_left, chart_right = st.columns([1.0, 1.15], gap="large")

    # Group ranking
    with chart_left:
        grouped = (
            analysis_df.groupby(axis_col, as_index=False)
            .agg(
                metric=(selected_col, "mean"),
                contents=("media_id", "count"),
            )
        )
        grouped = grouped[grouped["contents"] >= min_sample].copy()
        grouped = grouped.sort_values("metric", ascending=False).head(12).sort_values("metric", ascending=True)

        if grouped.empty:
            st.info("최소 표본 조건을 충족하는 분류가 없습니다.")
        else:
            palette = [
                "#2563EB", "#7C3AED", "#06B6D4", "#10B981", "#F59E0B", "#EC4899",
                "#6366F1", "#14B8A6", "#84CC16", "#F97316", "#A855F7", "#0EA5E9",
            ]
            color_map = {
                value: palette[index % len(palette)]
                for index, value in enumerate(grouped[axis_col].tolist())
            }

            fig_group = px.bar(
                grouped,
                x="metric",
                y=axis_col,
                orientation="h",
                text="metric",
                color=axis_col,
                color_discrete_map=color_map,
                hover_data={"contents": True, "metric": ":,.0f"},
            )
            fig_group.update_traces(
                texttemplate="%{text:,.0f}",
                textposition="outside",
                cliponaxis=False,
            )
            fig_group.update_layout(**chart_layout(410, showlegend=False))
            fig_group.update_layout(
                xaxis_title=f"평균 {selected_metric}",
                yaxis_title=None,
                margin=dict(l=12, r=35, t=15, b=25),
            )
            fig_group.update_xaxes(gridcolor="#EEF2F7", zeroline=False)
            fig_group.update_yaxes(showgrid=False)
            st.plotly_chart(fig_group, use_container_width=True, config=plot_config())

    # Reach x Interaction scatter
    with chart_right:
        scatter = analysis_df.copy()
        scatter["_reach"] = to_numeric_series(scatter[reach_col]) if reach_col in scatter.columns else 0
        scatter["_interactions"] = (
            to_numeric_series(scatter[interactions_col]) if interactions_col in scatter.columns else 0
        )
        scatter["_views"] = to_numeric_series(scatter[views_col]) if views_col in scatter.columns else 0
        scatter["_saved"] = to_numeric_series(scatter[saved_col]) if saved_col in scatter.columns else 0
        scatter = scatter.dropna(subset=["_reach", "_interactions"]).copy()
        scatter["_bubble"] = scatter["_views"].fillna(0).clip(lower=1)

        if scatter.empty:
            st.info("분포 차트를 그릴 수 있는 성과 데이터가 없습니다.")
        else:
            reach_median = float(scatter["_reach"].median())
            interactions_median = float(scatter["_interactions"].median())

            fig_scatter = px.scatter(
                scatter,
                x="_reach",
                y="_interactions",
                size="_bubble",
                size_max=28,
                color="content_type",
                color_discrete_map={"Feed": "#2563EB", "Reels": "#8B5CF6"},
                hover_name="_title",
                hover_data={
                    axis_col: True,
                    "_reach": ":,.0f",
                    "_interactions": ":,.0f",
                    "_views": ":,.0f",
                    "_saved": ":,.0f",
                    "_bubble": False,
                },
            )
            fig_scatter.add_vline(
                x=reach_median,
                line_width=1,
                line_dash="dot",
                line_color="#94A3B8",
            )
            fig_scatter.add_hline(
                y=interactions_median,
                line_width=1,
                line_dash="dot",
                line_color="#94A3B8",
            )
            fig_scatter.update_layout(**chart_layout(410, showlegend=True))
            fig_scatter.update_layout(
                xaxis_title="도달수",
                yaxis_title="인터랙션",
                legend=dict(orientation="h", yanchor="bottom", y=1.01, xanchor="right", x=1),
                margin=dict(l=12, r=12, t=30, b=35),
            )
            fig_scatter.update_xaxes(gridcolor="#EEF2F7", zeroline=False)
            fig_scatter.update_yaxes(gridcolor="#EEF2F7", zeroline=False)
            st.plotly_chart(fig_scatter, use_container_width=True, config=plot_config())
            st.caption("점선은 선택 콘텐츠의 도달수·인터랙션 중앙값입니다. 버블 크기는 조회수 기준입니다.")

    # --------------------------------------------------------
    # Group detail table
    # --------------------------------------------------------
    st.divider()
    render_section_title(
        f"{axis_label}별 상세 비교",
        "평균값과 전체 평균 대비 수준을 함께 확인합니다.",
    )

    overall_metric_mean = mean_metric(analysis_df, selected_col)

    table_rows = []
    for axis_value, group in analysis_df.groupby(axis_col):
        if len(group) < min_sample:
            continue

        selected_mean = mean_metric(group, selected_col)
        relative = safe_pct_change(selected_mean, overall_metric_mean)
        table_rows.append(
            {
                axis_label: axis_value,
                "콘텐츠수": len(group),
                "Paid 콘텐츠": int(group["has_paid_bool"].sum()) if "has_paid_bool" in group.columns else 0,
                "평균 조회수": mean_metric(group, views_col),
                "평균 도달수": mean_metric(group, reach_col),
                "평균 인터랙션": mean_metric(group, interactions_col),
                "평균 저장": mean_metric(group, saved_col),
                f"{selected_metric} 전체평균 대비": relative,
            }
        )

    group_table = pd.DataFrame(table_rows)
    if group_table.empty:
        st.info("상세 비교 표에 표시할 분류가 없습니다.")
    else:
        group_table = group_table.sort_values("평균 " + selected_metric, ascending=False).reset_index(drop=True)

        delta_col = f"{selected_metric} 전체평균 대비"
        styled = group_table.style.format(
            {
                "콘텐츠수": "{:,.0f}",
                "Paid 콘텐츠": "{:,.0f}",
                "평균 조회수": "{:,.0f}",
                "평균 도달수": "{:,.0f}",
                "평균 인터랙션": "{:,.0f}",
                "평균 저장": "{:,.0f}",
                delta_col: lambda x: "-" if pd.isna(x) else f"{x:+.1f}%",
            }
        )
        try:
            styled = styled.map(
                lambda value: (
                    "color:#047857;font-weight:700;" if pd.notna(value) and value > 0
                    else "color:#B91C1C;font-weight:700;" if pd.notna(value) and value < 0
                    else "color:#64748B;"
                ),
                subset=[delta_col],
            )
        except AttributeError:
            styled = styled.applymap(
                lambda value: (
                    "color:#047857;font-weight:700;" if pd.notna(value) and value > 0
                    else "color:#B91C1C;font-weight:700;" if pd.notna(value) and value < 0
                    else "color:#64748B;"
                ),
                subset=[delta_col],
            )

        st.dataframe(
            styled,
            use_container_width=True,
            hide_index=True,
            height=min(470, 42 + len(group_table) * 36),
        )

    # --------------------------------------------------------
    # Content explorer
    # --------------------------------------------------------
    st.divider()
    render_section_title(
        "콘텐츠 상세",
        "필터 결과의 개별 콘텐츠를 최신 게시순 또는 성과순으로 확인하고 CSV로 내려받을 수 있습니다.",
    )

    explorer_cols = st.columns([2.2, 1.0, 0.9, 0.9])
    with explorer_cols[0]:
        search_text = st.text_input(
            "콘텐츠 검색",
            placeholder="제목, 캡션, 상품명, 캠페인명 검색",
            key="cp_search",
        ).strip().lower()
    with explorer_cols[1]:
        sort_metric_options = ["최신 게시일", "조회수", "도달수", "인터랙션", "저장"]
        sort_metric = st.selectbox(
            "정렬 기준",
            sort_metric_options,
            index=0,
            key="cp_sort_metric_v2",
        )
    with explorer_cols[2]:
        row_limit = st.selectbox(
            "표시 개수",
            [20, 50, 100, "전체"],
            key="cp_row_limit",
        )

    explorer = analysis_df.copy()
    explorer["제목"] = explorer.apply(resolve_content_title, axis=1)

    if search_text:
        search_columns = [
            column
            for column in [
                "제목",
                "caption",
                "product_name",
                "campaign_name",
                "content_category",
                "content_subcategory",
            ]
            if column in explorer.columns
        ]
        combined = pd.Series("", index=explorer.index, dtype="object")
        for column in search_columns:
            combined = combined + " " + explorer[column].fillna("").astype(str).str.lower()
        explorer = explorer[combined.str.contains(search_text, regex=False)].copy()

    # 기본 정렬은 최신 게시일. 성과 지표를 선택한 경우 해당 지표 내림차순.
    if sort_metric == "최신 게시일":
        explorer["_sort_posted_at"] = pd.to_datetime(explorer["posted_at"], errors="coerce")
        explorer = explorer.sort_values("_sort_posted_at", ascending=False, na_position="last")
    else:
        sort_col = metric_column(sort_metric, performance_filter)
        if sort_col in explorer.columns:
            explorer = explorer.sort_values(sort_col, ascending=False, na_position="last")

    # CSV는 화면 표시 개수와 관계없이 현재 필터/검색 결과 전체를 내려받음.
    export_source = explorer.copy()

    def _series_or_blank(frame: pd.DataFrame, column: str) -> pd.Series:
        if column in frame.columns:
            return frame[column].fillna("")
        return pd.Series("", index=frame.index, dtype="object")

    def _thumbnail_series(frame: pd.DataFrame) -> pd.Series:
        # Reels는 thumbnail_url이 주로 존재하고, Feed는 media_url만 있는 경우가 많으므로 fallback 적용.
        thumb = _series_or_blank(frame, "thumbnail_url").astype(str).str.strip()
        media = _series_or_blank(frame, "media_url").astype(str).str.strip()
        return thumb.where(thumb.ne(""), media)

    def _metric_series(frame: pd.DataFrame, column: str) -> pd.Series:
        if column not in frame.columns:
            return pd.Series(0, index=frame.index, dtype="float64")
        return to_numeric_series(frame[column]).fillna(0)

    def _fmt_metric_series(series: pd.Series) -> pd.Series:
        return series.map(lambda value: f"{int(round(value)):,}" if pd.notna(value) else "-")

    def _build_detail_frame(frame: pd.DataFrame, *, formatted_numbers: bool) -> pd.DataFrame:
        thumb_series = _thumbnail_series(frame)
        permalink_series = _series_or_blank(frame, "permalink")
        category_series = _series_or_blank(frame, "content_category")
        subcategory_series = _series_or_blank(frame, "content_subcategory")
        paid_series = (
            frame["has_paid_bool"].map({True: "Y", False: "N"})
            if "has_paid_bool" in frame.columns
            else pd.Series("N", index=frame.index)
        )

        views_series = _metric_series(frame, views_col)
        reach_series = _metric_series(frame, reach_col)
        interactions_series = _metric_series(frame, interactions_col)
        saved_series = _metric_series(frame, saved_col)

        if formatted_numbers:
            views_values = _fmt_metric_series(views_series)
            reach_values = _fmt_metric_series(reach_series)
            interactions_values = _fmt_metric_series(interactions_series)
            saved_values = _fmt_metric_series(saved_series)
        else:
            views_values = views_series.round().astype("Int64")
            reach_values = reach_series.round().astype("Int64")
            interactions_values = interactions_series.round().astype("Int64")
            saved_values = saved_series.round().astype("Int64")

        return pd.DataFrame(
            {
                "썸네일": thumb_series,
                "게시일": pd.to_datetime(frame["posted_at"], errors="coerce").dt.strftime("%Y-%m-%d"),
                "제목": frame["제목"],
                "유형": frame["content_type"],
                "조회수": views_values,
                "도달수": reach_values,
                "인터랙션": interactions_values,
                "저장": saved_values,
                "Paid": paid_series,
                "카테고리": category_series,
                "서브카테고리": subcategory_series,
                "Instagram": permalink_series,
            }
        )

    if explorer.empty:
        st.info("검색 조건에 해당하는 콘텐츠가 없습니다.")
    else:
        # Excel에서 한글이 깨지지 않도록 UTF-8 BOM 포함.
        export_df = _build_detail_frame(export_source, formatted_numbers=False)
        csv_bytes = export_df.to_csv(index=False).encode("utf-8-sig")

        with explorer_cols[3]:
            st.markdown('<div style="height:1.78rem;"></div>', unsafe_allow_html=True)
            st.download_button(
                "CSV 다운로드",
                data=csv_bytes,
                file_name=(
                    f"greating_instagram_content_"
                    f"{period_start:%Y%m%d}_{period_end:%Y%m%d}.csv"
                ),
                mime="text/csv",
                use_container_width=True,
                key="cp_download_csv",
                help="현재 기간/필터/검색 결과 전체를 다운로드합니다. 표시 개수 제한은 적용하지 않습니다.",
            )

        display_source = explorer if row_limit == "전체" else explorer.head(int(row_limit))
        display = _build_detail_frame(display_source, formatted_numbers=True)

        st.dataframe(
            display,
            use_container_width=True,
            hide_index=True,
            height=min(720, 42 + len(display) * 58),
            column_config={
                "썸네일": st.column_config.ImageColumn("썸네일", width="small"),
                "게시일": st.column_config.TextColumn("게시일", width="small"),
                "제목": st.column_config.TextColumn("제목", width="large"),
                "유형": st.column_config.TextColumn("유형", width="small"),
                "조회수": st.column_config.TextColumn("조회수", width="small"),
                "도달수": st.column_config.TextColumn("도달수", width="small"),
                "인터랙션": st.column_config.TextColumn("인터랙션", width="small"),
                "저장": st.column_config.TextColumn("저장", width="small"),
                "Paid": st.column_config.TextColumn("Paid", width="small"),
                "카테고리": st.column_config.TextColumn("카테고리", width="medium"),
                "서브카테고리": st.column_config.TextColumn("서브카테고리", width="medium"),
                "Instagram": st.column_config.LinkColumn("Instagram", display_text="열기"),
            },
        )




with st.spinner("Google Sheets 데이터를 불러오는 중..."):
    _tables = get_tables()
render_content_performance(_tables)
