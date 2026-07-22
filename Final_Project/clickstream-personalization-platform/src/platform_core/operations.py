"""Lightweight project operations and evidence collector.

This module intentionally avoids Prometheus and Grafana. It collects the few signals
needed to prove that the local project is healthy and that its latest data result is
validated and published.
"""

from __future__ import annotations

import json
import os
import subprocess
import sys
import time
from dataclasses import asdict, dataclass
from datetime import UTC, datetime
from pathlib import Path
from typing import Any

import requests

from .compose import run_compose
from .config import load_settings, read_dotenv
from .streaming import start_streaming


@dataclass(frozen=True)
class OperationCheck:
    status: str
    component: str
    detail: str


CONTAINERS = {
    "postgres": "clickstream-postgres",
    "zookeeper": "clickstream-zookeeper",
    "kafka1": "clickstream-kafka1",
    "kafka2": "clickstream-kafka2",
    "kafka3": "clickstream-kafka3",
    "kafka_ui": "clickstream-kafka-ui",
    "debezium": "clickstream-debezium-connect",
    "minio": "clickstream-minio",
    "filebeat": "clickstream-filebeat",
    "spark": "clickstream-spark-engine",
    "airflow": "clickstream-airflow",
    "clickhouse": "clickstream-clickhouse",
    "operations_console": "clickstream-observability-ui",
}


def _now() -> str:
    return datetime.now(UTC).isoformat()


def _read_json(path: Path) -> dict[str, Any] | None:
    try:
        value = json.loads(path.read_text(encoding="utf-8"))
        return value if isinstance(value, dict) else None
    except (OSError, json.JSONDecodeError):
        return None


def _write_json(path: Path, value: dict[str, Any]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(value, indent=2) + "\n", encoding="utf-8")


def _inspect(container: str) -> tuple[str, str, bool]:
    command = [
        "docker",
        "inspect",
        "-f",
        "{{.State.Status}}|{{if .State.Health}}{{.State.Health.Status}}{{else}}none{{end}}|{{.State.OOMKilled}}",
        container,
    ]
    try:
        result = subprocess.run(command, capture_output=True, text=True, timeout=8, check=False)
    except OSError as error:
        return "missing", str(error), False
    if result.returncode != 0:
        return "missing", result.stderr.strip() or "container not found", False
    state, health, oom = (result.stdout.strip().split("|") + ["", ""])[:3]
    return state, health, oom.lower() == "true"


def _http(url: str) -> tuple[bool, str]:
    try:
        response = requests.get(url, timeout=4)
        return response.ok, f"HTTP {response.status_code}"
    except requests.RequestException as error:
        return False, f"{type(error).__name__}: {error}"


def _container_checks() -> list[OperationCheck]:
    checks: list[OperationCheck] = []
    for name, container in CONTAINERS.items():
        state, health, oom = _inspect(container)
        if oom:
            checks.append(OperationCheck("FAIL", name, "Container was OOMKilled"))
        elif state != "running":
            checks.append(OperationCheck("FAIL", name, f"Container state: {state}"))
        elif health not in {"healthy", "none"}:
            checks.append(OperationCheck("WARN", name, f"Health: {health}"))
        else:
            checks.append(OperationCheck("PASS", name, "Running"))
    return checks


def _service_checks(project_root: Path) -> list[OperationCheck]:
    settings = load_settings(project_root)
    env = read_dotenv(project_root / ".env")
    urls = {
        "MinIO": settings["runtime"]["host"]["minio_endpoint"] + "/minio/health/live",
        "Debezium": settings["runtime"]["host"]["debezium_url"] + "/connectors",
        "Airflow": f"http://localhost:{env.get('AIRFLOW_PORT', '8088')}/api/v2/monitor/health",
        "ClickHouse": settings["runtime"]["host"]["clickhouse_http_url"] + "/ping",
    }
    checks: list[OperationCheck] = []
    for name, url in urls.items():
        ok, detail = _http(url)
        checks.append(OperationCheck("PASS" if ok else "FAIL", name, detail))
    return checks


def _pipeline_checks(project_root: Path) -> list[OperationCheck]:
    checks: list[OperationCheck] = []

    streaming = _read_json(project_root / "runtime" / "streaming_status.json") or {}

    if str(streaming.get("status", "")).upper() == "RUNNING":
        last_batch_id = streaming.get(
            "last_successful_batch_id",
            "not recorded",
        )

        checks.append(
            OperationCheck(
                "PASS",
                "Spark streaming",
                f"Last completed batch: {last_batch_id}",
            )
        )
    else:
        checks.append(
            OperationCheck(
                "WARN",
                "Spark streaming",
                str(streaming.get("error", "Not running")),
            )
        )

    validation = _read_json(project_root / "reports" / "validation_latest.json") or {}

    validation_status = str(validation.get("status", "MISSING")).upper()

    checks.append(
        OperationCheck(
            "PASS" if validation_status == "PASSED" else "WARN",
            "Latest validation",
            validation_status,
        )
    )

    serving = _read_json(project_root / "reports" / "serving_latest.json") or {}

    serving_status = str(serving.get("status", "MISSING")).upper()
    serving_detail = str(serving.get("serving_build_id", "No active build recorded"))

    checks.append(
        OperationCheck(
            "PASS" if serving_status == "PASSED" else "WARN",
            "Active serving build",
            serving_detail,
        )
    )

    return checks


