"""Generate small valid live records and keep the real-time path active.

This host-side process appends one paired Clickstream event and Web Log at a
fixed low rate.

Rules:
- Clickstream and Web Logs contain ip_address only.
- Country/city are not generated here.
- Geo enrichment happens later in Spark using GeoLite2.
- Live records use the same compact sorted JSON style as initial source files.
"""

from __future__ import annotations

import argparse
import inspect
import json
import random
import time
import uuid
from datetime import UTC, datetime
from pathlib import Path
from typing import Any

from platform_core.config import load_settings
from platform_core.source_generation import _discover_geo_locations
from platform_core.streaming import _publish_clickstream


TRAFFIC_SOURCE = "direct"
DEVICE_TYPE = "mobile"
BROWSER = "Chrome"
OPERATING_SYSTEM = "Android"
LIVE_PRODUCT_ID = "PRD000001"
LIVE_USER_ID = "USR000001"


def parse_args() -> argparse.Namespace:
    """Parse CLI arguments.

    parse_known_args is intentional so this script stays compatible if the
    platform launcher passes extra operational arguments in the future.
    """
    parser = argparse.ArgumentParser( description="Generate small live Clickstream and Web Log source records" )
    parser.add_argument("--project-root", default=".")
    parser.add_argument("--interval-seconds", type=int, default=20)

    args, _unknown = parser.parse_known_args()
    return args


def utc_timestamp(value: datetime | None = None) -> str:
    """Return a UTC timestamp in the same format as the initial generator."""
    current = value or datetime.now(UTC)

    return ( current.astimezone(UTC) .replace(microsecond=0) .isoformat() .replace("+00:00", "Z") )


def json_line(payload: dict[str, Any]) -> str:
    """Write NDJSON in the same compact sorted style as initial source files."""
    return json.dumps( payload, separators=(",", ":"), sort_keys=True, )

def write_json(path: Path, payload: dict[str, Any]) -> None:
    """Write a small JSON state file atomically."""
    path.parent.mkdir(parents=True, exist_ok=True)

    temporary = path.with_suffix(path.suffix + ".tmp")
    temporary.write_text( json.dumps(payload, indent=2, sort_keys=True) + "\n", encoding="utf-8", )
    temporary.replace(path)


def read_state(path: Path) -> dict[str, Any]:
    """Read live generator state, or return a clean default state."""
    try:
        value = json.loads(path.read_text(encoding="utf-8"))
        return value if isinstance(value, dict) else {"sequence": 0}

    except (OSError, json.JSONDecodeError):
        return {"sequence": 0}


def append_line(path: Path, line: str) -> None:
    """Append one NDJSON line to a source file."""
    path.parent.mkdir(parents=True, exist_ok=True)

    with path.open("a", encoding="utf-8") as handle:
        handle.write(line + "\n")
        handle.flush()


def load_geoip_locations(project_root: Path) -> list[dict[str, Any]]:
    """Load the same GeoLite2-tested IP pool used by initial generation."""
    settings = load_settings(project_root)
    seed = int(settings["source_generation"]["deterministic_seed"]) + 7919

    locations = _discover_geo_locations( project_root, random.Random(seed), minimum=6, )

    if not locations:
        raise RuntimeError( "No GeoLite2-enrichable IP addresses are available for live generation" )

    return locations


def build_live_event( sequence: int, event_time: datetime, location: dict[str, Any], ) -> dict[str, Any]:
    """Build one valid live Clickstream record.

    The record carries ip_address only. Geo fields are intentionally not written
    here because Spark + GeoLite2 must produce them later.
    """
    suffix = uuid.uuid4().hex[:8]
    request_id = f"LIVE_REQ_{sequence:08d}_{suffix}"

    return {
        "browser": BROWSER,
        "checkout_id": None,
        "contract_version": "1.0",
        "device_type": DEVICE_TYPE,
        "event_id": f"LIVE_EVT_{sequence:08d}_{suffix}",
        "event_timestamp": utc_timestamp(event_time),
        "event_type": "product_view",
        "ip_address": str(location["ip_address"]),
        "operating_system": OPERATING_SYSTEM,
        "order_id": None,
        "page_url": f"/products/{LIVE_PRODUCT_ID}",
        "product_id": LIVE_PRODUCT_ID,
        "request_id": request_id,
        "scroll_depth_pct": 55,
        "search_query": "",
        "session_id": f"LIVE_SES_{sequence:08d}",
        "time_on_page_seconds": 18,
        "traffic_source": TRAFFIC_SOURCE,
        "user_id": LIVE_USER_ID,
        "visitor_id": f"LIVE_VIS_{sequence:08d}",
    }


def build_live_log( sequence: int, log_time: datetime, event: dict[str, Any], ) -> dict[str, Any]:
    """Build one valid Web Log correlated with the live Clickstream event."""
    suffix = str(event["event_id"]).split("_")[-1]

    return {
        "bytes_sent": 2048,
        "contract_version": "1.0",
        "endpoint": str(event["page_url"]),
        "http_method": "GET",
        "ip_address": str(event["ip_address"]),
        "log_id": f"LIVE_LOG_{sequence:08d}_{suffix}",
        "request_id": str(event["request_id"]),
        "response_time_ms": 90,
        "status_code": 200,
        "timestamp": utc_timestamp(log_time),
        "user_agent": f"SyntheticBrowser/{BROWSER}",
    }


def publish_clickstream_line(project_root: Path, line: str) -> None:
    """Publish one live Clickstream line to Kafka.

    The platform helper may evolve, so this wrapper supports the two practical
    calling styles used by local launchers.
    """
    signature = inspect.signature(_publish_clickstream)
    parameter_count = len(signature.parameters)

    if parameter_count == 2:
        _publish_clickstream(project_root, [line])
        return

    if parameter_count == 1:
        # Older helper versions publish from the source file directly.
        # This still works because the line has already been appended.
        _publish_clickstream(project_root)
        return

    raise RuntimeError( "Unsupported _publish_clickstream signature in platform_core.streaming" )


def run(project_root: Path, interval_seconds: int) -> int:
    """Append live source records forever at a low fixed rate."""
    interval = max(10, int(interval_seconds))

    source_root = project_root / "data" / "source"
    clickstream_path = source_root / "clickstream" / "clickstream_events.jsonl"
    web_log_path = source_root / "web_logs" / "webserver_access.log"

    state_path = ( project_root / "runtime" / "source_publishers" / "live_generator_state.json" )

    locations = load_geoip_locations(project_root)
    state = read_state(state_path)
    sequence = int(state.get("sequence", 0)) + 1

    while True:
        event_time = datetime.now(UTC)
        location = locations[(sequence - 1) % len(locations)]

        event = build_live_event(sequence, event_time, location)
        log = build_live_log(sequence, event_time, event)

        event_line = json_line(event)
        log_line = json_line(log)

        append_line(clickstream_path, event_line)
        append_line(web_log_path, log_line)

        publish_clickstream_line(project_root, event_line)

        write_json(
            state_path,
            {
                "sequence": sequence,
                "last_event_id": event["event_id"],
                "last_log_id": log["log_id"],
                "last_request_id": event["request_id"],
                "last_ip_address": event["ip_address"],
                "last_generated_at_utc": utc_timestamp(event_time),
                "interval_seconds": interval,
            },
        )

        sequence += 1
        time.sleep(interval)


def main() -> int:
    args = parse_args()
    project_root = Path(args.project_root).resolve()

    return run( project_root=project_root, interval_seconds=args.interval_seconds, )


if __name__ == "__main__":
    raise SystemExit(main())