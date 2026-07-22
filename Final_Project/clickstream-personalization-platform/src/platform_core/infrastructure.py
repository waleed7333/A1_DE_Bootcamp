"""Operational checks and commands for Infrastructure infrastructure."""

from __future__ import annotations

import json
import time
from dataclasses import asdict, dataclass
from datetime import UTC, datetime
from pathlib import Path
from typing import Any

import requests
import yaml

from platform_core.compose import run_compose, run_docker
from platform_core.config import load_settings, read_dotenv
from platform_core.environment import PLACEHOLDER_MARKERS


@dataclass(frozen=True)
class InfraCheckResult:
    """One check result written both to screen and the Infrastructure JSON report."""

    status: str
    check: str
    detail: str


EXPECTED_CONTAINERS = {
    "postgres": "clickstream-postgres",
    "zookeeper": "clickstream-zookeeper",
    "kafka1": "clickstream-kafka1",
    "kafka2": "clickstream-kafka2",
    "kafka3": "clickstream-kafka3",
    "kafka-ui": "clickstream-kafka-ui",
    "debezium-connect": "clickstream-debezium-connect",
    "minio": "clickstream-minio",
    "filebeat": "clickstream-filebeat",
    "spark-engine": "clickstream-spark-engine",
    "airflow": "clickstream-airflow",
    "clickhouse": "clickstream-clickhouse",
}

# The Streamlit Operations Console is part of the completed platform, but later
# infrastructure verification remains valid when the optional UI is intentionally stopped.
OPTIONAL_OPERATIONAL_CONTAINERS = {
    "observability-ui": "clickstream-observability-ui",
}

INFRASTRUCTURE_SECRET_KEYS = (
    "POSTGRES_PASSWORD",
    "MINIO_ROOT_PASSWORD",
    "CLICKHOUSE_PASSWORD",
)

HOST_PORT_KEYS = (
    "POSTGRES_PORT",
    "KAFKA1_HOST_PORT",
    "KAFKA2_HOST_PORT",
    "KAFKA3_HOST_PORT",
    "KAFKA_UI_PORT",
    "DEBEZIUM_PORT",
    "MINIO_PORT",
    "MINIO_CONSOLE_PORT",
    "AIRFLOW_PORT",
    "CLICKHOUSE_HTTP_PORT",
    "CLICKHOUSE_NATIVE_PORT",
)


def _is_placeholder(value: str | None) -> bool:
    """Return true only for missing or explicitly unfinished development values."""
    if value is None or not value.strip():
        return True
    normalized = value.strip().upper()
    return any(marker in normalized for marker in PLACEHOLDER_MARKERS)


def _check_result(status: str, check: str, detail: str) -> InfraCheckResult:
    """Create a result consistently so console and JSON always match."""
    return InfraCheckResult(status=status, check=check, detail=detail)


def _write_report(project_root: Path, results: list[InfraCheckResult], passed: bool) -> None:
    """Persist a non-secret Infrastructure report for troubleshooting and presentation evidence."""
    report_path = project_root / "reports" / "infrastructure_report.json"
    payload: dict[str, Any] = {
        "contract_version": 1,
        "checked_at_utc": datetime.now(UTC).isoformat(),
        "status": "PASSED" if passed else "FAILED",
        "results": [asdict(result) for result in results],
    }
    report_path.write_text(json.dumps(payload, indent=2) + "\n", encoding="utf-8")


def _inspect_container(container_name: str) -> tuple[str, str]:
    """Return Docker runtime and health state without depending on Compose JSON formats."""
    command = [
        "inspect",
        "--format",
        "{{.State.Status}}|{{if .State.Health}}{{.State.Health.Status}}{{else}}none{{end}}",
        container_name,
    ]
    ok, detail = run_docker(command)
    if not ok:
        return "missing", detail or "Container was not found"
    runtime, _, health = detail.partition("|")
    return runtime.strip(), health.strip() or "none"


def _container_results() -> list[InfraCheckResult]:
    """Check that each agreed infrastructure container exists and has not exited."""
    results: list[InfraCheckResult] = []
    for service, container_name in EXPECTED_CONTAINERS.items():
        runtime, health = _inspect_container(container_name)
        if runtime != "running":
            results.append(
                _check_result("FAIL", f"Container: {service}", f"state={runtime}; {health}")
            )
            continue
        if health == "unhealthy":
            results.append(
                _check_result(
                    "FAIL", f"Container: {service}", "Docker healthcheck reports unhealthy"
                )
            )
            continue
        detail = "running" if health == "none" else f"running; health={health}"
        results.append(_check_result("PASS", f"Container: {service}", detail))
    return results


