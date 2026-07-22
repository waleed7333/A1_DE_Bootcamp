"""Environment and project-foundation checks."""

from __future__ import annotations

import platform
import shutil
import subprocess
import sys
from dataclasses import dataclass
from pathlib import Path

from platform_core.config import load_settings, read_dotenv

PLACEHOLDER_MARKERS = ("CHANGE_ME", "REPLACE_ME", "YOUR_", "<", ">")


@dataclass(frozen=True)
class CheckResult:
    """One displayed result from the doctor command."""

    status: str
    name: str
    detail: str


def _command_output(command: list[str]) -> tuple[bool, str]:
    """Run a small host command and return a stable success/message pair."""
    try:
        result = subprocess.run(
            command,
            text=True,
            capture_output=True,
            check=False,
            timeout=20,
        )
    except (OSError, subprocess.TimeoutExpired) as error:
        return False, str(error)

    output = (result.stdout or result.stderr).strip().replace("\n", " ")
    return result.returncode == 0, output


def _is_placeholder(value: str | None) -> bool:
    """Return true for empty or clearly unconfigured environment values."""
    if value is None or not value.strip():
        return True
    normalized = value.strip().upper()
    return any(marker in normalized for marker in PLACEHOLDER_MARKERS)


def _memory_to_mb(value: str) -> int:
    """Convert compact Docker memory values such as 600MB or 3.5GB to MB."""
    raw = value.strip().upper()
    if raw.endswith("GB"):
        return int(float(raw[:-2]) * 1024)
    if raw.endswith("MB"):
        return int(float(raw[:-2]))
    raise ValueError(f"Unsupported memory format: {value}")


def _check_python() -> CheckResult:
    """Require a modern Python runtime for host commands and generators."""
    minimum = (3, 11)
    current = sys.version_info[:3]
    if current >= minimum:
        return CheckResult("PASS", "Python version", f"{platform.python_version()} (minimum: 3.11)")
    return CheckResult(
        "FAIL", "Python version", f"{platform.python_version()} is below the 3.11 minimum"
    )


def _check_file(project_root: Path, relative_path: str, required: bool = True) -> CheckResult:
    """Check that a required foundation file is present."""
    exists = (project_root / relative_path).exists()
    if exists:
        return CheckResult("PASS", relative_path, "Found")
    status = "FAIL" if required else "WARN"
    message = "Missing" if required else "Not created yet; expected in a later stage"
    return CheckResult(status, relative_path, message)


def _check_directories(project_root: Path, settings: dict) -> list[CheckResult]:
    """Verify that all standard runtime directories already exist."""
    results: list[CheckResult] = []
    for label, relative_path in settings["paths"].items():
        # These two paths are files and are checked separately.
        if label in {"geoip_database", "product_catalog"}:
            continue
        path = project_root / relative_path
        if path.is_dir():
            results.append(CheckResult("PASS", f"Directory: {relative_path}", "Ready"))
        else:
            results.append(CheckResult("FAIL", f"Directory: {relative_path}", "Missing"))
    return results


def _check_single_spark(settings: dict) -> CheckResult:
    """Validate that the documented memory plan contains exactly one Spark engine."""
    memory = settings.get("container_memory", {})
    spark_entries = [name for name in memory if "spark" in name]
    if spark_entries == ["spark_engine"]:
        return CheckResult("PASS", "Spark topology", "One spark-engine container is configured")
    return CheckResult(
        "FAIL", "Spark topology", f"Expected only spark_engine, found: {spark_entries}"
    )


def _check_kafka_topology(settings: dict) -> CheckResult:
    """Validate the fixed Kafka resilience requirement before any runtime starts."""
    kafka = settings.get("kafka", {})
    okay = (
        kafka.get("partitions") == 3
        and kafka.get("replication_factor") == 3
        and kafka.get("min_insync_replicas") == 2
    )
    if okay:
        return CheckResult("PASS", "Kafka topology", "3 partitions, RF=3, min ISR=2")
    return CheckResult(
        "FAIL",
        "Kafka topology",
        "Expected partitions=3, replication_factor=3, min_insync_replicas=2",
    )


