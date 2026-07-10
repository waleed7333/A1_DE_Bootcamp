"""CDC: seed PostgreSQL from local CSV files and verify Debezium initial snapshots.

This module deliberately does *not* run Spark Streaming. It proves the CDC hand-off only:
local CSV seed files -> PostgreSQL operational tables -> Debezium -> Kafka snapshot topics.
"""

from __future__ import annotations

import csv
import json
import time
import uuid
from dataclasses import asdict, dataclass
from datetime import UTC, datetime
from decimal import Decimal
from pathlib import Path
from typing import Any

import requests

from platform_core.config import load_settings, read_dotenv
from platform_core.infrastructure import run_infrastructure_check
from platform_core.initializer import ensure_kafka_topics
from platform_core.source_generation import ORDER_FIELDS, ORDER_ITEM_FIELDS, USER_FIELDS, validate_sources

USERS_FIELDS = USER_FIELDS
ORDERS_FIELDS = ORDER_FIELDS
ORDER_ITEMS_FIELDS = ORDER_ITEM_FIELDS


CDC_TABLES: tuple[dict[str, str], ...] = (
    {
        "table": "users",
        "primary_key": "user_id",
        "seed_key": "users",
        "topic_key": "users_cdc",
        "connector": "clickstream-users-cdc",
        "slot": "clickstream_users_cdc_slot",
        "publication": "clickstream_users_cdc_pub",
    },
    {
        "table": "orders",
        "primary_key": "order_id",
        "seed_key": "orders",
        "topic_key": "orders_cdc",
        "connector": "clickstream-orders-cdc",
        "slot": "clickstream_orders_cdc_slot",
        "publication": "clickstream_orders_cdc_pub",
    },
    {
        "table": "order_items",
        "primary_key": "order_item_id",
        "seed_key": "order_items",
        "topic_key": "order_items_cdc",
        "connector": "clickstream-order-items-cdc",
        "slot": "clickstream_order_items_cdc_slot",
        "publication": "clickstream_order_items_cdc_pub",
    },
)

SEED_HEADERS: dict[str, list[str]] = {
    "users": USERS_FIELDS,
    "orders": ORDERS_FIELDS,
    "order_items": ORDER_ITEMS_FIELDS,
}


@dataclass(frozen=True)
class CdcCheckResult:
    """One CDC result displayed in the terminal and persisted without secrets."""

    status: str
    check: str
    detail: str


def _result(status: str, check: str, detail: str) -> CdcCheckResult:
    return CdcCheckResult(status=status, check=check, detail=detail)


def _run_id(prefix: str) -> str:
    return f"{prefix}_{datetime.now(UTC).strftime('%Y%m%dT%H%M%SZ')}"


def _safe_error(error: Exception | str, *, limit: int = 500) -> str:
    """Return compact troubleshooting text and never serialize environment values."""
    message = str(error).replace("\n", " ").strip()
    return message[-limit:] if message else type(error).__name__ if isinstance(error, Exception) else "Unknown error"


def _utc_now() -> str:
    return datetime.now(UTC).isoformat()


def _read_csv(path: Path, expected_headers: list[str]) -> list[dict[str, str]]:
    if not path.is_file():
        raise FileNotFoundError(f"Missing seed file: {path}")
    with path.open("r", newline="", encoding="utf-8") as handle:
        reader = csv.DictReader(handle)
        if reader.fieldnames != expected_headers:
            raise ValueError(f"Unexpected header in {path.name}: {reader.fieldnames}")
        rows = list(reader)
    if not rows:
        raise ValueError(f"Seed file is empty: {path}")
    return rows


def _load_seed_rows(project_root: Path) -> dict[str, list[dict[str, str]]]:
    settings = load_settings(project_root)
    contract = settings["source_contract"]
    return {
        "users": _read_csv(project_root / contract["users"]["seed_file"], USERS_FIELDS),
        "orders": _read_csv(project_root / contract["orders"]["seed_file"], ORDERS_FIELDS),
        "order_items": _read_csv(project_root / contract["order_items"]["seed_file"], ORDER_ITEMS_FIELDS),
    }


def _initialization_passed(project_root: Path) -> bool:
    """Require a successful Initialization report before modifying operational source tables."""
    path = project_root / "reports" / "init_report.json"
    if not path.is_file():
        return False
    try:
        return json.loads(path.read_text(encoding="utf-8")).get("status") == "PASSED"
    except json.JSONDecodeError:
        return False


