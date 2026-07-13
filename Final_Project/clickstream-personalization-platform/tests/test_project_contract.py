"""Fast contract tests that do not require Docker, Kafka, Spark, generated source files, or external APIs."""

from __future__ import annotations

import csv
from pathlib import Path

import yaml

PROJECT_ROOT = Path(__file__).resolve().parents[1]


def load_settings() -> dict:
    return yaml.safe_load((PROJECT_ROOT / "config" / "settings.yaml").read_text(encoding="utf-8"))


def test_static_project_contract_matches_approved_scope() -> None:
    settings = load_settings()

    assert settings["project"]["name"] == "Clickstream Analysis for Website Personalization"
    assert settings["iceberg"]["catalog_name"] == "ecommerce"
    assert settings["iceberg"]["warehouse"] == "s3://ecommerce-lakehouse/warehouse"
    assert settings["source_contract"]["product_catalog"]["mode"] == "static_csv_initial_load_only"
    assert settings["source_contract"]["weather"]["mode"] == "scheduled_open_meteo_batch"
    assert settings["source_contract"]["holidays"]["mode"] == "scheduled_calendarific_batch"

    assert settings["kafka"]["partitions"] == 3
    assert settings["kafka"]["replication_factor"] == 3
    assert settings["kafka"]["min_insync_replicas"] == 2
    assert set(settings["kafka"]["topics"].values()) == {
        "clickstream-events",
        "webserver-logs",
        "users-cdc",
        "orders-cdc",
        "order-items-cdc",
    }


def test_static_product_catalog_is_present_and_clean() -> None:
    settings = load_settings()
    catalog_path = PROJECT_ROOT / settings["paths"]["product_catalog"]
    assert catalog_path.is_file()

    with catalog_path.open(newline="", encoding="utf-8") as handle:
        rows = list(csv.DictReader(handle))

    assert len(rows) == settings["source_generation"]["product_catalog_count"]
    product_ids = [row["product_id"] for row in rows]
    assert len(product_ids) == len(set(product_ids))
    for row in rows:
        assert row["product_id"]
        assert row["product_name"]
        assert row["category"]
        assert float(row["price"]) >= 0
        assert int(row["inventory"]) >= 0


def test_documentation_files_and_assets_exist() -> None:
    expected_docs = [
        "README.md",
        "docs/01_PROJECT_ARCHITECTURE.md",
        "docs/02_DATA_SOURCES_AND_CONTRACTS.md",
        "docs/03_PIPELINES_QUALITY_AND_LAKEHOUSE.md",
        "docs/04_SERVING_AND_DASHBOARDS.md",
        "docs/05_OPERATIONS_VALIDATION_AND_LIMITATIONS.md",
    ]
    expected_diagrams = [
        "diagrams/01_architecture_overview.png",
        "diagrams/02_data_flow.png",
        "diagrams/03_lakehouse_zones.png",
        "diagrams/04_cdc_scd2_flow.png",
        "diagrams/05_clickhouse_olap_model.png",
        "diagrams/06_analytics_refresh_orchestration.png",
        "diagrams/07_data_quality_audit_reconciliation.png",
        "diagrams/08_business_key_relationships.png",
        "diagrams/09_bronze_silver_gold_flow.png",
    ]

    for relative_path in expected_docs + expected_diagrams:
        assert (PROJECT_ROOT / relative_path).is_file(), relative_path


def test_cli_exposes_only_the_five_normal_commands() -> None:
    # The local test environment may not have every runtime dependency installed.
    # Inspect the parser source so this fast contract test remains dependency-light.
    main_source = (PROJECT_ROOT / "main.py").read_text(encoding="utf-8")
    for command in ["init", "start", "status", "stop", "reset"]:
        assert f'add_parser("{command}"' in main_source
    assert 'add_parser("bootstrap"' not in main_source
    assert 'add_parser("publish-serving"' not in main_source
