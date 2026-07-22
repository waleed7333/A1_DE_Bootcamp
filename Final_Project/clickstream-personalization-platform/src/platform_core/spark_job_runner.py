"""Single-process batch-job runner hosted inside the one spark-engine container.

Airflow is only the scheduler and monitor. Every actual Spark batch is launched
by this process inside ``spark-engine`` so the project keeps exactly one Spark
container. Airflow and the runner exchange small request/result JSON files
through the project's mounted ``runtime/airflow_requests`` directory.
"""

from __future__ import annotations

import json
import os
import subprocess
import time
import traceback
from datetime import UTC, datetime
from pathlib import Path
from typing import Any

RUNTIME = Path("/opt/project/runtime")
ROOT = RUNTIME / "airflow_requests"
PENDING = ROOT / "pending"
WORKING = ROOT / "working"
RESULTS = ROOT / "results"
LOGS = ROOT / "logs"
STATUS_PATH = RUNTIME / "spark_job_runner_status.json"
POLL_SECONDS = 2

# Keep the runner deliberately narrow. Adding a new Batch pipeline requires an
# explicit job specification here rather than permitting arbitrary command input.
JOB_SPECS: dict[str, dict[str, Any]] = {
    "user_scd2": {
        "script": "/opt/project/spark_jobs/user_scd2_incremental.py",
        "timeout_seconds": 360,
    },
    "weather_enrichment": {
        "script": "/opt/project/spark_jobs/weather_enrichment.py",
        "timeout_seconds": 420,
    },
    "holiday_enrichment": {
        "script": "/opt/project/spark_jobs/holiday_enrichment.py",
        "timeout_seconds": 420,
    },
    "validate_lakehouse": {
        "script": "/opt/project/spark_jobs/validate_lakehouse.py",
        "timeout_seconds": 420,
    },
    "publish_serving": {
        "script": "/opt/project/spark_jobs/publish_clickhouse.py",
        "timeout_seconds": 600,
    },
}


def utc_now() -> str:
    """Return a portable UTC ISO timestamp for local status artifacts."""
    return datetime.now(UTC).isoformat()


def _safe_id(value: object, *, field: str) -> str:
    candidate = str(value or "").strip()
    allowed = "abcdefghijklmnopqrstuvwxyzABCDEFGHIJKLMNOPQRSTUVWXYZ0123456789_-"
    if not candidate or any(character not in allowed for character in candidate):
        raise ValueError(f"{field} may contain only letters, digits, underscore, and hyphen")
    return candidate


def write_json(path: Path, payload: dict[str, Any]) -> None:
    """Atomically publish one small runner artifact."""
    path.parent.mkdir(parents=True, exist_ok=True)
    temporary = path.with_suffix(path.suffix + ".tmp")
    temporary.write_text(json.dumps(payload, indent=2, sort_keys=True) + "\n", encoding="utf-8")
    temporary.replace(path)


def make_dirs() -> None:
    """Create request paths with cross-container development permissions."""
    for directory in (PENDING, WORKING, RESULTS, LOGS):
        directory.mkdir(parents=True, exist_ok=True)
        # Airflow and the notebook-derived Spark image have different users.
        # The request files contain no secrets and are only local orchestration
        # metadata, so mode 0777 is intentionally limited to this exchange area.
        try:
            directory.chmod(0o777)
        except OSError:
            pass


def write_heartbeat(
    *, status: str, active_request_id: str | None = None, detail: str | None = None
) -> None:
    """Write a fresh liveness signal consumed by Batch Processing preflight."""
    write_json(
        STATUS_PATH,
        {
            "service": "spark_job_runner",
            "status": status,
            "pid": os.getpid(),
            "active_request_id": active_request_id,
            "detail": detail,
            "updated_at_utc": utc_now(),
            "supported_jobs": sorted(JOB_SPECS),
        },
    )


def recover_orphaned_requests() -> int:
    """Return requests left in working after a container restart to pending.

    Spark is not running while this runner process is restarted, so moving a
    previously claimed request back to pending is safe and preserves Airflow's
    original request rather than silently dropping it.
    """
    recovered = 0
    for path in sorted(WORKING.glob("*.json")):
        destination = PENDING / path.name
        if destination.exists():
            # A newer copy has already been submitted. Preserve the old evidence
            # under results rather than overwriting either request.
            path.replace(RESULTS / f"orphaned_{path.name}")
        else:
            path.replace(destination)
        recovered += 1
    return recovered


def claim_next_request() -> Path | None:
    """Atomically claim the oldest pending request."""
    for pending_file in sorted(PENDING.glob("*.json")):
        claimed = WORKING / pending_file.name
        try:
            pending_file.replace(claimed)
            return claimed
        except FileNotFoundError:
            continue
    return None