def _postgres_connection(project_root: Path):
    import psycopg2

    env = read_dotenv(project_root / ".env")
    return psycopg2.connect(
        host="localhost",
        port=int(env["POSTGRES_PORT"]),
        dbname=env["POSTGRES_DB"],
        user=env["POSTGRES_USER"],
        password=env["POSTGRES_PASSWORD"],
        connect_timeout=10,
    )


def _expected_counts(rows: dict[str, list[dict[str, str]]]) -> dict[str, int]:
    return {name: len(values) for name, values in rows.items()}


def _postgres_counts(connection) -> dict[str, int]:
    with connection.cursor() as cursor:
        result: dict[str, int] = {}
        for table in ("users", "orders", "order_items"):
            cursor.execute(f"SELECT COUNT(*) FROM public.{table}")
            result[table] = int(cursor.fetchone()[0])
    return result


def _check_postgres_logical_replication(project_root: Path) -> CdcCheckResult:
    try:
        connection = _postgres_connection(project_root)
        try:
            with connection.cursor() as cursor:
                cursor.execute("SHOW wal_level")
                wal_level = str(cursor.fetchone()[0])
                cursor.execute("SHOW max_replication_slots")
                slots = int(cursor.fetchone()[0])
                cursor.execute("SHOW max_wal_senders")
                senders = int(cursor.fetchone()[0])
        finally:
            connection.close()
        if wal_level != "logical":
            return _result("FAIL", "PostgreSQL logical replication", f"wal_level={wal_level}; expected logical")
        if slots < len(CDC_TABLES) or senders < len(CDC_TABLES):
            return _result(
                "FAIL",
                "PostgreSQL logical replication",
                f"max_replication_slots={slots}, max_wal_senders={senders}; need at least {len(CDC_TABLES)}",
            )
        return _result("PASS", "PostgreSQL logical replication", f"wal_level=logical; slots={slots}; wal_senders={senders}")
    except Exception as error:
        return _result("FAIL", "PostgreSQL logical replication", _safe_error(error))


def cdc_preflight(project_root: Path) -> tuple[list[CdcCheckResult], bool]:
    """Ensure required prerequisites are verified before loading any source record."""
    results: list[CdcCheckResult] = []

    infra_results, infra_ok = run_infrastructure_check(project_root)
    if infra_ok:
        results.append(_result("PASS", "Infrastructure infrastructure", "All required platform containers and live service checks passed"))
    else:
        failed = [item.check for item in infra_results if item.status == "FAIL"]
        results.append(_result("FAIL", "Infrastructure infrastructure", f"Fix before CDC load: {', '.join(failed[:5])}"))

    source_results, source_ok = validate_sources(project_root, write_report=True)
    if source_ok:
        results.append(_result("PASS", "Source Generation local sources", "CSV seed files and cross-source relationships passed"))
    else:
        failed = [item.check for item in source_results if item.status == "FAIL"]
        results.append(_result("FAIL", "Source Generation local sources", f"Fix before CDC load: {', '.join(failed[:5])}"))

    if _initialization_passed(project_root):
        results.append(_result("PASS", "Initialization initialization", "Kafka, PostgreSQL source schema, MinIO, and Iceberg catalog are verified"))
    else:
        results.append(_result("FAIL", "Initialization initialization", "Missing successful reports/init_report.json; run: python main.py init"))

    results.append(_check_postgres_logical_replication(project_root))
    passed = all(result.status == "PASS" for result in results)
    return results, passed


def _seed_insert_sql(table: str) -> str:
    headers = SEED_HEADERS[table]
    columns = ", ".join(headers)
    placeholders = ", ".join(["%s"] * len(headers))
    return f"INSERT INTO public.{table} ({columns}) VALUES ({placeholders})"


