"""Shared fail-closed provenance semantics for N2A synthetic contracts."""

from __future__ import annotations

import re
from dataclasses import dataclass
from enum import StrEnum

from .errors import InvalidProvenanceError


class ProducerType(StrEnum):
    """Only declared producers may provide structured pose or segmentation facts."""

    FAKE_BACKEND = "FAKE_BACKEND"
    SYNTHETIC_FIXTURE = "SYNTHETIC_FIXTURE"
    REAL_MODEL = "REAL_MODEL"


_SHA256_RE = re.compile(r"^[0-9a-f]{64}$")


@dataclass(frozen=True)
class Provenance:
    """Producer identity without paths, weight bytes, or model execution claims."""

    producer_type: ProducerType
    producer_id: str
    synthetic: bool
    model_id: str | None = None
    model_revision: str | None = None
    artifact_sha256: str | None = None

    def __post_init__(self) -> None:
        try:
            producer_type = ProducerType(self.producer_type)
        except ValueError as exc:
            raise InvalidProvenanceError("producer_type is not authorized for N2A") from exc
        object.__setattr__(self, "producer_type", producer_type)
        if not self.producer_id:
            raise InvalidProvenanceError("producer_id is required")
        if producer_type in {ProducerType.FAKE_BACKEND, ProducerType.SYNTHETIC_FIXTURE}:
            if not self.synthetic:
                raise InvalidProvenanceError("synthetic producer must declare synthetic=true")
            if any(
                value is not None
                for value in (self.model_id, self.model_revision, self.artifact_sha256)
            ):
                raise InvalidProvenanceError(
                    "synthetic producer cannot declare real model artifacts"
                )
            return
        if self.synthetic:
            raise InvalidProvenanceError("REAL_MODEL provenance must declare synthetic=false")
        if not self.model_id or not self.model_revision or not self.artifact_sha256:
            raise InvalidProvenanceError(
                "REAL_MODEL provenance requires model identity, revision, and artifact hash"
            )
        if not _SHA256_RE.fullmatch(self.artifact_sha256):
            raise InvalidProvenanceError("artifact_sha256 must be a lowercase SHA-256")


def validate_provenance(provenance: Provenance) -> None:
    """Re-run dataclass invariants at every product boundary."""

    Provenance(
        producer_type=provenance.producer_type,
        producer_id=provenance.producer_id,
        synthetic=provenance.synthetic,
        model_id=provenance.model_id,
        model_revision=provenance.model_revision,
        artifact_sha256=provenance.artifact_sha256,
    )
