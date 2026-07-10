"""Fast contract tests that do not require Docker, Kafka, Spark, or external APIs."""

from __future__ import annotations

import json
import subprocess
import sys
from pathlib import Path

PROJECT_ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(PROJECT_ROOT / "src"))

from platform_core.source_generation import validate_sources  # noqa: E402


def test_mixed_source_files_and_static_catalog_are_valid() -> None:
    checks, passed = validate_sources(PROJECT_ROOT, write_report=False)
    assert passed, [check.detail for check in checks]
    assert (PROJECT_ROOT / "data/source/clickstream/clickstream_events.jsonl").is_file()
    assert (PROJECT_ROOT / "data/source/web_logs/webserver_access.log").is_file()
    assert (PROJECT_ROOT / "data/reference/product_catalog.csv").is_file()


def test_generation_manifest_describes_one_file_per_stream_source() -> None:
    manifest = json.loads((PROJECT_ROOT / "data/source/generation_manifest.json").read_text(encoding="utf-8"))
    assert manifest["source_policy"]["clickstream_file"].endswith(".jsonl")
    assert manifest["source_policy"]["web_log_file"].endswith(".log")
    assert manifest["source_policy"]["mixed_quality_records"] is True
    assert manifest["source_policy"]["product_catalog_is_static_and_clean"] is True


def test_cli_exposes_only_the_five_normal_commands() -> None:
    result = subprocess.run([sys.executable, "main.py", "--help"], cwd=PROJECT_ROOT, capture_output=True, text=True, check=True)
    assert "{init,start,status,stop,reset}" in result.stdout
    assert "bootstrap" not in result.stdout
    assert "publish-serving" not in result.stdout



