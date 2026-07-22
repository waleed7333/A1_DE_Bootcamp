"""Initialization platform initialization: Kafka topics, MinIO, PostgreSQL, and Iceberg."""

from __future__ import annotations

import json
import re
import time
from dataclasses import asdict, dataclass
from datetime import UTC, datetime
from pathlib import Path
from typing import Any

from platform_core.compose import run_compose
from platform_core.config import load_settings, read_dotenv
from platform_core.infrastructure import run_infrastructure_check
from platform_core.source_generation import validate_sources


@dataclass(frozen=True)
class InitCheckResult:
    """One Initialization result shown in the terminal and persisted in the init report."""

    status: str
    check: str
    detail: str


NORMAL_TOPIC_KEYS = ("clickstream", "web_logs", "users_cdc", "orders_cdc", "order_items_cdc")
CONNECT_INTERNAL_TOPICS = {
    "debezium-connect-configs": {"partitions": 1, "cleanup.policy": "compact"},
    "debezium-connect-offsets": {"partitions": 3, "cleanup.policy": "compact"},
    "debezium-connect-status": {"partitions": 3, "cleanup.policy": "compact"},
}

EXPECTED_PROCESSED_TABLES = (
    "product_catalog_clean",
    "clickstream_clean",
    "webserver_logs_clean",
    "users_cdc_clean",
    "orders_cdc_clean",
    "order_items_cdc_clean",
    "user_profile_scd2",
    "weather_clean",
    "holidays_clean",
)
EXPECTED_RAW_TABLES = ("kafka_messages",)
EXPECTED_AUDIT_TABLES = (
    "pipeline_runs",
    "quality_metrics",
    "quarantine_records",
    "external_api_failures",
    "watermarks",
    "validation_runs",
    "serving_builds",
)
EXPECTED_POSTGRES_TABLES = ("users", "orders", "order_items")


def _result(status: str, check: str, detail: str) -> InitCheckResult:
    return InitCheckResult(status=status, check=check, detail=detail)


def _safe_error(error: Exception | str, *, limit: int = 500) -> str:
    """Return compact troubleshooting text without leaking environment values."""
    message = str(error).replace("\n", " ").strip()
    return (
        message[-limit:]
        if message
        else error.__class__.__name__ if isinstance(error, Exception) else "Unknown error"
    )


def _utc_now() -> str:
    return datetime.now(UTC).isoformat()


def _run_id(prefix: str) -> str:
    return f"{prefix}_{datetime.now(UTC).strftime('%Y%m%dT%H%M%SZ')}"


def _write_init_report(
    project_root: Path, results: list[InitCheckResult], passed: bool, *, run_id: str | None = None
) -> None:
    """Write a non-secret, presentation-friendly record for the initialization."""
    payload: dict[str, Any] = {
        "stage": "platform_initialization_and_static_catalog",
        "run_id": run_id,
        "checked_at_utc": _utc_now(),
        "status": "PASSED" if passed else "FAILED",
        "results": [asdict(result) for result in results],
    }
    report_path = project_root / "reports" / "init_report.json"
    report_path.parent.mkdir(parents=True, exist_ok=True)
    report_path.write_text(json.dumps(payload, indent=2) + "\n", encoding="utf-8")


def _write_project_state(project_root: Path, *, status: str, run_id: str) -> None:
    """Maintain a tiny lifecycle record without storing secrets or source data."""
    state_path = project_root / "runtime" / "project_state.json"
    state_path.parent.mkdir(parents=True, exist_ok=True)
    payload = {
        "lifecycle_state": status,
        "initialization_run_id": run_id,
        "updated_at_utc": _utc_now(),
        "note": "Initialization initializes infrastructure contracts and loads only the static product catalog.",
    }
    state_path.write_text(json.dumps(payload, indent=2) + "\n", encoding="utf-8")


def _source_manifest(project_root: Path) -> dict[str, Any]:
    """Load source generation manifest because it is the contract for static catalog checks."""
    manifest_path = project_root / "data" / "source" / "generation_manifest.json"
    if not manifest_path.exists():
        raise FileNotFoundError(
            "Missing data/source/generation_manifest.json. Run: python main.py init"
        )
    payload = json.loads(manifest_path.read_text(encoding="utf-8"))
    if payload.get("status") != "GENERATED":
        raise ValueError("Source manifest is not marked GENERATED. Re-run: python main.py init")
    return payload


