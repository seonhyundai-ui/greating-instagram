from __future__ import annotations

import calendar
import html
from datetime import date

import pandas as pd
import streamlit as st

from config.settings import GOOGLE_SPREADSHEET_ID
from src.sheets_client import get_gspread_client
from dashboard.config import COLORS, METRIC_LABELS, PERFORMANCE_LABELS, SHEETS

# ============================================================
# Data loading
# ============================================================

@st.cache_data(ttl=300, show_spinner=False)
def load_all_data() -> dict[str, pd.DataFrame]:
    client = get_gspread_client()
    spreadsheet = client.open_by_key(GOOGLE_SPREADSHEET_ID)

    result: dict[str, pd.DataFrame] = {}

    for sheet_name in SHEETS:
        worksheet = spreadsheet.worksheet(sheet_name)
        records = worksheet.get_all_records()
        result[sheet_name] = pd.DataFrame(records)

    return result


def reload_data() -> None:
    st.cache_data.clear()
    st.rerun()


# ============================================================
# Generic helpers
# ============================================================

def to_numeric_series(series: pd.Series) -> pd.Series:
    return pd.to_numeric(series, errors="coerce")


def safe_pct_change(current: float | int | None, previous: float | int | None) -> float | None:
    if current is None or previous is None:
        return None

    try:
        current_f = float(current)
        previous_f = float(previous)
    except (TypeError, ValueError):
        return None

    if previous_f == 0:
        return None

    return (current_f - previous_f) / previous_f * 100


def fmt_delta(value: float | None) -> str:
    if value is None or pd.isna(value):
        return "-"

    sign = "+" if value > 0 else ""
    return f"{sign}{value:.1f}%"


def fmt_int(value) -> str:
    if value is None or pd.isna(value):
        return "-"
    return f"{int(round(float(value))):,}"


def fmt_won(value) -> str:
    if value is None or pd.isna(value):
        return "-"
    return f"₩{int(round(float(value))):,}"


def fmt_period(start: date, end: date) -> str:
    """Use a normal hyphen instead of '~' so the displayed date never visually runs together."""
    if start.year == end.year:
        return f"{start.year}.{start.month:02d}.{start.day:02d} - {end.month:02d}.{end.day:02d}"
    return f"{start.isoformat()} - {end.isoformat()}"


def previous_month_same_period(current_start: date, current_end: date) -> tuple[date, date]:
    if current_start.month == 1:
        year = current_start.year - 1
        month = 12
    else:
        year = current_start.year
        month = current_start.month - 1

    start = date(year, month, 1)
    end_day = min(current_end.day, calendar.monthrange(year, month)[1])
    end = date(year, month, end_day)
    return start, end


def previous_year_same_period(current_start: date, current_end: date) -> tuple[date, date]:
    year = current_start.year - 1
    start = date(year, current_start.month, 1)
    end_day = min(current_end.day, calendar.monthrange(year, current_end.month)[1])
    end = date(year, current_end.month, end_day)
    return start, end


def metric_column(metric_label: str, performance_label: str) -> str:
    metric = METRIC_LABELS[metric_label]
    layer = PERFORMANCE_LABELS[performance_label]

    if metric == "reach" and layer == "total":
        return "reach_total_gross"

    return f"{metric}_{layer}"


def content_type_from_row(row: pd.Series) -> str:
    product_type = str(row.get("media_product_type", "")).upper().strip()
    if product_type == "REELS":
        return "Reels"
    return "Feed"


def filter_by_period(df: pd.DataFrame, start: date, end: date) -> pd.DataFrame:
    if df.empty or "posted_date" not in df.columns:
        return df.iloc[0:0].copy()

    mask = (df["posted_date"] >= start) & (df["posted_date"] <= end)
    return df.loc[mask].copy()


def filter_content_type(df: pd.DataFrame, content_type: str) -> pd.DataFrame:
    if content_type == "전체":
        return df.copy()
    return df[df["content_type"] == content_type].copy()


def filter_performance_scope(df: pd.DataFrame, performance_label: str) -> pd.DataFrame:
    """
    Overview performance scope policy:
    - 전체: all selected contents, use total metrics.
    - Organic: all selected contents, use organic metrics.
      Paid contents remain included because they also have organic performance.
    - Paid: only contents that actually ran paid media, use paid metrics.
    """
    if df.empty:
        return df.copy()

    if performance_label != "Paid":
        return df.copy()

    if "has_paid_bool" not in df.columns:
        return df.iloc[0:0].copy()

    return df[df["has_paid_bool"]].copy()


