"""Configuration constants and dataclasses for N2B2 synthetic validation."""

from __future__ import annotations

from dataclasses import dataclass, field
from enum import Enum
from pathlib import Path
from typing import Literal

# Ollama loopback gate (CODEX §4). Only this host/port is ever contacted.
LOOPBACK_HOST = "127.0.0.1"
LOOPBACK_PORT = 11434
OLLAMA_BASE_URL = f"http://{LOOPBACK_HOST}:{LOOPBACK_PORT}"

# Owner Choice A (CODEX §3.2): local qwen3.5:9b replaces planned Qwen3-VL-2B.
QWEN_MODEL = "qwen3.5:9b"
QWEN_QUANTIZATION = "Q4_K_M"

# Hard GPU ceiling (CODEX §12).
GPU_LIMIT_MIB = 11500

# Fixed stage seed for Qwen repeatability (CODEX §13).
STAGE_SEED = 20260805

# Synthetic fixture set identifiers.
S3_CASE_COUNT = 3
S20_CASE_COUNT = 20

# Canonical model identity strings (must match the vision_fact_contract schema).
KEYPOINT_MODEL_ID = "torchvision-keypointrcnn-resnet50-fpn-coco-v1"
LRASPP_MODEL_ID = "torchvision-lraspp-mobilenet-v3-large-coco-voc-v1"
DEEPLAB_MODEL_ID = "torchvision-deeplabv3-mobilenet-v3-large-coco-voc-v1"


class TorchVisionRole(str, Enum):
    """The three TorchVision models used by N2B2 (CODEX §3.1)."""

    POSE_BASELINE_SMOKE = "POSE_BASELINE_SMOKE"
    SEGMENTATION_PRIMARY = "SEGMENTATION_PRIMARY"
    SEGMENTATION_QUALITY_COMPARATOR = "SEGMENTATION_QUALITY_COMPARATOR"


# role -> (canonical model id, expected weights filename in the cache)
ROLE_MODEL_MAP: dict[TorchVisionRole, tuple[str, str]] = {
    TorchVisionRole.POSE_BASELINE_SMOKE: (KEYPOINT_MODEL_ID, "keypointrcnn_resnet50_fpn_coco.pth"),
    TorchVisionRole.SEGMENTATION_PRIMARY: (LRASPP_MODEL_ID, "lraspp_mobilenet_v3_large_coco.pth"),
    TorchVisionRole.SEGMENTATION_QUALITY_COMPARATOR: (
        DEEPLAB_MODEL_ID,
        "deeplabv3_mobilenet_v3_large_coco.pth",
    ),
}


@dataclass(frozen=True)
class N2B2RunConfig:
    """Frozen run configuration for one N2B2 validation pass.

    ``backend`` selects the vision backend: ``"real"`` lazily imports
    torch/torchvision and loads from ``cache_root``; ``"fake"`` uses a
    deterministic in-process backend for tests (no torch required).
    """

    project_root: Path
    cache_root: Path
    fixtures_dir: Path
    runtime_out_dir: Path
    generator_version: str = "synthetic-fixture-v1"
    seed: int | None = STAGE_SEED
    stage_seed: int = STAGE_SEED
    backend: Literal["real", "fake"] = "fake"
    ollama_base_url: str = OLLAMA_BASE_URL
    gpu_limit_mib: int = GPU_LIMIT_MIB
    # role -> content-addressed cache sub-directory name (sha256)
    cache_subdirs: dict[TorchVisionRole, str] = field(
        default_factory=lambda: {
            # Content-addressed cache sub-directory names (sha256) — immutable, so noqa on length.
            TorchVisionRole.POSE_BASELINE_SMOKE: "fc266e953d2b302cdcbb9ae66f71f6b0d4649928bf02dc573961e361e4918926",  # noqa: E501
            TorchVisionRole.SEGMENTATION_PRIMARY: "d234d4eae9d55d5f76de18b77cf0dc62c66fe5c5482758209d00f950c92bb280",  # noqa: E501
            TorchVisionRole.SEGMENTATION_QUALITY_COMPARATOR: "6aa7571eda2286cc622cfa6370680cdb943ce524e029aa579ac643eb4fa528dc",  # noqa: E501
        }
    )
