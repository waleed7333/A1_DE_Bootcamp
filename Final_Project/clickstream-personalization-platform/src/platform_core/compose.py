"""Small Docker Compose helpers used by the platform commands."""

from __future__ import annotations

import subprocess
from pathlib import Path


def run_compose(
    project_root: Path,
    arguments: list[str],
    *,
    timeout: int | None = None,
    stream_output: bool = False,
) -> tuple[bool, str]:
    """Run one Docker Compose command in the project directory."""
    command = ["docker", "compose", *arguments]
    try:
        if stream_output:
            result = subprocess.run(command, cwd=project_root, check=False, timeout=timeout)
            return result.returncode == 0, ""
        result = subprocess.run(
            command,
            cwd=project_root,
            text=True,
            capture_output=True,
            check=False,
            timeout=timeout,
        )
    except (OSError, subprocess.TimeoutExpired) as error:
        return False, str(error)

    detail = "\n".join(part for part in (result.stdout, result.stderr) if part).strip()
    return result.returncode == 0, detail


def run_docker(
    arguments: list[str],
    *,
    timeout: int = 20,
) -> tuple[bool, str]:
    """Run a short Docker command and return its output without raising errors."""
    try:
        result = subprocess.run(
            ["docker", *arguments],
            text=True,
            capture_output=True,
            check=False,
            timeout=timeout,
        )
    except (OSError, subprocess.TimeoutExpired) as error:
        return False, str(error)

    detail = "\n".join(part for part in (result.stdout, result.stderr) if part).strip()
    return result.returncode == 0, detail