def sum_metric(df: pd.DataFrame, column: str) -> float:
    if df.empty or column not in df.columns:
        return 0.0

    values = to_numeric_series(df[column])
    return float(values.sum(min_count=1)) if values.notna().any() else 0.0


def mean_metric(df: pd.DataFrame, column: str) -> float:
    if df.empty or column not in df.columns:
        return 0.0

    values = to_numeric_series(df[column])
    return float(values.mean()) if values.notna().any() else 0.0


def bool_series(series: pd.Series) -> pd.Series:
    return series.astype(str).str.strip().str.upper().isin(["TRUE", "1", "YES"])


def plot_config() -> dict:
    return {
        "displayModeBar": False,
        "responsive": True,
    }


def chart_layout(height: int, *, showlegend: bool = False) -> dict:
    return {
        "height": height,
        "margin": dict(l=8, r=8, t=18, b=8),
        "paper_bgcolor": "rgba(0,0,0,0)",
        "plot_bgcolor": "rgba(0,0,0,0)",
        "font": dict(color="#475569", size=11),
        "showlegend": showlegend,
        "hoverlabel": dict(bgcolor="#0F172A", font_color="#FFFFFF"),
    }


def render_section_title(title: str, note: str | None = None) -> None:
    st.markdown(
        f"""
        <div class="section-title-wrap">
            <span class="section-dot"></span>
            <span class="section-title">{html.escape(title)}</span>
        </div>
        """,
        unsafe_allow_html=True,
    )
    if note:
        st.markdown(f'<div class="section-note">{html.escape(note)}</div>', unsafe_allow_html=True)


def delta_class(value: float | None) -> str:
    if value is None or pd.isna(value) or abs(float(value)) < 1e-12:
        return "delta-flat"
    return "delta-up" if float(value) > 0 else "delta-down"


def delta_arrow(value: float | None) -> str:
    if value is None or pd.isna(value) or abs(float(value)) < 1e-12:
        return "•"
    return "↑" if float(value) > 0 else "↓"


def sparkline_svg(values: list[float], color: str) -> str:
    clean = [float(v) for v in values if v is not None and not pd.isna(v)]
    if not clean:
        return ""

    width = 250.0
    height = 28.0
    pad = 2.0

    if len(clean) == 1:
        y = height / 2
        points = f"{pad},{y:.1f} {width - pad},{y:.1f}"
    else:
        min_v = min(clean)
        max_v = max(clean)
        span = max(max_v - min_v, 1.0)
        points_list = []
        for i, value in enumerate(clean):
            x = pad + (width - 2 * pad) * i / (len(clean) - 1)
            y = pad + (height - 2 * pad) * (1 - (value - min_v) / span)
            points_list.append(f"{x:.1f},{y:.1f}")
        points = " ".join(points_list)

    return (
        f'<svg viewBox="0 0 {width:.0f} {height:.0f}" width="100%" height="28" '
        f'preserveAspectRatio="none" aria-hidden="true">'
        f'<polyline fill="none" stroke="{color}" stroke-width="2.2" '
        f'stroke-linecap="round" stroke-linejoin="round" points="{points}" />'
        f'</svg>'
    )


def render_kpi_card(
    *,
    label: str,
    value: str,
    accent: str,
    prev_delta: float | None = None,
    yoy_delta: float | None = None,
    prev_label: str = "전월동기 대비",
    yoy_label: str = "전년동기 대비",
    subline: str | None = None,
    spark_values: list[float] | None = None,
    direct_delta_text: str | None = None,
    direct_delta_value: float | None = None,
    direct_delta_label: str = "직전 수집일 대비",
) -> None:
    compare_html = ""

    if direct_delta_text is not None:
        compare_html += (
            f'<span class="delta-pill {delta_class(direct_delta_value)}">'
            f'{delta_arrow(direct_delta_value)} {html.escape(direct_delta_label)} {html.escape(direct_delta_text)}'
            f'</span>'
        )
    else:
        compare_html += (
            f'<span class="delta-pill {delta_class(prev_delta)}">'
            f'{delta_arrow(prev_delta)} {html.escape(prev_label)} {html.escape(fmt_delta(prev_delta))}'
            f'</span>'
        )
        compare_html += (
            f'<span class="delta-pill {delta_class(yoy_delta)}">'
            f'{delta_arrow(yoy_delta)} {html.escape(yoy_label)} {html.escape(fmt_delta(yoy_delta))}'
            f'</span>'
        )

    spark_html = ""
    if spark_values:
        spark_html = f'<div class="spark-wrap">{sparkline_svg(spark_values, accent)}</div>'

    subline_html = ""
    if subline:
        subline_html = f'<div class="kpi-subline">{html.escape(subline)}</div>'

    card_html = (
        f'<div class="kpi-card" style="--accent:{accent}">'
        f'<div class="kpi-label">{html.escape(label)}</div>'
        f'<div class="kpi-value-row">'
        f'<div class="kpi-value">{html.escape(value)}</div>'
        f'{spark_html}'
        f'</div>'
        f'<div class="kpi-compare-row">{compare_html}</div>'
        f'{subline_html}'
        f'</div>'
    )
    st.markdown(card_html, unsafe_allow_html=True)


