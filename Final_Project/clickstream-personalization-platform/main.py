#!/usr/bin/env python3
"""Simple command line interface for the Clickstream Personalization Platform.

Normal use intentionally has only five commands:
    init, start, status, stop, reset --confirm

The command line keeps the operator workflow simple while the supporting modules
perform ingestion, streaming, batch refresh, validation, and serving publication.
"""

from __future__ import annotations

import argparse
import json
import os
import secrets
import shutil
import string
import sys
import textwrap
import threading
import time
import subprocess
from dataclasses import dataclass
from pathlib import Path
from typing import Any, Callable, TypeVar

PROJECT_ROOT = Path(__file__).resolve().parent
sys.path.insert(0, str(PROJECT_ROOT / "src"))

from platform_core.cdc import ( apply_controlled_mutations, load_and_snapshot, )  # noqa: E402
from platform_core.compose import run_compose  # noqa: E402
from platform_core.config import load_settings, read_dotenv  # noqa: E402
from platform_core.environment import run_doctor  # noqa: E402
from platform_core.initializer import initialize_platform  # noqa: E402
from platform_core.operations import ( collect_status, start_platform, stop_health_collector, )# noqa: E402
from platform_core.orchestration import run_analytics_refresh  # noqa: E402
from platform_core.source_generation import LocalSourceGenerator  # noqa: E402
from platform_core.streaming import (   stop_streaming, wait_for_initial_sources, )# noqa: E402

T = TypeVar("T")

@dataclass(frozen=True)
class CliResult:
    """A small result object for command-line-only actions."""

    status: str
    check: str
    detail: str


# Main visual separators used by the CLI output.
# Keep these centralized so the terminal style can be changed from one place.
TERMINAL_WIDTH = 104
SECTION_LINE = "─" * TERMINAL_WIDTH
TABLE_BORDER = "═" * TERMINAL_WIDTH
TABLE_HEADER_LINE = "─" * TERMINAL_WIDTH
BETWEEN_TABLES_LINE = "◆" + ("─" * (TERMINAL_WIDTH - 2)) + "◆"


class StageProgress:
    """Show clean stage progress and truthful overall workflow progress."""

    _FRAMES = ("|", "/", "-", "\\")

    def __init__(self, step: int, total: int, title: str) -> None:
        self.step = step
        self.total = total
        self.title = title
        self.started_at = 0.0
        self._stop_event = threading.Event()
        self._thread: threading.Thread | None = None
        self._frame_index = 0

    def _overall_percentage(self, completed: bool) -> int:
        """Return progress across the full workflow, not the current stage only."""
        completed_steps = self.step if completed else self.step - 1
        return round((completed_steps / self.total) * 100)

    def _line(self, *, completed: bool, message: str) -> str:
        width = 20
        elapsed = int(time.monotonic() - self.started_at) if self.started_at else 0
        overall_percentage = self._overall_percentage(completed)

        if completed:
            marker = "✓" if message == "PASSED" else "✗"
            bar = "#" * width
            stage_status = "STAGE 100%"
            step_status = f"STEP {self.step}/{self.total} {message}"
        else:
            marker = self._FRAMES[self._frame_index]
            position = self._frame_index % width
            bar = "." * position + ">" + "." * (width - position - 1)
            stage_status = "STAGE RUNNING"
            step_status = f"STEP {self.step}/{self.total} RUNNING"

        return (
            f"\r{marker} [{bar}] {stage_status:<13} "
            f"| OVERALL {overall_percentage:>3}% "
            f"| {step_status:<18} "
            f"| {self.title:<28} "
            f"| {message:<10} "
            f"| {elapsed:>3}s"
        )

    def _animate(self) -> None:
        while not self._stop_event.is_set():
            print(
                self._line(completed=False, message="Running"),
                end="",
                flush=True,
            )
            self._frame_index = (self._frame_index + 1) % len(self._FRAMES)
            time.sleep(0.2)

    def start(self) -> None:
        self.started_at = time.monotonic()
        self._thread = threading.Thread(
            target=self._animate,
            daemon=True,
        )
        self._thread.start()

    def finish(self, passed: bool) -> None:
        self._stop_event.set()

        if self._thread is not None:
            self._thread.join(timeout=1)

        message = "PASSED" if passed else "FAILED"

        print(self._line(completed=True, message=message))
        #print(SECTION_LINE)
        print()


