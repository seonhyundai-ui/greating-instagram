from __future__ import annotations

from zoneinfo import ZoneInfo

APP_VERSION = "0.7.0"
KST = ZoneInfo("Asia/Seoul")

SHEETS = [
    "ACCOUNT_HISTORY",
    "AUDIENCE_HISTORY",
    "CONTENT_MASTER",
    "CONTENT_LIFETIME",
    "MEDIA_SNAPSHOT",
    "ADS_DAILY",
    "STORY_HISTORY",
]

PERFORMANCE_LABELS = {
    "전체": "total",
    "Organic": "organic",
    "Paid": "paid",
}

METRIC_LABELS = {
    "조회수": "views",
    "도달수": "reach",
    "인터랙션": "interactions",
    "저장": "saved",
}

COLORS = {
    "primary": "#2563EB",
    "primary_soft": "#EFF6FF",
    "blue_2": "#60A5FA",
    "cyan": "#38BDF8",
    "green": "#10B981",
    "green_soft": "#ECFDF5",
    "orange": "#F59E0B",
    "orange_soft": "#FFFBEB",
    "red": "#EF4444",
    "red_soft": "#FEF2F2",
    "purple": "#7C3AED",
    "pink": "#EC4899",
    "slate": "#64748B",
    "slate_2": "#94A3B8",
    "border": "#E2E8F0",
    "text": "#0F172A",
    "muted": "#64748B",
    "surface": "#FFFFFF",
    "surface_2": "#F8FAFC",
}
