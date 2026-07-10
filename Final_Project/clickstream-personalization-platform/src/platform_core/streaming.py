"""Small host-side controller for the single Spark Structured Streaming job.

The controller deliberately does only three things:
1. Publish the mixed Clickstream source file once, using a durable local cursor.
2. Start or stop the one Spark streaming process inside spark-engine.
3. Read the streaming heartbeat written by the Spark job.

All validation, filtering, deduplication, watermarking, Raw writes, Clean writes and
Quarantine writes remain inside ``spark_jobs/streaming_ingestion.py``.
"""

from __future__ import annotations

import json
import os
import signal
import subprocess
import sys
import time
from dataclasses import asdict, dataclass
from datetime import UTC, datetime
from pathlib import Path
from typing import Any

from .compose import run_compose
from .config import load_settings

TOPIC_TO_SOURCE = {
    "clickstream-events": "clickstream",
    "webserver-logs": "web_logs",
    "users-cdc": "users_cdc",
    "orders-cdc": "orders_cdc",
    "order-items-cdc": "order_items_cdc",
}


@dataclass(frozen=True)
class StreamingCheck:
    """One concise result shown by the command line and Operations Console."""

    status: str
    check: str
    detail: str


def _now() -> str:
    return datetime.now(UTC).isoformat()


def _run_id() -> str:
    return f"streaming_{datetime.now(UTC).strftime('%Y%m%dT%H%M%SZ')}"


def _read_json(path: Path) -> dict[str, Any] | None:
    try:
        value = json.loads(path.read_text(encoding="utf-8"))
        return value if isinstance(value, dict) else None
    except (OSError, json.JSONDecodeError):
        return None


def _write_json(path: Path, value: dict[str, Any]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(value, indent=2) + "\n", encoding="utf-8")


def _status_path(project_root: Path) -> Path:
    settings = load_settings(project_root)
    return project_root / settings["streaming"]["status_file"]


def _cursor_path(project_root: Path) -> Path:
    settings = load_settings(project_root)
    return project_root / settings["streaming"]["source_publisher_state"] / "clickstream_cursor.json"


def _clickstream_path(project_root: Path) -> Path:
    settings = load_settings(project_root)
    return project_root / settings["source_contract"]["clickstream"]["source_file"]


def _spark_process_running(project_root: Path) -> bool:
    """Return true only when the Spark query itself is running.

    The bracket pattern prevents pgrep from matching the command that is
    performing the check.
    """
    ok, _ = run_compose(
        project_root,
        [
            "exec",
            "-T",
            "spark-engine",
            "bash",
            "-lc",
            "pgrep -f '[s]treaming_ingestion.py' >/dev/null",
        ],
        timeout=20,
    )
    return ok


def _publish_clickstream(project_root: Path) -> StreamingCheck:
    """Publish every pending source line and advance the cursor only after Kafka confirms delivery."""
    source = _clickstream_path(project_root)
    if not source.exists():
        return StreamingCheck("FAIL", "Clickstream publisher", f"Missing source file: {source}")

    cursor_path = _cursor_path(project_root)
    cursor = _read_json(cursor_path) or {"next_line": 0}
    start_at = int(cursor.get("next_line", 0) or 0)

    lines = source.read_text(encoding="utf-8").splitlines()
    if start_at >= len(lines):
        return StreamingCheck(
            "PASS",
            "Clickstream publisher",
            f"No new records; cursor is at line {start_at}",
        )

    try:
        from confluent_kafka import Producer
    except ImportError:
        return StreamingCheck(
            "FAIL",
            "Clickstream publisher",
            "Python dependencies are missing. Run: pip install -r requirements.txt",
        )

    settings = load_settings(project_root)
    producer = Producer(
        {
            "bootstrap.servers": settings["runtime"]["host"]["kafka_bootstrap_servers"]
        }
    )
    topic = settings["kafka"]["topics"]["clickstream"]
    delivery_errors: list[str] = []

    def on_delivery(error: Any, _message: Any) -> None:
        if error is not None:
            delivery_errors.append(str(error))

    try:
        for line in lines[start_at:]:
            while True:
                try:
                    producer.produce(
                        topic,
                        value=line.encode("utf-8"),
                        on_delivery=on_delivery,
                    )
                    break
                except BufferError:
                    producer.poll(1)

            producer.poll(0)

        undelivered = producer.flush(30)

        if undelivered:
            return StreamingCheck(
                "FAIL",
                "Clickstream publisher",
                f"Kafka still has {undelivered} undelivered record(s)",
            )

        if delivery_errors:
            return StreamingCheck(
                "FAIL",
                "Clickstream publisher",
                f"Kafka delivery failed: {delivery_errors[0]}",
            )

        _write_json(
            cursor_path,
            {
                "next_line": len(lines),
                "updated_at_utc": _now(),
            },
        )

        return StreamingCheck(
            "PASS",
            "Clickstream publisher",
            f"Published {len(lines) - start_at} raw source line(s) to {topic}",
        )

    except Exception as error:
        return StreamingCheck(
            "FAIL",
            "Clickstream publisher",
            f"{type(error).__name__}: {error}",
        )

