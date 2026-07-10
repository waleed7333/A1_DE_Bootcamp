from __future__ import annotations

import json
import os
from datetime import UTC, datetime
from pathlib import Path
from typing import Any

import pandas as pd
import plotly.graph_objects as go
import requests
import streamlit as st

try:
    import clickhouse_connect
except Exception:  # pragma: no cover
    clickhouse_connect = None


# -----------------------------------------------------------------------------
# Configuration
# -----------------------------------------------------------------------------
RUNTIME_ROOT = Path(os.getenv("OBSERVABILITY_RUNTIME_ROOT", "/opt/project/runtime"))
REPORTS_ROOT = Path(os.getenv("OBSERVABILITY_REPORTS_ROOT", "/opt/project/reports"))
DATA_ROOT = Path(os.getenv("OBSERVABILITY_DATA_ROOT", "/opt/project/data"))

CLICKHOUSE_HOST = os.getenv("CLICKHOUSE_HOST", "clickhouse")
CLICKHOUSE_PORT = int(os.getenv("CLICKHOUSE_PORT", "8123"))
CLICKHOUSE_USER = os.getenv("CLICKHOUSE_USER", "default")
CLICKHOUSE_PASSWORD = os.getenv("CLICKHOUSE_PASSWORD", "")
CLICKHOUSE_DATABASE = os.getenv("CLICKHOUSE_DATABASE", "personalization_olap")

REFRESH_SECONDS = int(os.getenv("OBSERVABILITY_REFRESH_SECONDS", "20"))

SERVICES = [
    "postgres",
    "zookeeper",
    "kafka1",
    "kafka2",
    "kafka3",
    "kafka_ui",
    "debezium",
    "filebeat",
    "spark",
    "airflow",
    "minio",
    "clickhouse",
    "operations_console",
]

TOPICS = [
    "clickstream-events",
    "webserver-logs",
    "users-cdc",
    "orders-cdc",
    "order-items-cdc",
    "debezium-connect-configs",
    "debezium-connect-offsets",
    "debezium-connect-status",
]

POWER_BI_VIEWS = [
    "v_dim_date",
    "v_dim_product",
    "v_dim_user_current",
    "v_fact_clickstream_event",
    "v_fact_order",
    "v_fact_order_item",
    "v_mart_journey_session",
    "v_mart_navigation_paths",
    "v_mart_product_performance_daily",
    "v_mart_web_experience_daily",
    "v_mart_context_impact_daily",
    "v_mart_personalization_candidates",
]


# -----------------------------------------------------------------------------
# Page setup and visual theme
# -----------------------------------------------------------------------------
st.set_page_config(
    page_title="Clickstream Operations Console",
    page_icon="◉",
    layout="wide",
    initial_sidebar_state="collapsed",
)

st.markdown(f'<meta http-equiv="refresh" content="{REFRESH_SECONDS}">', unsafe_allow_html=True)

st.markdown(
    """
    <style>
    :root {
        --bg: #F8FAFC;
        --card: #FFFFFF;
        --text: #0F172A;
        --muted: #64748B;
        --border: #E2E8F0;
        --blue: #2563EB;
        --green: #16A34A;
        --amber: #F59E0B;
        --red: #DC2626;
        --gray: #94A3B8;
        --purple: #7C3AED;
        --orange: #EA580C;
        --teal: #0F766E;
    }

    .main {
        background: var(--bg);
    }

    div[data-testid="stAppViewContainer"] {
        background: var(--bg);
    }

    div[data-testid="stHeader"] {
        background: rgba(248, 250, 252, 0.85);
    }

    .block-container {
        padding-top: 1.4rem;
        padding-bottom: 2rem;
        max-width: 1680px;
    }

    h1, h2, h3 {
        color: var(--text);
        letter-spacing: -0.02em;
    }

    .hero {
        background: linear-gradient(135deg, #0F172A 0%, #1D4ED8 56%, #0F766E 100%);
        border-radius: 22px;
        padding: 26px 30px;
        color: white;
        margin-bottom: 18px;
        box-shadow: 0 14px 30px rgba(15, 23, 42, 0.16);
    }

    .hero-title {
        font-size: 34px;
        font-weight: 800;
        margin: 0;
    }

    .hero-subtitle {
        font-size: 15px;
        color: #DBEAFE;
        margin-top: 6px;
    }

    .card {
        background: var(--card);
        border: 1px solid var(--border);
        border-radius: 18px;
        padding: 18px 18px;
        box-shadow: 0 8px 20px rgba(15, 23, 42, 0.05);
        min-height: 112px;
    }

    .metric-label {
        color: var(--muted);
        font-size: 13px;
        font-weight: 700;
        text-transform: uppercase;
        letter-spacing: .04em;
    }

    .metric-value {
        color: var(--text);
        font-size: 25px;
        font-weight: 800;
        line-height: 1.2;
        margin-top: 8px;
    }

    .metric-help {
        color: var(--muted);
        font-size: 13px;
        margin-top: 8px;
    }

    .badge {
        display: inline-flex;
        align-items: center;
        gap: 6px;
        border-radius: 999px;
        padding: 6px 11px;
        font-size: 12px;
        font-weight: 800;
        border: 1px solid transparent;
        white-space: nowrap;
    }

    .badge-green {
        background: #DCFCE7;
        color: #166534;
        border-color: #BBF7D0;
    }

    .badge-amber {
        background: #FEF3C7;
        color: #92400E;
        border-color: #FDE68A;
    }

    .badge-red {
        background: #FEE2E2;
        color: #991B1B;
        border-color: #FECACA;
    }

    .badge-gray {
        background: #F1F5F9;
        color: #475569;
        border-color: #CBD5E1;
    }

    .badge-blue {
        background: #DBEAFE;
        color: #1E40AF;
        border-color: #BFDBFE;
    }

    .section-title {
        display: flex;
        align-items: center;
        gap: 10px;
        font-size: 22px;
        font-weight: 800;
        margin: 26px 0 12px 0;
        color: var(--text);
    }

    .small-note {
        color: var(--muted);
        font-size: 13px;
    }

    div[data-testid="stDataFrame"] {
        border: 1px solid var(--border);
        border-radius: 14px;
        overflow: hidden;
    }

    .stTabs [data-baseweb="tab-list"] {
        gap: 8px;
    }

    .stTabs [data-baseweb="tab"] {
        background: #FFFFFF;
        border: 1px solid #E2E8F0;
        border-radius: 999px;
        color: #334155;
        padding: 8px 14px;
    }

    .stTabs [aria-selected="true"] {
        background: #DBEAFE !important;
        color: #1D4ED8 !important;
    }
    </style>
    """,
    unsafe_allow_html=True,
)