def _seed_database(project_root: Path) -> CdcCheckResult:
    """Load the three CSV seeds exactly once, preserving a matching prior load on re-run."""
    try:
        rows = _load_seed_rows(project_root)
        expected = _expected_counts(rows)
        connection = _postgres_connection(project_root)
        try:
            existing = _postgres_counts(connection)
            if all(value == 0 for value in existing.values()):
                with connection.cursor() as cursor:
                    # Foreign-key order is deliberate and mirrors the approved source lineage.
                    for table in ("users", "orders", "order_items"):
                        headers = SEED_HEADERS[table]
                        values = [tuple(row[column] for column in headers) for row in rows[table]]
                        cursor.executemany(_seed_insert_sql(table), values)
                connection.commit()
                inserted = True
            elif existing == expected:
                inserted = False
            else:
                connection.rollback()
                raise RuntimeError(
                    "PostgreSQL source tables are partially populated or do not match the approved seed counts: "
                    f"actual={existing}, expected={expected}. Do not mix a new seed with old operational data."
                )

            actual = _postgres_counts(connection)
            if actual != expected:
                raise RuntimeError(f"PostgreSQL counts do not match seed files: actual={actual}, expected={expected}")

            with connection.cursor() as cursor:
                cursor.execute(
                    """
                    SELECT COUNT(*)
                    FROM public.orders o
                    LEFT JOIN public.users u ON u.user_id = o.user_id
                    WHERE u.user_id IS NULL
                    """
                )
                orphan_orders = int(cursor.fetchone()[0])
                cursor.execute(
                    """
                    SELECT COUNT(*)
                    FROM public.order_items oi
                    LEFT JOIN public.orders o ON o.order_id = oi.order_id
                    WHERE o.order_id IS NULL
                    """
                )
                orphan_items = int(cursor.fetchone()[0])
                cursor.execute("SELECT COALESCE(SUM(total_amount), 0) FROM public.orders")
                db_order_total = Decimal(str(cursor.fetchone()[0]))
                cursor.execute("SELECT COALESCE(SUM(line_total), 0) FROM public.order_items")
                db_item_total = Decimal(str(cursor.fetchone()[0]))
            if orphan_orders or orphan_items:
                raise RuntimeError(f"Relational integrity failed: orphan_orders={orphan_orders}, orphan_items={orphan_items}")

            expected_order_total = sum((Decimal(row["total_amount"]) for row in rows["orders"]), Decimal("0"))
            expected_item_total = sum((Decimal(row["line_total"]) for row in rows["order_items"]), Decimal("0"))
            if db_order_total != expected_order_total or db_item_total != expected_item_total:
                raise RuntimeError(
                    "PostgreSQL monetary reconciliation failed: "
                    f"orders={db_order_total}/{expected_order_total}, items={db_item_total}/{expected_item_total}"
                )
        finally:
            connection.close()

        mode = "inserted from local CSV" if inserted else "already matched local CSV; no rows were reinserted"
        return _result(
            "PASS",
            "PostgreSQL seed load",
            f"{mode}; users={expected['users']}, orders={expected['orders']}, order_items={expected['order_items']}",
        )
    except Exception as error:
        return _result("FAIL", "PostgreSQL seed load", _safe_error(error))


def _connector_config(project_root: Path, spec: dict[str, str]) -> dict[str, str]:
    """Build one narrow connector per source table so each target Kafka topic stays explicit."""
    settings = load_settings(project_root)
    env = read_dotenv(project_root / ".env")
    target_topic = settings["kafka"]["topics"][spec["topic_key"]]
    table = spec["table"]
    # Debezium requires the topic prefix to be unique across connectors.
    # The RegexRouter still maps the output to the approved project topic.
    topic_prefix = f"ecommerce_{table}"
    # Each connector watches exactly one table, then routes its Debezium logical topic
    # to the already-created project topic (users-cdc, orders-cdc, or order-items-cdc).
    return {
        "connector.class": "io.debezium.connector.postgresql.PostgresConnector",
        "tasks.max": "1",
        "plugin.name": "pgoutput",
        "database.hostname": settings["runtime"]["docker"]["postgres_host"],
        "database.port": str(settings["runtime"]["docker"]["postgres_port"]),
        "database.user": env["POSTGRES_USER"],
        "database.password": env["POSTGRES_PASSWORD"],
        "database.dbname": env["POSTGRES_DB"],
        "topic.prefix": topic_prefix,
        "schema.include.list": "public",
        "table.include.list": f"public.{table}",
        "slot.name": spec["slot"],
        "publication.name": spec["publication"],
        "publication.autocreate.mode": "filtered",
        "snapshot.mode": "initial",
        "snapshot.fetch.size": "1000",
        "tombstones.on.delete": "false",
        "heartbeat.interval.ms": "0",
        "decimal.handling.mode": "string",
        "include.schema.changes": "false",
        "key.converter": "org.apache.kafka.connect.json.JsonConverter",
        "key.converter.schemas.enable": "false",
        "value.converter": "org.apache.kafka.connect.json.JsonConverter",
        "value.converter.schemas.enable": "false",
        "transforms": "route",
        "transforms.route.type": "org.apache.kafka.connect.transforms.RegexRouter",
        "transforms.route.regex": rf"{topic_prefix}\.public\.{table}",
        "transforms.route.replacement": target_topic,
    }