def _optional_operational_container_results() -> list[InfraCheckResult]:
    """Report the optional Streamlit Operations Console without blocking infrastructure checks."""
    results: list[InfraCheckResult] = []
    for service, container_name in OPTIONAL_OPERATIONAL_CONTAINERS.items():
        runtime, health = _inspect_container(container_name)
        if runtime in {"missing", "created", "exited"}:
            results.append(
                _check_result(
                    "SKIP", f"Container: {service}", "Optional Operations Console is not started"
                )
            )
        elif runtime != "running":
            results.append(
                _check_result("WARN", f"Container: {service}", f"state={runtime}; {health}")
            )
        elif health == "unhealthy":
            results.append(
                _check_result(
                    "WARN",
                    f"Container: {service}",
                    "Optional Operations Console healthcheck is unhealthy",
                )
            )
        else:
            detail = "running" if health == "none" else f"running; health={health}"
            results.append(_check_result("PASS", f"Container: {service}", detail))
    return results


def _http_get(url: str, *, timeout: int = 5, **kwargs: Any) -> tuple[bool, str]:
    """Perform a small HTTP readiness probe without exposing secrets in any output."""
    try:
        response = requests.get(url, timeout=timeout, **kwargs)
    except requests.RequestException as error:
        return False, str(error)
    return response.ok, f"HTTP {response.status_code}"


def _check_postgres(env_values: dict[str, str]) -> InfraCheckResult:
    """Open a real PostgreSQL connection from the host, not merely a container ping."""
    try:
        import psycopg2

        connection = psycopg2.connect(
            host="localhost",
            port=int(env_values["POSTGRES_PORT"]),
            dbname=env_values["POSTGRES_DB"],
            user=env_values["POSTGRES_USER"],
            password=env_values["POSTGRES_PASSWORD"],
            connect_timeout=5,
        )
        with connection.cursor() as cursor:
            cursor.execute("SELECT 1")
            cursor.fetchone()
        connection.close()
        return _check_result("PASS", "PostgreSQL query", "Connected and executed SELECT 1")
    except Exception as error:  # psycopg2's exception tree is intentionally broad here.
        return _check_result("FAIL", "PostgreSQL query", str(error).split("\n", 1)[0])


def _check_kafka(settings: dict) -> InfraCheckResult:
    """Read broker metadata from the host and prove all three brokers joined the cluster."""
    bootstrap = settings["runtime"]["host"]["kafka_bootstrap_servers"]
    try:
        from confluent_kafka.admin import AdminClient

        metadata = AdminClient(
            {"bootstrap.servers": bootstrap, "socket.timeout.ms": 5000}
        ).list_topics(timeout=8)
        broker_ids = sorted(metadata.brokers)
        if len(broker_ids) == 3:
            return _check_result("PASS", "Kafka cluster", f"3 brokers reachable: {broker_ids}")
        return _check_result(
            "FAIL", "Kafka cluster", f"Expected 3 brokers, found {len(broker_ids)}: {broker_ids}"
        )
    except Exception as error:
        return _check_result("FAIL", "Kafka cluster", str(error).split("\n", 1)[0])


def _check_kafka_ui(env_values: dict[str, str]) -> InfraCheckResult:
    """Verify the UI process responds after it has connected to the Kafka cluster."""
    ok, detail = _http_get(f"http://localhost:{env_values['KAFKA_UI_PORT']}/actuator/health")
    return _check_result("PASS" if ok else "FAIL", "Kafka UI HTTP", detail)


def _check_debezium(env_values: dict[str, str]) -> InfraCheckResult:
    """Verify the Kafka Connect REST endpoint is ready before any connector is registered."""
    ok, detail = _http_get(f"http://localhost:{env_values['DEBEZIUM_PORT']}/connectors")
    return _check_result("PASS" if ok else "FAIL", "Debezium Connect REST", detail)


def _check_minio(env_values: dict[str, str]) -> InfraCheckResult:
    """Verify MinIO's official liveness endpoint is reachable from the host."""
    ok, detail = _http_get(f"http://localhost:{env_values['MINIO_PORT']}/minio/health/live")
    return _check_result("PASS" if ok else "FAIL", "MinIO health", detail)