# -----------------------------------------------------------------------------
# Generic helpers
# -----------------------------------------------------------------------------
def now_utc() -> datetime:
    """Return the current UTC timestamp."""
    return datetime.now(UTC)


def read_json(path: Path) -> dict[str, Any]:
    """Read optional JSON evidence files without crashing the dashboard."""
    try:
        payload = json.loads(path.read_text(encoding="utf-8"))
        return payload if isinstance(payload, dict) else {}
    except (OSError, json.JSONDecodeError):
        return {}


def first_value(*values: Any, default: Any = "Not available") -> Any:
    """Return the first useful value from a list of optional values."""
    for value in values:
        if value not in (None, "", [], {}):
            return value
    return default


def nested(payload: dict[str, Any], *keys: str, default: Any = None) -> Any:
    """Safely fetch a nested value from a dictionary."""
    current: Any = payload
    for key in keys:
        if not isinstance(current, dict) or key not in current:
            return default
        current = current[key]
    return current


def parse_dt(value: Any) -> datetime | None:
    """Parse common ISO timestamp formats."""
    if not value:
        return None

    if isinstance(value, datetime):
        return value if value.tzinfo else value.replace(tzinfo=UTC)

    text = str(value).strip()
    if not text:
        return None

    try:
        text = text.replace("Z", "+00:00")
        parsed = datetime.fromisoformat(text)
        return parsed if parsed.tzinfo else parsed.replace(tzinfo=UTC)
    except ValueError:
        return None


def age_label(value: Any) -> str:
    """Return a human-readable age for a timestamp."""
    parsed = parse_dt(value)
    if not parsed:
        return "Not available"

    seconds = max(0, int((now_utc() - parsed.astimezone(UTC)).total_seconds()))

    if seconds < 60:
        return f"{seconds}s ago"

    minutes = seconds // 60

    if minutes < 60:
        return f"{minutes}m ago"

    hours = minutes // 60

    if hours < 24:
        return f"{hours}h ago"

    return f"{hours // 24}d ago"


def minutes_between(left: Any, right: Any) -> str:
    """Return the absolute gap in minutes between two timestamps."""
    a = parse_dt(left)
    b = parse_dt(right)

    if not a or not b:
        return "Not available"

    minutes = abs((b.astimezone(UTC) - a.astimezone(UTC)).total_seconds()) / 60
    return f"{minutes:.1f} min"


def normalize_status(value: Any) -> str:
    """Normalize many possible status spellings into a small status vocabulary."""
    text = str(value or "UNKNOWN").strip().upper()

    if text in {
        "PASS",
        "PASSED",
        "SUCCESS",
        "SUCCEEDED",
        "HEALTHY",
        "RUNNING",
        "ACTIVE",
        "READY",
        "OK",
        "TRUE",
    }:
        return "HEALTHY"

    if text in {
        "WARN",
        "WARNING",
        "DEGRADED",
        "STARTING",
        "PENDING",
        "STALE",
    }:
        return "DEGRADED"

    if text in {
        "FAIL",
        "FAILED",
        "ERROR",
        "UNHEALTHY",
        "EXITED",
        "DOWN",
        "FALSE",
    }:
        return "FAILED"

    if text in {
        "STOPPED",
        "MAINTENANCE",
        "MISSING",
        "UNKNOWN",
        "NOT AVAILABLE",
    }:
        return "MAINTENANCE"

    return text


def badge_html(value: Any) -> str:
    """Render a colored status badge."""
    status = normalize_status(value)

    css = {
        "HEALTHY": "badge-green",
        "DEGRADED": "badge-amber",
        "FAILED": "badge-red",
        "MAINTENANCE": "badge-gray",
    }.get(status, "badge-blue")

    label = str(value if value not in (None, "") else "UNKNOWN")
    return f'<span class="badge {css}">{label}</span>'


def render_section(title: str, icon: str = "") -> None:
    """Render a section title with consistent styling."""
    st.markdown(
        f'<div class="section-title">{icon} {title}</div>',
        unsafe_allow_html=True,
    )


def render_card(
    label: str,
    value: Any,
    help_text: str = "",
    status: bool = False,
) -> None:
    """Render one executive metric card."""
    rendered_value = badge_html(value) if status else str(value)

    st.markdown(
        f"""
        <div class="card">
            <div class="metric-label">{label}</div>
            <div class="metric-value">{rendered_value}</div>
            <div class="metric-help">{help_text}</div>
        </div>
        """,
        unsafe_allow_html=True,
    )


def dataframe(rows: list[dict[str, Any]], empty_message: str) -> None:
    """Render a dataframe or a clear empty-state message."""
    if rows:
        st.dataframe(pd.DataFrame(rows), use_container_width=True, hide_index=True)
    else:
        st.info(empty_message)


