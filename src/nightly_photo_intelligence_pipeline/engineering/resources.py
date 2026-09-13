"""Finite, explicit resource measurements. Missing measurements never mean zero."""

from __future__ import annotations

import math

from .common import EngineeringError, require


def validate_gpu_peak(value: object, *, ceiling_mib: int = 11500) -> float:
    require(type(ceiling_mib) is int and ceiling_mib > 0, "NPI_GPU_CEILING_INVALID")
    require(type(value) in (int, float), "NPI_GPU_MEASUREMENT_INVALID")
    try:
        peak = float(value)  # type: ignore[arg-type]
    except (OverflowError, ValueError, TypeError) as exc:
        raise EngineeringError("NPI_GPU_MEASUREMENT_INVALID") from exc
    require(math.isfinite(peak) and peak > 0, "NPI_GPU_MEASUREMENT_INVALID")
    require(peak <= ceiling_mib, "NPI_GPU_CEILING_EXCEEDED")
    return peak
