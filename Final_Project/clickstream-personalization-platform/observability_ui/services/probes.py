"""Read-only helpers for the lightweight Operations Console."""

from __future__ import annotations

import json
import os
from datetime import UTC, datetime
from pathlib import Path
from typing import Any

RUNTIME = Path(os.getenv("OBSERVABILITY_RUNTIME_ROOT", "/opt/project/runtime"))
REPORTS = Path(os.getenv("OBSERVABILITY_REPORTS_ROOT", "/opt/project/reports"))


def read_json(path: Path) -> dict[str, Any]:
    """Return an empty dictionary when an optional evidence file is not ready yet."""
    try:
        payload = json.loads(path.read_text(encoding="utf-8"))
        return payload if isinstance(payload, dict) else {}
    except (OSError, json.JSONDecodeError):
        return {}


def latest_snapshot() -> dict[str, Any]:
    return read_json(RUNTIME / "observability" / "latest.json")


def streaming_status() -> dict[str, Any]:
    return read_json(RUNTIME / "streaming_status.json")


def validation_status() -> dict[str, Any]:
    return read_json(REPORTS / "validation_latest.json")


def serving_status() -> dict[str, Any]:
    return read_json(REPORTS / "serving_latest.json")


def generation_manifest() -> dict[str, Any]:
    return read_json(Path("/opt/project/data/source/generation_manifest.json"))


def evidence_rows() -> list[dict[str, str]]:
    """Return compact platform evidence for the Operations Console."""
    snapshot = latest_snapshot()
    streaming = streaming_status()
    validation = validation_status()
    serving = serving_status()
    return [
        {
            "Evidence": "Platform health",
            "Status": str(snapshot.get("overall_status", "MISSING")),
            "Detail": str(snapshot.get("captured_at_utc", "No snapshot")),
        },
        {
            "Evidence": "Spark streaming",
            "Status": str(streaming.get("status", "MISSING")),
            "Detail": f"Batch: {streaming.get('last_successful_batch_id', 'not recorded')}",
        },
        {
            "Evidence": "Lakehouse validation",
            "Status": str(validation.get("status", "MISSING")),
            "Detail": str(
                validation.get("validation_id", validation.get("error", "No validation"))
            ),
        },
        {
            "Evidence": "Active serving build",
            "Status": str(serving.get("status", "MISSING")),
            "Detail": str(
                serving.get("serving_build_id", serving.get("error", "No serving build"))
            ),
        },
    ]


def quality_rows() -> list[dict[str, Any]]:
    validation = validation_status()
    details = validation.get("details", {})
    rows: list[dict[str, Any]] = []
    if isinstance(details, dict):
        for source in ("clickstream", "web_logs", "users_cdc", "orders_cdc", "order_items_cdc"):
            values = details.get(source)
            if isinstance(values, dict):
                rows.append(
                    {
                        "Source": source,
                        "Raw": values.get("raw", 0),
                        "Clean": values.get("clean", 0),
                        "Quarantine": values.get("quarantine", 0),
                        "Reconciled": values.get("reconciled", False),
                    }
                )
    return rows


def rendered_at() -> str:
    return datetime.now(UTC).isoformat()