# -----------------------------------------------------------------------------
# Evidence loaders
# -----------------------------------------------------------------------------
def load_evidence() -> dict[str, dict[str, Any]]:
    """Load all known project evidence files."""
    return {
        "snapshot": read_json(RUNTIME_ROOT / "observability" / "latest.json"),
        "streaming": read_json(RUNTIME_ROOT / "streaming_status.json"),
        "validation": read_json(REPORTS_ROOT / "validation_latest.json"),
        "serving": read_json(REPORTS_ROOT / "serving_latest.json"),
        "manifest": read_json(DATA_ROOT / "source" / "generation_manifest.json"),
        "live": read_json(RUNTIME_ROOT / "source_publishers" / "live_generator_state.json"),
    }


def checks_from_snapshot(snapshot: dict[str, Any]) -> list[dict[str, Any]]:
    """Return normalized checks from the latest observability snapshot."""
    checks = snapshot.get("checks", [])
    return checks if isinstance(checks, list) else []


@st.cache_data(ttl=10, show_spinner=False)
def http_get_json(url: str) -> Any:
    """Fetch a small HTTP endpoint used for health evidence."""
    response = requests.get(url, timeout=4)
    response.raise_for_status()

    try:
        return response.json()
    except ValueError:
        return response.text


@st.cache_resource(show_spinner=False)
def clickhouse_client() -> Any:
    """Create a cached ClickHouse client when clickhouse-connect is installed."""
    if clickhouse_connect is None:
        return None

    try:
        return clickhouse_connect.get_client(
            host=CLICKHOUSE_HOST,
            port=CLICKHOUSE_PORT,
            username=CLICKHOUSE_USER,
            password=CLICKHOUSE_PASSWORD,
            database=CLICKHOUSE_DATABASE,
        )
    except Exception:
        return None


def clickhouse_query(sql: str) -> pd.DataFrame:
    """Run a ClickHouse query and return a DataFrame. Fail closed with an empty DataFrame."""
    client = clickhouse_client()

    if client is None:
        return pd.DataFrame()

    try:
        return client.query_df(sql)
    except Exception:
        return pd.DataFrame()


@st.cache_data(ttl=15, show_spinner=False)
def clickhouse_view_counts() -> pd.DataFrame:
    """Return row counts for the Power BI serving views."""
    parts = [
        f"SELECT '{view}' AS view_name, count() AS rows FROM {view}"
        for view in POWER_BI_VIEWS
    ]
    sql = " UNION ALL ".join(parts)
    return clickhouse_query(sql)


@st.cache_data(ttl=15, show_spinner=False)
def clickhouse_latest_event() -> pd.DataFrame:
    """Return the latest clickstream timestamp available in ClickHouse."""
    return clickhouse_query(
        """
        SELECT
            count() AS clickstream_rows,
            max(event_timestamp) AS latest_event_timestamp
        FROM v_fact_clickstream_event
        """
    )


# -----------------------------------------------------------------------------
# Row builders
# -----------------------------------------------------------------------------
def build_container_rows(snapshot: dict[str, Any]) -> list[dict[str, Any]]:
    """Build container health rows from snapshot checks when available."""
    checks = checks_from_snapshot(snapshot)
    rows: list[dict[str, Any]] = []

    for service in SERVICES:
        matching = [
            check
            for check in checks
            if service.replace("-", "_") in str(check).lower()
            or service in str(check).lower()
        ]

        status = "Not available"
        detail = "Waiting for host-collected snapshot"

        if matching:
            status = first_value(matching[0].get("status"), default="UNKNOWN")
            detail = first_value(
                matching[0].get("details"),
                matching[0].get("detail"),
                default="No detail",
            )

        rows.append(
            {
                "Container": service,
                "Status": normalize_status(status),
                "Health": status,
                "CPU %": "N/A",
                "Memory": "N/A",
                "Restart Count": "N/A",
                "Uptime": "N/A",
                "Ports": "Configured in docker-compose.yml",
                "Detail": detail,
            }
        )

    return rows


def build_source_rows(
    manifest: dict[str, Any],
    live: dict[str, Any],
) -> list[dict[str, Any]]:
    """Build source generation rows from the generation manifest."""
    counts = manifest.get("counts", {}) if isinstance(manifest, dict) else {}

    return [
        {
            "Source": "Clickstream Events",
            "Count": counts.get("clickstream_total", "N/A"),
            "Valid": counts.get("clickstream_valid", "N/A"),
            "Invalid": counts.get("clickstream_invalid", "N/A"),
            "Duplicates": counts.get("clickstream_duplicates", "N/A"),
            "Status": "Generated" if counts else "Not available",
        },
        {
            "Source": "Web Server Logs",
            "Count": counts.get("web_logs_total", "N/A"),
            "Valid": counts.get("web_logs_valid", "N/A"),
            "Invalid": counts.get("web_logs_invalid", "N/A"),
            "Duplicates": counts.get("web_logs_duplicates", "N/A"),
            "Status": "Generated" if counts else "Not available",
        },
        {
            "Source": "Product Catalog",
            "Count": first_value(
                counts.get("product_catalog"),
                counts.get("product_count"),
                default="N/A",
            ),
            "Valid": "N/A",
            "Invalid": "N/A",
            "Duplicates": "N/A",
            "Status": "Static reference",
        },
        {
            "Source": "Users Seed",
            "Count": first_value(
                counts.get("users"),
                counts.get("user_count"),
                default="N/A",
            ),
            "Valid": "N/A",
            "Invalid": "N/A",
            "Duplicates": "N/A",
            "Status": "PostgreSQL seed",
        },
        {
            "Source": "Orders Seed",
            "Count": first_value(
                counts.get("orders"),
                counts.get("order_count"),
                default="N/A",
            ),
            "Valid": "N/A",
            "Invalid": "N/A",
            "Duplicates": "N/A",
            "Status": "PostgreSQL seed",
        },
        {
            "Source": "Order Items Seed",
            "Count": first_value(
                counts.get("order_items"),
                counts.get("order_item_count"),
                default="N/A",
            ),
            "Valid": "N/A",
            "Invalid": "N/A",
            "Duplicates": "N/A",
            "Status": "PostgreSQL seed",
        },
        {
            "Source": "Live Generator",
            "Count": first_value(
                live.get("published_count"),
                live.get("generated_count"),
                default="N/A",
            ),
            "Valid": "N/A",
            "Invalid": "N/A",
            "Duplicates": "N/A",
            "Status": first_value(
                live.get("status"),
                live.get("state"),
                default="Not available",
            ),
        },
    ]


