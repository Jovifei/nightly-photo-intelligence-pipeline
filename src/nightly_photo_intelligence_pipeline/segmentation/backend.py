"""Typed segmentation backend boundary; no concrete model dependency."""

from __future__ import annotations

from typing import Protocol

from .contracts import SegmentationInput, SegmentationResult


class SegmentationBackend(Protocol):
    backend_id: str
    synthetic: bool

    def predict(self, request: SegmentationInput) -> SegmentationResult:
        """Return typed metadata without deciding model authorization."""
