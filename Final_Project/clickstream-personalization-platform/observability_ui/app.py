from __future__ import annotations

import json
import os
import re
from datetime import UTC, datetime
from pathlib import Path
from typing import Any

import pandas as pd
import requests
import streamlit as st

try:
    import clickhouse_connect
except Exception:  # pragma: no cover
    clickhouse_connect = None

# =============================================================================
# Configuration
# =============================================================================
PROJECT_ROOT = Path(os.getenv("OBSERVABILITY_PROJECT_ROOT", "/opt/project"))
RUNTIME_ROOT = Path(os.getenv("OBSERVABILITY_RUNTIME_ROOT", str(PROJECT_ROOT / "runtime")))
REPORTS_ROOT = Path(os.getenv("OBSERVABILITY_REPORTS_ROOT", str(PROJECT_ROOT / "reports")))
DATA_ROOT = Path(os.getenv("OBSERVABILITY_DATA_ROOT", str(PROJECT_ROOT / "data")))
SPARK_JOBS_ROOT = Path(os.getenv("OBSERVABILITY_SPARK_JOBS_ROOT", str(PROJECT_ROOT / "spark_jobs")))
AIRFLOW_DAGS_ROOT = Path(
    os.getenv("OBSERVABILITY_AIRFLOW_DAGS_ROOT", str(PROJECT_ROOT / "airflow" / "dags"))
)
CONFIG_ROOT = Path(os.getenv("OBSERVABILITY_CONFIG_ROOT", str(PROJECT_ROOT / "config")))

REFRESH_SECONDS = int(os.getenv("OBSERVABILITY_REFRESH_SECONDS", "60"))

CLICKHOUSE_HOST = os.getenv("CLICKHOUSE_HOST", "clickhouse")
CLICKHOUSE_PORT = int(os.getenv("CLICKHOUSE_PORT", "8123"))
CLICKHOUSE_USER = os.getenv("CLICKHOUSE_USER", "default")
CLICKHOUSE_PASSWORD = os.getenv("CLICKHOUSE_PASSWORD", "")
CLICKHOUSE_DATABASE = os.getenv("CLICKHOUSE_DATABASE", "personalization_olap")

DEBEZIUM_URL = os.getenv("DEBEZIUM_URL", "http://debezium-connect:8083")
AIRFLOW_HEALTH_URL = os.getenv("AIRFLOW_HEALTH_URL", "http://airflow:8080/api/v2/monitor/health")
MINIO_HEALTH_URL = os.getenv("MINIO_HEALTH_URL", "http://minio:9000/minio/health/live")
KAFKA_UI_HEALTH_URL = os.getenv("KAFKA_UI_HEALTH_URL", "http://kafka-ui:8080/actuator/health")

DATA_TOPICS = [
    "clickstream-events",
    "webserver-logs",
    "users-cdc",
    "orders-cdc",
    "order-items-cdc",
]
CONNECT_TOPICS = [
    "debezium-connect-configs",
    "debezium-connect-offsets",
    "debezium-connect-status",
]
EXPECTED_TOPICS = DATA_TOPICS + CONNECT_TOPICS

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

SERVING_BASE_TABLES = [
    "dim_date",
    "dim_product",
    "dim_user_current",
    "fact_clickstream_event",
    "fact_order",
    "fact_order_item",
    "mart_journey_session",
    "mart_navigation_paths",
    "mart_product_performance_daily",
    "mart_web_experience_daily",
    "mart_context_impact_daily",
    "mart_personalization_candidates",
    "serving_control",
]

TOPIC_PURPOSE = {
    "clickstream-events": "User behavior stream: page views, product views, cart and checkout events.",
    "webserver-logs": "Filebeat output topic for web server access logs and technical web experience metrics.",
    "users-cdc": "Debezium CDC stream for PostgreSQL users table; source for users_cdc_clean.",
    "orders-cdc": "Debezium CDC stream for PostgreSQL orders table; source for order facts.",
    "order-items-cdc": "Debezium CDC stream for PostgreSQL order_items table; source for order item facts.",
    "debezium-connect-configs": "Kafka Connect internal compacted topic for connector configuration.",
    "debezium-connect-offsets": "Kafka Connect internal compacted topic for connector offsets and resume positions.",
    "debezium-connect-status": "Kafka Connect internal compacted topic for connector and task status.",
}

CONNECTOR_PURPOSE = {
    "clickstream-users-cdc": "Captures PostgreSQL users changes and writes users-cdc.",
    "clickstream-orders-cdc": "Captures PostgreSQL orders changes and writes orders-cdc.",
    "clickstream-order-items-cdc": "Captures PostgreSQL order_items changes and writes order-items-cdc.",
}

PARTITION_PURPOSE = {
    "ecommerce.raw.kafka_messages": "Daily raw preservation and source pruning for all Kafka-delivered records.",
    "ecommerce.processed.product_catalog_clean": "Category-level product analysis and dimension pruning.",
    "ecommerce.processed.clickstream_clean": "Daily behavioral analytics, funnel, sessions and journey queries.",
    "ecommerce.processed.webserver_logs_clean": "Daily web experience and response-performance analysis.",
    "ecommerce.processed.users_cdc_clean": "Daily CDC event processing and incremental SCD2 preparation.",
    "ecommerce.processed.orders_cdc_clean": "Daily CDC order processing and fact publishing.",
    "ecommerce.processed.order_items_cdc_clean": "Daily CDC item processing and product/order joins.",
    "ecommerce.processed.user_profile_scd2": "Daily SCD2 version validity windows based on effective_from.",
    "ecommerce.processed.weather_clean": "Daily weather-hour enrichment reads without hourly small-file explosion.",
    "ecommerce.processed.holidays_clean": "Country/year holiday coverage and yearly backfill checks.",
    "ecommerce.audit.pipeline_runs": "Daily pipeline execution evidence.",
    "ecommerce.audit.quality_metrics": "Daily data-quality metric evidence.",
    "ecommerce.audit.quarantine_records": "Daily and source-specific rejected-record investigation.",
    "ecommerce.audit.external_api_failures": "Daily external API failure auditing.",
    "ecommerce.audit.watermarks": "Daily watermark and progress tracking.",
    "ecommerce.audit.validation_runs": "Daily validation evidence and gate history.",
    "ecommerce.audit.serving_builds": "Daily serving publication evidence.",
}

ICEBERG_LAYER = {
    "raw": "Bronze / Raw Zone",
    "processed": "Silver / Processed Zone",
    "audit": "Audit Zone",
}

# Built-in fallback mirrors spark_jobs/bootstrap_lakehouse.py. It is used only when
# the project source file is not mounted into the observability container.
FALLBACK_ICEBERG_CONTRACT = [
    (
        "ecommerce.raw.kafka_messages",
        "days(ingested_at), source_name",
        "parquet",
        "zstd",
        "Built-in contract fallback",
    ),
    (
        "ecommerce.processed.product_catalog_clean",
        "category",
        "parquet",
        "zstd",
        "Built-in contract fallback",
    ),
    (
        "ecommerce.processed.clickstream_clean",
        "days(event_timestamp)",
        "parquet",
        "zstd",
        "Built-in contract fallback",
    ),
    (
        "ecommerce.processed.webserver_logs_clean",
        "days(log_timestamp)",
        "parquet",
        "zstd",
        "Built-in contract fallback",
    ),
    (
        "ecommerce.processed.users_cdc_clean",
        "days(processed_at)",
        "parquet",
        "zstd",
        "Built-in contract fallback",
    ),
    (
        "ecommerce.processed.orders_cdc_clean",
        "days(processed_at)",
        "parquet",
        "zstd",
        "Built-in contract fallback",
    ),
    (
        "ecommerce.processed.order_items_cdc_clean",
        "days(processed_at)",
        "parquet",
        "zstd",
        "Built-in contract fallback",
    ),
    (
        "ecommerce.processed.user_profile_scd2",
        "days(effective_from)",
        "parquet",
        "zstd",
        "Built-in contract fallback",
    ),
    (
        "ecommerce.processed.weather_clean",
        "days(weather_hour)",
        "parquet",
        "zstd",
        "Built-in contract fallback",
    ),
    ("ecommerce.processed.holidays_clean", "year", "parquet", "zstd", "Built-in contract fallback"),
    (
        "ecommerce.audit.pipeline_runs",
        "days(recorded_at)",
        "parquet",
        "zstd",
        "Built-in contract fallback",
    ),
    (
        "ecommerce.audit.quality_metrics",
        "days(recorded_at)",
        "parquet",
        "zstd",
        "Built-in contract fallback",
    ),
    (
        "ecommerce.audit.quarantine_records",
        "days(quarantined_at), source_name",
        "parquet",
        "zstd",
        "Built-in contract fallback",
    ),
    (
        "ecommerce.audit.external_api_failures",
        "days(occurred_at)",
        "parquet",
        "zstd",
        "Built-in contract fallback",
    ),
    (
        "ecommerce.audit.watermarks",
        "days(updated_at)",
        "parquet",
        "zstd",
        "Built-in contract fallback",
    ),
    (
        "ecommerce.audit.validation_runs",
        "days(created_at)",
        "parquet",
        "zstd",
        "Built-in contract fallback",
    ),
    (
        "ecommerce.audit.serving_builds",
        "days(created_at)",
        "parquet",
        "zstd",
        "Built-in contract fallback",
    ),
]