def build_quality_rows(validation: dict[str, Any]) -> list[dict[str, Any]]:
    """Build quality reconciliation rows from validation report details."""
    details = validation.get("details", {}) if isinstance(validation, dict) else {}

    sources = [
        "clickstream",
        "web_logs",
        "users_cdc",
        "orders_cdc",
        "order_items_cdc",
        "product_catalog",
        "weather",
        "holidays",
    ]

    rows: list[dict[str, Any]] = []

    for source in sources:
        data = details.get(source, {}) if isinstance(details, dict) else {}

        raw = (
            first_value(data.get("raw"), data.get("input_rows"), default="N/A")
            if isinstance(data, dict)
            else "N/A"
        )
        clean = (
            first_value(data.get("clean"), data.get("accepted_rows"), default="N/A")
            if isinstance(data, dict)
            else "N/A"
        )
        quarantine = (
            first_value(data.get("quarantine"), data.get("rejected_rows"), default="N/A")
            if isinstance(data, dict)
            else "N/A"
        )
        duplicates = (
            first_value(data.get("duplicates"), data.get("duplicate_rows"), default="N/A")
            if isinstance(data, dict)
            else "N/A"
        )

        success = "N/A"

        try:
            if raw not in ("N/A", 0, "0") and clean != "N/A":
                success = f"{(float(clean) / float(raw)) * 100:.1f}%"
        except Exception:
            pass

        rows.append(
            {
                "Source": source,
                "Raw/Input": raw,
                "Clean/Accepted": clean,
                "Quarantine/Rejected": quarantine,
                "Duplicates": duplicates,
                "Success %": success,
                "Reconciled": data.get("reconciled", "N/A")
                if isinstance(data, dict)
                else "N/A",
            }
        )

    return rows


def build_batch_rows(
    validation: dict[str, Any],
    serving: dict[str, Any],
) -> list[dict[str, Any]]:
    """Build batch job status rows from reports."""
    jobs = [
        "user_scd2",
        "weather_enrichment",
        "holiday_enrichment",
        "validate_lakehouse",
        "publish_serving",
    ]

    validation_jobs = (
        validation.get("jobs", {}) if isinstance(validation.get("jobs"), dict) else {}
    )
    serving_jobs = serving.get("jobs", {}) if isinstance(serving.get("jobs"), dict) else {}

    rows: list[dict[str, Any]] = []

    for job in jobs:
        data = validation_jobs.get(job) or serving_jobs.get(job) or {}

        rows.append(
            {
                "Job": job,
                "Status": first_value(
                    data.get("status") if isinstance(data, dict) else None,
                    validation.get("status") if job == "validate_lakehouse" else None,
                    serving.get("status") if job == "publish_serving" else None,
                    default="Not available",
                ),
                "Last Run ID": first_value(
                    validation.get("run_id"),
                    serving.get("run_id"),
                    default="N/A",
                ),
                "Duration": first_value(
                    data.get("duration_seconds") if isinstance(data, dict) else None,
                    default="N/A",
                ),
                "Output": first_value(
                    data.get("output") if isinstance(data, dict) else None,
                    default="N/A",
                ),
            }
        )

    return rows


def build_alerts(
    e: dict[str, dict[str, Any]],
    ch_counts: pd.DataFrame,
) -> list[dict[str, Any]]:
    """Create actionable alerts from available evidence."""
    alerts: list[dict[str, Any]] = []

    snapshot = e["snapshot"]
    streaming = e["streaming"]
    validation = e["validation"]
    serving = e["serving"]

    overall = normalize_status(snapshot.get("overall_status"))

    if overall not in {"HEALTHY", "MAINTENANCE"}:
        alerts.append(
            {
                "Severity": "ERROR",
                "Component": "Platform",
                "Message": f"Overall status is {overall}",
                "Suggested Action": "Run python main.py status and inspect failed checks.",
            }
        )

    streaming_status = normalize_status(streaming.get("status"))

    if streaming_status not in {"HEALTHY", "MAINTENANCE"}:
        alerts.append(
            {
                "Severity": "WARNING",
                "Component": "Spark Streaming",
                "Message": "Streaming is not confirmed as running.",
                "Suggested Action": "Check streaming process and runtime/streaming_status.json.",
            }
        )

    if normalize_status(validation.get("status")) == "FAILED":
        alerts.append(
            {
                "Severity": "ERROR",
                "Component": "Validation",
                "Message": "Latest lakehouse validation failed.",
                "Suggested Action": "Open reports/validation_latest.json and fix failed checks before serving.",
            }
        )

    if normalize_status(serving.get("status")) == "FAILED":
        alerts.append(
            {
                "Severity": "ERROR",
                "Component": "Serving",
                "Message": "Latest ClickHouse serving build failed.",
                "Suggested Action": "Check reports/serving_latest.json and rerun analytics refresh after fixing the cause.",
            }
        )

    if not ch_counts.empty and "rows" in ch_counts.columns:
        zero_views = (
            ch_counts[ch_counts["rows"] == 0]["view_name"].tolist()
            if "view_name" in ch_counts.columns
            else []
        )

        if zero_views:
            alerts.append(
                {
                    "Severity": "WARNING",
                    "Component": "ClickHouse",
                    "Message": f"Some serving views have zero rows: {', '.join(zero_views[:4])}",
                    "Suggested Action": "Run validation and publish_serving, then refresh Power BI.",
                }
            )

    last_batch_time = first_value(
        streaming.get("last_successful_batch_time"),
        streaming.get("last_micro_batch_time"),
        streaming.get("updated_at"),
        default=None,
    )

    parsed_batch = parse_dt(last_batch_time)

    if parsed_batch and (now_utc() - parsed_batch.astimezone(UTC)).total_seconds() > 15 * 60:
        alerts.append(
            {
                "Severity": "WARNING",
                "Component": "Spark Streaming",
                "Message": "No recent micro-batch was detected.",
                "Suggested Action": "Check Spark streaming logs and Kafka input activity.",
            }
        )

    if not alerts:
        alerts.append(
            {
                "Severity": "INFO",
                "Component": "Platform",
                "Message": "No critical alerts from the available evidence.",
                "Suggested Action": "Continue monitoring normal freshness and validation reports.",
            }
        )

    return alerts