def format_table_value(metric_name: str, value: float) -> str:
    if metric_name == "콘텐츠수":
        return f"{int(round(value)):,}개"
    return f"{int(round(value)):,}"


def comparison_delta_html(value: float | None) -> str:
    if value is None or pd.isna(value):
        return '<span class="table-delta table-delta-flat">-</span>'

    value_f = float(value)
    if abs(value_f) < 1e-12:
        css_class = "table-delta-flat"
        arrow = "•"
    elif value_f > 0:
        css_class = "table-delta-up"
        arrow = "↑"
    else:
        css_class = "table-delta-down"
        arrow = "↓"

    return (
        f'<span class="table-delta {css_class}">'
        f'{arrow} {html.escape(fmt_delta(value_f))}'
        f'</span>'
    )


def render_comparison_table(rows: list[dict]) -> None:
    body_rows = []
    for row in rows:
        body_rows.append(
            "<tr>"
            f"<td>{html.escape(str(row['지표']))}</td>"
            f"<td>{html.escape(str(row['이번달']))}</td>"
            f"<td>{html.escape(str(row['전월동기']))}</td>"
            f"<td>{html.escape(str(row['전년동기']))}</td>"
            f"<td>{comparison_delta_html(row['전월동기 대비'])}</td>"
            f"<td>{comparison_delta_html(row['전년동기 대비'])}</td>"
            "</tr>"
        )

    table_html = (
        '<div class="comparison-table-wrap">'
        '<table class="comparison-table">'
        '<thead><tr>'
        '<th>지표</th>'
        '<th>이번달</th>'
        '<th>전월동기</th>'
        '<th>전년동기</th>'
        '<th>전월 대비</th>'
        '<th>전년 대비</th>'
        '</tr></thead>'
        f"<tbody>{''.join(body_rows)}</tbody>"
        '</table></div>'
    )
    st.markdown(table_html, unsafe_allow_html=True)


# ============================================================
# Normalize source tables
# ============================================================

