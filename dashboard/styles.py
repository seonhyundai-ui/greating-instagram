from __future__ import annotations

import streamlit as st

from dashboard.config import COLORS


def apply_styles() -> None:
    st.markdown(
        f"""
        <style>
            :root {{
                --gt-primary: {COLORS['primary']};
                --gt-text: {COLORS['text']};
                --gt-muted: {COLORS['muted']};
                --gt-border: {COLORS['border']};
                --gt-surface: {COLORS['surface']};
                --gt-surface-2: {COLORS['surface_2']};
            }}

            /* Reset the login-only layout after authentication.
               Login CSS is rendered before st.rerun and can remain in the browser DOM. */
            [data-testid="stSidebar"] {{
                display: block !important;
                visibility: visible !important;
                border-right: 1px solid var(--gt-border);
            }}

            [data-testid="stHeader"] {{
                background: transparent;
            }}

            .block-container {{
                padding-top: 1.15rem !important;
                padding-bottom: 2.2rem !important;
                max-width: 1560px !important;
            }}

            h1, h2, h3, h4 {{
                color: var(--gt-text);
                letter-spacing: -0.02em;
            }}

            h1 {{
                font-size: 2.05rem !important;
                margin-bottom: 0.1rem !important;
            }}

            .dashboard-subtitle {{
                color: var(--gt-muted);
                font-size: 0.9rem;
                margin-bottom: 0.8rem;
            }}

            .period-row {{
                display: flex;
                flex-wrap: wrap;
                gap: 8px;
                margin: 0.55rem 0 0.75rem 0;
            }}

            .period-chip {{
                display: inline-flex;
                align-items: center;
                gap: 7px;
                padding: 7px 11px;
                border-radius: 10px;
                border: 1px solid var(--gt-border);
                background: #FFFFFF;
                color: #334155;
                font-size: 0.82rem;
                box-shadow: 0 1px 2px rgba(15, 23, 42, 0.03);
            }}

            .period-chip strong {{
                color: var(--gt-text);
                font-weight: 800;
            }}

            .filter-note {{
                color: var(--gt-muted);
                font-size: 0.8rem;
                line-height: 1.45;
                padding-top: 1.95rem;
            }}

            .section-title-wrap {{
                display: flex;
                align-items: center;
                gap: 9px;
                margin: 0.15rem 0 0.25rem 0;
            }}

            .section-dot {{
                width: 9px;
                height: 9px;
                border-radius: 999px;
                background: var(--gt-primary);
                box-shadow: 0 0 0 5px #DBEAFE;
                flex: 0 0 auto;
            }}

            .section-title {{
                font-size: 1.28rem;
                font-weight: 800;
                color: var(--gt-text);
                letter-spacing: -0.02em;
            }}

            .section-note {{
                color: var(--gt-muted);
                font-size: 0.82rem;
                margin: 0 0 0.65rem 0;
            }}

            .dynamic-note {{
                background: #F8FAFC;
                border: 1px solid #E2E8F0;
                border-left: 3px solid var(--gt-primary);
                color: #475569;
                border-radius: 9px;
                font-size: 0.8rem;
                padding: 9px 11px;
                margin: 0.25rem 0 0.8rem 0;
            }}

            .kpi-card {{
                position: relative;
                min-height: 156px;
                background: #FFFFFF;
                border: 1px solid var(--gt-border);
                border-radius: 15px;
                padding: 16px 17px 14px 17px;
                overflow: hidden;
                box-shadow: 0 2px 9px rgba(15, 23, 42, 0.035);
            }}

            .kpi-card::before {{
                content: "";
                position: absolute;
                left: 0;
                top: 0;
                right: 0;
                height: 4px;
                background: var(--accent);
            }}

            .kpi-label {{
                color: #475569;
                font-size: 0.81rem;
                font-weight: 700;
                margin-bottom: 7px;
            }}

            .kpi-value-row {{
                display: flex;
                align-items: center;
                justify-content: space-between;
                gap: 10px;
            }}

            .kpi-value {{
                color: var(--gt-text);
                font-size: 1.85rem;
                line-height: 1.05;
                font-weight: 820;
                letter-spacing: -0.035em;
                white-space: nowrap;
                flex: 0 0 auto;
            }}

            .kpi-compare-row {{
                display: flex;
                flex-wrap: wrap;
                gap: 5px;
                margin-top: 10px;
            }}

            .delta-pill {{
                display: inline-flex;
                align-items: center;
                padding: 4px 7px;
                border-radius: 999px;
                font-size: 0.72rem;
                font-weight: 700;
                white-space: nowrap;
            }}

            .delta-up {{
                background: #ECFDF5;
                color: #047857;
            }}

            .delta-down {{
                background: #FEF2F2;
                color: #B91C1C;
            }}

            .delta-flat {{
                background: #F1F5F9;
                color: #475569;
            }}

            .kpi-subline {{
                color: var(--gt-muted);
                font-size: 0.76rem;
                margin-top: 8px;
                line-height: 1.35;
            }}

            .spark-wrap {{
                width: 46%;
                min-width: 96px;
                max-width: 145px;
                height: 30px;
                flex: 1 1 auto;
                opacity: 0.95;
            }}

            .compact-card {{
                background: #FFFFFF;
                border: 1px solid var(--gt-border);
                border-radius: 14px;
                padding: 13px 14px;
                min-height: 170px;
            }}

            div[data-testid="stDataFrame"] {{
                border: 1px solid var(--gt-border);
                border-radius: 12px;
                overflow: hidden;
            }}

            div[data-testid="stPlotlyChart"] {{
                border-radius: 12px;
            }}

            .top-rank {{
                display: inline-flex;
                align-items: center;
                justify-content: center;
                min-width: 48px;
                width: auto;
                height: 28px;
                padding: 0 10px;
                border-radius: 999px;
                color: #FFFFFF;
                background: var(--gt-primary);
                font-size: 0.73rem;
                line-height: 1;
                font-weight: 800;
                white-space: nowrap;
                margin: 2px 0 9px 0;
                box-sizing: border-box;
                overflow: visible;
            }}

            .top-title {{
                font-weight: 800;
                color: var(--gt-text);
                font-size: 0.88rem;
                line-height: 1.35;
                min-height: 2.45rem;
                margin: 3px 0 5px 0;
            }}

            .top-meta {{
                color: var(--gt-muted);
                font-size: 0.72rem;
                margin-bottom: 6px;
            }}

            .top-score {{
                color: var(--gt-primary);
                font-size: 1.15rem;
                font-weight: 800;
                margin-bottom: 4px;
            }}

            .comparison-table-wrap {{
                border: 1px solid var(--gt-border);
                border-radius: 13px;
                overflow: hidden;
                background: #FFFFFF;
                box-shadow: 0 1px 4px rgba(15, 23, 42, 0.03);
            }}

            .comparison-table {{
                width: 100%;
                border-collapse: collapse;
                font-size: 0.78rem;
            }}

            .comparison-table thead th {{
                background: #F1F5F9;
                color: #475569;
                font-weight: 800;
                padding: 10px 9px;
                text-align: right;
                border-bottom: 1px solid var(--gt-border);
                white-space: nowrap;
            }}

            .comparison-table thead th:first-child,
            .comparison-table tbody td:first-child {{
                text-align: left;
            }}

            .comparison-table tbody td {{
                padding: 11px 9px;
                border-bottom: 1px solid #EEF2F7;
                text-align: right;
                color: #334155;
                font-variant-numeric: tabular-nums;
            }}

            .comparison-table tbody tr:nth-child(even) td {{
                background: #FBFDFF;
            }}

            .comparison-table tbody tr:last-child td {{
                border-bottom: 0;
            }}

            .comparison-table tbody td:first-child {{
                font-weight: 750;
                color: var(--gt-text);
            }}

            .table-delta {{
                display: inline-flex;
                align-items: center;
                justify-content: center;
                min-width: 58px;
                padding: 4px 7px;
                border-radius: 999px;
                font-weight: 800;
                font-size: 0.72rem;
            }}

            .table-delta-up {{
                background: #ECFDF5;
                color: #047857;
            }}

            .table-delta-down {{
                background: #FEF2F2;
                color: #B91C1C;
            }}

            .table-delta-flat {{
                background: #F1F5F9;
                color: #64748B;
            }}

            .mini-chart-label {{
                color: #475569;
                font-size: 0.78rem;
                font-weight: 800;
                margin: 0 0 0.15rem 0;
            }}

            hr {{
                border-color: #EEF2F7 !important;
            }}

            /* Streamlit radio/select polish */
            div[role="radiogroup"] {{
                gap: 0.35rem;
            }}

            div[data-baseweb="select"] > div {{
                border-radius: 10px;
                border-color: var(--gt-border);
                background: #F8FAFC;
            }}
        </style>
        """,
        unsafe_allow_html=True,
    )
