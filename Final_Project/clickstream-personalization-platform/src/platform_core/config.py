"""Configuration loading helpers used by host-side commands."""

from __future__ import annotations

from pathlib import Path
from typing import Any

import yaml


def load_settings(project_root: Path) -> dict[str, Any]:
    """Load the non-secret YAML settings and validate the top-level structure."""
    settings_path = project_root / "config" / "settings.yaml"
    if not settings_path.exists():
        raise FileNotFoundError(f"Missing required configuration file: {settings_path}")

    with settings_path.open("r", encoding="utf-8") as file:
        settings = yaml.safe_load(file)

    if not isinstance(settings, dict):
        raise ValueError("config/settings.yaml must contain a YAML mapping at its root.")

    return settings


def read_dotenv(env_path: Path) -> dict[str, str]:
    """Read a simple KEY=VALUE .env file without exposing secret values."""
    values: dict[str, str] = {}
    if not env_path.exists():
        return values

    for raw_line in env_path.read_text(encoding="utf-8").splitlines():
        line = raw_line.strip()
        if not line or line.startswith("#") or "=" not in line:
            continue
        key, value = line.split("=", 1)
        values[key.strip()] = value.strip().strip('"').strip("'")

    return values