def _warehouse_bucket(settings: dict[str, Any]) -> str:
    """Extract the bucket name from the configured Iceberg s3:// warehouse URI."""
    warehouse = str(settings["iceberg"]["warehouse"])
    matched = re.fullmatch(r"s3://([^/]+)/.+", warehouse)
    if not matched:
        raise ValueError(f"Iceberg warehouse must be an s3:// bucket path, found: {warehouse}")
    return matched.group(1)


def preflight(project_root: Path) -> tuple[list[InitCheckResult], bool]:
    """Verify infrastructure and Source generation before any initialization resource is created."""
    results: list[InitCheckResult] = []
    settings = load_settings(project_root)
    env_values = read_dotenv(project_root / ".env")

    infra_results, infra_ok = run_infrastructure_check(project_root)
    if infra_ok:
        results.append(
            _result(
                "PASS",
                "infrastructure infrastructure",
                "All required platform containers and live service checks passed",
            )
        )
    else:
        failed = [item.check for item in infra_results if item.status == "FAIL"]
        results.append(
            _result(
                "FAIL", "infrastructure infrastructure", f"Fix before init: {', '.join(failed[:5])}"
            )
        )

    source_results, source_ok = validate_sources(project_root, write_report=True)
    if source_ok:
        results.append(
            _result(
                "PASS",
                "Source generation local sources",
                "Source contracts, lineage, and manifest checks passed",
            )
        )
    else:
        failed = [item.check for item in source_results if item.status == "FAIL"]
        results.append(
            _result(
                "FAIL",
                "Source generation local sources",
                f"Fix before init: {', '.join(failed[:5])}",
            )
        )

    try:
        manifest = _source_manifest(project_root)
        product_count = int(manifest["counts"]["products"])
        checksum = str(manifest["catalog_checksum"])
        if product_count > 0 and len(checksum) == 64:
            results.append(
                _result(
                    "PASS",
                    "Static catalog manifest",
                    f"{product_count} products; checksum={checksum[:12]}",
                )
            )
        else:
            results.append(
                _result(
                    "FAIL", "Static catalog manifest", "Missing product count or SHA-256 checksum"
                )
            )
    except Exception as error:
        results.append(_result("FAIL", "Static catalog manifest", _safe_error(error)))

    try:
        expected_bucket = _warehouse_bucket(settings)
        configured_bucket = env_values.get("MINIO_BUCKET", "")
        if configured_bucket == expected_bucket:
            results.append(
                _result(
                    "PASS",
                    "MinIO bucket contract",
                    f"{configured_bucket} matches the Iceberg warehouse",
                )
            )
        else:
            results.append(
                _result(
                    "FAIL",
                    "MinIO bucket contract",
                    f"MINIO_BUCKET={configured_bucket or '<empty>'}; expected {expected_bucket}",
                )
            )
    except Exception as error:
        results.append(_result("FAIL", "MinIO bucket contract", _safe_error(error)))

    passed = all(item.status == "PASS" for item in results)
    return results, passed


def _topic_specs(settings: dict[str, Any]) -> dict[str, dict[str, Any]]:
    """Return the full Kafka topic contract, including Debezium Connect internal topics."""
    kafka = settings["kafka"]
    specs: dict[str, dict[str, Any]] = {}
    for key in NORMAL_TOPIC_KEYS:
        specs[kafka["topics"][key]] = {
            "partitions": int(kafka["partitions"]),
            "replication_factor": int(kafka["replication_factor"]),
            "config": {
                "min.insync.replicas": str(kafka["min_insync_replicas"]),
                "cleanup.policy": "delete",
            },
        }
    for topic, internal in CONNECT_INTERNAL_TOPICS.items():
        specs[topic] = {
            "partitions": int(internal["partitions"]),
            "replication_factor": int(kafka["replication_factor"]),
            "config": {
                "min.insync.replicas": str(kafka["min_insync_replicas"]),
                "cleanup.policy": str(internal["cleanup.policy"]),
            },
        }
    return specs