def _run_stage( step: int, total: int, title: str, action: Callable[[], T], is_successful: Callable[[T], bool], ) -> T:
    """Run one stage with live terminal progress and a final truthful status."""
    if step == 1:
        print()
    progress = StageProgress(step, total, title)
    progress.start()

    try:
        result = action()
    except Exception:
        progress.finish(False)
        raise

    progress.finish(is_successful(result))
    return result


def _result_parts(item: Any) -> tuple[str, str, str]:
    """Read result objects and dictionaries through one display contract."""
    if isinstance(item, dict):
        status = str(item.get("status", "UNKNOWN"))
        name = str(
            item.get(
                "check",
                item.get("component", item.get("job", item.get("name", "check"))),
            )
        )
        detail = str(item.get("detail", item.get("error", "")))
        return status, name, detail

    status = str(getattr(item, "status", "UNKNOWN"))
    name = str(
        getattr(
            item,
            "check",
            getattr(
                item,
                "component",
                getattr(item, "job", getattr(item, "name", "check")),
            ),
        )
    )
    detail = str(getattr(item, "detail", getattr(item, "error", "")))

    return status, name, detail


def _print_results(title: str, results: list[Any], passed: bool) -> None:
    """Print a clearly separated result table."""
    summary = "PASSED" if passed else "FAILED"

    print(TABLE_BORDER)
    print(f"{title}  [{summary}]")
    print(TABLE_BORDER)
    print(f"{'STATUS':<8} {'CHECK':<34} DETAILS")
    print(TABLE_HEADER_LINE)

    for item in results:
        status, name, detail = _result_parts(item)
        wrapped_detail = textwrap.wrap(detail, width=58) or [""]

        print(f"{status:<8} {name:<34} {wrapped_detail[0]}")

        for line in wrapped_detail[1:]:
            print(f"{'':<8} {'':<34} {line}")

    print(TABLE_BORDER)
    print(BETWEEN_TABLES_LINE)
    print()

def _ensure_directories() -> None:
    """Create only folders needed by the final project layout."""
    folders = [
        "config",
        "data/reference",
        "data/source/clickstream",
        "data/source/web_logs",
        "data/source/postgres",
        "data/minio/data",
        "data/clickhouse",
        "runtime/checkpoints",
        "runtime/observability",
        "runtime/source_publishers",
        "runtime/logs",
        "reports",
        "docs",
    ]

    for folder in folders:
        (PROJECT_ROOT / folder).mkdir(parents=True, exist_ok=True)

def _remove_path(path: Path) -> None:
    """Remove one dynamic file or directory and fail loudly if it remains."""
    if not path.exists():
        return

    if path.is_dir() and not path.is_symlink():
        shutil.rmtree(path)
    else:
        path.unlink()

    if path.exists():
        raise RuntimeError(f"Could not remove dynamic path: {path}")

def _placeholder(value: str | None) -> bool:
    return not value or any(
        token in value.upper()
        for token in ("CHANGE_ME", "REPLACE_ME", "YOUR_", "<", ">")
    )


def _random_password() -> str:
    alphabet = string.ascii_letters + string.digits
    return "dev_" + "".join(secrets.choice(alphabet) for _ in range(28))


def _prepare_env() -> tuple[bool, str]:
    """Create .env once and generate safe local passwords when placeholders remain."""
    env_path = PROJECT_ROOT / ".env"
    example_path = PROJECT_ROOT / ".env.example"

    if not env_path.exists():
        shutil.copyfile(example_path, env_path)

    values = read_dotenv(env_path)
    lines = env_path.read_text(encoding="utf-8").splitlines()
    updates: dict[str, str] = {}

    for key in ("POSTGRES_PASSWORD", "MINIO_ROOT_PASSWORD", "CLICKHOUSE_PASSWORD"):
        if _placeholder(values.get(key)):
            updates[key] = _random_password()

    if updates:
        new_lines: list[str] = []

        for line in lines:
            key = line.split("=", 1)[0] if "=" in line else ""
            new_lines.append(f"{key}={updates[key]}" if key in updates else line)

        env_path.write_text("\n".join(new_lines) + "\n", encoding="utf-8")

    values = read_dotenv(env_path)

    if _placeholder(values.get("CALENDARIFIC_API_KEY")):
        return False, "Set CALENDARIFIC_API_KEY in .env before running init."

    geoip_path = values.get("GEOIP_DATABASE_PATH", "")

    if _placeholder(geoip_path) or not Path(geoip_path).exists():
        return (
            False,
            "Set GEOIP_DATABASE_PATH in .env to an existing GeoLite2-City.mmdb file before running init.",
        )

    return True, ".env is ready"


