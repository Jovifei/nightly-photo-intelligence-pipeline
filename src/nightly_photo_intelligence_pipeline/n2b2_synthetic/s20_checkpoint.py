"""Atomic, binding-aware S20 checkpoint state."""

from __future__ import annotations

import json
import os
from pathlib import Path
from typing import Any


def write_checkpoint(path: Path, payload: dict[str, Any]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    temp = path.with_name(f".{path.name}.tmp")
    temp.write_text(
        json.dumps(payload, sort_keys=True, separators=(",", ":"), ensure_ascii=False),
        encoding="utf-8",
    )
    os.replace(temp, path)


def load_checkpoint(path: Path) -> dict[str, Any] | None:
    if not path.is_file():
        return None
    value = json.loads(path.read_text(encoding="utf-8"))
    if not isinstance(value, dict):
        raise ValueError("N2B2_S20_RESUME_BINDING_MISMATCH: checkpoint must be an object")
    return value


def assert_checkpoint_binding(checkpoint: dict[str, Any], expected: dict[str, str]) -> None:
    for key, value in expected.items():
        if checkpoint.get(key) != value:
            raise ValueError(f"N2B2_S20_RESUME_BINDING_MISMATCH: {key}")