def _check_spark(project_root: Path) -> InfraCheckResult:
    """Run Spark's own version command in the only Spark container."""
    ok, detail = run_compose(
        project_root,
        ["exec", "-T", "spark-engine", "bash", "-lc", "spark-submit --version"],
        timeout=30,
    )
    normalized = detail.replace("\n", " ")
    if ok and "3.5.0" in normalized:
        return _check_result(
            "PASS", "Spark engine", "spark-submit 3.5.0 is executable in spark-engine"
        )
    return _check_result(
        "FAIL", "Spark engine", normalized[-300:] or "spark-submit did not succeed"
    )


def _check_airflow(env_values: dict[str, str], project_root: Path) -> InfraCheckResult:
    """Require Airflow's published health endpoint and its component states to be healthy."""
    url = f"http://localhost:{env_values['AIRFLOW_PORT']}/api/v2/monitor/health"
    try:
        response = requests.get(url, timeout=8)
    except requests.RequestException as error:
        response = None
        detail = str(error)
    else:
        detail = f"HTTP {response.status_code}"

    if response is not None and response.ok:
        try:
            payload = response.json()
        except ValueError:
            payload = {}
        unhealthy = [
            name
            for name, value in payload.items()
            if isinstance(value, dict) and value.get("status") not in {"healthy", None}
        ]
        if not unhealthy:
            return _check_result(
                "PASS", "Airflow health", "HTTP 200; reported components are healthy"
            )
        return _check_result(
            "FAIL", "Airflow health", f"HTTP 200 but unhealthy components: {unhealthy}"
        )

    command_ok, command_detail = run_compose(
        project_root,
        ["exec", "-T", "airflow", "bash", "-lc", "airflow version"],
        timeout=30,
    )
    if command_ok:
        return _check_result(
            "FAIL", "Airflow health", "API is still initializing; airflow CLI is reachable"
        )
    return _check_result(
        "FAIL", "Airflow health", f"{detail}; CLI fallback: {command_detail[-180:]}"
    )


def _check_clickhouse(env_values: dict[str, str]) -> InfraCheckResult:
    """Execute a real authenticated ClickHouse query using the project credentials."""
    url = f"http://localhost:{env_values['CLICKHOUSE_HTTP_PORT']}"
    try:
        response = requests.post(
            url,
            params={"query": "SELECT 1"},
            auth=(env_values["CLICKHOUSE_USER"], env_values["CLICKHOUSE_PASSWORD"]),
            timeout=8,
        )
    except requests.RequestException as error:
        return _check_result("FAIL", "ClickHouse query", str(error))

    if response.ok and response.text.strip() == "1":
        return _check_result("PASS", "ClickHouse query", "Authenticated SELECT 1 returned 1")
    return _check_result("FAIL", "ClickHouse query", f"HTTP {response.status_code}")