def _read_json(path: Path) -> dict[str, Any]:
    try:
        payload = json.loads(path.read_text(encoding="utf-8"))
        return payload if isinstance(payload, dict) else {}
    except (OSError, json.JSONDecodeError):
        return {}


def _streaming_report() -> tuple[list[Any], bool]:
    """Read the streaming evidence written by the streaming controller."""
    report = _read_json(PROJECT_ROOT / "reports" / "streaming_start_report.json")
    results = report.get("results", [])
    passed = str(report.get("status", "")).upper() == "PASSED"

    if not results:
        results = [
            CliResult(
                "FAIL",
                "Streaming start report",
                "The report was not created. Read runtime/logs/streaming_ingestion.log.",
            )
        ]
        passed = False

    return results, passed


def _infrastructure_results(snapshot: dict[str, Any]) -> list[Any]:
    """Hide expected pipeline warnings before Streaming and Validation are started."""
    expected_later = {
        "Spark streaming",
        "Latest validation",
        "Active serving build",
    }

    return [
        item
        for item in snapshot.get("checks", [])
        if str(item.get("component", "")) not in expected_later
    ]


def _print_validation_diagnostics() -> None:
    """Show the actual validation reason instead of a generic Spark exit code."""
    report = _read_json(PROJECT_ROOT / "reports" / "validation_latest.json")

    if not report:
        _print_results(
            "VALIDATION FAILURE DETAILS",
            [
                CliResult(
                    "FAIL",
                    "Validation report",
                    "validation_latest.json was not created. Inspect the validate_lakehouse log path shown above.",
                )
            ],
            False,
        )
        return

    details = report.get("details", {})
    rows: list[Any] = [
        CliResult(
            str(report.get("status", "FAILED")),
            "Validation status",
            "Lakehouse validation result",
        ),
        CliResult(
            str(report.get("quality_status", "UNKNOWN")),
            "Source reconciliation",
            "Raw, Clean, and Quarantine counts",
        ),
        CliResult(
            str(report.get("relationship_status", "UNKNOWN")),
            "Relationship integrity",
            "Orders, products, and request correlation",
        ),
        CliResult(
            str(report.get("scd2_status", "UNKNOWN")),
            "SCD Type 2 integrity",
            "User history validation",
        ),
        CliResult(
            str(report.get("coverage_status", "UNKNOWN")),
            "Enrichment coverage",
            "Weather and holiday coverage status",
        ),
    ]

    if report.get("error"):
        rows.append(
            CliResult(
                "FAIL",
                "Validation error",
                str(report["error"]),
            )
        )

    scd2 = details.get("scd2", {}) if isinstance(details, dict) else {}

    if isinstance(scd2, dict):
        rows.append(
            CliResult(
                "INFO",
                "SCD2 counts",
                (
                    f"users={scd2.get('users', 'n/a')}, "
                    f"current_rows={scd2.get('current_rows', 'n/a')}, "
                    f"duplicate_current={scd2.get('duplicate_current', 'n/a')}, "
                    f"invalid_ranges={scd2.get('invalid_ranges', 'n/a')}"
                ),
            )
        )

    _print_results("VALIDATION FAILURE DETAILS", rows, False)


def _wait_for_health_collector_to_stop(timeout_seconds: int = 6) -> None:
    """Avoid a local collector recreating runtime files during reset."""
    pid_path = PROJECT_ROOT / "runtime" / "health_collector.pid"
    deadline = time.monotonic() + timeout_seconds

    while time.monotonic() < deadline:
        try:
            pid = int(pid_path.read_text(encoding="utf-8").strip())
            os.kill(pid, 0)
        except (OSError, ValueError):
            return

        time.sleep(0.2)


def _mark_streaming_stopped() -> None:
    """Make status output truthful after Docker Compose stops spark-engine."""
    settings = load_settings(PROJECT_ROOT)
    status_path = PROJECT_ROOT / settings["streaming"]["status_file"]
    payload = _read_json(status_path)

    payload["status"] = "STOPPED"
    payload["stopped_at_utc"] = time.strftime( "%Y-%m-%dT%H:%M:%SZ", time.gmtime(), )

    status_path.parent.mkdir(parents=True, exist_ok=True)
    status_path.write_text( json.dumps(payload, indent=2) + "\n", encoding="utf-8", )