def ensure_kafka_topics(project_root: Path) -> InitCheckResult:
    """Create Kafka topics, then wait until metadata and replication are stable."""
    settings = load_settings(project_root)
    specs = _topic_specs(settings)

    try:
        from confluent_kafka.admin import AdminClient, NewTopic

        admin = AdminClient(
            {
                "bootstrap.servers": settings["runtime"]["host"]["kafka_bootstrap_servers"],
                "socket.timeout.ms": 10_000,
                "request.timeout.ms": 20_000,
            }
        )

        metadata = admin.list_topics(timeout=20)

        missing_topics = [topic_name for topic_name in specs if topic_name not in metadata.topics]

        if missing_topics:
            futures = admin.create_topics(
                [
                    NewTopic(
                        topic_name,
                        num_partitions=specs[topic_name]["partitions"],
                        replication_factor=specs[topic_name]["replication_factor"],
                        config=specs[topic_name]["config"],
                    )
                    for topic_name in missing_topics
                ],
                request_timeout=30,
                operation_timeout=30,
            )

            for topic_name, future in futures.items():
                try:
                    future.result(35)
                except Exception as error:
                    message = str(error).upper()

                    if "TOPIC_ALREADY_EXISTS" not in message:
                        raise RuntimeError(f"Topic {topic_name}: {_safe_error(error)}") from error

        deadline = time.monotonic() + 75
        last_failures: list[str] = []

        while time.monotonic() < deadline:
            metadata = admin.list_topics(timeout=20)
            failures: list[str] = []

            for topic_name, spec in specs.items():
                topic = metadata.topics.get(topic_name)

                if topic is None or topic.error is not None:
                    failures.append(f"{topic_name}: missing")
                    continue

                partitions = topic.partitions

                if len(partitions) != spec["partitions"]:
                    failures.append(f"{topic_name}: partitions={len(partitions)}")
                    continue

                replica_lengths = {len(partition.replicas) for partition in partitions.values()}

                isr_lengths = {len(partition.isrs) for partition in partitions.values()}

                if replica_lengths != {spec["replication_factor"]}:
                    failures.append(f"{topic_name}: replicas={sorted(replica_lengths)}")

                if min(
                    isr_lengths,
                    default=0,
                ) < int(settings["kafka"]["min_insync_replicas"]):
                    failures.append(f"{topic_name}: ISR={sorted(isr_lengths)}")

            if not failures:
                created_text = (
                    f"created {len(missing_topics)}" if missing_topics else "all already existed"
                )

                return _result(
                    "PASS",
                    "Kafka topic contract",
                    (f"{len(specs)} topics verified; " f"{created_text}; RF=3"),
                )

            last_failures = failures
            time.sleep(3)

        return _result(
            "FAIL",
            "Kafka topic contract",
            (
                "Timed out while waiting for Kafka topic metadata and "
                f"replication: {'; '.join(last_failures)}"
            ),
        )

    except Exception as error:
        return _result(
            "FAIL",
            "Kafka topic contract",
            _safe_error(error),
        )


def _minio_client(env_values: dict[str, str], settings: dict[str, Any]):
    """Build a path-style S3 client for local MinIO without printing credentials."""
    import boto3
    from botocore.config import Config

    endpoint = settings["runtime"]["host"]["minio_endpoint"]
    return boto3.client(
        "s3",
        endpoint_url=endpoint,
        aws_access_key_id=env_values["MINIO_ROOT_USER"],
        aws_secret_access_key=env_values["MINIO_ROOT_PASSWORD"],
        region_name="us-east-1",
        config=Config(
            s3={"addressing_style": "path"}, retries={"max_attempts": 3, "mode": "standard"}
        ),
    )


def ensure_minio_bucket(project_root: Path) -> InitCheckResult:
    """Create only the approved Iceberg bucket and prove it is writable through S3 API."""
    settings = load_settings(project_root)
    env_values = read_dotenv(project_root / ".env")
    try:
        bucket = _warehouse_bucket(settings)
        client = _minio_client(env_values, settings)
        bucket_names = {item["Name"] for item in client.list_buckets().get("Buckets", [])}
        if bucket not in bucket_names:
            client.create_bucket(Bucket=bucket)
        client.head_bucket(Bucket=bucket)
        return _result(
            "PASS",
            "MinIO Iceberg bucket",
            f"Bucket {bucket} exists and is reachable through S3 API",
        )
    except Exception as error:
        return _result("FAIL", "MinIO Iceberg bucket", _safe_error(error))