def _check_reference_assets(project_root: Path, settings: dict, strict: bool) -> list[CheckResult]:
    """Check reference assets without pretending they have been generated yet."""
    results: list[CheckResult] = []
    paths = settings["paths"]
    catalog = project_root / paths["product_catalog"]
    geoip = project_root / paths["geoip_database"]

    catalog_status = "PASS" if catalog.is_file() else ("FAIL" if strict else "WARN")
    catalog_detail = (
        "Found" if catalog.is_file() else "Created once in Source Generation, then remains static"
    )
    results.append(CheckResult(catalog_status, "Reference product catalog", catalog_detail))

    geoip_status = "PASS" if geoip.is_file() else ("FAIL" if strict else "WARN")
    geoip_detail = (
        "Found" if geoip.is_file() else "Place GeoLite2-City.mmdb in data/reference before init"
    )
    results.append(CheckResult(geoip_status, "GeoLite2 database", geoip_detail))
    return results


def _check_env(env_values: dict[str, str], strict: bool) -> list[CheckResult]:
    """Report configuration status without ever printing secret values."""
    results: list[CheckResult] = []
    required_keys = [
        "POSTGRES_PASSWORD",
        "MINIO_ROOT_PASSWORD",
        "CLICKHOUSE_PASSWORD",
        "CALENDARIFIC_API_KEY",
        "GEOIP_DATABASE_PATH",
    ]
    for key in required_keys:
        configured = not _is_placeholder(env_values.get(key))
        status = "PASS" if configured else ("FAIL" if strict else "WARN")
        detail = "Configured" if configured else "Set a non-placeholder value in .env"
        results.append(CheckResult(status, f"Environment variable: {key}", detail))
    return results


def _check_docker(settings: dict, offline: bool) -> list[CheckResult]:
    """Verify Docker only when the command runs on the user's actual machine."""
    if offline:
        return [CheckResult("WARN", "Docker checks", "Skipped by --offline")]

    results: list[CheckResult] = []
    if shutil.which("docker") is None:
        return [CheckResult("FAIL", "Docker CLI", "docker command was not found on PATH")]

    ok, output = _command_output(["docker", "--version"])
    results.append(
        CheckResult("PASS" if ok else "FAIL", "Docker CLI", output or "Unable to read version")
    )

    ok, output = _command_output(["docker", "compose", "version"])
    results.append(
        CheckResult(
            "PASS" if ok else "FAIL", "Docker Compose", output or "Compose plugin is unavailable"
        )
    )

    ok, output = _command_output(["docker", "info", "--format", "{{.MemTotal}}"])
    if not ok:
        results.append(
            CheckResult("FAIL", "Docker daemon", output or "Docker daemon is not reachable")
        )
        return results

    try:
        memory_bytes = int(output)
        memory_gib = memory_bytes / (1024**3)
        required_mb = _memory_to_mb(settings["container_memory"]["recommended_docker_memory"])
        required_gib = required_mb / 1024
        status = "PASS" if memory_gib >= required_gib else "FAIL"
        detail = (
            f"{memory_gib:.1f} GiB available; low-memory project profile requires at least "
            f"{required_gib:.1f} GiB"
        )
    except ValueError:
        status = "WARN"
        detail = f"Daemon reachable, but memory could not be parsed: {output}"
    results.append(CheckResult(status, "Docker daemon memory", detail))
    return results


def run_doctor(
    project_root: Path, *, strict: bool, offline: bool
) -> tuple[list[CheckResult], bool]:
    """Run environment checks and return results plus an overall pass flag."""
    results: list[CheckResult] = [_check_python()]

    foundation_files = [
        "docker-compose.yml",
        "Dockerfile.spark",
        "Dockerfile.airflow",
        "requirements.txt",
        "config/settings.yaml",
        "config/filebeat.yml",
        "config/spark-defaults.conf",
        ".env",
    ]
    results.extend(_check_file(project_root, item) for item in foundation_files)

    try:
        settings = load_settings(project_root)
    except (OSError, ValueError) as error:
        results.append(CheckResult("FAIL", "Configuration parsing", str(error)))
        return results, False

    results.extend(_check_directories(project_root, settings))
    results.append(_check_single_spark(settings))
    results.append(_check_kafka_topology(settings))
    results.extend(_check_reference_assets(project_root, settings, strict))

    env_values = read_dotenv(project_root / ".env")
    results.extend(_check_env(env_values, strict))
    results.extend(_check_docker(settings, offline))

    passed = all(result.status != "FAIL" for result in results)
    return results, passed