def prepare_tables(data: dict[str, pd.DataFrame]) -> dict[str, pd.DataFrame]:
    account = data["ACCOUNT_HISTORY"].copy()
    audience = data["AUDIENCE_HISTORY"].copy()
    master = data["CONTENT_MASTER"].copy()
    lifetime = data["CONTENT_LIFETIME"].copy()
    snapshot = data["MEDIA_SNAPSHOT"].copy()
    ads = data["ADS_DAILY"].copy()
    story = data["STORY_HISTORY"].copy()

    if not account.empty:
        account["snapshot_date"] = pd.to_datetime(account["snapshot_date"], errors="coerce")
        account["followers_count"] = to_numeric_series(account["followers_count"])
        account = account.dropna(subset=["snapshot_date"]).sort_values("snapshot_date")

    if not audience.empty:
        audience["snapshot_date"] = pd.to_datetime(audience["snapshot_date"], errors="coerce")
        audience["value"] = to_numeric_series(audience["value"])
        audience["percentage"] = to_numeric_series(audience["percentage"])
        audience["dimension_total"] = to_numeric_series(audience["dimension_total"])

    if not master.empty:
        master["media_id"] = master["media_id"].astype(str)
        master["posted_at"] = pd.to_datetime(master["posted_at"], errors="coerce")
        master["posted_date"] = master["posted_at"].dt.date
        master["content_type"] = master.apply(content_type_from_row, axis=1)
        if "has_paid" in master.columns:
            master["has_paid_bool"] = bool_series(master["has_paid"])
        else:
            master["has_paid_bool"] = False

    if not lifetime.empty:
        lifetime["media_id"] = lifetime["media_id"].astype(str)
        lifetime["posted_at_metric"] = pd.to_datetime(lifetime["posted_at"], errors="coerce")

    metric_columns = [
        "views_total", "views_organic", "views_paid",
        "reach_total_gross", "reach_organic", "reach_paid",
        "likes_total", "likes_organic", "likes_paid",
        "comments_total", "comments_organic", "comments_paid",
        "saved_total", "saved_organic", "saved_paid",
        "shares_total", "shares_organic", "shares_paid",
        "interactions_total", "interactions_organic", "interactions_paid",
    ]

    for column in metric_columns:
        if column in lifetime.columns:
            lifetime[column] = to_numeric_series(lifetime[column])

    if not snapshot.empty:
        snapshot["media_id"] = snapshot["media_id"].astype(str)
        snapshot["snapshot_date"] = pd.to_datetime(snapshot["snapshot_date"], errors="coerce")
        snapshot["posted_at_snapshot"] = pd.to_datetime(snapshot["posted_at"], errors="coerce")
        snapshot["snapshot_age_days"] = (
            snapshot["snapshot_date"].dt.normalize()
            - snapshot["posted_at_snapshot"].dt.normalize()
        ).dt.days
        for column in metric_columns:
            if column in snapshot.columns:
                snapshot[column] = to_numeric_series(snapshot[column])

    if master.empty:
        content = master.copy()
    else:
        metric_keep = ["media_id"] + [c for c in metric_columns if c in lifetime.columns]
        if "metric_qa_status" in lifetime.columns:
            metric_keep.append("metric_qa_status")

        content = master.merge(
            lifetime[metric_keep] if not lifetime.empty else pd.DataFrame(columns=metric_keep),
            on="media_id",
            how="left",
        )

    if not ads.empty:
        ads["date"] = pd.to_datetime(ads["date"], errors="coerce")
        ads["ad_date"] = ads["date"].dt.date
        for column in [
            "spend", "impressions", "reach_paid", "frequency",
            "clicks", "ctr", "cpc", "cpm",
            "paid_likes", "paid_saved", "paid_interactions",
        ]:
            if column in ads.columns:
                ads[column] = to_numeric_series(ads[column])

    if not story.empty:
        story["story_id"] = story["story_id"].astype(str)
        story["posted_at"] = pd.to_datetime(story["posted_at"], errors="coerce")
        story["posted_date"] = story["posted_at"].dt.date
        story["first_collected_at"] = pd.to_datetime(
            story.get("first_collected_at"), errors="coerce"
        )
        story["last_collected_at"] = pd.to_datetime(
            story.get("last_collected_at"), errors="coerce"
        )

        story_numeric_columns = [
            "views", "reach", "shares", "replies", "total_interactions",
            "follows", "profile_visits", "link_clicks", "tap_forward",
            "tap_back", "tap_exit", "swipe_forward",
        ]
        for column in story_numeric_columns:
            if column in story.columns:
                story[column] = to_numeric_series(story[column])

        # Rates are calculated only when the denominator is available.
        if "reach" in story.columns:
            safe_reach = story["reach"].replace(0, pd.NA)
            if "total_interactions" in story.columns:
                story["interaction_rate"] = (story["total_interactions"] / safe_reach) * 100
            if "link_clicks" in story.columns:
                story["link_click_rate"] = (story["link_clicks"] / safe_reach) * 100

    return {
        "account": account,
        "audience": audience,
        "master": master,
        "lifetime": lifetime,
        "snapshot": snapshot,
        "content": content,
        "ads": ads,
        "story": story,
    }


# ============================================================
# Summary helpers
# ============================================================

def period_summary(df: pd.DataFrame, performance_label: str) -> dict[str, float]:
    result = {
        "contents": float(len(df)),
    }

    for metric_label in ["조회수", "도달수", "인터랙션", "저장"]:
        column = metric_column(metric_label, performance_label)
        result[f"sum_{metric_label}"] = sum_metric(df, column)
        result[f"mean_{metric_label}"] = mean_metric(df, column)

    return result




def get_tables() -> dict[str, pd.DataFrame]:
    """Load and normalize dashboard tables. Raw Google Sheets reads are cached for 5 minutes."""
    return prepare_tables(load_all_data())
