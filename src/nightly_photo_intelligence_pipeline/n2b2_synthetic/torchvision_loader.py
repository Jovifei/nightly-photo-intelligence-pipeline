"""TorchVision model loading and deterministic detection backends for N2B2.

Two backends implement the same protocol:

* :class:`RealTorchVisionBackend` lazily imports ``torch``/``torchvision`` and
  loads each model **only** from its content-addressed cache path. It never
  triggers a download.
* :class:`FakeTorchVisionBackend` produces deterministic, schema-shaped
  detections without torch — used by the test-suite so the full pipeline can
  be exercised in the managed ``.venv``.

Both backends return plain ``bytes``-in / structured-out data; no absolute
paths or source images are persisted.
"""

from __future__ import annotations

import hashlib
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any, Protocol

from .config import (
    ROLE_MODEL_MAP,
    TorchVisionRole,
)


@dataclass
class RawPoseDetections:
    person_boxes: list[dict[str, float]] = field(default_factory=list)
    pose_keypoints: list[list[dict[str, float]]] = field(default_factory=list)
    pose_scores: list[float] = field(default_factory=list)


@dataclass
class RawSegmentation:
    foreground_ratio: float = 0.0


class TorchVisionBackend(Protocol):
    """Common interface implemented by both backends."""

    def detect_pose(self, image_bytes: bytes) -> RawPoseDetections: ...

    def segment(self, image_bytes: bytes, role: TorchVisionRole) -> RawSegmentation: ...


def _sha256_hex(data: bytes) -> str:
    return hashlib.sha256(data).hexdigest()


class FakeTorchVisionBackend:
    """Deterministic, torch-free backend derived purely from the image hash.

    The mapping is stable: ``image_sha256`` modulo 3 selects 0/1/2 persons so
    that a batch of distinct fixtures exercises both the no-person negative
    control and the single/multi-person happy paths.
    """

    def detect_pose(self, image_bytes: bytes) -> RawPoseDetections:
        digest = _sha256_hex(image_bytes)
        bucket = int(digest[:8], 16) % 3
        persons = bucket  # 0, 1 or 2
        boxes: list[dict[str, float]] = []
        keypoints: list[list[dict[str, float]]] = []
        scores: list[float] = []
        for i in range(persons):
            boxes.append(
                {"x_min": 40.0 + i * 10, "y_min": 30.0, "x_max": 200.0 + i * 10, "y_max": 300.0}
            )
            kps = [
                {"x": 100.0 + i * 10 + k, "y": 120.0 + k * 2.0, "score": 0.91 - (k % 5) * 0.01}
                for k in range(17)
            ]
            keypoints.append(kps)
            scores.append(round(0.88 - i * 0.02, 4))
        return RawPoseDetections(person_boxes=boxes, pose_keypoints=keypoints, pose_scores=scores)

    def segment(self, image_bytes: bytes, role: TorchVisionRole) -> RawSegmentation:
        digest = _sha256_hex(image_bytes)
        # Stable pseudo-ratio in (0, 1) derived from the hash.
        ratio = (int(digest[8:16], 16) % 1000) / 1000.0
        return RawSegmentation(foreground_ratio=round(ratio, 6))