POSTGRES_DDL = (
    """
    CREATE TABLE IF NOT EXISTS public.users (
        user_id VARCHAR(32) PRIMARY KEY,
        email TEXT NOT NULL UNIQUE,
        first_name TEXT NOT NULL,
        last_name TEXT NOT NULL,
        membership_type TEXT NOT NULL,
        account_status TEXT NOT NULL,
        country_code VARCHAR(8) NOT NULL,
        city TEXT NOT NULL,
        created_at TIMESTAMPTZ NOT NULL,
        updated_at TIMESTAMPTZ NOT NULL
    )
    """,
    """
    CREATE TABLE IF NOT EXISTS public.orders (
        order_id VARCHAR(32) PRIMARY KEY,
        user_id VARCHAR(32) NOT NULL REFERENCES public.users(user_id),
        checkout_id VARCHAR(32) NOT NULL UNIQUE,
        order_timestamp TIMESTAMPTZ NOT NULL,
        order_status TEXT NOT NULL,
        payment_status TEXT NOT NULL,
        currency VARCHAR(8) NOT NULL,
        subtotal_amount NUMERIC(12, 2) NOT NULL,
        discount_amount NUMERIC(12, 2) NOT NULL,
        tax_amount NUMERIC(12, 2) NOT NULL,
        shipping_amount NUMERIC(12, 2) NOT NULL,
        total_amount NUMERIC(12, 2) NOT NULL,
        created_at TIMESTAMPTZ NOT NULL,
        updated_at TIMESTAMPTZ NOT NULL
    )
    """,
    """
    CREATE TABLE IF NOT EXISTS public.order_items (
        order_item_id VARCHAR(32) PRIMARY KEY,
        order_id VARCHAR(32) NOT NULL REFERENCES public.orders(order_id),
        product_id VARCHAR(32) NOT NULL,
        quantity INTEGER NOT NULL CHECK (quantity > 0),
        unit_price NUMERIC(12, 2) NOT NULL CHECK (unit_price > 0),
        line_total NUMERIC(12, 2) NOT NULL CHECK (line_total > 0),
        created_at TIMESTAMPTZ NOT NULL,
        updated_at TIMESTAMPTZ NOT NULL
    )
    """,
    "CREATE INDEX IF NOT EXISTS idx_orders_user_id ON public.orders (user_id)",
    "CREATE INDEX IF NOT EXISTS idx_order_items_order_id ON public.order_items (order_id)",
)


def ensure_postgres_source_schema(project_root: Path) -> InitCheckResult:
    """Create empty operational source tables; CDC alone will load seed rows into them."""
    env_values = read_dotenv(project_root / ".env")
    try:
        import psycopg2

        connection = psycopg2.connect(
            host="localhost",
            port=int(env_values["POSTGRES_PORT"]),
            dbname=env_values["POSTGRES_DB"],
            user=env_values["POSTGRES_USER"],
            password=env_values["POSTGRES_PASSWORD"],
            connect_timeout=8,
        )
        try:
            with connection.cursor() as cursor:
                for statement in POSTGRES_DDL:
                    cursor.execute(statement)
                cursor.execute("""
                    SELECT relname
                    FROM pg_class
                    JOIN pg_namespace ON pg_namespace.oid = pg_class.relnamespace
                    WHERE pg_namespace.nspname = 'public'
                      AND relname IN ('users', 'orders', 'order_items')
                    """)
                found = {row[0] for row in cursor.fetchall()}
                if found != set(EXPECTED_POSTGRES_TABLES):
                    raise RuntimeError(
                        f"Expected source tables missing: {sorted(set(EXPECTED_POSTGRES_TABLES) - found)}"
                    )
                cursor.execute("SELECT COUNT(*) FROM public.users")
                user_rows = int(cursor.fetchone()[0])
                cursor.execute("SELECT COUNT(*) FROM public.orders")
                order_rows = int(cursor.fetchone()[0])
                cursor.execute("SELECT COUNT(*) FROM public.order_items")
                item_rows = int(cursor.fetchone()[0])
            connection.commit()
        finally:
            connection.close()

        if user_rows or order_rows or item_rows:
            return _result(
                "PASS",
                "PostgreSQL source schema",
                f"Operational tables exist; existing rows preserved (users={user_rows}, orders={order_rows}, order_items={item_rows})",
            )
        return _result(
            "PASS",
            "PostgreSQL source schema",
            "users, orders, order_items created and intentionally empty",
        )
    except Exception as error:
        return _result("FAIL", "PostgreSQL source schema", _safe_error(error))