def command_init() -> int:
    """Build the project once from a clean state and publish its first serving snapshot."""
    total_steps = 9
    _ensure_directories()

    ready, message = _prepare_env()

    if not ready:
        print(f"INIT FAILED: {message}")
        return 2

    print("\nEnvironment file ready.")

    doctor_results, doctor_ok = _run_stage(
        1,
        total_steps,
        "Environment check",
        lambda: run_doctor(PROJECT_ROOT, strict=True, offline=False),
        lambda result: result[1],
    )

    _print_results("ENVIRONMENT CHECK", doctor_results, doctor_ok)

    if not doctor_ok:
        return 2

    source_results, source_ok = _run_stage(
        2,
        total_steps,
        "Source generation",
        lambda: LocalSourceGenerator(PROJECT_ROOT).generate(),
        lambda result: result[1],
    )

    _print_results("SOURCE GENERATION", source_results, source_ok)

    if not source_ok:
        return 2

    infrastructure_snapshot, infrastructure_ok = _run_stage(
        3,
        total_steps,
        "Infrastructure startup",
        lambda: start_platform(
            PROJECT_ROOT,
            timeout_seconds=360,
            start_streaming_job=False,
        ),
        lambda result: result[1],
    )

    _print_results(
        "INFRASTRUCTURE STARTUP",
        _infrastructure_results(infrastructure_snapshot),
        infrastructure_ok,
    )

    if not infrastructure_ok:
        print("Read runtime/observability/latest.json for infrastructure details.")
        return 2

    init_results, init_ok, _ = _run_stage(
        4,
        total_steps,
        "Lakehouse initialization",
        lambda: initialize_platform(PROJECT_ROOT),
        lambda result: result[1],
    )

    _print_results("LAKEHOUSE INITIALIZATION", init_results, init_ok)

    if not init_ok:
        return 2

    cdc_results, cdc_ok, _ = _run_stage(
        5,
        total_steps,
        "PostgreSQL and CDC",
        lambda: load_and_snapshot(PROJECT_ROOT),
        lambda result: result[1],
    )

    _print_results("POSTGRESQL AND CDC INITIALIZATION", cdc_results, cdc_ok)

    if not cdc_ok:
        return 2

    _, start_call_ok = _run_stage(
        6,
        total_steps,
        "Streaming startup",
        lambda: start_platform(PROJECT_ROOT, timeout_seconds=300),
        lambda result: result[1],
    )

    streaming_results, streaming_ok = _streaming_report()
    streaming_ok = start_call_ok and streaming_ok

    _print_results("STREAMING START", streaming_results, streaming_ok)

    if not streaming_ok:
        print(
            "Read runtime/streaming_status.json and runtime/logs/streaming_ingestion.log."
        )
        return 2

    mutation_result = _run_stage(
        7,
        total_steps,
        "Controlled CDC mutations",
        lambda: apply_controlled_mutations(PROJECT_ROOT),
        lambda result: getattr(result, "status", "FAIL") == "PASS",
    )

    mutation_ok = getattr(mutation_result, "status", "FAIL") == "PASS"

    _print_results(
        "CONTROLLED CDC MUTATIONS",
        [mutation_result],
        mutation_ok,
    )

    if not mutation_ok:
        return 2

    initial_load = _run_stage(
        8,
        total_steps,
        "Initial streaming load",
        lambda: wait_for_initial_sources(PROJECT_ROOT, timeout_seconds=600),
        lambda result: getattr(result, "status", "FAIL") == "PASS",
    )

    initial_load_ok = getattr(initial_load, "status", "FAIL") == "PASS"

    _print_results( "STREAMING INITIAL LOAD", [initial_load], initial_load_ok, )

    if not initial_load_ok:
        return 2

    refresh_results, refresh_ok, refresh_run_id = _run_stage(
        9,
        total_steps,
        "Analytics refresh",
        lambda: run_analytics_refresh(PROJECT_ROOT, timeout_seconds=1800),
        lambda result: result[1],
    )

    _print_results("ANALYTICS REFRESH", refresh_results, refresh_ok)
    print(f"Refresh run: {refresh_run_id}")

    if not refresh_ok:
        _print_validation_diagnostics()
        return 2

    snapshot, status_ok = collect_status(PROJECT_ROOT, persist=True)

    print("\nINIT COMPLETE")
    print("=" * 104)
    print(f"Platform status: {snapshot.get('overall_status', 'UNKNOWN')}")
    print(
        "Streaming remains active. New clickstream, web-log, and PostgreSQL CDC "
        "records will continue to be processed."
    )
    print(
        "Open the Operations Console and confirm the latest validation "
        "and serving build are PASSED."
    )
    print("=" * 104)

    return 0 if status_ok else 2


