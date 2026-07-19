"""Finite-number guards shared by every public N2A contract boundary."""

from __future__ import annotations

import math
from collections.abc import Mapping, Sequence

from .errors import NonFiniteNumberError


def require_finite_number(value: object) -> float:
    """Return a finite JSON number or raise a stable, redacted domain error."""

    if isinstance(value, bool) or not isinstance(value, (int, float)):
        raise NonFiniteNumberError("numeric contract value must be finite")
    number = float(value)
    if not math.isfinite(number):
        raise NonFiniteNumberError("numeric contract value must be finite")
    return number


def reject_non_finite_numbers(value: object) -> None:
    """Reject NaN and infinities recursively before public JSON validation."""

    if isinstance(value, float):
        require_finite_number(value)
        return
    if isinstance(value, Mapping):
        for nested in value.values():
            reject_non_finite_numbers(nested)
        return
    if isinstance(value, Sequence) and not isinstance(value, (str, bytes, bytearray)):
        for nested in value:
            reject_non_finite_numbers(nested)