def _spark_report_path(project_root: Path, run_id: str, name: str) -> Path:
    return project_root / "runtime" / f"{name}_{run_id}.json"


def _run_spark_job(
    project_root: Path, script_name: str, run_id: str, *, timeout: int = 420
) -> tuple[bool, str]:
    """Run one Spark job inside the only Spark container without exposing credentials in command arguments."""
    command = [
        "exec",
        "-T",
        "spark-engine",
        "bash",
        "-lc",
        (
            "PYTHONPATH=/opt/project/src "
            "spark-submit --master local[2] "
            f"/opt/project/spark_jobs/{script_name} --run-id {run_id}"
        ),
    ]
    return run_compose(project_root, command, timeout=timeout)


def bootstrap_iceberg_and_catalog(project_root: Path, *, run_id: str) -> InitCheckResult:
    """Create all approved Iceberg tables and load only product_catalog_clean using Spark."""
    report_path = _spark_report_path(project_root, run_id, "bootstrap_lakehouse")
    try:
        ok, detail = _run_spark_job(project_root, "bootstrap_lakehouse.py", run_id)
        if not ok:
            return _result(
                "FAIL", "Spark Iceberg bootstrap", _safe_error(detail or "spark-submit failed")
            )
        if not report_path.exists():
            return _result(
                "FAIL",
                "Spark Iceberg bootstrap",
                "Spark completed but did not write its Initialization report",
            )
        report = json.loads(report_path.read_text(encoding="utf-8"))
        if report.get("status") != "PASSED":
            return _result(
                "FAIL",
                "Spark Iceberg bootstrap",
                str(report.get("error", "Spark report is not PASSED")),
            )
        return _result(
            "PASS",
            "Spark Iceberg bootstrap",
            f"{report['tables_created_or_verified']} tables verified; product_catalog_clean={report['product_catalog_rows']} rows",
        )
    except Exception as error:
        return _result("FAIL", "Spark Iceberg bootstrap", _safe_error(error))


def _verify_postgres_schema(project_root: Path) -> InitCheckResult:
    """Verify source tables remain available without reading or changing source data."""
    env_values = read_dotenv(project_root / ".env")
    try:
        import psycopg2

        connection = psycopg2.connect(
            host="localhost",
            port=int(env_values["POSTGRES_PORT"]),
            dbname=env_values["POSTGRES_DB"],
            user=env_values["POSTGRES_USER"],
            password=env_values["POSTGRES_PASSWORD"],
            connect_timeout=8,
        )
        with connection.cursor() as cursor:
            cursor.execute("""
                SELECT relname
                FROM pg_class
                JOIN pg_namespace ON pg_namespace.oid = pg_class.relnamespace
                WHERE pg_namespace.nspname = 'public'
                  AND relname IN ('users', 'orders', 'order_items')
                """)
            found = {row[0] for row in cursor.fetchall()}
        connection.close()
        if found == set(EXPECTED_POSTGRES_TABLES):
            return _result(
                "PASS",
                "PostgreSQL source tables",
                "users, orders, order_items are ready for the later CDC load",
            )
        return _result(
            "FAIL",
            "PostgreSQL source tables",
            f"Missing: {sorted(set(EXPECTED_POSTGRES_TABLES) - found)}",
        )
    except Exception as error:
        return _result("FAIL", "PostgreSQL source tables", _safe_error(error))


