"""Typed pose backend boundary; no concrete model dependency is imported."""

from __future__ import annotations

from typing import Protocol

from .contracts import PoseInput, PoseResult


class PoseBackend(Protocol):
    backend_id: str
    synthetic: bool

    def predict(self, request: PoseInput) -> PoseResult:
        """Return a typed result without deciding authorization."""