def _start_spark(project_root: Path, run_id: str) -> StreamingCheck:
    """Start one background streaming query in the existing Spark container."""
    if _spark_process_running(project_root):
        return StreamingCheck("PASS", "Spark streaming process", "Already running")

    command = (
        "mkdir -p /opt/project/runtime/logs && "
        "nohup spark-submit /opt/project/spark_jobs/streaming_ingestion.py "
        f"--run-id {run_id} "
        "> /opt/project/runtime/logs/streaming_ingestion.log 2>&1 &"
    )
    ok, output = run_compose(
        project_root,
        ["exec", "-T", "spark-engine", "bash", "-lc", command],
        timeout=30,
    )
    if not ok:
        return StreamingCheck("FAIL", "Spark streaming process", output[-500:] or "spark-submit could not start")
    return StreamingCheck("PASS", "Spark streaming process", f"Started run {run_id}")


def _wait_for_heartbeat(
    project_root: Path,
    timeout_seconds: int,
) -> StreamingCheck:
    """Confirm that Spark started without requiring the full first batch to finish."""
    deadline = time.monotonic() + timeout_seconds
    path = _status_path(project_root)
    last_state = "missing"

    while time.monotonic() < deadline:
        status = _read_json(path) or {}
        state = str(status.get("status", "")).upper()

        if state:
            last_state = state

        if state == "RUNNING":
            return StreamingCheck(
                "PASS",
                "Spark heartbeat",
                f"Run {status.get('run_id', 'unknown')} completed a micro-batch",
            )

        if state == "STARTING" and _spark_process_running(project_root):
            return StreamingCheck(
                "PASS",
                "Spark heartbeat",
                "Spark started and is processing its initial micro-batch",
            )

        if state == "FAILED":
            return StreamingCheck(
                "FAIL",
                "Spark heartbeat",
                str(status.get("error", "streaming failed")),
            )

        time.sleep(3)

    return StreamingCheck(
        "FAIL",
        "Spark heartbeat",
        f"Spark did not start within {timeout_seconds} seconds; last status={last_state}",
    )

def _live_generator_pid_path(project_root: Path) -> Path:
    return project_root / "runtime" / "source_publishers" / "live_generator.pid"


def _pid_is_running(pid_path: Path) -> bool:
    try:
        pid = int(pid_path.read_text(encoding="utf-8").strip())
        os.kill(pid, 0)
        return True
    except (OSError, ValueError):
        pid_path.unlink(missing_ok=True)
        return False


def _start_live_generator(project_root: Path) -> StreamingCheck:
    """Start one very small host process that appends valid live source records."""
    pid_path = _live_generator_pid_path(project_root)

    if _pid_is_running(pid_path):
        return StreamingCheck("PASS", "Live source generator", "Already running")

    settings = load_settings(project_root)
    interval = int(
        settings["streaming"].get("live_generation_interval_seconds", 20)
    )

    environment = os.environ.copy()
    source_path = str(project_root / "src")
    environment["PYTHONPATH"] = (
        source_path + os.pathsep + environment.get("PYTHONPATH", "")
    )

    log_path = project_root / "runtime" / "logs" / "live_source_generator.log"
    log_path.parent.mkdir(parents=True, exist_ok=True)

    command = [
        sys.executable,
        "-m",
        "platform_core.live_source_generator",
        "--project-root",
        str(project_root),
        "--interval-seconds",
        str(interval),
    ]

    with log_path.open("a", encoding="utf-8") as log_handle:
        process = subprocess.Popen(
            command,
            cwd=str(project_root),
            env=environment,
            stdout=log_handle,
            stderr=subprocess.STDOUT,
            start_new_session=True,
        )

    pid_path.parent.mkdir(parents=True, exist_ok=True)
    pid_path.write_text(f"{process.pid}\n", encoding="utf-8")

    return StreamingCheck(
        "PASS",
        "Live source generator",
        f"Started with a {interval}-second interval",
    )


def _stop_live_generator(project_root: Path) -> StreamingCheck:
    pid_path = _live_generator_pid_path(project_root)

    if not _pid_is_running(pid_path):
        return StreamingCheck("PASS", "Live source generator", "Already stopped")

    try:
        pid = int(pid_path.read_text(encoding="utf-8").strip())
        os.kill(pid, signal.SIGTERM)
        pid_path.unlink(missing_ok=True)

        return StreamingCheck("PASS", "Live source generator", "Stopped")

    except (OSError, ValueError) as error:
        return StreamingCheck(
            "FAIL",
            "Live source generator",
            f"{type(error).__name__}: {error}",
        )