def mini_gauge(title: str, value: float, suffix: str = "%") -> go.Figure:
    """Small gauge chart for health metrics."""
    fig = go.Figure(
        go.Indicator(
            mode="gauge+number",
            value=value,
            number={"suffix": suffix, "font": {"size": 26}},
            title={"text": title, "font": {"size": 14}},
            gauge={
                "axis": {"range": [0, 100]},
                "bar": {"color": "#2563EB"},
            },
        )
    )

    fig.update_layout(
        height=210,
        margin=dict(l=10, r=10, t=30, b=10),
        paper_bgcolor="rgba(0,0,0,0)",
    )

    return fig


# -----------------------------------------------------------------------------
# Main dashboard
# -----------------------------------------------------------------------------
e = load_evidence()

snapshot = e["snapshot"]
streaming = e["streaming"]
validation = e["validation"]
serving = e["serving"]
manifest = e["manifest"]
live = e["live"]

ch_counts = clickhouse_view_counts()
ch_latest = clickhouse_latest_event()

platform_status = first_value(snapshot.get("overall_status"), default="MISSING")
streaming_status = first_value(streaming.get("status"), default="MISSING")
validation_status = first_value(validation.get("status"), default="MISSING")
serving_status = first_value(serving.get("status"), default="MISSING")

active_build = first_value(
    serving.get("serving_build_id"),
    serving.get("active_serving_build_id"),
    default="Not available",
)

clickhouse_latest_time = None

if not ch_latest.empty and "latest_event_timestamp" in ch_latest.columns:
    clickhouse_latest_time = ch_latest.iloc[0]["latest_event_timestamp"]

source_latest_time = first_value(
    nested(manifest, "time_window", "max_event_time"),
    manifest.get("max_event_time") if isinstance(manifest, dict) else None,
    streaming.get("latest_event_timestamp") if isinstance(streaming, dict) else None,
    default=None,
)

st.markdown(
    """
    <div class="hero">
        <div class="hero-title">Clickstream Personalization Platform — Operations Console</div>
        <div class="hero-subtitle">
            Read-only monitoring for platform health, streaming, CDC, data quality, lakehouse, serving, and Power BI readiness.
        </div>
    </div>
    """,
    unsafe_allow_html=True,
)


# -----------------------------------------------------------------------------
# Executive platform status
# -----------------------------------------------------------------------------
cols = st.columns(7)

with cols[0]:
    render_card("Overall", platform_status, "Platform status", status=True)

with cols[1]:
    render_card("Streaming", streaming_status, "Spark micro-batches", status=True)

with cols[2]:
    render_card("Validation", validation_status, "Lakehouse checks", status=True)

with cols[3]:
    render_card("Serving", serving_status, "ClickHouse build", status=True)

with cols[4]:
    render_card(
        "Mode",
        first_value(snapshot.get("active_mode"), default="LIVE"),
        "Current mode",
    )

with cols[5]:
    render_card(
        "Freshness Gap",
        minutes_between(source_latest_time, clickhouse_latest_time),
        "Source → ClickHouse",
    )

with cols[6]:
    render_card(
        "Power BI",
        "READY" if normalize_status(serving_status) == "HEALTHY" else "CHECK",
        "Reads ClickHouse v_* views",
        status=True,
    )


# -----------------------------------------------------------------------------
# Freshness and run lineage
# -----------------------------------------------------------------------------
render_section("Freshness & Run Lineage", "⏱️")

lineage_cols = st.columns(5)

lineage = [
    (
        "Streaming Run",
        first_value(
            streaming.get("run_id"),
            streaming.get("streaming_run_id"),
            default="N/A",
        ),
        age_label(streaming.get("updated_at")),
    ),
    (
        "Analytics Run",
        first_value(validation.get("run_id"), serving.get("run_id"), default="N/A"),
        "Last batch refresh evidence",
    ),
    (
        "Validation ID",
        first_value(validation.get("validation_id"), default="N/A"),
        age_label(validation.get("created_at")),
    ),
    (
        "Serving Build",
        active_build,
        age_label(serving.get("created_at")),
    ),
    (
        "Latest CH Event",
        first_value(clickhouse_latest_time, default="N/A"),
        age_label(clickhouse_latest_time),
    ),
]