def _connector_url(base_url: str, connector_name: str | None = None) -> str:
    suffix = "/connectors" if connector_name is None else f"/connectors/{connector_name}"
    return base_url.rstrip("/") + suffix


def _register_connectors(project_root: Path) -> CdcCheckResult:
    """Create only missing connectors; existing matching connectors are never reset automatically."""
    settings = load_settings(project_root)
    base_url = settings["runtime"]["host"]["debezium_url"]
    try:
        existing_response = requests.get(_connector_url(base_url), timeout=10)
        existing_response.raise_for_status()
        existing = set(existing_response.json())
        created: list[str] = []
        reused: list[str] = []

        for spec in CDC_TABLES:
            name = spec["connector"]
            expected = _connector_config(project_root, spec)
            if name in existing:
                config_response = requests.get(_connector_url(base_url, name) + "/config", timeout=10)
                config_response.raise_for_status()
                actual = config_response.json()
                expected_pairs = {
                    "connector.class": expected["connector.class"],
                    "table.include.list": expected["table.include.list"],
                    "slot.name": expected["slot.name"],
                    "publication.name": expected["publication.name"],
                    "topic.prefix": expected["topic.prefix"],
                    "transforms.route.regex": expected["transforms.route.regex"],
                    "transforms.route.replacement": expected["transforms.route.replacement"],
                }
                mismatches = [key for key, value in expected_pairs.items() if actual.get(key) != value]
                if mismatches:
                    raise RuntimeError(f"Existing connector {name} does not match CDC contract: {', '.join(mismatches)}")
                reused.append(name)
                continue

            response = requests.post(
                _connector_url(base_url),
                json={"name": name, "config": expected},
                timeout=20,
            )
            if response.status_code not in {200, 201}:
                raise RuntimeError(f"Connector {name} registration failed: HTTP {response.status_code}")
            created.append(name)

        return _result(
            "PASS",
            "Debezium connector registration",
            f"created={len(created)}, reused={len(reused)}; one connector per approved CDC source table",
        )
    except Exception as error:
        return _result("FAIL", "Debezium connector registration", _safe_error(error))


def _wait_for_connector_tasks(project_root: Path, *, timeout_seconds: int = 180) -> CdcCheckResult:
    settings = load_settings(project_root)
    base_url = settings["runtime"]["host"]["debezium_url"]
    deadline = time.monotonic() + timeout_seconds
    last_detail = "No status response yet"
    try:
        while time.monotonic() < deadline:
            healthy = True
            states: list[str] = []
            for spec in CDC_TABLES:
                name = spec["connector"]
                response = requests.get(_connector_url(base_url, name) + "/status", timeout=10)
                if response.status_code != 200:
                    healthy = False
                    last_detail = f"{name}: HTTP {response.status_code}"
                    break
                payload = response.json()
                connector_state = str(payload.get("connector", {}).get("state", "UNKNOWN"))
                tasks = payload.get("tasks", [])
                task_states = [str(task.get("state", "UNKNOWN")) for task in tasks]
                states.append(f"{name}={connector_state}/{','.join(task_states) or 'no-task'}")
                if connector_state != "RUNNING" or not task_states or any(state != "RUNNING" for state in task_states):
                    healthy = False
            if healthy:
                return _result("PASS", "Debezium connector tasks", "All 3 connectors and their tasks are RUNNING")
            last_detail = "; ".join(states) or last_detail
            time.sleep(3)
        return _result("FAIL", "Debezium connector tasks", f"Timed out after {timeout_seconds}s: {last_detail}")
    except Exception as error:
        return _result("FAIL", "Debezium connector tasks", _safe_error(error))