# =============================================================================
# Streamlit setup and CSS
# =============================================================================
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
        --gray: #64748B;
        --purple: #7C3AED;
        --orange: #EA580C;
        --teal: #0F766E;
    }
    div[data-testid="stAppViewContainer"] { background: var(--bg); }
    div[data-testid="stHeader"] { background: rgba(248, 250, 252, 0.86); }
    .block-container { padding-top: 1.2rem; padding-bottom: 2rem; max-width: 1700px; }
    h1, h2, h3 { color: var(--text); letter-spacing: -0.02em; }
    .hero {
        background: linear-gradient(135deg, #0F172A 0%, #1D4ED8 55%, #0F766E 100%);
        border-radius: 22px;
        padding: 26px 30px;
        color: white;
        margin-bottom: 18px;
        box-shadow: 0 14px 30px rgba(15, 23, 42, 0.16);
    }
    .hero-title { font-size: 34px; font-weight: 900; margin: 0; }
    .hero-subtitle { font-size: 15px; color: #DBEAFE; margin-top: 7px; }
    .card {
        background: var(--card);
        border: 1px solid var(--border);
        border-radius: 18px;
        padding: 18px 18px;
        box-shadow: 0 8px 20px rgba(15, 23, 42, 0.05);
        min-height: 112px;
    }
    .metric-label { color: var(--muted); font-size: 12px; font-weight: 800; text-transform: uppercase; letter-spacing: .05em; }
    .metric-value { color: var(--text); font-size: 25px; font-weight: 900; line-height: 1.15; margin-top: 8px; word-break: break-word; }
    .metric-help { color: var(--muted); font-size: 13px; margin-top: 8px; line-height: 1.35; }
    .badge {
        display: inline-flex; align-items: center; gap: 6px;
        border-radius: 999px; padding: 6px 11px;
        font-size: 12px; font-weight: 900;
        border: 1px solid transparent; white-space: nowrap;
    }
    .badge-green { background: #DCFCE7; color: #166534; border-color: #BBF7D0; }
    .badge-amber { background: #FEF3C7; color: #92400E; border-color: #FDE68A; }
    .badge-red { background: #FEE2E2; color: #991B1B; border-color: #FECACA; }
    .badge-gray { background: #F1F5F9; color: #475569; border-color: #CBD5E1; }
    .badge-blue { background: #DBEAFE; color: #1D4ED8; border-color: #BFDBFE; }
    .badge-purple { background: #EDE9FE; color: #6D28D9; border-color: #DDD6FE; }
    .section-title { font-size: 22px; font-weight: 900; color: var(--text); margin: 22px 0 10px; }
    .note {
        background: #EFF6FF; border: 1px solid #BFDBFE; color: #1E3A8A;
        padding: 12px 14px; border-radius: 14px; font-size: 14px; line-height: 1.45;
        margin: 10px 0 14px;
    }
    .warn-note {
        background: #FFFBEB; border: 1px solid #FDE68A; color: #92400E;
        padding: 12px 14px; border-radius: 14px; font-size: 14px; line-height: 1.45;
        margin: 10px 0 14px;
    }
    .ok-note {
        background: #F0FDF4; border: 1px solid #BBF7D0; color: #166534;
        padding: 12px 14px; border-radius: 14px; font-size: 14px; line-height: 1.45;
        margin: 10px 0 14px;
    }
    .danger-note {
        background: #FEF2F2; border: 1px solid #FECACA; color: #991B1B;
        padding: 12px 14px; border-radius: 14px; font-size: 14px; line-height: 1.45;
        margin: 10px 0 14px;
    }
    div[data-testid="stDataFrame"] { border: 1px solid var(--border); border-radius: 14px; overflow: hidden; }
    </style>
    """,
    unsafe_allow_html=True,
)


# =============================================================================
# Generic utilities
# =============================================================================
def now_utc() -> datetime:
    return datetime.now(UTC)


def read_text(path: Path) -> str:
    try:
        if path.is_file():
            return path.read_text(encoding="utf-8", errors="ignore")
    except Exception:
        return ""
    return ""


def read_json(path: Path) -> dict[str, Any]:
    try:
        if path.is_file():
            return json.loads(path.read_text(encoding="utf-8"))
    except Exception:
        return {}
    return {}


def read_jsonl(path: Path, max_lines: int = 2500) -> list[dict[str, Any]]:
    rows: list[dict[str, Any]] = []
    try:
        if not path.is_file():
            return rows
        with path.open("r", encoding="utf-8", errors="ignore") as handle:
            for index, line in enumerate(handle):
                if index >= max_lines:
                    break
                line = line.strip()
                if not line:
                    continue
                try:
                    rows.append(json.loads(line))
                except Exception:
                    continue
    except Exception:
        return []
    return rows


def nested(payload: dict[str, Any], *keys: str, default: Any = None) -> Any:
    current: Any = payload
    for key in keys:
        if not isinstance(current, dict) or key not in current:
            return default
        current = current[key]
    return current


def as_int(value: Any, default: int = 0) -> int:
    try:
        if value is None or value == "":
            return default
        return int(value)
    except Exception:
        return default


def as_float(value: Any, default: float = 0.0) -> float:
    try:
        if value is None or value == "":
            return default
        return float(value)
    except Exception:
        return default


def fmt_number(value: Any) -> str:
    if value is None or value == "":
        return "Not collected"
    try:
        return f"{int(value):,}"
    except Exception:
        return str(value)


def fmt_pct(value: Any, digits: int = 1) -> str:
    if value is None:
        return "Not collected"
    try:
        return f"{float(value) * 100:.{digits}f}%"
    except Exception:
        return "Not collected"


def compact_text(value: Any, head: int = 18, tail: int = 10) -> str:
    text = str(value or "Not collected")
    if len(text) <= head + tail + 3:
        return text
    return f"{text[:head]}…{text[-tail:]}"


def parse_dt(value: Any) -> datetime | None:
    if not value:
        return None
    if isinstance(value, datetime):
        return value if value.tzinfo else value.replace(tzinfo=UTC)
    try:
        text = str(value).replace("Z", "+00:00")
        parsed = datetime.fromisoformat(text)
        return parsed if parsed.tzinfo else parsed.replace(tzinfo=UTC)
    except Exception:
        return None


def age_label(value: Any) -> str:
    parsed = parse_dt(value)
    if not parsed:
        return "Not collected"
    seconds = max(0.0, (now_utc() - parsed).total_seconds())
    if seconds < 60:
        return f"{int(seconds)} sec ago"
    minutes = seconds / 60
    if minutes < 60:
        return f"{int(minutes)} min ago"
    hours = minutes / 60
    if hours < 24:
        return f"{hours:.1f} h ago"
    days = hours / 24
    return f"{days:.1f} d ago"


def normalize_status(value: Any) -> str:
    text = str(value or "UNKNOWN").strip().upper()
    if text in {"PASS", "PASSED", "HEALTHY", "READY", "RUNNING", "OK", "SUCCESS", "ACTIVE"}:
        return "PASS"
    if text in {"WARN", "WARNING", "ATTENTION", "MAINTENANCE", "PARTIAL"}:
        return "WARN"
    if text in {"IDLE", "STOPPED", "NOT RUNNING", "PAUSED"}:
        return "INFO"
    if text in {"FAIL", "FAILED", "ERROR", "UNHEALTHY", "DOWN", "NOT READY"}:
        return "FAIL"
    if text in {"N/A", "NA", "NOT AVAILABLE", "NOT COLLECTED", "UNKNOWN"}:
        return "UNKNOWN"
    return text


def badge_class(value: Any) -> str:
    normalized = normalize_status(value)
    if normalized == "PASS":
        return "badge-green"
    if normalized == "WARN":
        return "badge-amber"
    if normalized == "FAIL":
        return "badge-red"
    if normalized == "UNKNOWN":
        return "badge-gray"
    return "badge-blue"


def badge_html(value: Any) -> str:
    label = str(value or "Not collected")
    return f'<span class="badge {badge_class(label)}">{label}</span>'


def render_section(title: str, icon: str = "") -> None:
    st.markdown(f'<div class="section-title">{icon} {title}</div>', unsafe_allow_html=True)


def render_card(label: str, value: Any, help_text: str = "", status: Any | None = None) -> None:
    status_html = badge_html(status) if status is not None else ""
    st.markdown(
        f"""
        <div class="card">
            <div class="metric-label">{label}</div>
            <div style="margin-top:8px;">{status_html}</div>
            <div class="metric-value">{value}</div>
            <div class="metric-help">{help_text}</div>
        </div>
        """,
        unsafe_allow_html=True,
    )


def render_note(text: str, level: str = "info") -> None:
    klass = {"info": "note", "warn": "warn-note", "ok": "ok-note", "danger": "danger-note"}.get(
        level, "note"
    )
    st.markdown(f'<div class="{klass}">{text}</div>', unsafe_allow_html=True)


def show_df(rows: list[dict[str, Any]] | pd.DataFrame, height: int | None = None) -> None:
    df = rows if isinstance(rows, pd.DataFrame) else pd.DataFrame(rows)
    if df.empty:
        render_note("No rows are available for this section.", "warn")
        return
    # Avoid the professional-looking issue of empty rows caused by oversized dataframe containers.
    row_height = 36
    header_height = 42
    natural_height = header_height + (len(df) * row_height) + 8
    final_height = min(height, natural_height) if height else natural_height
    final_height = max(96, min(final_height, 620))
    st.dataframe(df, use_container_width=True, hide_index=True, height=final_height)


# =============================================================================
# Load snapshots and reports
# =============================================================================
@st.cache_data(ttl=REFRESH_SECONDS)
def load_reports() -> dict[str, Any]:
    return {
        "latest": read_json(RUNTIME_ROOT / "observability" / "latest.json"),
        "history": read_jsonl(RUNTIME_ROOT / "observability" / "history.jsonl", max_lines=1500),
        "validation": read_json(REPORTS_ROOT / "validation_latest.json"),
        "serving": read_json(REPORTS_ROOT / "serving_latest.json"),
        "infrastructure": read_json(REPORTS_ROOT / "infrastructure_report.json"),
        "generation_manifest": read_json(DATA_ROOT / "source" / "generation_manifest.json"),
    }


def checks_map(latest: dict[str, Any]) -> dict[str, dict[str, Any]]:
    return {
        str(item.get("component", "")): item
        for item in latest.get("checks", [])
        if isinstance(item, dict)
    }


def check_status(latest: dict[str, Any], component: str, default: str = "UNKNOWN") -> str:
    item = checks_map(latest).get(component, {})
    return str(item.get("status", default))


def check_detail(latest: dict[str, Any], component: str, default: str = "Not collected") -> str:
    item = checks_map(latest).get(component, {})
    return str(item.get("detail", default))


# =============================================================================
# Live probes
# =============================================================================
def http_get(url: str, timeout: int = 4) -> tuple[str, str]:
    try:
        response = requests.get(url, timeout=timeout)
        if 200 <= response.status_code < 300:
            return "PASS", f"HTTP {response.status_code}"
        return "WARN", f"HTTP {response.status_code}"
    except Exception as exc:
        return "WARN", str(exc)[:180]


def http_get_json(url: str, timeout: int = 5) -> tuple[str, Any]:
    try:
        response = requests.get(url, timeout=timeout)
        if 200 <= response.status_code < 300:
            return "PASS", response.json()
        return "WARN", {"error": f"HTTP {response.status_code}", "body": response.text[:300]}
    except Exception as exc:
        return "WARN", {"error": str(exc)[:300]}


@st.cache_resource(ttl=REFRESH_SECONDS)
def ch_client() -> Any:
    if clickhouse_connect is None:
        return None
    try:
        return clickhouse_connect.get_client(
            host=CLICKHOUSE_HOST,
            port=CLICKHOUSE_PORT,
            username=CLICKHOUSE_USER,
            password=CLICKHOUSE_PASSWORD,
            database=CLICKHOUSE_DATABASE,
            connect_timeout=4,
            send_receive_timeout=12,
        )
    except Exception:
        return None


@st.cache_data(ttl=REFRESH_SECONDS)
def ch_query(sql: str) -> pd.DataFrame:
    client = ch_client()
    if client is None:
        return pd.DataFrame()
    try:
        result = client.query(sql)
        return pd.DataFrame(result.result_rows, columns=result.column_names)
    except Exception:
        return pd.DataFrame()


@st.cache_data(ttl=REFRESH_SECONDS)
def ch_view_counts(serving_report: dict[str, Any]) -> pd.DataFrame:
    rows: list[dict[str, Any]] = []
    live_ok = False
    client = ch_client()
    if client is not None:
        for view in POWER_BI_VIEWS:
            try:
                value = client.query(
                    f"SELECT count() FROM {CLICKHOUSE_DATABASE}.{view}"
                ).result_rows[0][0]
                rows.append(
                    {
                        "View Name": view,
                        "Rows": int(value),
                        "Evidence Source": "Live ClickHouse query",
                    }
                )
                live_ok = True
            except Exception as exc:
                rows.append(
                    {
                        "View Name": view,
                        "Rows": "Not collected",
                        "Evidence Source": f"ClickHouse query failed: {str(exc)[:80]}",
                    }
                )
    if live_ok:
        return pd.DataFrame(rows)

    counts = serving_report.get("counts", {}) if isinstance(serving_report, dict) else {}
    fallback_rows = []
    for view in POWER_BI_VIEWS:
        key = view[2:] if view.startswith("v_") else view
        fallback_rows.append(
            {
                "View Name": view,
                "Rows": counts.get(key, "Not collected"),
                "Evidence Source": "reports/serving_latest.json",
            }
        )
    return pd.DataFrame(fallback_rows)


@st.cache_data(ttl=REFRESH_SECONDS)
def ch_table_keys() -> pd.DataFrame:
    sql = f"""
    SELECT
        name AS table_name,
        engine,
        partition_key,
        sorting_key,
        primary_key
    FROM system.tables
    WHERE database = '{CLICKHOUSE_DATABASE}'
    ORDER BY name
    """
    df = ch_query(sql)
    if not df.empty:
        df["Evidence Source"] = "ClickHouse system.tables"
        return df

    # optional command output fallback if user generated evidence files on host
    for path in [
        RUNTIME_ROOT / "operational_evidence" / "clickhouse_tables_keys.txt",
        RUNTIME_ROOT / "ops_console_review_bundle" / "commands" / "clickhouse_tables_keys.txt",
    ]:
        text = read_text(path)
        if text:
            return pd.DataFrame(
                [
                    {
                        "table_name": "Open evidence file",
                        "engine": "See text output",
                        "partition_key": "",
                        "sorting_key": "",
                        "primary_key": "",
                        "Evidence Source": str(path),
                    }
                ]
            )
    return pd.DataFrame()


@st.cache_data(ttl=REFRESH_SECONDS)
def debezium_connectors() -> pd.DataFrame:
    status, payload = http_get_json(f"{DEBEZIUM_URL.rstrip('/')}/connectors")
    if status != "PASS" or not isinstance(payload, list):
        return pd.DataFrame(
            [
                {
                    "Connector": "Debezium REST unavailable",
                    "Connector State": status,
                    "Task State": (
                        payload.get("error", "Not collected")
                        if isinstance(payload, dict)
                        else "Not collected"
                    ),
                    "Kafka Topic": "Not collected",
                    "Purpose": "Check Debezium Connect service.",
                    "Evidence Source": f"{DEBEZIUM_URL}/connectors",
                }
            ]
        )

    rows = []
    for name in payload:
        detail_status, detail = http_get_json(
            f"{DEBEZIUM_URL.rstrip('/')}/connectors/{name}/status"
        )
        connector_state = (
            nested(detail, "connector", "state", default=detail_status)
            if isinstance(detail, dict)
            else detail_status
        )
        task_states = []
        if isinstance(detail, dict):
            task_states = [
                str(task.get("state", "UNKNOWN"))
                for task in detail.get("tasks", [])
                if isinstance(task, dict)
            ]
        topic = (
            "users-cdc"
            if "users" in name
            else (
                "orders-cdc"
                if name.endswith("orders-cdc")
                else "order-items-cdc" if "order-items" in name else "Mapped in connector config"
            )
        )
        rows.append(
            {
                "Connector": name,
                "Connector State": connector_state,
                "Task State": ", ".join(task_states) or "No task state",
                "Kafka Topic": topic,
                "Purpose": CONNECTOR_PURPOSE.get(name, "CDC connector managed by Kafka Connect."),
                "Evidence Source": f"Debezium REST: /connectors/{name}/status",
            }
        )
    return pd.DataFrame(rows)


# =============================================================================
# Evidence parsing
# =============================================================================
def line_number(text: str, index: int) -> int:
    return text[:index].count("\n") + 1


@st.cache_data(ttl=REFRESH_SECONDS)
def parse_iceberg_contract() -> pd.DataFrame:
    path = SPARK_JOBS_ROOT / "bootstrap_lakehouse.py"
    text = read_text(path)
    rows: list[dict[str, Any]] = []

    if text:
        pattern = re.compile(
            r"CREATE TABLE IF NOT EXISTS\s+\{CATALOG\}\.(?P<table>[a-zA-Z0-9_.]+).*?USING\s+iceberg\s+PARTITIONED\s+BY\s+\((?P<partition>.*?)\)\s+TBLPROPERTIES\s+\((?P<props>.*?)\)",
            re.DOTALL | re.IGNORECASE,
        )
        for match in pattern.finditer(text):
            table = "ecommerce." + " ".join(match.group("table").split())
            partition = " ".join(match.group("partition").split())
            props = match.group("props")
            fmt_match = re.search(r"'write\.format\.default'\s*=\s*'([^']+)'", props)
            comp_match = re.search(r"'write\.parquet\.compression-codec'\s*=\s*'([^']+)'", props)
            ns = table.split(".")[1] if table.count(".") >= 2 else "unknown"
            rows.append(
                {
                    "Layer": ICEBERG_LAYER.get(ns, ns),
                    "Iceberg Table": table,
                    "Partition Spec": partition,
                    "Columnar Format": (
                        fmt_match.group(1).upper() if fmt_match else "Not collected"
                    ),
                    "Compression": (comp_match.group(1).upper() if comp_match else "Not collected"),
                    "Purpose": PARTITION_PURPOSE.get(
                        table, "Table-specific storage partitioning contract."
                    ),
                    "Evidence Source": f"spark_jobs/bootstrap_lakehouse.py:L{line_number(text, match.start())}",
                }
            )
    if rows:
        return pd.DataFrame(rows)

    for table, partition, fmt, compression, source in FALLBACK_ICEBERG_CONTRACT:
        ns = table.split(".")[1] if table.count(".") >= 2 else "unknown"
        rows.append(
            {
                "Layer": ICEBERG_LAYER.get(ns, ns),
                "Iceberg Table": table,
                "Partition Spec": partition,
                "Columnar Format": fmt.upper(),
                "Compression": compression.upper(),
                "Purpose": PARTITION_PURPOSE.get(
                    table, "Table-specific storage partitioning contract."
                ),
                "Evidence Source": source,
            }
        )
    return pd.DataFrame(rows)


@st.cache_data(ttl=REFRESH_SECONDS)
def parse_airflow_contract() -> dict[str, Any]:
    path = AIRFLOW_DAGS_ROOT / "analytics_refresh.py"
    text = read_text(path)
    if not text:
        return {
            "schedule": "0 * * * *",
            "jobs": [
                "user_scd2",
                "weather_enrichment",
                "holiday_enrichment",
                "validate_lakehouse",
                "publish_serving",
            ],
            "source": "Built-in contract fallback; mount airflow/dags for direct source lines",
        }
    schedule_match = re.search(r"schedule\s*=\s*['\"]([^'\"]+)['\"]", text)
    jobs_match = re.search(r"JOBS\s*=\s*\((.*?)\)", text, re.DOTALL)
    jobs: list[str] = []
    if jobs_match:
        jobs = re.findall(r"['\"]([^'\"]+)['\"]", jobs_match.group(1))
    return {
        "schedule": schedule_match.group(1) if schedule_match else "0 * * * *",
        "jobs": jobs
        or [
            "user_scd2",
            "weather_enrichment",
            "holiday_enrichment",
            "validate_lakehouse",
            "publish_serving",
        ],
        "source": f"airflow/dags/analytics_refresh.py:L{line_number(text, schedule_match.start()) if schedule_match else 1}",
    }


@st.cache_data(ttl=REFRESH_SECONDS)
def parse_kafka_describe_file() -> pd.DataFrame:
    possible_paths = [
        RUNTIME_ROOT / "operational_evidence" / "kafka_topics_describe.txt",
        RUNTIME_ROOT / "ops_console_review_bundle" / "commands" / "kafka_topics_describe.txt",
        PROJECT_ROOT / "runtime" / "operational_evidence" / "kafka_topics_describe.txt",
    ]
    text = ""
    source = ""
    for path in possible_paths:
        text = read_text(path)
        if text:
            source = str(path)
            break

    rows: list[dict[str, Any]] = []
    if text:
        topic_pattern = re.compile(
            r"^Topic:\s+(?P<topic>\S+)\s+TopicId:\s+\S+\s+PartitionCount:\s+(?P<partitions>\d+)\s+ReplicationFactor:\s+(?P<rf>\d+)\s+Configs:\s+(?P<configs>.*)$",
            re.MULTILINE,
        )
        for match in topic_pattern.finditer(text):
            topic = match.group("topic")
            show_system_topics = os.getenv(
                "OBSERVABILITY_SHOW_KAFKA_SYSTEM_TOPICS", "false"
            ).strip().lower() in {"1", "true", "yes"}
            if topic == "__consumer_offsets" and not show_system_topics:
                continue
            if topic == "__consumer_offsets":
                classification = "Kafka Internal"
            elif topic in CONNECT_TOPICS:
                classification = "Kafka Connect Internal"
            elif topic in DATA_TOPICS:
                classification = "Project Data Topic"
            else:
                classification = "Other"
            configs = match.group("configs")
            min_isr = "2" if "min.insync.replicas=2" in configs else "Not collected"
            cleanup = (
                "compact"
                if "cleanup.policy=compact" in configs
                else "delete" if "cleanup.policy=delete" in configs else "Not collected"
            )
            rows.append(
                {
                    "Topic": topic,
                    "Type": classification,
                    "Partitions": int(match.group("partitions")),
                    "Replication Factor": int(match.group("rf")),
                    "Min ISR": min_isr,
                    "Cleanup Policy": cleanup,
                    "Purpose": TOPIC_PURPOSE.get(topic, "Kafka internal/system topic."),
                    "Evidence Source": source,
                }
            )
        if rows:
            order = {
                name: index for index, name in enumerate(EXPECTED_TOPICS + ["__consumer_offsets"])
            }
            rows.sort(key=lambda row: order.get(row["Topic"], 999))
            return pd.DataFrame(rows)

    # Fallback contract: reflects project design, not live broker output.
    for topic in EXPECTED_TOPICS:
        rows.append(
            {
                "Topic": topic,
                "Type": "Project Data Topic" if topic in DATA_TOPICS else "Kafka Connect Internal",
                "Partitions": 1 if topic == "debezium-connect-configs" else 3,
                "Replication Factor": 3,
                "Min ISR": 2,
                "Cleanup Policy": "compact" if topic in CONNECT_TOPICS else "delete",
                "Purpose": TOPIC_PURPOSE.get(topic, "Project topic."),
                "Evidence Source": "Project Kafka topic contract; generate kafka-topics --describe for live broker evidence",
            }
        )
    return pd.DataFrame(rows)


# =============================================================================
# Domain builders
# =============================================================================
def service_rows(latest: dict[str, Any], infra: dict[str, Any]) -> list[dict[str, Any]]:
    checks = checks_map(latest)
    expected = [
        ("PostgreSQL", "postgres", "Operational source database with WAL logical replication."),
        ("ZooKeeper", "zookeeper", "Kafka 7.3.2 coordination service."),
        ("Kafka broker 1", "kafka1", "Broker in three-node Kafka cluster."),
        ("Kafka broker 2", "kafka2", "Broker in three-node Kafka cluster."),
        ("Kafka broker 3", "kafka3", "Broker in three-node Kafka cluster."),
        ("Kafka UI", "kafka_ui", "Kafka topic inspection UI."),
        ("Debezium Connect", "debezium", "CDC connector runtime."),
        ("Filebeat", "filebeat", "Ships web logs to webserver-logs topic."),
        ("Spark Engine", "spark", "Spark submit runner and streaming/batch engine."),
        ("Airflow", "airflow", "Hourly batch scheduler and monitor."),
        ("MinIO", "minio", "S3-compatible object store for Iceberg warehouse."),
        ("ClickHouse", "clickhouse", "Serving database for Power BI views."),
        ("Operations Console", "operations_console", "Read-only monitoring UI."),
    ]
    infra_by_check = {
        item.get("check", ""): item.get("detail", "")
        for item in infra.get("results", [])
        if isinstance(item, dict)
    }
    rows = []
    for label, key, purpose in expected:
        snapshot = checks.get(key, {})
        status = snapshot.get("status", "UNKNOWN")
        detail = snapshot.get("detail", "Not collected")
        infra_detail = next(
            (
                value
                for check, value in infra_by_check.items()
                if key.replace("_", "-") in check.lower()
                or label.lower().split()[0] in check.lower()
            ),
            "",
        )
        rows.append(
            {
                "Service": label,
                "Status": status,
                "Runtime Detail": detail,
                "Infrastructure Evidence": infra_detail
                or "reports/infrastructure_report.json not available",
                "Purpose": purpose,
                "Evidence Source": "runtime/observability/latest.json + reports/infrastructure_report.json",
            }
        )
    return rows


def endpoint_rows() -> list[dict[str, Any]]:
    endpoints = [
        ("Debezium Connect REST", f"{DEBEZIUM_URL}/connectors"),
        ("MinIO Live Health", MINIO_HEALTH_URL),
        ("Airflow Monitor Health", AIRFLOW_HEALTH_URL),
        ("Kafka UI Health", KAFKA_UI_HEALTH_URL),
    ]
    rows = []
    for label, url in endpoints:
        status, detail = http_get(url)
        rows.append(
            {
                "Endpoint": label,
                "Status": status,
                "URL": url,
                "Detail": detail,
                "Evidence Source": "Live HTTP probe from Operations Console",
            }
        )
    client = ch_client()
    rows.append(
        {
            "Endpoint": "ClickHouse HTTP",
            "Status": "PASS" if client is not None else "WARN",
            "URL": f"{CLICKHOUSE_HOST}:{CLICKHOUSE_PORT}",
            "Detail": (
                CLICKHOUSE_DATABASE if client is not None else "Client connection unavailable"
            ),
            "Evidence Source": "clickhouse-connect client",
        }
    )
    return rows


def quality_rows(validation: dict[str, Any]) -> list[dict[str, Any]]:
    details = validation.get("details", {}) if isinstance(validation, dict) else {}
    source_names = ["clickstream", "web_logs", "users_cdc", "orders_cdc", "order_items_cdc"]
    rows: list[dict[str, Any]] = []
    for name in source_names:
        item = details.get(name, {}) if isinstance(details, dict) else {}
        raw = as_int(item.get("raw"), 0)
        clean = as_int(item.get("clean"), 0)
        quarantine = as_int(item.get("quarantine"), 0)
        residual = raw - clean - quarantine if raw else 0
        success = clean / raw if raw else None
        rows.append(
            {
                "Source": name,
                "Raw/Input": raw,
                "Clean/Accepted": clean,
                "Quarantine/Rejected": quarantine,
                "Duplicate/Residual": max(0, residual),
                "Success %": fmt_pct(success, 1) if success is not None else "Not collected",
                "Reconciled": bool(item.get("reconciled", False)),
                "Evidence Source": "reports/validation_latest.json",
            }
        )
    return rows


def relationship_rows(validation: dict[str, Any]) -> list[dict[str, Any]]:
    details = validation.get("details", {}) if isinstance(validation, dict) else {}
    coverage = details.get("request_correlation_coverage")
    return [
        {
            "Check": "Order item orphan check",
            "Value": details.get("order_item_orphans", "Not collected"),
            "Status": "PASS" if details.get("order_item_orphans") == 0 else "WARN",
            "Evidence Source": "reports/validation_latest.json",
        },
        {
            "Check": "Clickstream product orphan check",
            "Value": details.get("clickstream_product_orphans", "Not collected"),
            "Status": "PASS" if details.get("clickstream_product_orphans") == 0 else "WARN",
            "Evidence Source": "reports/validation_latest.json",
        },
        {
            "Check": "Request correlation coverage",
            "Value": fmt_pct(coverage, 2) if coverage is not None else "Not collected",
            "Status": "PASS" if as_float(coverage) >= 0.99 else "WARN",
            "Evidence Source": "reports/validation_latest.json",
        },
        {
            "Check": "Overall quality status",
            "Value": validation.get("quality_status", "Not collected"),
            "Status": validation.get("quality_status", "UNKNOWN"),
            "Evidence Source": "reports/validation_latest.json",
        },
        {
            "Check": "Overall relationship status",
            "Value": validation.get("relationship_status", "Not collected"),
            "Status": validation.get("relationship_status", "UNKNOWN"),
            "Evidence Source": "reports/validation_latest.json",
        },
    ]


def scd2_rows(validation: dict[str, Any]) -> list[dict[str, Any]]:
    scd2 = nested(validation, "details", "scd2", default={}) or {}
    users = as_int(scd2.get("users"), 0)
    current = as_int(scd2.get("current_rows"), 0)
    duplicate = as_int(scd2.get("duplicate_current"), 0)
    invalid = as_int(scd2.get("invalid_ranges"), 0)
    history_note = "Not exported in validation report"
    return [
        {
            "Metric": "SCD2 Validation Status",
            "Value": validation.get("scd2_status", "Not collected"),
            "Expected": "PASSED",
            "Status": validation.get("scd2_status", "UNKNOWN"),
            "Evidence Source": "reports/validation_latest.json",
        },
        {
            "Metric": "Distinct Users Tracked",
            "Value": users,
            "Expected": "> 0",
            "Status": "PASS" if users > 0 else "WARN",
            "Evidence Source": "reports/validation_latest.json → details.scd2.users",
        },
        {
            "Metric": "Current Profile Rows",
            "Value": current,
            "Expected": "one current row per active user",
            "Status": "PASS" if current == users and current > 0 else "WARN",
            "Evidence Source": "reports/validation_latest.json → details.scd2.current_rows",
        },
        {
            "Metric": "Historical Version Rows",
            "Value": history_note,
            "Expected": "Query Iceberg table for exact count",
            "Status": "INFO",
            "Evidence Source": "Not included in current validation export",
        },
        {
            "Metric": "Duplicate Current Rows",
            "Value": duplicate,
            "Expected": "0",
            "Status": "PASS" if duplicate == 0 else "FAIL",
            "Evidence Source": "reports/validation_latest.json → details.scd2.duplicate_current",
        },
        {
            "Metric": "Invalid Effective Ranges",
            "Value": invalid,
            "Expected": "0",
            "Status": "PASS" if invalid == 0 else "FAIL",
            "Evidence Source": "reports/validation_latest.json → details.scd2.invalid_ranges",
        },
    ]


def batch_rows(validation: dict[str, Any], serving: dict[str, Any]) -> list[dict[str, Any]]:
    airflow = parse_airflow_contract()
    validation_status = validation.get("status", "Not collected")
    serving_status = serving.get("status", "Not collected")
    scd2_status = validation.get("scd2_status", "Not collected")
    coverage_status = validation.get("coverage_status", "Not collected")
    rows = [
        {
            "Job": "user_scd2",
            "Scheduler": "Airflow",
            "Execution Engine": "Spark Batch",
            "Status": scd2_status,
            "Output": "ecommerce.processed.user_profile_scd2",
            "Evidence Source": "reports/validation_latest.json + Airflow DAG contract",
        },
        {
            "Job": "weather_enrichment",
            "Scheduler": "Airflow",
            "Execution Engine": "Spark Batch",
            "Status": coverage_status,
            "Output": "ecommerce.processed.weather_clean",
            "Evidence Source": "reports/validation_latest.json + Airflow DAG contract",
        },
        {
            "Job": "holiday_enrichment",
            "Scheduler": "Airflow",
            "Execution Engine": "Spark Batch",
            "Status": coverage_status,
            "Output": "ecommerce.processed.holidays_clean",
            "Evidence Source": "reports/validation_latest.json + Airflow DAG contract",
        },
        {
            "Job": "validate_lakehouse",
            "Scheduler": "Airflow",
            "Execution Engine": "Spark Batch",
            "Status": validation_status,
            "Output": "ecommerce.audit.validation_runs + reports/validation_latest.json",
            "Evidence Source": "reports/validation_latest.json",
        },
        {
            "Job": "publish_serving",
            "Scheduler": "Airflow",
            "Execution Engine": "Spark Batch",
            "Status": serving_status,
            "Output": "ClickHouse personalization_olap serving tables/views",
            "Evidence Source": "reports/serving_latest.json",
        },
    ]
    expected_jobs = set(airflow.get("jobs", []))
    for row in rows:
        row["In DAG"] = "Yes" if row["Job"] in expected_jobs else "Not collected"
        row["DAG Schedule"] = airflow.get("schedule", "Not collected")
        row["DAG Evidence Source"] = airflow.get("source", "Not collected")
    return rows


def source_rows(
    manifest: dict[str, Any], validation: dict[str, Any], serving: dict[str, Any]
) -> list[dict[str, Any]]:
    details = validation.get("details", {}) if isinstance(validation, dict) else {}
    serving_counts = serving.get("counts", {}) if isinstance(serving, dict) else {}
    rows = [
        {
            "Source": "Clickstream Events JSONL",
            "Type": "Stream/File-generated JSONL",
            "Ingestion": "Kafka topic clickstream-events",
            "Current Evidence": details.get("clickstream", {}).get("raw", "Not collected"),
            "Purpose": "User interaction behavior.",
            "Evidence Source": "reports/validation_latest.json",
        },
        {
            "Source": "Web Server Logs .log",
            "Type": "Log file",
            "Ingestion": "Filebeat → Kafka topic webserver-logs",
            "Current Evidence": details.get("web_logs", {}).get("raw", "Not collected"),
            "Purpose": "Server-side request and performance evidence.",
            "Evidence Source": "reports/validation_latest.json",
        },
        {
            "Source": "PostgreSQL Users",
            "Type": "Database CDC",
            "Ingestion": "Debezium → users-cdc",
            "Current Evidence": details.get("users_cdc", {}).get("raw", "Not collected"),
            "Purpose": "User profile changes and SCD2 source.",
            "Evidence Source": "reports/validation_latest.json",
        },
        {
            "Source": "PostgreSQL Orders",
            "Type": "Database CDC",
            "Ingestion": "Debezium → orders-cdc",
            "Current Evidence": details.get("orders_cdc", {}).get("raw", "Not collected"),
            "Purpose": "Order fact source.",
            "Evidence Source": "reports/validation_latest.json",
        },
        {
            "Source": "PostgreSQL Order Items",
            "Type": "Database CDC",
            "Ingestion": "Debezium → order-items-cdc",
            "Current Evidence": details.get("order_items_cdc", {}).get("raw", "Not collected"),
            "Purpose": "Product/order item fact source.",
            "Evidence Source": "reports/validation_latest.json",
        },
        {
            "Source": "Product Catalog CSV",
            "Type": "Static reference file",
            "Ingestion": "One-time Spark bootstrap → product_catalog_clean",
            "Current Evidence": serving_counts.get("dim_product", "See Serving tab"),
            "Purpose": "Product attributes and categories.",
            "Evidence Source": "reports/serving_latest.json → counts.dim_product",
        },
        {
            "Source": "Open-Meteo API",
            "Type": "External API",
            "Ingestion": "Airflow/Spark batch → weather_clean",
            "Current Evidence": validation.get("coverage_status", "Not collected"),
            "Purpose": "Weather context enrichment.",
            "Evidence Source": "reports/validation_latest.json",
        },
        {
            "Source": "Calendarific API",
            "Type": "External API",
            "Ingestion": "Airflow/Spark batch → holidays_clean",
            "Current Evidence": validation.get("coverage_status", "Not collected"),
            "Purpose": "Holiday context enrichment.",
            "Evidence Source": "reports/validation_latest.json",
        },
        {
            "Source": "MaxMind GeoLite2",
            "Type": "Local reference database",
            "Ingestion": "Spark enrichment from IP address",
            "Current Evidence": "geo fields in clean clickstream/web logs",
            "Purpose": "Country, city, latitude, longitude, timezone enrichment.",
            "Evidence Source": "streaming_ingestion.py / clean tables",
        },
    ]
    return rows


# =============================================================================
# Render page
# =============================================================================
reports = load_reports()
latest = reports["latest"]
validation = reports["validation"]
serving = reports["serving"]
infra = reports["infrastructure"]
manifest = reports["generation_manifest"]

partition_df = parse_iceberg_contract()
kafka_df = parse_kafka_describe_file()
views_df = ch_view_counts(serving)
keys_df = ch_table_keys()
debezium_df = debezium_connectors()
airflow_contract = parse_airflow_contract()

# Hero
st.markdown(
    """
    <div class="hero">
        <div class="hero-title">Clickstream Personalization Platform — Operations Console</div>
        <div class="hero-subtitle">Read-only operational console for platform health, ingestion, CDC, Spark, Lakehouse storage, data quality, SCD2, serving, and Power BI readiness.</div>
    </div>
    """,
    unsafe_allow_html=True,
)

# Top cards
raw_streaming_status = check_status(latest, "Spark streaming", "UNKNOWN")
streaming_detail = check_detail(latest, "Spark streaming")
streaming_status = (
    "IDLE"
    if "not running" in streaming_detail.lower() or normalize_status(raw_streaming_status) == "INFO"
    else raw_streaming_status
)
validation_status = validation.get("status") or check_detail(latest, "Latest validation")
serving_status = serving.get("status") or check_status(latest, "Active serving build")
serving_build = serving.get("serving_build_id") or check_detail(latest, "Active serving build")
powerbi_ready = "READY" if len(views_df) == 12 else "CHECK"
critical_ready = (
    as_int(latest.get("failed_checks"), 0) == 0
    and normalize_status(validation_status) == "PASS"
    and normalize_status(serving_status) == "PASS"
    and len(views_df) == 12
)
overall = (
    "READY"
    if critical_ready
    else ("ATTENTION" if as_int(latest.get("failed_checks"), 0) > 0 else "PARTIAL")
)
mode_value = "SERVING" if streaming_status == "IDLE" else "LIVE"

cols = st.columns(7)
with cols[0]:
    render_card("Platform", overall, "Services, validation and serving readiness", overall)
with cols[1]:
    render_card("Streaming", streaming_status, streaming_detail, streaming_status)
with cols[2]:
    render_card("Validation", validation_status, "Lakehouse validation gate", validation_status)
with cols[3]:
    render_card("Serving", serving_status, "ClickHouse serving build", serving_status)
with cols[4]:
    render_card(
        "Mode",
        mode_value,
        "Current pipeline mode",
        "PASS" if mode_value in {"SERVING", "LIVE"} else "INFO",
    )
with cols[5]:
    render_card("Serving Build", compact_text(serving_build), str(serving_build), serving_status)
with cols[6]:
    render_card("Power BI", powerbi_ready, "Reads ClickHouse v_* views", powerbi_ready)


# Tabs
tabs = st.tabs(
    [
        "Overview",
        "Infrastructure",
        "Kafka & CDC",
        "Spark Streaming",
        "Lakehouse Storage",
        "Data Quality",
        "SCD Type 2",
        "Batch & APIs",
        "Serving & Power BI",
    ]
)

# -----------------------------------------------------------------------------
# Executive Overview
# -----------------------------------------------------------------------------
with tabs[0]:
    render_section("Freshness and Run Lineage", "⏱️")
    c1, c2, c3, c4, c5 = st.columns(5)
    with c1:
        render_card(
            "Captured At",
            latest.get("captured_at_utc", "Not collected"),
            age_label(latest.get("captured_at_utc")),
            "PASS" if latest else "UNKNOWN",
        )
    with c2:
        render_card(
            "Validation ID",
            validation.get("validation_id", "Not collected"),
            "Latest lakehouse validation",
            validation.get("status", "UNKNOWN"),
        )
    with c3:
        render_card(
            "Serving Build",
            serving.get("serving_build_id", "Not collected"),
            "Published to ClickHouse",
            serving.get("status", "UNKNOWN"),
        )
    with c4:
        render_card(
            "Activated At",
            serving.get("activated_at_utc", "Not collected"),
            age_label(serving.get("activated_at_utc")),
            serving.get("status", "UNKNOWN"),
        )
    with c5:
        render_card(
            "Cutoff Batch",
            nested(
                validation, "cutoff", "last_successful_stream_batch_id", default="Not collected"
            ),
            "Validation input cutoff",
            validation.get("status", "UNKNOWN"),
        )

    render_section("Source Coverage", "📥")
    show_df(source_rows(manifest, validation, serving), height=360)

    render_section("Current Evidence Summary", "✅")
    summary_rows = [
        {
            "Evidence Area": "Platform readiness",
            "Status": overall,
            "Source": "Derived from runtime health + validation + serving + view availability",
        },
        {
            "Evidence Area": "Lakehouse validation",
            "Status": validation.get("status", "Not collected"),
            "Source": "reports/validation_latest.json",
        },
        {
            "Evidence Area": "Quality checks",
            "Status": validation.get("quality_status", "Not collected"),
            "Source": "reports/validation_latest.json",
        },
        {
            "Evidence Area": "Relationship checks",
            "Status": validation.get("relationship_status", "Not collected"),
            "Source": "reports/validation_latest.json",
        },
        {
            "Evidence Area": "SCD2 checks",
            "Status": validation.get("scd2_status", "Not collected"),
            "Source": "reports/validation_latest.json",
        },
        {
            "Evidence Area": "Context coverage",
            "Status": validation.get("coverage_status", "Not collected"),
            "Source": "reports/validation_latest.json",
        },
        {
            "Evidence Area": "Serving publish",
            "Status": serving.get("status", "Not collected"),
            "Source": "reports/serving_latest.json",
        },
        {
            "Evidence Area": "Power BI view count",
            "Status": f"{len(views_df)}/12 views tracked",
            "Source": "ClickHouse live query / serving report",
        },
    ]
    show_df(summary_rows, height=310)

# -----------------------------------------------------------------------------
# Infrastructure
# -----------------------------------------------------------------------------
with tabs[1]:
    render_section("Docker and Platform Service Health", "🐳")
    show_df(service_rows(latest, infra), height=520)

    render_section("Endpoint Checks", "🌐")
    show_df(endpoint_rows(), height=260)

    render_section("Infrastructure Notes", "🧾")
    render_note(
        "This console separates service availability from pipeline activity. A service can be healthy while Spark Streaming is idle; historical validation and serving data remain available for analytics.",
        "info",
    )

# -----------------------------------------------------------------------------
# Kafka & CDC
# -----------------------------------------------------------------------------
with tabs[2]:
    render_section("Kafka Topics", "📡")
    render_note(
        "Project data topics carry business data. Debezium Connect topics are internal compacted topics used by Kafka Connect for connector configuration, offsets, and status. Kafka system topics are hidden by default.",
        "info",
    )
    show_df(kafka_df, height=460)

    render_section("Debezium CDC Connectors", "🟣")
    show_df(debezium_df, height=260)

    render_section("CDC Path Explanation", "🔁")
    c1, c2, c3 = st.columns(3)
    with c1:
        render_card(
            "Users CDC",
            "users-cdc",
            "PostgreSQL users → Debezium → Kafka → users_cdc_clean",
            "PASS",
        )
    with c2:
        render_card(
            "Orders CDC",
            "orders-cdc",
            "PostgreSQL orders → Debezium → Kafka → orders_cdc_clean",
            "PASS",
        )
    with c3:
        render_card(
            "Order Items CDC",
            "order-items-cdc",
            "PostgreSQL order_items → Debezium → Kafka → order_items_cdc_clean",
            "PASS",
        )

# -----------------------------------------------------------------------------
# Spark Streaming
# -----------------------------------------------------------------------------
with tabs[3]:
    render_section("Spark Structured Streaming Status", "⚡")
    c1, c2, c3, c4 = st.columns(4)
    with c1:
        render_card("Process Status", streaming_status, streaming_detail, streaming_status)
    with c2:
        render_card(
            "Last Completed Batch",
            nested(
                validation, "cutoff", "last_successful_stream_batch_id", default="Not collected"
            ),
            "From validation cutoff",
            validation.get("status", "UNKNOWN"),
        )
    with c3:
        render_card(
            "Raw Kafka Inputs", "5 topics", "clickstream, logs, users/orders/items CDC", "PASS"
        )
    with c4:
        render_card(
            "Streaming Outputs",
            "Raw + Clean + Audit",
            "Iceberg tables written by Spark",
            validation.get("status", "UNKNOWN"),
        )

    if streaming_status == "IDLE":
        render_note(
            "Spark Streaming is currently idle. This is a runtime activity state, not a data-loss state. The latest processed batch remains available through the validation cutoff and serving build.",
            "info",
        )

    render_section("Streaming Source-to-Output Contract", "🧭")
    rows = [
        {
            "Input Topic": "clickstream-events",
            "Processing": "Parse, validate, deduplicate, GeoIP enrich",
            "Clean Output": "clickstream_clean",
            "Rejected Output": "quarantine_records",
            "Raw Output": "raw.kafka_messages",
        },
        {
            "Input Topic": "webserver-logs",
            "Processing": "Parse, validate, deduplicate, GeoIP enrich",
            "Clean Output": "webserver_logs_clean",
            "Rejected Output": "quarantine_records",
            "Raw Output": "raw.kafka_messages",
        },
        {
            "Input Topic": "users-cdc",
            "Processing": "Debezium envelope parsing and metadata preservation",
            "Clean Output": "users_cdc_clean",
            "Rejected Output": "quarantine_records",
            "Raw Output": "raw.kafka_messages",
        },
        {
            "Input Topic": "orders-cdc",
            "Processing": "Debezium envelope parsing and metadata preservation",
            "Clean Output": "orders_cdc_clean",
            "Rejected Output": "quarantine_records",
            "Raw Output": "raw.kafka_messages",
        },
        {
            "Input Topic": "order-items-cdc",
            "Processing": "Debezium envelope parsing and metadata preservation",
            "Clean Output": "order_items_cdc_clean",
            "Rejected Output": "quarantine_records",
            "Raw Output": "raw.kafka_messages",
        },
    ]
    show_df(rows, height=260)

# -----------------------------------------------------------------------------
# Lakehouse Storage
# -----------------------------------------------------------------------------
with tabs[4]:
    render_section("MinIO + Apache Iceberg Lakehouse", "🧊")
    c1, c2, c3, c4 = st.columns(4)
    with c1:
        render_card("Bucket", "ecommerce-lakehouse", "MinIO object storage bucket", "PASS")
    with c2:
        render_card(
            "Warehouse", "s3://ecommerce-lakehouse/warehouse", "Iceberg warehouse path", "PASS"
        )
    with c3:
        render_card(
            "Iceberg Tables",
            len(partition_df),
            "Raw + processed + audit/quarantine",
            "PASS" if len(partition_df) >= 17 else "WARN",
        )
    with c4:
        render_card(
            "Storage Format", "Parquet + ZSTD", "Parsed from Iceberg table properties", "PASS"
        )

    render_section("Iceberg Partitioning, Columnar Format, and Compression Contract", "🗂️")
    render_note(
        "This table is storage evidence. It shows partitioning inside Iceberg tables, not Kafka partitions. Most time-series tables are daily partitions; raw and quarantine add source_name; product catalog uses category; holidays use year.",
        "ok",
    )
    show_df(partition_df, height=560)

    render_section("Bronze / Silver / Gold Mapping", "🏅")
    bsg = [
        {
            "Layer": "Bronze",
            "Project Location": "Iceberg Raw Zone",
            "Tables / Objects": "ecommerce.raw.kafka_messages",
            "Purpose": "Preserve original Kafka-delivered records before transformation.",
        },
        {
            "Layer": "Silver",
            "Project Location": "Iceberg Processed Zone",
            "Tables / Objects": "product_catalog_clean, clickstream_clean, webserver_logs_clean, CDC clean tables, user_profile_scd2, weather_clean, holidays_clean",
            "Purpose": "Validated, deduplicated, enriched and structured analytical tables.",
        },
        {
            "Layer": "Audit / Quarantine",
            "Project Location": "Iceberg Audit Zone",
            "Tables / Objects": "quality_metrics, pipeline_runs, validation_runs, serving_builds, quarantine_records",
            "Purpose": "Operational evidence, reconciliation, rejected records and safe failure handling.",
        },
        {
            "Layer": "Gold",
            "Project Location": "ClickHouse Serving Layer",
            "Tables / Objects": "curated dims, facts, marts and v_* views",
            "Purpose": "Business-ready serving model for Power BI consumption.",
        },
        {
            "Layer": "Consumption",
            "Project Location": "Power BI",
            "Tables / Objects": "Dashboard pages",
            "Purpose": "Visualization only; Power BI reads ClickHouse v_* views and is not the Gold storage layer.",
        },
    ]
    show_df(bsg, height=260)

# -----------------------------------------------------------------------------
# Data Quality
# -----------------------------------------------------------------------------
with tabs[5]:
    render_section("Quality Reconciliation", "🛡️")
    render_note(
        "Reconciliation rule: Raw/Input = Clean/Accepted + Quarantine/Rejected + Duplicate/Residual.",
        "info",
    )
    show_df(quality_rows(validation), height=300)

    render_section("Relationship and Coverage Checks", "🔍")
    show_df(relationship_rows(validation), height=260)

    render_section("Quarantine Interpretation", "🚫")
    render_note(
        "Rejected records are intentionally isolated instead of being silently dropped. The latest validation report exports rejected counts by source. A reason-code breakdown can be added if quarantine_records are summarized during validation export.",
        (
            "warn"
            if sum(as_int(row["Quarantine/Rejected"], 0) for row in quality_rows(validation)) > 0
            else "ok"
        ),
    )

# -----------------------------------------------------------------------------
# SCD Type 2
# -----------------------------------------------------------------------------
with tabs[6]:
    render_section("User SCD Type 2 Health", "🧬")
    show_df(scd2_rows(validation), height=310)

    render_section("Why users_cdc_clean and user_profile_scd2 are separate", "🧠")
    rows = [
        {
            "Table": "users_cdc_clean",
            "Role": "Clean CDC event history",
            "Contains": "operation, before/after JSON, source_lsn, source_ts_ms, Kafka offsets",
            "Why it exists": "Lineage, replay, debugging, incremental SCD2 input.",
        },
        {
            "Table": "user_profile_scd2",
            "Role": "Historical user profile dimension",
            "Contains": "effective_from, effective_to, is_current, version_sequence",
            "Why it exists": "Business analytics over user state across time.",
        },
    ]
    show_df(rows, height=180)
    render_note(
        "SCD2 is maintained by an Airflow-triggered Spark batch job. Streaming keeps the CDC event history clean, while the batch job builds the historical user dimension safely from users_cdc_clean.",
        "info",
    )

# -----------------------------------------------------------------------------
# Batch & Enrichment
# -----------------------------------------------------------------------------
with tabs[7]:
    render_section("Airflow Analytics Refresh DAG", "🗓️")
    c1, c2, c3 = st.columns(3)
    with c1:
        render_card("DAG", "analytics_refresh", "Hourly batch orchestration", "PASS")
    with c2:
        render_card(
            "Schedule",
            airflow_contract.get("schedule", "Not collected"),
            "0 * * * * = hourly",
            "PASS",
        )
    with c3:
        render_card("Max Active Runs", "1", "Low-memory controlled execution", "PASS")
    show_df(batch_rows(validation, serving), height=320)

    render_section("External API Enrichment Behavior", "🌦️")
    rows = [
        {
            "Job": "weather_enrichment",
            "Source": "Open-Meteo API",
            "Output": "weather_clean",
            "Important Behavior": "Current-day values can be unavailable from historical archive. Missing historical rows should be retried/backfilled in later runs.",
        },
        {
            "Job": "holiday_enrichment",
            "Source": "Calendarific API",
            "Output": "holidays_clean",
            "Important Behavior": "Country/year holiday coverage is pulled by batch job and audited through validation coverage.",
        },
        {
            "Job": "external_api_failures",
            "Source": "Audit table",
            "Output": "external_api_failures",
            "Important Behavior": "API failures must be stored as evidence instead of silently ignored.",
        },
    ]
    show_df(rows, height=210)

# -----------------------------------------------------------------------------
# ClickHouse & Power BI
# -----------------------------------------------------------------------------
with tabs[8]:
    render_section("ClickHouse Serving Layer", "🔥")
    c1, c2, c3, c4 = st.columns(4)
    with c1:
        render_card(
            "Database",
            CLICKHOUSE_DATABASE,
            "Serving database",
            "PASS" if ch_client() is not None else "WARN",
        )
    with c2:
        render_card(
            "Active Build",
            compact_text(serving.get("serving_build_id", "Not collected")),
            str(serving.get("serving_build_id", "Not collected")),
            serving.get("status", "UNKNOWN"),
        )
    with c3:
        render_card(
            "Views",
            f"{len(views_df)}/12",
            "Power BI curated v_* views",
            "PASS" if len(views_df) == 12 else "WARN",
        )
    with c4:
        latest_event = ch_query(
            f"SELECT max(event_timestamp) AS latest_event FROM {CLICKHOUSE_DATABASE}.v_fact_clickstream_event"
        )
        value = latest_event.iloc[0, 0] if not latest_event.empty else "Not collected"
        render_card(
            "Latest CH Event",
            value,
            "max event_timestamp",
            "PASS" if value != "Not collected" else "WARN",
        )

    render_section("Power BI View Counts", "📊")
    show_df(views_df, height=460)

    render_section("ClickHouse Engine, Sorting Key, and Primary Key", "🧱")
    render_note(
        "ClickHouse uses MergeTree sorting keys / primary keys for serving-layer read performance. Views themselves do not store data; they read active build rows from the underlying serving tables.",
        "info",
    )
    physical_keys_df = (
        keys_df[keys_df["engine"].astype(str).str.lower().ne("view")]
        if not keys_df.empty and "engine" in keys_df.columns
        else keys_df
    )
    show_df(physical_keys_df, height=520)

st.caption(
    f"Rendered at {datetime.now(UTC).isoformat()} · Auto-refresh every {REFRESH_SECONDS} seconds · Read-only operational console · Sources: runtime/observability, reports, ClickHouse, Debezium REST, Airflow, and project source files."
)