for col, (label, value, help_text) in zip(lineage_cols, lineage):
    with col:
        render_card(label, value, help_text)


# -----------------------------------------------------------------------------
# Main tabs
# -----------------------------------------------------------------------------
tab_infra, tab_stream, tab_data, tab_serving, tab_alerts = st.tabs(
    [
        "Infrastructure",
        "Streaming & CDC",
        "Data Quality & Lakehouse",
        "Serving & Power BI",
        "Alerts",
    ]
)


# -----------------------------------------------------------------------------
# Infrastructure tab
# -----------------------------------------------------------------------------
with tab_infra:
    render_section("Docker & Container Health", "🐳")

    dataframe(
        build_container_rows(snapshot),
        "Container health evidence is not available yet.",
    )

    render_section("Service Endpoint Checks", "🌐")

    endpoint_rows = []

    endpoints = {
        "Debezium Connect": "http://debezium-connect:8083/connectors",
        "MinIO Live Health": "http://minio:9000/minio/health/live",
        "Airflow Health": "http://airflow:8080/health",
    }

    for name, url in endpoints.items():
        try:
            payload = http_get_json(url)
            endpoint_rows.append(
                {
                    "Service": name,
                    "Status": "HEALTHY",
                    "Endpoint": url,
                    "Detail": str(payload)[:160],
                }
            )
        except Exception as exc:
            endpoint_rows.append(
                {
                    "Service": name,
                    "Status": "DEGRADED",
                    "Endpoint": url,
                    "Detail": str(exc)[:160],
                }
            )

    endpoint_rows.append(
        {
            "Service": "ClickHouse",
            "Status": "HEALTHY" if clickhouse_client() is not None else "DEGRADED",
            "Endpoint": f"{CLICKHOUSE_HOST}:{CLICKHOUSE_PORT}",
            "Detail": CLICKHOUSE_DATABASE,
        }
    )

    dataframe(endpoint_rows, "No endpoint checks available.")

    render_section("Source Generation", "🧾")

    dataframe(
        build_source_rows(manifest, live),
        "Source generation manifest is not available yet.",
    )

    source_window = (
        nested(manifest, "time_window", default={})
        if isinstance(manifest, dict)
        else {}
    )

    sw_cols = st.columns(4)

    with sw_cols[0]:
        render_card(
            "Min Event Time",
            first_value(
                source_window.get("min_event_time")
                if isinstance(source_window, dict)
                else None,
                default="N/A",
            ),
            "Historical source window",
        )

    with sw_cols[1]:
        render_card(
            "Max Event Time",
            first_value(
                source_window.get("max_event_time")
                if isinstance(source_window, dict)
                else None,
                default="N/A",
            ),
            "Historical source window",
        )

    with sw_cols[2]:
        render_card(
            "Live Interval",
            first_value(
                live.get("interval_seconds"),
                live.get("live_interval_seconds"),
                default="N/A",
            ),
            "Seconds",
        )

    with sw_cols[3]:
        last_live_event = first_value(
            live.get("last_generated_at"),
            live.get("last_event_time"),
            default=None,
        )

        render_card(
            "Last Live Event",
            first_value(last_live_event, default="N/A"),
            age_label(last_live_event),
        )