def _overall(checks: list[OperationCheck]) -> str:
    if any(check.status == "FAIL" for check in checks):
        return "UNHEALTHY"
    if any(check.status == "WARN" for check in checks):
        return "ATTENTION"
    return "HEALTHY"


def collect_status(project_root: Path, *, persist: bool = True) -> tuple[dict[str, Any], bool]:
    """Collect one compact health-and-evidence snapshot."""
    checks = _container_checks() + _service_checks(project_root) + _pipeline_checks(project_root)
    overall = _overall(checks)
    payload = {
        "captured_at_utc": _now(),
        "overall_status": overall,
        "failed_checks": sum(check.status == "FAIL" for check in checks),
        "warning_checks": sum(check.status == "WARN" for check in checks),
        "checks": [asdict(check) for check in checks],
    }
    if persist:
        latest = project_root / "runtime" / "observability" / "latest.json"
        _write_json(latest, payload)
        history = project_root / "runtime" / "observability" / "history.jsonl"
        history.parent.mkdir(parents=True, exist_ok=True)
        with history.open("a", encoding="utf-8") as handle:
            handle.write(json.dumps(payload) + "\n")
    return payload, overall != "UNHEALTHY"


def _collector_pid_path(project_root: Path) -> Path:
    return project_root / "runtime" / "health_collector.pid"


def _collector_stop_path(project_root: Path) -> Path:
    return project_root / "runtime" / "health_collector.stop"


def _collector_running(project_root: Path) -> bool:
    """Return True when the tiny host collector process is still alive."""
    pid_path = _collector_pid_path(project_root)
    try:
        pid = int(pid_path.read_text(encoding="utf-8").strip())
        os.kill(pid, 0)
        return True
    except (OSError, ValueError):
        pid_path.unlink(missing_ok=True)
        return False


def start_health_collector(project_root: Path) -> None:
    """Start one low-cost host collector without creating another Docker service."""
    if _collector_running(project_root):
        return
    stop_path = _collector_stop_path(project_root)
    stop_path.unlink(missing_ok=True)
    environment = os.environ.copy()
    source_path = str(project_root / "src")
    environment["PYTHONPATH"] = source_path + os.pathsep + environment.get("PYTHONPATH", "")
    command = [
        sys.executable,
        "-m",
        "platform_core.health_collector",
        "--project-root",
        str(project_root),
        "--interval-seconds",
        "20",
    ]
    log_path = project_root / "runtime" / "logs" / "health_collector.log"
    log_path.parent.mkdir(parents=True, exist_ok=True)
    with log_path.open("a", encoding="utf-8") as log_handle:
        subprocess.Popen(
            command,
            cwd=str(project_root),
            env=environment,
            stdout=log_handle,
            stderr=subprocess.STDOUT,
            start_new_session=True,
        )


def stop_health_collector(project_root: Path) -> None:
    """Request a clean collector shutdown; it exits within one collection interval."""
    stop_path = _collector_stop_path(project_root)
    stop_path.parent.mkdir(parents=True, exist_ok=True)
    stop_path.write_text("stop\n", encoding="utf-8")


def _write_mode(project_root: Path, state: str) -> None:
    _write_json(
        project_root / "runtime" / "operations" / "mode.json",
        {"mode": "live", "status": state, "updated_at_utc": _now()},
    )


def start_platform(
    project_root: Path, *, timeout_seconds: int = 300, start_streaming_job: bool = True
) -> tuple[dict[str, Any], bool]:
    """Start Docker services and the single Spark streaming job from existing state."""
    _write_mode(project_root, "STARTING")
    ok, output = run_compose(
        project_root,
        ["up", "-d"],
        timeout=timeout_seconds,
    )
    if not ok:
        payload = {
            "overall_status": "UNHEALTHY",
            "error": output[-700:] or "docker compose up failed",
            "captured_at_utc": _now(),
            "checks": [],
        }
        _write_json(project_root / "runtime" / "observability" / "latest.json", payload)
        return payload, False
    # Wait only for required infrastructure readiness. Pipeline evidence may still be
    # WARN during the first initialization because no validation has run yet.
    deadline = time.monotonic() + timeout_seconds
    snapshot: dict[str, Any] = {}
    ready = False
    while time.monotonic() < deadline:
        snapshot, _ = collect_status(project_root, persist=True)
        service_failures = [
            check
            for check in snapshot.get("checks", [])
            if check.get("status") == "FAIL"
            and check.get("component")
            not in {"Spark streaming", "Latest validation", "Active serving build"}
        ]
        if not service_failures:
            ready = True
            break
        time.sleep(5)
    if not ready:
        _write_mode(project_root, "UNHEALTHY")
        return snapshot, False

    streaming_ok = True
    if start_streaming_job:
        _, streaming_ok, _ = start_streaming(
            project_root, timeout_seconds=min(timeout_seconds, 150)
        )
    start_health_collector(project_root)
    _write_mode(project_root, "RUNNING" if streaming_ok else "ATTENTION")

    final_snapshot, final_status_ok = collect_status(
        project_root,
        persist=True,
    )

    return final_snapshot, final_status_ok and streaming_ok