def _wait_for_connect_api(project_root: Path, *, timeout_seconds: int) -> CdcCheckResult:
    """Wait for Debezium Connect REST before registering connectors.

    A running container can still reset HTTP connections while Kafka Connect finishes
    loading plugins and internal topics.  Retrying here prevents a normal restart from
    being classified as a permanent connector failure.
    """
    settings = load_settings(project_root)
    base_url = settings["runtime"]["host"]["debezium_url"]
    deadline = time.monotonic() + timeout_seconds
    last_detail = "No HTTP response yet"
    while time.monotonic() < deadline:
        try:
            response = requests.get(_connector_url(base_url), timeout=8)
            if response.ok and isinstance(response.json(), list):
                return _result("PASS", "Debezium Connect REST readiness", "Connector API is ready")
            last_detail = f"HTTP {response.status_code}"
        except (requests.RequestException, ValueError) as error:
            last_detail = _safe_error(error)
        time.sleep(3)
    return _result("FAIL", "Debezium Connect REST readiness", f"Timed out after {timeout_seconds}s: {last_detail}")


def ensure_cdc_connectors(project_root: Path, *, timeout_seconds: int = 180) -> tuple[list[CdcCheckResult], bool]:
    """Ensure only the three approved Debezium connectors are present and running.

    This operational helper deliberately does not seed PostgreSQL and does not verify
    historical snapshot counts. It waits for the REST API first, creates only missing
    connectors, and then waits for all connector tasks to become RUNNING.
    """
    api_result = _wait_for_connect_api(project_root, timeout_seconds=min(timeout_seconds, 120))
    if api_result.status != "PASS":
        return [api_result], False
    registration_result = _register_connectors(project_root)
    if registration_result.status != "PASS":
        return [api_result, registration_result], False
    task_timeout = max(30, timeout_seconds - 10)
    task_result = _wait_for_connector_tasks(project_root, timeout_seconds=task_timeout)
    results = [api_result, registration_result, task_result]
    return results, all(item.status == "PASS" for item in results)


def _read_snapshot_messages(
    bootstrap_servers: str,
    topic: str,
    primary_key: str,
    expected_ids: set[str],
    *,
    timeout_seconds: int,
) -> tuple[int, set[str], list[str]]:
    """Read a topic from offset zero with an isolated group and validate snapshot envelopes."""
    from confluent_kafka import Consumer, KafkaError

    consumer = Consumer(
        {
            "bootstrap.servers": bootstrap_servers,
            "group.id": f"cdc-verify-{topic}-{uuid.uuid4().hex[:12]}",
            "enable.auto.commit": False,
            "auto.offset.reset": "earliest",
            "session.timeout.ms": 10_000,
        }
    )
    count = 0
    ids: set[str] = set()
    errors: list[str] = []
    deadline = time.monotonic() + timeout_seconds
    idle_after_expected_started: float | None = None
    try:
        consumer.subscribe([topic])
        while time.monotonic() < deadline:
            message = consumer.poll(1.0)
            if message is None:
                if len(ids) >= len(expected_ids):
                    if idle_after_expected_started is None:
                        idle_after_expected_started = time.monotonic()
                    elif time.monotonic() - idle_after_expected_started >= 3:
                        break
                continue
            idle_after_expected_started = None
            if message.error():
                # EOF is not an error for verification; other Kafka errors are.
                if message.error().code() != KafkaError._PARTITION_EOF:
                    errors.append(str(message.error()))
                continue
            count += 1
            raw = message.value()
            try:
                payload = json.loads(raw.decode("utf-8") if isinstance(raw, bytes) else raw)
            except Exception as error:
                errors.append(f"non-JSON message at {topic}[{message.partition()}]@{message.offset()}: {error}")
                continue
            operation = payload.get("op")
            after = payload.get("after")
            source = payload.get("source", {})
            if operation != "r":
                errors.append(f"message {count} operation={operation!r}; expected snapshot op='r'")
                continue
            if not isinstance(after, dict) or not after.get(primary_key):
                errors.append(f"message {count} has no after.{primary_key}")
                continue
            expected_table = {"user_id": "users", "order_id": "orders", "order_item_id": "order_items"}[primary_key]
            if source.get("table") not in {None, expected_table}:
                errors.append(f"message {count} source.table={source.get('table')!r}; expected {expected_table!r}")
                continue
            row_id = str(after[primary_key])
            if row_id in ids:
                errors.append(f"duplicate snapshot key {row_id}")
            ids.add(row_id)
            if len(ids) > len(expected_ids):
                break
    finally:
        consumer.close()
    return count, ids, errors