# -----------------------------------------------------------------------------
# Streaming and CDC tab
# -----------------------------------------------------------------------------
with tab_stream:
    render_section("Kafka & Live Ingestion", "📨")

    kafka_rows = []
    topic_evidence = snapshot.get("topics", {}) if isinstance(snapshot.get("topics"), dict) else {}

    for topic in TOPICS:
        t = topic_evidence.get(topic, {}) if isinstance(topic_evidence, dict) else {}

        kafka_rows.append(
            {
                "Topic": topic,
                "Partitions": first_value(
                    t.get("partitions") if isinstance(t, dict) else None,
                    default=3 if topic in TOPICS else "N/A",
                ),
                "Replication Factor": first_value(
                    t.get("replication_factor") if isinstance(t, dict) else None,
                    default=3,
                ),
                "Min ISR": first_value(
                    t.get("min_isr") if isinstance(t, dict) else None,
                    default=2,
                ),
                "Latest Offset": first_value(
                    t.get("latest_offset") if isinstance(t, dict) else None,
                    default="N/A",
                ),
                "Consumer Lag": first_value(
                    t.get("lag") if isinstance(t, dict) else None,
                    default="N/A",
                ),
                "Last Message": first_value(
                    t.get("last_message_time") if isinstance(t, dict) else None,
                    default="N/A",
                ),
            }
        )

    dataframe(kafka_rows, "Kafka topic evidence is not available yet.")

    render_section("Spark Streaming Reliability", "⚡")

    s_cols = st.columns(4)

    with s_cols[0]:
        render_card("Process Status", streaming_status, "Streaming process", status=True)

    with s_cols[1]:
        render_card(
            "Last Batch ID",
            first_value(
                streaming.get("last_successful_batch_id"),
                streaming.get("last_micro_batch_id"),
                default="N/A",
            ),
            "Micro-batch",
        )

    with s_cols[2]:
        last_batch_time = first_value(
            streaming.get("last_successful_batch_time"),
            streaming.get("last_micro_batch_time"),
            streaming.get("updated_at"),
            default=None,
        )

        render_card(
            "Last Batch Time",
            first_value(last_batch_time, default="N/A"),
            age_label(last_batch_time),
        )

    with s_cols[3]:
        render_card(
            "Rows Last Batch",
            first_value(
                streaming.get("last_batch_rows"),
                streaming.get("rows_processed_last_batch"),
                default="N/A",
            ),
            "Rows processed",
        )

    streaming_rows = [
        {
            "Metric": "Processing Duration",
            "Value": first_value(
                streaming.get("processing_duration_ms"),
                streaming.get("last_processing_duration_ms"),
                default="N/A",
            ),
        },
        {
            "Metric": "Input Rows / Sec",
            "Value": first_value(streaming.get("input_rows_per_second"), default="N/A"),
        },
        {
            "Metric": "Processed Rows / Sec",
            "Value": first_value(streaming.get("processed_rows_per_second"), default="N/A"),
        },
        {
            "Metric": "Checkpoint Path",
            "Value": first_value(streaming.get("checkpoint_path"), default="N/A"),
        },
        {
            "Metric": "Last Checkpoint Update",
            "Value": first_value(streaming.get("last_checkpoint_update"), default="N/A"),
        },
        {
            "Metric": "Late Arrivals",
            "Value": first_value(streaming.get("late_arrivals"), default="N/A"),
        },
        {
            "Metric": "Last Spark Error",
            "Value": first_value(streaming.get("last_error"), default="None"),
        },
    ]

    dataframe(streaming_rows, "No detailed streaming metrics available yet.")

    render_section("CDC & Debezium", "🟣")

    connector_rows = []

    try:
        connectors = http_get_json("http://debezium-connect:8083/connectors")

        if isinstance(connectors, list):
            for connector in connectors:
                try:
                    status_payload = http_get_json(
                        f"http://debezium-connect:8083/connectors/{connector}/status"
                    )

                    connector_status = (
                        status_payload.get("connector", {}).get("state", "UNKNOWN")
                        if isinstance(status_payload, dict)
                        else "UNKNOWN"
                    )

                    tasks = (
                        status_payload.get("tasks", [])
                        if isinstance(status_payload, dict)
                        else []
                    )

                    task_status = (
                        ", ".join([str(t.get("state", "UNKNOWN")) for t in tasks])
                        if tasks
                        else "N/A"
                    )

                except Exception:
                    connector_status = "UNKNOWN"
                    task_status = "N/A"

                connector_rows.append(
                    {
                        "Connector": connector,
                        "Connector Status": connector_status,
                        "Task Status": task_status,
                        "Snapshot": "Captured by Debezium",
                        "Topic": "Mapped in connector config",
                        "Last CDC Event": "See CDC clean tables",
                    }
                )

    except Exception:
        connector_rows = [
            {
                "Connector": "users",
                "Connector Status": "Not available",
                "Task Status": "N/A",
                "Snapshot": "N/A",
                "Topic": "users-cdc",
                "Last CDC Event": "N/A",
            },
            {
                "Connector": "orders",
                "Connector Status": "Not available",
                "Task Status": "N/A",
                "Snapshot": "N/A",
                "Topic": "orders-cdc",
                "Last CDC Event": "N/A",
            },
            {
                "Connector": "order_items",
                "Connector Status": "Not available",
                "Task Status": "N/A",
                "Snapshot": "N/A",
                "Topic": "order-items-cdc",
                "Last CDC Event": "N/A",
            },
        ]

    dataframe(connector_rows, "Debezium connector evidence is not available yet.")

    render_section("SCD Type 2 Health", "🧬")

    scd = nested(validation, "details", "scd2", default={}) if isinstance(validation, dict) else {}

    scd_cols = st.columns(6)

    with scd_cols[0]:
        render_card(
            "Total SCD2 Rows",
            first_value(scd.get("current_rows") if isinstance(scd, dict) else None, default="N/A"),
            "All versions",
        )

    with scd_cols[1]:
        render_card(
            "Current Users",
            first_value(scd.get("users") if isinstance(scd, dict) else None, default="N/A"),
            "is_current = 1",
        )

    with scd_cols[2]:
        render_card(
            "Historical Versions",
            first_value(
                scd.get("duplicate_current") if isinstance(scd, dict) else None,
                default="N/A",
            ),
            "Closed versions",
        )

    with scd_cols[3]:
        render_card(
            "Deleted Users",
            first_value(scd.get("deleted_users") if isinstance(scd, dict) else None, default="N/A"),
            "Soft-delete history",
        )

    with scd_cols[4]:
        render_card(
            "Duplicate Current",
            first_value(
                scd.get("invalid_ranges") if isinstance(scd, dict) else None,
                default="0",
            ),
            "Expected: 0",
        )

    with scd_cols[5]:
        render_card(
            "Invalid Ranges",
            first_value(scd.get("invalid_ranges") if isinstance(scd, dict) else None, default="0"),
            "Expected: 0",
        )


