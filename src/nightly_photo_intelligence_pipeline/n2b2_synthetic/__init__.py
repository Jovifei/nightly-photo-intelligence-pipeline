"""N2B2 synthetic photography model-stack validation.

This package implements the deterministic-vision + local-VLM validation
described in ``docs/plan/nightly-photo-intelligence-pipeline_N2B2_handoff/
CODEX_N2B2_Execution_Prompt.md``.

Hard boundaries (enforced in code, not just docs):

* TorchVision weights are loaded **only** from the content-addressed local
  cache. Re-download is never attempted.
* The VLM is reached **only** over ``http://127.0.0.1:11434`` (Ollama
  loopback). No cloud, no remote host, no other port.
* Images are sent as in-memory Base64 bytes; absolute paths never leave the
  process and are never written to outputs.
* Pure synthetic data only: ``REAL_PHOTO_READ_COUNT`` / ``REAL_EXIF_READ_COUNT``
  / ``G1_SOURCE_ACCESS`` / ``SQLITE_WRITE_COUNT`` / ``APP_WRITE_COUNT`` /
  ``OBSIDIAN_WRITE_COUNT`` are all hard-coded to ``0``.

The real TorchVision backend imports ``torch``/``torchvision`` lazily so that
this package (and its tests) remains importable and lint-clean in the managed
``.venv`` which does not carry those heavy dependencies.
"""

from __future__ import annotations

from .config import (
    GPU_LIMIT_MIB,
    LOOPBACK_HOST,
    LOOPBACK_PORT,
    OLLAMA_BASE_URL,
    QWEN_MODEL,
    QWEN_QUANTIZATION,
    N2B2RunConfig,
    TorchVisionRole,
)
from .orchestrator import N2B2Result, SyntheticFixture, run_n2b2

__all__ = [
    "GPU_LIMIT_MIB",
    "LOOPBACK_HOST",
    "LOOPBACK_PORT",
    "OLLAMA_BASE_URL",
    "QWEN_MODEL",
    "QWEN_QUANTIZATION",
    "N2B2RunConfig",
    "TorchVisionRole",
    "N2B2Result",
    "SyntheticFixture",
    "run_n2b2",
]