def _verify_snapshot_topics(project_root: Path, *, timeout_seconds: int = 180) -> CdcCheckResult:
    """Require exact initial-snapshot messages for every PostgreSQL seed row."""
    try:
        settings = load_settings(project_root)
        seed_rows = _load_seed_rows(project_root)
        bootstrap = settings["runtime"]["host"]["kafka_bootstrap_servers"]
        details: list[str] = []
        failures: list[str] = []
        per_topic_timeout = max(30, timeout_seconds // len(CDC_TABLES))

        for spec in CDC_TABLES:
            table = spec["table"]
            primary_key = spec["primary_key"]
            topic = settings["kafka"]["topics"][spec["topic_key"]]
            expected_ids = {str(row[primary_key]) for row in seed_rows[table]}
            count, actual_ids, errors = _read_snapshot_messages(
                bootstrap,
                topic,
                primary_key,
                expected_ids,
                timeout_seconds=per_topic_timeout,
            )
            missing = expected_ids - actual_ids
            unexpected = actual_ids - expected_ids
            if errors or missing or unexpected or count != len(expected_ids):
                failures.append(
                    f"{topic}: messages={count}/{len(expected_ids)}, missing={len(missing)}, "
                    f"unexpected={len(unexpected)}, envelope_errors={len(errors)}"
                )
            else:
                details.append(f"{topic}={count}")

        if failures:
            return _result("FAIL", "Debezium initial snapshot", "; ".join(failures))
        return _result("PASS", "Debezium initial snapshot", ", ".join(details) + "; all messages have op='r'")
    except Exception as error:
        return _result("FAIL", "Debezium initial snapshot", _safe_error(error))


def _write_report(project_root: Path, results: list[CdcCheckResult], passed: bool, run_id: str) -> None:
    payload = {
        "stage": "postgres_seed_and_debezium_initial_snapshot",
        "run_id": run_id,
        "checked_at_utc": _utc_now(),
        "status": "PASSED" if passed else "FAILED",
        "results": [asdict(result) for result in results],
        "scope": {
            "postgres_tables": [spec["table"] for spec in CDC_TABLES],
            "kafka_topics": [load_settings(project_root)["kafka"]["topics"][spec["topic_key"]] for spec in CDC_TABLES],
            "spark_streaming_started": False,
        },
    }
    path = project_root / "reports" / "cdc_initial_snapshot_report.json"
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(payload, indent=2) + "\n", encoding="utf-8")


def _write_state(project_root: Path, run_id: str) -> None:
    path = project_root / "runtime" / "project_state.json"
    payload = {
        "lifecycle_state": "CDC_SNAPSHOT_READY",
        "cdc_run_id": run_id,
        "updated_at_utc": _utc_now(),
        "note": "PostgreSQL seeds match local CSV files and Debezium initial snapshots are verified in Kafka. Spark Streaming has not started.",
    }
    path.write_text(json.dumps(payload, indent=2) + "\n", encoding="utf-8")


def load_and_snapshot(project_root: Path) -> tuple[list[CdcCheckResult], bool, str]:
    """Run CDC in the only valid order: validate -> seed Postgres -> register Debezium -> verify Kafka snapshots."""
    run_id = _run_id("cdc")
    results, ready = cdc_preflight(project_root)
    if not ready:
        _write_report(project_root, results, False, run_id)
        return results, False, run_id

    topic_result = ensure_kafka_topics(project_root)
    results.append(_result(topic_result.status, "Kafka CDC topic contract", topic_result.detail))
    if topic_result.status != "PASS":
        _write_report(project_root, results, False, run_id)
        return results, False, run_id

    for action in (_seed_database, _register_connectors, _wait_for_connector_tasks, _verify_snapshot_topics):
        result = action(project_root)
        results.append(result)
        if result.status != "PASS":
            _write_report(project_root, results, False, run_id)
            return results, False, run_id

    passed = all(result.status == "PASS" for result in results)
    _write_report(project_root, results, passed, run_id)
    if passed:
        _write_state(project_root, run_id)
    return results, passed, run_id