def infrastructure_preflight(project_root: Path) -> tuple[list[InfraCheckResult], bool]:
    """Check only requirements needed to safely launch the Infrastructure containers."""
    results: list[InfraCheckResult] = []
    env_values = read_dotenv(project_root / ".env")

    for key in INFRASTRUCTURE_SECRET_KEYS:
        if _is_placeholder(env_values.get(key)):
            results.append(
                _check_result(
                    "FAIL",
                    f"Required local secret: {key}",
                    "Run: python main.py configure-dev-secrets",
                )
            )
        else:
            results.append(_check_result("PASS", f"Required local secret: {key}", "Configured"))

    used_ports: dict[str, str] = {}
    for key in HOST_PORT_KEYS:
        value = env_values.get(key, "").strip()
        if not value.isdigit():
            results.append(
                _check_result(
                    "FAIL", f"Host port: {key}", f"Invalid or missing value: {value or '<empty>'}"
                )
            )
            continue
        if value in used_ports:
            results.append(
                _check_result(
                    "FAIL",
                    "Host port uniqueness",
                    f"{key} and {used_ports[value]} both use {value}",
                )
            )
        else:
            used_ports[value] = key
            results.append(_check_result("PASS", f"Host port: {key}", value))

    compose_path = project_root / "docker-compose.yml"
    try:
        compose = yaml.safe_load(compose_path.read_text(encoding="utf-8"))
        service_names = list(compose["services"])
        allowed = set(EXPECTED_CONTAINERS) | set(OPTIONAL_OPERATIONAL_CONTAINERS)
        missing = sorted(set(EXPECTED_CONTAINERS) - set(service_names))
        unexpected = sorted(set(service_names) - allowed)
        init_services = sorted(name for name in service_names if "init" in name.lower())
        spark_services = [name for name in service_names if "spark" in name]
        if missing:
            results.append(
                _check_result(
                    "FAIL", "Compose service contract", f"Missing core services: {missing}"
                )
            )
        elif unexpected:
            results.append(
                _check_result(
                    "FAIL", "Compose service contract", f"Unexpected services: {unexpected}"
                )
            )
        elif init_services:
            results.append(
                _check_result(
                    "FAIL",
                    "Compose service contract",
                    f"Init services are forbidden: {init_services}",
                )
            )
        elif spark_services != ["spark-engine"]:
            results.append(
                _check_result(
                    "FAIL",
                    "Compose service contract",
                    f"Expected one spark-engine, found {spark_services}",
                )
            )
        else:
            results.append(
                _check_result(
                    "PASS",
                    "Compose service contract",
                    "12 core services plus one optional Operations Console; no init services; one Spark container",
                )
            )
    except Exception as error:
        results.append(_check_result("FAIL", "Compose service contract", str(error)))

    compose_ok, compose_detail = run_compose(project_root, ["config", "--quiet"], timeout=30)
    if compose_ok:
        results.append(
            _check_result(
                "PASS", "Docker Compose syntax", "docker compose config --quiet succeeded"
            )
        )
    else:
        results.append(
            _check_result(
                "FAIL",
                "Docker Compose syntax",
                compose_detail[-400:] or "docker compose config failed",
            )
        )

    passed = all(result.status != "FAIL" for result in results)
    return results, passed


def run_infrastructure_check(project_root: Path) -> tuple[list[InfraCheckResult], bool]:
    """Run deterministic runtime checks and save a non-secret report."""
    settings = load_settings(project_root)
    env_values = read_dotenv(project_root / ".env")
    results = _container_results()
    results.extend(_optional_operational_container_results())

    # Functional checks still run even if one container fails so the final report is useful.
    results.extend(
        [
            _check_postgres(env_values),
            _check_kafka(settings),
            _check_kafka_ui(env_values),
            _check_debezium(env_values),
            _check_minio(env_values),
            _check_spark(project_root),
            _check_airflow(env_values, project_root),
            _check_clickhouse(env_values),
        ]
    )

    # Optional operational services may be intentionally stopped during maintenance work.
    passed = all(result.status != "FAIL" for result in results)
    _write_report(project_root, results, passed)
    return results, passed


def infra_up(project_root: Path, timeout_seconds: int) -> tuple[list[InfraCheckResult], bool]:
    """Build/start the project then poll until all infrastructure checks are truly green."""
    preflight_results, preflight_ok = infrastructure_preflight(project_root)
    if not preflight_ok:
        _write_report(project_root, preflight_results, False)
        return preflight_results, False

    started, detail = run_compose(
        project_root, ["up", "-d", "--build", "--remove-orphans"], stream_output=True
    )
    if not started:
        result = _check_result(
            "FAIL", "docker compose up", detail or "Docker Compose returned a non-zero status"
        )
        _write_report(project_root, [result], False)
        return [result], False

    deadline = time.monotonic() + timeout_seconds
    last_results: list[InfraCheckResult] = []
    while time.monotonic() < deadline:
        last_results, passed = run_infrastructure_check(project_root)
        if passed:
            return last_results, True
        failed_checks = ", ".join(
            result.check for result in last_results if result.status == "FAIL"
        )
        print(f"Infrastructure is still initializing: {failed_checks}")
        time.sleep(5)

    return last_results, False


def infra_down(project_root: Path) -> tuple[list[InfraCheckResult], bool]:
    """Stop containers without deleting local ClickHouse data or Docker named volumes."""
    ok, detail = run_compose(project_root, ["down", "--remove-orphans"], stream_output=True)
    result = _check_result(
        "PASS" if ok else "FAIL",
        "docker compose down",
        (
            "Containers stopped; named volumes and data/clickhouse were preserved"
            if ok
            else detail[-400:]
        ),
    )
    return [result], ok
