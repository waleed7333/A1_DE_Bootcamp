"""Low-memory orchestration helpers for the one Spark runner.

Airflow schedules the same refresh sequence. This module runs the sequence once
from `python main.py init` so the first serving snapshot exists immediately.
"""

from __future__ import annotations

import json
import time
from dataclasses import dataclass, asdict
from datetime import UTC, datetime
from pathlib import Path
from typing import Any


JOBS = ("user_scd2", "weather_enrichment", "holiday_enrichment", "validate_lakehouse", "publish_serving")


@dataclass(frozen=True)
class RefreshResult:
    """One result from the initial analytics refresh sequence."""

    status: str
    job: str
    detail: str


def _run_id() -> str:
    return f"initial_refresh_{datetime.now(UTC).strftime('%Y%m%dT%H%M%SZ')}"


def _write_json(path: Path, payload: dict[str, Any]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    temporary = path.with_suffix(path.suffix + ".tmp")
    temporary.write_text(json.dumps(payload, indent=2, sort_keys=True) + "\n", encoding="utf-8")
    temporary.replace(path)


def run_analytics_refresh(project_root: Path, timeout_seconds: int = 1500) -> tuple[list[RefreshResult], bool, str]:
    """Submit the approved refresh jobs to the existing Spark runner in sequence."""
    run_id = _run_id()
    root = project_root / "runtime" / "airflow_requests"
    pending = root / "pending"
    results_dir = root / "results"
    pending.mkdir(parents=True, exist_ok=True)
    results: list[RefreshResult] = []
    deadline = time.monotonic() + timeout_seconds

    for job in JOBS:
        request_id = f"{run_id}_{job}"
        request_path = pending / f"{request_id}.json"
        _write_json(request_path, {"request_id": request_id, "run_id": request_id, "job": job, "requested_by": "initialization", "dag_id": "analytics_refresh"})
        result_path = results_dir / f"{request_id}.json"
        while time.monotonic() < deadline:
            if result_path.is_file():
                payload = json.loads(result_path.read_text(encoding="utf-8"))
                if payload.get("status") == "PASSED":
                    results.append(RefreshResult("PASS", job, f"Spark runner completed {job}"))
                    break
                detail = str(payload.get("error") or payload.get("log_path") or "Spark runner reported failure")
                results.append(RefreshResult("FAIL", job, detail))
                _write_report(project_root, results, False, run_id)
                return results, False, run_id
            time.sleep(2)
        else:
            results.append(RefreshResult("FAIL", job, f"Timed out waiting for {job}"))
            _write_report(project_root, results, False, run_id)
            return results, False, run_id

    _write_report(project_root, results, True, run_id)
    return results, True, run_id


def _write_report(project_root: Path, results: list[RefreshResult], passed: bool, run_id: str) -> None:
    """Persist a small non-secret report consumed by the Operations Console."""
    _write_json(
        project_root / "reports" / "analytics_refresh_report.json",
        {"run_id": run_id, "status": "PASSED" if passed else "FAILED", "finished_at_utc": datetime.now(UTC).isoformat(), "results": [asdict(item) for item in results]},
    )