def apply_controlled_mutations(project_root: Path) -> CdcCheckResult:
    """Apply one idempotent CDC demonstration after the initial Debezium snapshot.

    The source seed files remain clean. These changes happen only in PostgreSQL so
    Debezium can prove update and delete propagation through Kafka.
    """
    state_path = project_root / "runtime" / "controlled_mutations.json"
    if state_path.is_file():
        try:
            prior = json.loads(state_path.read_text(encoding="utf-8"))
            if prior.get("status") == "PASSED":
                return _result("PASS", "Controlled CDC mutations", "already applied; no database changes were repeated")
        except json.JSONDecodeError:
            # A malformed local state file is safe to replace after the database check below.
            pass

    try:
        connection = _postgres_connection(project_root)
        try:
            with connection.cursor() as cursor:
                # Update an existing seeded user after the snapshot so Debezium emits op='u'.
                cursor.execute(
                    "SELECT user_id FROM public.users WHERE membership_type <> 'premium' ORDER BY user_id LIMIT 1"
                )
                user_row = cursor.fetchone()
                if user_row is None:
                    raise RuntimeError("No seeded user is available for the controlled membership update")
                updated_user_id = str(user_row[0])
                cursor.execute(
                    "UPDATE public.users SET membership_type = 'premium', updated_at = NOW() WHERE user_id = %s",
                    (updated_user_id,),
                )

                # Update an existing order; normal order history uses status changes, never physical deletes.
                cursor.execute(
                    "SELECT order_id FROM public.orders WHERE order_status = 'shipped' ORDER BY order_id LIMIT 1"
                )
                order_row = cursor.fetchone()
                if order_row is None:
                    raise RuntimeError("No seeded shipped order is available for the controlled order update")
                updated_order_id = str(order_row[0])
                cursor.execute(
                    "UPDATE public.orders SET order_status = 'delivered', updated_at = NOW() WHERE order_id = %s",
                    (updated_order_id,),
                )

                # A temporary user has no orders. Inserting then deleting it proves the Debezium delete path
                # without breaking any historical order relationship.
                deleted_user_id = "USR999999"
                cursor.execute("SELECT 1 FROM public.users WHERE user_id = %s", (deleted_user_id,))
                if cursor.fetchone() is None:
                    cursor.execute(
                        """
                        INSERT INTO public.users (
                            user_id, email, first_name, last_name, membership_type,
                            account_status, country_code, city, created_at, updated_at
                        ) VALUES (%s, %s, %s, %s, %s, %s, %s, %s, NOW(), NOW())
                        """,
                        (
                            deleted_user_id,
                            "deleted.demo.user@example.test",
                            "Delete",
                            "Demo",
                            "standard",
                            "active",
                            "US",
                            "New York",
                        ),
                    )
                cursor.execute("DELETE FROM public.users WHERE user_id = %s", (deleted_user_id,))
            connection.commit()
        finally:
            connection.close()

        payload = {
            "status": "PASSED",
            "applied_at_utc": _utc_now(),
            "updated_user_id": updated_user_id,
            "updated_order_id": updated_order_id,
            "deleted_user_id": deleted_user_id,
            "note": "Controlled mutations were applied after the Debezium snapshot to demonstrate CDC update and delete events.",
        }
        state_path.parent.mkdir(parents=True, exist_ok=True)
        state_path.write_text(json.dumps(payload, indent=2) + "\n", encoding="utf-8")
        return _result(
            "PASS",
            "Controlled CDC mutations",
            f"updated user={updated_user_id}, updated order={updated_order_id}, deleted temporary user={deleted_user_id}",
        )
    except Exception as error:
        return _result("FAIL", "Controlled CDC mutations", _safe_error(error))

def verify_cdc_snapshot(project_root: Path) -> tuple[list[CdcCheckResult], bool, str]:
    """Re-read PostgreSQL, connector status, and Kafka snapshot topics without creating records."""
    run_id = _run_id("cdc_verify")
    results, ready = cdc_preflight(project_root)
    if not ready:
        _write_report(project_root, results, False, run_id)
        return results, False, run_id

    for action in (_seed_database, _wait_for_connector_tasks, _verify_snapshot_topics):
        result = action(project_root)
        # _seed_database is idempotent: it confirms matching rows and never reinserts when already loaded.
        results.append(result)
        if result.status != "PASS":
            _write_report(project_root, results, False, run_id)
            return results, False, run_id

    passed = all(result.status == "PASS" for result in results)
    _write_report(project_root, results, passed, run_id)
    return results, passed, run_id