def _result_payload(
    *,
    request_id: str,
    run_id: str | None,
    job_name: str | None,
    request: dict[str, Any],
    status: str,
    started: str,
    return_code: int | None,
    log_path: Path,
    error: str | None = None,
) -> dict[str, Any]:
    payload: dict[str, Any] = {
        "request_id": request_id,
        "run_id": run_id,
        "job": job_name,
        "requested_by": request.get("requested_by", "unknown"),
        "dag_id": request.get("dag_id"),
        "status": status,
        "started_at_utc": started,
        "finished_at_utc": utc_now(),
        "return_code": return_code,
        "log_path": str(log_path),
    }
    if error:
        payload["error"] = error
    return payload


def process_request(path: Path) -> None:
    """Run one allow-listed Spark batch and publish a durable result."""
    request: dict[str, Any] = {}
    request_id = path.stem
    run_id: str | None = None
    job_name: str | None = None
    started = utc_now()
    log_path = LOGS / f"{request_id}.log"
    try:
        request = json.loads(path.read_text(encoding="utf-8"))
        if not isinstance(request, dict):
            raise ValueError("request payload must be a JSON object")
        request_id = _safe_id(request.get("request_id", request_id), field="request_id")
        if request_id != path.stem:
            raise ValueError("request_id does not match the request filename")
        run_id = _safe_id(request.get("run_id", f"batch_{request_id}"), field="run_id")
        job_name = str(request.get("job", "")).strip()
        spec = JOB_SPECS.get(job_name)
        if spec is None:
            raise ValueError(f"unsupported batch job: {job_name}")
        script = Path(str(spec["script"]))
        if not script.is_file():
            raise FileNotFoundError(f"missing batch job script: {script}")

        write_heartbeat(
            status="RUNNING",
            active_request_id=request_id,
            detail=f"job={job_name}; run_id={run_id}",
        )
        command = [
            "/usr/local/spark/bin/spark-submit",
            "--master",
            "local[1]",
            "--driver-memory",
            "768m",
            "--conf",
            "spark.executor.memory=768m",
            "--conf",
            "spark.sql.shuffle.partitions=1",
            "--conf",
            "spark.default.parallelism=1",
            "--conf",
            "spark.sql.adaptive.enabled=false",
            "--conf",
            "spark.sql.session.timeZone=UTC",
            str(script),
            "--run-id",
            run_id,
        ]
        with log_path.open("w", encoding="utf-8") as log_handle:
            completed = subprocess.run(
                command,
                stdout=log_handle,
                stderr=subprocess.STDOUT,
                text=True,
                timeout=int(spec["timeout_seconds"]),
                check=False,
                env=os.environ.copy(),
            )
        if completed.returncode != 0:
            tail = ""
            try:
                tail = " | ".join(
                    log_path.read_text(encoding="utf-8", errors="replace").splitlines()[-12:]
                )
            except OSError:
                pass
            raise RuntimeError(
                f"Spark batch exited {completed.returncode}; see {log_path}"
                + (f"; tail={tail[-800:]}" if tail else "")
            )

        result = _result_payload(
            request_id=request_id,
            run_id=run_id,
            job_name=job_name,
            request=request,
            status="PASSED",
            started=started,
            return_code=completed.returncode,
            log_path=log_path,
        )
        write_json(RESULTS / f"{request_id}.json", result)
        write_heartbeat(status="IDLE", detail=f"last_request={request_id}; status=PASSED")
    except subprocess.TimeoutExpired:
        result = _result_payload(
            request_id=request_id,
            run_id=run_id,
            job_name=job_name,
            request=request,
            status="FAILED",
            started=started,
            return_code=None,
            log_path=log_path,
            error="Spark batch job timed out",
        )
        write_json(RESULTS / f"{request_id}.json", result)
        write_heartbeat(status="IDLE", detail=f"last_request={request_id}; status=FAILED")
    except Exception as error:  # defensive runtime boundary
        result = _result_payload(
            request_id=request_id,
            run_id=run_id,
            job_name=job_name,
            request=request,
            status="FAILED",
            started=started,
            return_code=None,
            log_path=log_path,
            error=f"{type(error).__name__}: {error}",
        )
        result["traceback"] = traceback.format_exc(limit=6)
        write_json(RESULTS / f"{request_id}.json", result)
        write_heartbeat(status="IDLE", detail=f"last_request={request_id}; status=FAILED")
    finally:
        try:
            path.unlink(missing_ok=True)
        except OSError:
            pass


def main() -> int:
    make_dirs()
    recovered = recover_orphaned_requests()
    write_heartbeat(status="IDLE", detail=f"runner started; recovered_orphaned={recovered}")
    try:
        while True:
            request_path = claim_next_request()
            if request_path is None:
                write_heartbeat(status="IDLE")
                time.sleep(POLL_SECONDS)
                continue
            process_request(request_path)
    except KeyboardInterrupt:
        write_heartbeat(status="STOPPED", detail="keyboard interrupt")
        return 0
    except Exception as error:  # pragma: no cover - container boundary
        write_heartbeat(status="FAILED", detail=f"{type(error).__name__}: {error}")
        raise


if __name__ == "__main__":
    raise SystemExit(main())
