"""Internal path resolution helpers (not part of the public CLI surface)."""

from __future__ import annotations

import os
from pathlib import Path

# Markers that identify the project root.
_ROOT_MARKERS = ("PROJECT_STATE.json", "MASTER_EXECUTION_CONTRACT.md")


def find_project_root(start: Path | None = None) -> Path:
    """Walk upward from *start* (default: this file) to locate the project root.

    The project root is the nearest directory containing PROJECT_STATE.json and
    MASTER_EXECUTION_CONTRACT.md. Falls back to the NPI_PROJECT_ROOT env var.
    """
    env_root = os.environ.get("NPI_PROJECT_ROOT")
    if env_root:
        candidate = Path(env_root).resolve()
        if (candidate / "PROJECT_STATE.json").is_file():
            return candidate

    start = Path(__file__).resolve() if start is None else Path(start).resolve()

    current = start
    for _ in range(20):
        if all((current / marker).is_file() for marker in _ROOT_MARKERS):
            return current
        if current.parent == current:
            break
        current = current.parent

    # Last resort: assume the package's src parent's parent is the root.
    return Path(__file__).resolve().parents[2]
