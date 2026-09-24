"""Bounded Real20 preparation and read-only evaluation entry points."""

from typing import Any

from .contracts import EXIF_ALLOWLIST, Real20Error

__all__ = ["EXIF_ALLOWLIST", "Real20Error", "prepare_real20", "run_real20"]


def __getattr__(name: str) -> Any:
    if name in {"prepare_real20", "run_real20"}:
        from .runner import prepare_real20, run_real20

        return prepare_real20 if name == "prepare_real20" else run_real20
    raise AttributeError(name)