def command_start() -> int:
    """Start existing containers and continue from preserved state."""
    _ensure_directories()

    if not (PROJECT_ROOT / ".env").exists():
        print("START FAILED: .env is missing. Run: python main.py init")
        return 2

    snapshot, start_ok = _run_stage(
        1,
        1,
        "Starting existing platform",
        lambda: start_platform(PROJECT_ROOT, timeout_seconds=300),
        lambda result: result[1],
    )

    streaming_results, streaming_ok = _streaming_report()
    overall_ok = start_ok and streaming_ok

    _print_results("STREAMING START", streaming_results, overall_ok)
    print(f"Platform status: {snapshot.get('overall_status', 'UNKNOWN')}")

    if overall_ok:
        print(
            "Existing data and checkpoints were preserved. Streaming is active again."
        )

    return 0 if overall_ok else 2


def command_status() -> int:
    """Show the concise operational and data-evidence status."""
    snapshot, _ = collect_status(PROJECT_ROOT, persist=True)
    print(json.dumps(snapshot, indent=2))
    return 0


def command_stop() -> int:
    """Stop containers without removing containers, networks, volumes, or project data."""
    _ensure_directories()

    stop_health_collector(PROJECT_ROOT)
    _wait_for_health_collector_to_stop()

    streaming_results, streaming_ok = _run_stage(
        1,
        2,
        "Stopping streaming",
        lambda: stop_streaming(PROJECT_ROOT),
        lambda result: result[1],
    )

    ok, output = _run_stage(
        2,
        2,
        "Stopping platform",
        lambda: run_compose(PROJECT_ROOT, ["stop"], timeout=120),
        lambda result: result[0],
    )

    _mark_streaming_stopped()

    results = list(streaming_results) + [
        CliResult(
            "PASS" if ok else "FAIL",
            "Docker Compose",
            (
                "Containers stopped and preserved"
                if ok
                else (output[-700:] or "docker compose stop failed")
            ),
        )
    ]

    stop_ok = streaming_ok and ok
    _print_results("PLATFORM STOP", results, stop_ok)

    return 0 if stop_ok else 2

def _make_local_state_writable() -> None:
    """Make Docker-created local files removable by the current host user.

    Some bind-mounted files are created by container users, especially MinIO
    metadata files such as xl.meta. A normal chmod from the host user may fail
    because the host user does not own those files. This function first tries a
    best-effort host chmod, then uses a temporary Docker container running as root
    to chown/chmod the local dynamic folders.
    """
    targets = [
        PROJECT_ROOT / "data" / "minio",
        PROJECT_ROOT / "data" / "clickhouse",
        PROJECT_ROOT / "runtime",
        PROJECT_ROOT / "reports",
        PROJECT_ROOT / "data" / "source",
    ]

    existing_targets = [path for path in targets if path.exists()]

    if not existing_targets:
        return

    # Best-effort host-side chmod. This works for files already owned by the
    # current user and is harmless for files owned by Docker users.
    for path in existing_targets:
        try:
            if path.is_dir():
                for root, dirs, files in os.walk(path):
                    for name in dirs:
                        try:
                            os.chmod(Path(root) / name, 0o700)
                        except OSError:
                            pass

                    for name in files:
                        try:
                            os.chmod(Path(root) / name, 0o600)
                        except OSError:
                            pass

                os.chmod(path, 0o700)
            else:
                os.chmod(path, 0o600)

        except OSError:
            pass

    # Docker-side permission repair. This is the important part for MinIO and
    # ClickHouse bind-mounted files created by container users.
    uid = os.getuid() if hasattr(os, "getuid") else 1000
    gid = os.getgid() if hasattr(os, "getgid") else 1000

    container_targets = [
        f"/project/{path.relative_to(PROJECT_ROOT).as_posix()}"
        for path in existing_targets
    ]

    target_list = " ".join(f'"{path}"' for path in container_targets)

    permission_script = f"""
set -eu

for path in {target_list}; do
    if [ -e "$path" ]; then
        chown -R {uid}:{gid} "$path" 2>/dev/null || true
        chmod -R u+rwX "$path" 2>/dev/null || true
    fi
done
"""

    # Use the already-installed ClickHouse image as a small root helper.
    # This avoids requiring sudo and avoids pulling a new image.
    subprocess.run(
        [ "docker", "run", "--rm", "--user", "0:0", "-v", f"{PROJECT_ROOT}:/project", "--entrypoint", "/bin/sh", "clickhouse/clickhouse-server:24.8.14.39", "-c", permission_script, ],
        cwd=PROJECT_ROOT,
        stdout=subprocess.DEVNULL,
        stderr=subprocess.DEVNULL,
        check=False,
    )
