"""Pydantic configuration models loaded from config/execution_defaults.yaml.

Strict (extra='forbid') so an unexpected key fails loudly rather than being
silently dropped. Runtime paths (source_root / runtime_root) are null in the
yaml and resolved at runtime from env vars or CLI args.
"""

from __future__ import annotations

from pathlib import Path
from typing import Any

import yaml
from pydantic import BaseModel, ConfigDict

from .._paths import find_project_root


class _Strict(BaseModel):
    model_config = ConfigDict(extra="forbid", frozen=True)


class NetworkConfig(_Strict):
    default: str
    cloud_image_processing: bool


class PathsConfig(_Strict):
    source_root: Path | None = None
    runtime_root: Path | None = None
    allow_source_symlink: bool
    allow_file_symlink: bool
    redact_absolute_paths: bool


class DatabaseConfig(_Strict):
    engine: str
    foreign_keys: bool
    busy_timeout_ms: int
    journal_mode_candidate: str
    note: str | None = None


class IngestConfig(_Strict):
    allowed_extensions_candidate: list[str]
    sniff_media_type: bool
    hash_chunk_bytes: int
    dry_run_mutates_database: bool


class TelemetryConfig(_Strict):
    enabled: bool


class ReviewConfig(_Strict):
    automatic_approval: bool


class ExportConfig(_Strict):
    include_original_image: bool
    approved_only: bool
    absolute_paths_forbidden: bool


class PipelineConfig(_Strict):
    schema_version: str
    local_first: bool
    network: NetworkConfig
    paths: PathsConfig
    database: DatabaseConfig
    ingest: IngestConfig
    telemetry: TelemetryConfig
    review: ReviewConfig
    export: ExportConfig

    @property
    def allowed_extensions(self) -> tuple[str, ...]:
        return tuple(self.ingest.allowed_extensions_candidate)


def load_config(config_path: Path | None = None) -> PipelineConfig:
    """Load the pipeline config from execution_defaults.yaml."""
    path = config_path or (find_project_root() / "config" / "execution_defaults.yaml")
    if not path.is_file():
        raise FileNotFoundError(f"config file not found: {path}")
    data: dict[str, Any] = yaml.safe_load(path.read_text(encoding="utf-8"))
    return PipelineConfig.model_validate(data)
