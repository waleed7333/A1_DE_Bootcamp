"""Static project contract tests for the final project package."""

from __future__ import annotations

import ast
from pathlib import Path

PROJECT_ROOT = Path(__file__).resolve().parents[1]

EXPECTED_SERVING_TABLES = (
    "dim_date",
    "dim_product",
    "dim_user_current",
    "fact_clickstream_event",
    "fact_order",
    "fact_order_item",
    "mart_journey_session",
    "mart_product_performance_daily",
    "mart_web_experience_daily",
    "mart_navigation_paths",
    "mart_personalization_candidates",
    "mart_context_impact_daily",
)

EXPECTED_OPERATIONS_SECTIONS = (
    "Overview",
    "Infrastructure",
    "Kafka & CDC",
    "Spark Streaming",
    "Lakehouse Storage",
    "Data Quality",
    "SCD Type 2",
    "Batch & APIs",
    "Serving & Power BI",
)


def read_text(relative_path: str) -> str:
    return (PROJECT_ROOT / relative_path).read_text(encoding="utf-8")


def serving_tables_from_source() -> tuple[str, ...]:
    source = read_text("spark_jobs/serving_common.py")
    tree = ast.parse(source)

    for node in tree.body:
        if isinstance(node, ast.Assign):
            for target in node.targets:
                if isinstance(target, ast.Name) and target.id == "TABLES":
                    value = ast.literal_eval(node.value)
                    return tuple(value)

    raise AssertionError("TABLES constant was not found in spark_jobs/serving_common.py")


def test_serving_layer_exposes_twelve_stable_tables() -> None:
    tables = serving_tables_from_source()

    assert tables == EXPECTED_SERVING_TABLES
    assert len(tables) == 12


def test_power_bi_documentation_uses_expected_serving_views() -> None:
    docs_text = "\n".join(
        file_path.read_text(encoding="utf-8")
        for file_path in [
            PROJECT_ROOT / "README.md",
            PROJECT_ROOT / "docs" / "04_SERVING_AND_DASHBOARDS.md",
        ]
        if file_path.is_file()
    )

    for table_name in EXPECTED_SERVING_TABLES:
        view_name = f"v_{table_name}"
        assert view_name in docs_text, f"{view_name} is missing from dashboard documentation"


def test_operations_console_sections_match_platform_layers() -> None:
    text = read_text("observability_ui/app.py")

    for section in EXPECTED_OPERATIONS_SECTIONS:
        assert section in text


def test_weather_enrichment_uses_upsert_and_coverage_status() -> None:
    text = read_text("spark_jobs/weather_enrichment.py")

    assert "write_weather_updates" in text
    assert "MERGE INTO" in text
    assert "weather_enrichment_updates" in text
    assert "coverage_status" in text
    assert "complete" in text
    assert "unavailable" in text
    assert "left_anti" in text


def test_publish_serving_validates_tables_and_views() -> None:
    text = read_text("spark_jobs/publish_clickhouse.py")
    common = read_text("spark_jobs/serving_common.py")

    assert "validate_serving_tables_for_build" in common
    assert "validate_active_serving_views" in common
    assert "view_validation" in text
    assert "table_validation" in text


def test_checkout_completion_requires_order_identifier() -> None:
    text = read_text("spark_jobs/streaming_ingestion.py")

    assert "checkout_complete" in text
    assert "MISSING_ORDER_ID" in text
    assert 'F.col("order_id").isNull()' in text