def command_reset() -> int:
    """Return the project to a clean first-run state."""
    _ensure_directories()

    stop_health_collector(PROJECT_ROOT)
    _wait_for_health_collector_to_stop()
    stop_streaming(PROJECT_ROOT)

    docker_ok, docker_output = _run_stage(
        1,
        2,
        "Removing Docker state",
        lambda: run_compose(
            PROJECT_ROOT,
            ["down", "-v", "--remove-orphans"],
            timeout=180,
        ),
        lambda result: result[0],
    )

    cleanup_paths = [
        "data/source/clickstream",
        "data/source/web_logs",
        "data/source/postgres",
        "data/source/generation_manifest.json",
        "data/minio/data",
        "data/clickhouse/data",
        "data/clickhouse/log",
        "runtime",
        "reports",
    ]

    def remove_local_state() -> tuple[bool, str]:
        try:
            _make_local_state_writable()

            for relative in cleanup_paths:
                _remove_path(PROJECT_ROOT / relative)

            _ensure_directories()

            storage_paths = [
                PROJECT_ROOT / "data/minio/data",
                PROJECT_ROOT / "data/clickhouse/data",
                PROJECT_ROOT / "data/clickhouse/log",
            ]

            non_empty = [ str(path.relative_to(PROJECT_ROOT)) for path in storage_paths if path.exists() and any(path.iterdir()) ]

            if non_empty: return ( False, "Reset finished but these storage folders are not empty: " + ", ".join(non_empty), )

            return ( True, "All dynamic local data was removed; storage folders are empty", )

        except Exception as error:
            return False, f"{type(error).__name__}: {error}"

    local_result = _run_stage( 2, 2, "Removing local state", remove_local_state, lambda result: result[0], )

    local_ok, local_detail = local_result

    results = [
        CliResult( "PASS" if docker_ok else "FAIL", "Docker state", ( "Containers and Docker volumes removed" if docker_ok else (docker_output[-700:] or "docker compose down failed") ), ),
        CliResult( "PASS" if local_ok else "FAIL", "Local dynamic state", local_detail, ),
        CliResult( "INFO", "Preserved reference data", ".env, Product Catalog, GeoLite2 database, source code, and documentation", ),
    ]

    reset_ok = docker_ok and local_ok
    _print_results("RESET", results, reset_ok)

    return 0 if reset_ok else 2


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(description="Clickstream Personalization Platform")

    sub = parser.add_subparsers(dest="command", required=True)

    sub.add_parser("init", help="Build the platform once from a clean state")
    sub.add_parser("start", help="Start the existing platform")
    sub.add_parser("status", help="Show platform health and evidence")
    sub.add_parser("stop", help="Stop containers without deleting data")

    reset = sub.add_parser("reset", help="Delete dynamic state and start again")
    reset.add_argument(
        "--confirm",
        action="store_true",
        help="Required safety confirmation",
    )

    return parser


def main() -> int:
    args = build_parser().parse_args()

    if args.command == "init":
        return command_init()

    if args.command == "start":
        return command_start()

    if args.command == "status":
        return command_status()

    if args.command == "stop":
        return command_stop()

    if args.command == "reset":
        if not args.confirm:
            print("RESET REFUSED: run exactly: python main.py reset --confirm")
            return 2

        return command_reset()

    return 2


if __name__ == "__main__":
    raise SystemExit(main())