def verify_minio_warehouse(project_root: Path) -> InitCheckResult:
    """Verify Iceberg created physical objects under the approved MinIO warehouse prefix."""
    settings = load_settings(project_root)
    env_values = read_dotenv(project_root / ".env")
    try:
        bucket = _warehouse_bucket(settings)
        client = _minio_client(env_values, settings)
        client.head_bucket(Bucket=bucket)
        listing = client.list_objects_v2(Bucket=bucket, Prefix="warehouse/", MaxKeys=10)
        count = int(listing.get("KeyCount", 0))
        if count <= 0:
            return _result(
                "FAIL",
                "MinIO Iceberg objects",
                "Bucket exists but warehouse/ contains no Iceberg objects",
            )
        return _result(
            "PASS",
            "MinIO Iceberg objects",
            f"warehouse/ contains at least {count} Iceberg object(s)",
        )
    except Exception as error:
        return _result("FAIL", "MinIO Iceberg objects", _safe_error(error))


def verify_iceberg_tables(project_root: Path, *, run_id: str) -> InitCheckResult:
    """Run a separate Spark read verification; do not trust a previous job report alone."""
    report_path = _spark_report_path(project_root, run_id, "verify_lakehouse_bootstrap")
    try:
        ok, detail = _run_spark_job(project_root, "verify_lakehouse_bootstrap.py", run_id)
        if not ok:
            return _result(
                "FAIL", "Iceberg read verification", _safe_error(detail or "spark-submit failed")
            )
        if not report_path.exists():
            return _result(
                "FAIL",
                "Iceberg read verification",
                "Spark verification completed without its report",
            )
        report = json.loads(report_path.read_text(encoding="utf-8"))
        if report.get("status") != "PASSED":
            return _result(
                "FAIL",
                "Iceberg read verification",
                str(report.get("error", "Verification report is not PASSED")),
            )
        return _result(
            "PASS",
            "Iceberg read verification",
            f"{report['table_count']} tables readable; product catalog rows={report['product_catalog_rows']}",
        )
    except Exception as error:
        return _result("FAIL", "Iceberg read verification", _safe_error(error))


def _verify_topics(project_root: Path) -> InitCheckResult:
    """Reuse the create-and-verify operation because it is safely idempotent."""
    return ensure_kafka_topics(project_root)


def initialize_platform(project_root: Path) -> tuple[list[InitCheckResult], bool, str]:
    """Run the complete initialization in an idempotent, observable order."""
    run_id = _run_id("init")
    results, ready = preflight(project_root)
    if not ready:
        _write_init_report(project_root, results, False, run_id=run_id)
        return results, False, run_id

    for action in (ensure_kafka_topics, ensure_minio_bucket, ensure_postgres_source_schema):
        result = action(project_root)
        results.append(result)
        if result.status != "PASS":
            _write_init_report(project_root, results, False, run_id=run_id)
            return results, False, run_id

    bootstrap_result = bootstrap_iceberg_and_catalog(project_root, run_id=run_id)
    results.append(bootstrap_result)
    if bootstrap_result.status != "PASS":
        _write_init_report(project_root, results, False, run_id=run_id)
        return results, False, run_id

    verification_run_id = _run_id("verify")
    for action in (_verify_topics, _verify_postgres_schema, verify_minio_warehouse):
        result = action(project_root)
        results.append(result)
        if result.status != "PASS":
            _write_init_report(project_root, results, False, run_id=run_id)
            return results, False, run_id

    iceberg_result = verify_iceberg_tables(project_root, run_id=verification_run_id)
    results.append(iceberg_result)
    passed = all(item.status == "PASS" for item in results)
    _write_init_report(project_root, results, passed, run_id=run_id)
    if passed:
        _write_project_state(project_root, status="CATALOG_INITIALIZED", run_id=run_id)
    return results, passed, run_id


def verify_initialization(project_root: Path) -> tuple[list[InitCheckResult], bool, str]:
    """Verify initialization resources without changing source data or loading operational tables."""
    run_id = _run_id("verify")
    results, ready = preflight(project_root)
    if not ready:
        _write_init_report(project_root, results, False, run_id=run_id)
        return results, False, run_id

    for action in (
        _verify_topics,
        ensure_minio_bucket,
        _verify_postgres_schema,
        verify_minio_warehouse,
    ):
        result = action(project_root)
        results.append(result)

    iceberg_result = verify_iceberg_tables(project_root, run_id=run_id)
    results.append(iceberg_result)
    passed = all(item.status == "PASS" for item in results)
    _write_init_report(project_root, results, passed, run_id=run_id)
    return results, passed, run_id