class RealTorchVisionBackend:
    """Lazy torch/torchvision backend that loads from the local cache only.

    Raises :class:`FileNotFoundError` (never a download) if a cached weight
    file is absent, and raises :class:`RuntimeError` if ``torch`` is not
    importable in the active interpreter.
    """

    def __init__(self, cache_root: Path, subdirs: dict[TorchVisionRole, str]) -> None:
        self._cache_root = Path(cache_root)
        self._subdirs = subdirs
        self._models: dict[TorchVisionRole, Any] = {}
        self._torch: Any = None
        self._tv: Any = None

    def _ensure_torch(self) -> tuple[Any, Any]:
        if self._torch is not None:
            return self._torch, self._tv
        try:
            import torch  # noqa: PLC0415
            import torchvision  # noqa: PLC0415
        except Exception as exc:  # pragma: no cover - env dependent
            raise RuntimeError(
                "torch/torchvision not available in this interpreter; "
                "N2B2 real execution requires them in the active environment"
            ) from exc
        self._torch = torch
        self._tv = torchvision
        return torch, torchvision

    def _weight_path(self, role: TorchVisionRole) -> Path:
        _, filename = ROLE_MODEL_MAP[role]
        subdir = self._subdirs[role]
        path = self._cache_root / subdir / filename
        if not path.is_file():
            # Hard rule: never download. Refuse and surface CACHE_MISS clearly.
            raise FileNotFoundError(
                f"TorchVision cache miss for {role.value} ({filename}) at {path}; "
                "N2B2 must not download weights."
            )
        return path

    def _load(self, role: TorchVisionRole) -> Any:
        if role in self._models:
            return self._models[role]
        torch, torchvision = self._ensure_torch()
        path = self._weight_path(role)
        weights_path = str(path)
        if role is TorchVisionRole.POSE_BASELINE_SMOKE:
            model = torchvision.models.detection.keypointrcnn_resnet50_fpn(
                weights=None, weights_path=weights_path
            )
        elif role is TorchVisionRole.SEGMENTATION_PRIMARY:
            model = torchvision.models.segmentation.lraspp_mobilenet_v3_large(
                weights=None, weights_path=weights_path
            )
        else:
            model = torchvision.models.segmentation.deeplabv3_mobilenet_v3_large(
                weights=None, weights_path=weights_path
            )
        model.eval()
        self._models[role] = model
        return model

    def detect_pose(self, image_bytes: bytes) -> RawPoseDetections:
        torch, _ = self._ensure_torch()
        model = self._load(TorchVisionRole.POSE_BASELINE_SMOKE)
        tensor = self._decode_image(torch, image_bytes)
        with torch.no_grad():
            out = model([tensor])[0]
        boxes = out["boxes"].tolist()
        kps = out.get("keypoints", torch.empty(0)).tolist()
        scores = out.get("scores", torch.empty(0)).tolist()
        detections = RawPoseDetections()
        for box, score in zip(boxes, scores, strict=False):
            if score < 0.5:
                continue
            detections.person_boxes.append(
                {
                    "x_min": float(box[0]),
                    "y_min": float(box[1]),
                    "x_max": float(box[2]),
                    "y_max": float(box[3]),
                }
            )
            detections.pose_scores.append(round(float(score), 4))
        for person_kps in kps:
            detections.pose_keypoints.append(
                [
                    {"x": float(p[0]), "y": float(p[1]), "score": round(float(p[2]), 4)}
                    for p in person_kps
                ]
            )
        return detections

    def segment(self, image_bytes: bytes, role: TorchVisionRole) -> RawSegmentation:
        torch, _ = self._ensure_torch()
        model = self._load(role)
        tensor = self._decode_image(torch, image_bytes)
        with torch.no_grad():
            out = model(tensor.unsqueeze(0))["out"][0]
        fg = (out.argmax(0) > 0).float().mean().item()
        return RawSegmentation(foreground_ratio=round(float(fg), 6))

    @staticmethod
    def _decode_image(_torch: Any, image_bytes: bytes) -> Any:
        from io import BytesIO  # noqa: PLC0415

        from PIL import Image  # noqa: PLC0415

        img = Image.open(BytesIO(image_bytes)).convert("RGB")
        import torchvision.transforms as T  # noqa: PLC0415

        return T.ToTensor()(img)


def verify_cache_hit(cache_root: Path, subdirs: dict[TorchVisionRole, str]) -> list[dict[str, str]]:
    """Confirm all three cached weight files exist. Never downloads.

    Returns one entry per role with ``artifact_id``, ``role`` and the resolved
    cache path. Raises :class:`FileNotFoundError` if any weight is missing.
    """

    entries: list[dict[str, str]] = []
    for role, (artifact_id, filename) in ROLE_MODEL_MAP.items():
        path = Path(cache_root) / subdirs[role] / filename
        if not path.is_file():
            raise FileNotFoundError(f"TorchVision CACHE_MISS for {artifact_id} at {path}")
        entries.append({"artifact_id": artifact_id, "role": role.value, "path": str(path)})
    return entries


def load_backend(
    backend: str, cache_root: Path, subdirs: dict[TorchVisionRole, str]
) -> TorchVisionBackend:
    if backend == "fake":
        return FakeTorchVisionBackend()
    if backend == "real":
        return RealTorchVisionBackend(cache_root, subdirs)
    raise ValueError(f"unknown backend: {backend!r}")
