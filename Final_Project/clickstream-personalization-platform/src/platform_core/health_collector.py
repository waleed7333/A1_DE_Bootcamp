"""Tiny host-side health collector for the Operations Console.

It intentionally uses the existing `collect_status` function and writes one compact
JSON snapshot every 20 seconds. No new Docker service, database, or monitoring stack
is required.
"""

from __future__ import annotations

import argparse
import os
import time
from pathlib import Path

from platform_core.operations import collect_status


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="Run the lightweight platform health collector")
    parser.add_argument("--project-root", required=True)
    parser.add_argument("--interval-seconds", type=int, default=20)
    return parser.parse_args()


def main() -> int:
    args = parse_args()
    project_root = Path(args.project_root).resolve()
    interval = max(5, int(args.interval_seconds))
    runtime = project_root / "runtime"
    stop_file = runtime / "health_collector.stop"
    pid_file = runtime / "health_collector.pid"
    runtime.mkdir(parents=True, exist_ok=True)
    pid_file.write_text(str(os.getpid()) + "\n", encoding="utf-8")
    try:
        while not stop_file.exists():
            collect_status(project_root, persist=True)
            for _ in range(interval):
                if stop_file.exists():
                    break
                time.sleep(1)
    finally:
        try:
            pid_file.unlink(missing_ok=True)
        except OSError:
            pass
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