# -----------------------------------------------------------------------------
# Data quality and lakehouse tab
# -----------------------------------------------------------------------------
with tab_data:
    render_section("Data Quality, Audit & Quarantine", "🛡️")

    st.markdown("**Reconciliation rule:** `Input = Accepted Clean + Rejected Quarantine + Duplicates`")

    dataframe(
        build_quality_rows(validation),
        "Validation quality details are not available yet. Run analytics refresh after initialization.",
    )

    q_reasons = nested(validation, "details", "top_rejection_reasons", default=[])

    render_section("Top Rejection Reasons", "🚫")

    if isinstance(q_reasons, list) and q_reasons:
        dataframe(q_reasons, "No rejection reasons available.")
    else:
        dataframe([], "No rejection reason summary available yet.")

    render_section("Iceberg / MinIO Lakehouse", "🧊")

    lakehouse = nested(validation, "details", "lakehouse", default={}) if isinstance(validation, dict) else {}

    l_cols = st.columns(5)

    with l_cols[0]:
        render_card(
            "Bucket",
            first_value(
                lakehouse.get("bucket") if isinstance(lakehouse, dict) else None,
                default="ecommerce-lakehouse",
            ),
            "MinIO bucket",
        )

    with l_cols[1]:
        render_card(
            "Iceberg Tables",
            first_value(
                lakehouse.get("table_count") if isinstance(lakehouse, dict) else None,
                default="17",
            ),
            "Raw + processed + audit",
        )

    with l_cols[2]:
        render_card(
            "Warehouse",
            first_value(
                lakehouse.get("warehouse") if isinstance(lakehouse, dict) else None,
                default="s3://ecommerce-lakehouse/warehouse/",
            ),
            "Iceberg path",
        )

    with l_cols[3]:
        render_card(
            "Latest Snapshot",
            first_value(
                lakehouse.get("latest_snapshot_id") if isinstance(lakehouse, dict) else None,
                default="N/A",
            ),
            "Iceberg metadata",
        )

    with l_cols[4]:
        render_card(
            "Read Check",
            first_value(
                lakehouse.get("read_check") if isinstance(lakehouse, dict) else None,
                default=validation_status,
            ),
            "Validation evidence",
            status=True,
        )

    table_rows = []
    table_counts = nested(validation, "details", "table_counts", default={})

    if isinstance(table_counts, dict):
        for name, count in table_counts.items():
            table_rows.append(
                {
                    "Iceberg Table": name,
                    "Rows": count,
                }
            )

    dataframe(
        table_rows,
        "Iceberg row-count details are not available in the latest validation report.",
    )

    render_section("Batch Jobs & External APIs", "🗓️")

    dataframe(build_batch_rows(validation, serving), "Batch job details are not available yet.")

    api_rows = [
        {
            "API / Enrichment": "Open-Meteo Historical Weather",
            "Coverage": first_value(
                nested(validation, "details", "weather", "coverage_status"),
                default="Tracked by weather_clean",
            ),
            "Important Behavior": "Current-day weather can be unavailable by design for historical archive.",
        },
        {
            "API / Enrichment": "Calendarific Holiday API",
            "Coverage": first_value(
                nested(validation, "details", "holidays", "coverage_status"),
                default="Tracked by holidays_clean",
            ),
            "Important Behavior": "Country/year holiday coverage is pulled by batch job.",
        },
        {
            "API / Enrichment": "External API Failures",
            "Coverage": first_value(
                nested(validation, "details", "external_api_failures", "count"),
                default="N/A",
            ),
            "Important Behavior": "Failures are audited, not silently ignored.",
        },
    ]

    dataframe(api_rows, "API coverage details are not available yet.")


# -----------------------------------------------------------------------------
# Serving and Power BI tab
# -----------------------------------------------------------------------------
with tab_serving:
    render_section("ClickHouse & Serving Layer", "🔥")

    c_cols = st.columns(5)

    with c_cols[0]:
        render_card(
            "ClickHouse",
            "HEALTHY" if clickhouse_client() is not None else "DEGRADED",
            "Database connectivity",
            status=True,
        )

    with c_cols[1]:
        render_card("Database", CLICKHOUSE_DATABASE, "Serving database")

    with c_cols[2]:
        render_card("Active Build", active_build, "serving_build_id")

    with c_cols[3]:
        render_card("Views", len(POWER_BI_VIEWS), "Power BI v_* views")

    with c_cols[4]:
        render_card(
            "Latest Event",
            first_value(clickhouse_latest_time, default="N/A"),
            age_label(clickhouse_latest_time),
        )

    if not ch_counts.empty:
        st.dataframe(ch_counts, use_container_width=True, hide_index=True)
    else:
        st.info(
            "ClickHouse view counts are not available yet. Verify ClickHouse is running and publish_serving has completed."
        )

    render_section("Power BI Readiness", "📊")

    readiness_rows = [
        {
            "Check": "ClickHouse reachable",
            "Status": "PASSED" if clickhouse_client() is not None else "FAILED",
            "Detail": f"{CLICKHOUSE_HOST}:{CLICKHOUSE_PORT}",
        },
        {
            "Check": "Serving report",
            "Status": serving_status,
            "Detail": active_build,
        },
        {
            "Check": "Views available",
            "Status": "PASSED" if not ch_counts.empty else "MISSING",
            "Detail": f"{len(ch_counts) if not ch_counts.empty else 0}/{len(POWER_BI_VIEWS)} views counted",
        },
        {
            "Check": "Power BI mode",
            "Status": "READY",
            "Detail": "Import mode over ClickHouse v_* views",
        },
    ]

    dataframe(readiness_rows, "Power BI readiness could not be evaluated.")


# -----------------------------------------------------------------------------
# Alerts tab
# -----------------------------------------------------------------------------
with tab_alerts:
    render_section("Alerts & Recommendations", "🚨")

    alerts = build_alerts(e, ch_counts)

    dataframe(alerts, "No alerts available.")

    render_section("Suggested Safe Commands", "🧰")

    safe_commands = [
        {
            "Purpose": "Check platform status",
            "Command": "python main.py status",
        },
        {
            "Purpose": "Stop safely",
            "Command": "python main.py stop",
        },
        {
            "Purpose": "Start existing platform",
            "Command": "python main.py start",
        },
        {
            "Purpose": "View validation report",
            "Command": "python -m json.tool reports/validation_latest.json",
        },
        {
            "Purpose": "View serving report",
            "Command": "python -m json.tool reports/serving_latest.json",
        },
        {
            "Purpose": "Full dynamic-state rebuild",
            "Command": "python main.py reset --confirm",
        },
    ]

    dataframe(safe_commands, "No command reference available.")

    st.warning(
        "`reset --confirm` is destructive for dynamic runtime state. Use `stop` for normal shutdown."
    )


st.caption(
    f"Rendered at {now_utc().isoformat()} · Auto-refresh every {REFRESH_SECONDS} seconds · Read-only console"
)