def wait_for_initial_sources(
    project_root: Path,
    timeout_seconds: int = 600,
) -> StreamingCheck:
    """Wait until Spark has processed every approved source at least once."""
    required_sources = set(TOPIC_TO_SOURCE.values())
    deadline = time.monotonic() + timeout_seconds
    status_path = _status_path(project_root)

    while time.monotonic() < deadline:
        status = _read_json(status_path) or {}
        state = str(status.get("status", "")).upper()

        if state == "FAILED":
            return StreamingCheck(
                "FAIL",
                "Initial streaming load",
                str(status.get("error", "Spark streaming failed")),
            )

        processed = status.get("processed_source_records", {}) or {}

        missing = sorted(
            source
            for source in required_sources
            if int(processed.get(source, 0) or 0) == 0
        )

        if state == "RUNNING" and not missing:
            return StreamingCheck(
                "PASS",
                "Initial streaming load",
                "All approved source types completed Spark processing",
            )

        if state in {"STARTING", "RUNNING"} and not _spark_process_running(project_root):
            return StreamingCheck(
                "FAIL",
                "Initial streaming load",
                "Spark process stopped before the initial load completed",
            )

        time.sleep(3)

    return StreamingCheck(
        "FAIL",
        "Initial streaming load",
        "Timed out before Spark processed all sources",
    )

def start_streaming(
    project_root: Path,
    timeout_seconds: int = 120,
) -> tuple[list[StreamingCheck], bool, str]:
    """Publish pending source lines, start Spark, then start low-cost live generation."""
    run_id = _run_id()

    checks = [
        _publish_clickstream(project_root),
        _start_spark(project_root, run_id),
    ]

    if all(check.status == "PASS" for check in checks):
        checks.append(_wait_for_heartbeat(project_root, timeout_seconds))

    if all(check.status == "PASS" for check in checks):
        checks.append(_start_live_generator(project_root))

    passed = all(check.status == "PASS" for check in checks)

    report = {
        "run_id": run_id,
        "status": "PASSED" if passed else "FAILED",
        "checked_at_utc": _now(),
        "results": [asdict(check) for check in checks],
    }

    _write_json(project_root / "reports" / "streaming_start_report.json", report)

    return checks, passed, run_id


def verify_streaming(project_root: Path) -> tuple[list[StreamingCheck], bool, str]:
    """Read evidence only; this function never republishes or changes project data."""
    status = _read_json(_status_path(project_root)) or {}
    checks: list[StreamingCheck] = []
    if str(status.get("status", "")).upper() == "RUNNING":
        checks.append(StreamingCheck("PASS", "Spark streaming status", f"Last batch: {status.get('last_micro_batch_id', 'not recorded')}"))
    else:
        checks.append(StreamingCheck("FAIL", "Spark streaming status", str(status.get("error", "No running heartbeat"))))
    checks.append(StreamingCheck("PASS" if _spark_process_running(project_root) else "FAIL", "Spark process", "streaming_ingestion.py detected" if _spark_process_running(project_root) else "No streaming process detected"))
    passed = all(check.status == "PASS" for check in checks)
    return checks, passed, str(status.get("run_id", "unknown"))


def stop_streaming(project_root: Path) -> tuple[list[StreamingCheck], bool]:
    """Stop live generation and the Spark query while preserving data and checkpoints."""
    live_check = _stop_live_generator(project_root)

    ok, output = run_compose(
        project_root,
        [
            "exec",
            "-T",
            "spark-engine",
            "bash",
            "-lc",
            "pkill -f '[s]treaming_ingestion.py' || true",
        ],
        timeout=30,
    )

    status = _read_json(_status_path(project_root)) or {}
    status.update(
        {
            "status": "STOPPED",
            "stopped_at_utc": _now(),
        }
    )
    _write_json(_status_path(project_root), status)

    detail = (
        "Stopped streaming process"
        if ok
        else output[-400:] or "Unable to stop streaming process"
    )

    spark_check = StreamingCheck(
        "PASS" if ok else "FAIL",
        "Spark streaming stop",
        detail,
    )

    checks = [live_check, spark_check]

    return checks, all(check.status == "PASS" for check in checks)


def start_operational_streaming(project_root: Path, timeout_seconds: int = 120) -> tuple[list[StreamingCheck], bool, str]:
    """Compatibility alias used by the simplified platform workflow."""
    return start_streaming(project_root, timeout_seconds)
