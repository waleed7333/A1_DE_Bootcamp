"""Single low-memory Airflow DAG for the project refresh cycle.

Airflow schedules and monitors the work. The only Spark container receives small
request files and runs one approved Spark job at a time.
"""

from __future__ import annotations

import json
import time
from datetime import timedelta
from pathlib import Path

import pendulum
from airflow.sdk import dag, task

REQUEST_ROOT = Path("/opt/project/runtime/airflow_requests")
PENDING = REQUEST_ROOT / "pending"
RESULTS = REQUEST_ROOT / "results"
JOBS = (
    "user_scd2",
    "weather_enrichment",
    "holiday_enrichment",
    "validate_lakehouse",
    "publish_serving",
)


def safe_id(value: str) -> str:
    """Keep request file names safe and deterministic."""
    return "".join(char if char.isalnum() or char in "_-" else "_" for char in value)[:180]


@dag(
    dag_id="analytics_refresh",
    description="Incremental SCD2, enrichment, validation, and versioned serving publication.",
    schedule="0 * * * *",
    start_date=pendulum.datetime(2026, 1, 1, tz="UTC"),
    catchup=False,
    max_active_runs=1,
    default_args={"retries": 1, "retry_delay": timedelta(minutes=3)},
    tags=["clickstream", "analytics", "low-memory"],
)
def analytics_refresh():
    @task
    def submit(job: str, run_marker: str) -> str:
        """Write one approved Spark request for the single Spark runner."""
        request_id = safe_id(f"{run_marker}_{job}")
        PENDING.mkdir(parents=True, exist_ok=True)
        request = {
            "request_id": request_id,
            "run_id": request_id,
            "job": job,
            "requested_by": "airflow",
            "dag_id": "analytics_refresh",
        }
        target = PENDING / f"{request_id}.json"
        temporary = target.with_suffix(".json.tmp")
        temporary.write_text(json.dumps(request, indent=2) + "\n", encoding="utf-8")
        temporary.replace(target)
        return request_id

    @task(execution_timeout=timedelta(minutes=12))
    def wait_for_result(request_id: str) -> str:
        """Wait for the Spark runner and fail the DAG when a job fails."""
        result_path = RESULTS / f"{request_id}.json"
        deadline = time.monotonic() + 660
        while time.monotonic() < deadline:
            if result_path.is_file():
                payload = json.loads(result_path.read_text(encoding="utf-8"))
                if payload.get("status") == "PASSED":
                    return request_id
                raise RuntimeError(payload.get("error") or "Spark job failed")
            time.sleep(2)
        raise RuntimeError(f"Timed out waiting for {request_id}")

    previous: str | None = None
    for job in JOBS:
        marker = "scheduled"
        request_id = submit.override(task_id=f"submit_{job}")(job, marker)
        if previous is not None:
            previous >> request_id
        completed = wait_for_result.override(task_id=f"wait_for_{job}")(request_id)
        previous = completed


analytics_refresh()
