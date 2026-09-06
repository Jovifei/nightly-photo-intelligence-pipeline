"""Offline TorchVision backends for the N2B2 synthetic smoke contract."""

from __future__ import annotations

import gc
import hashlib
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any, Protocol

from .config import ROLE_MODEL_MAP, TorchVisionRole

POSE_SCORE_THRESHOLD = 0.5
VOC_PERSON_CLASS_ID = 15


@dataclass
class RawPoseDetections:
    person_boxes: list[dict[str, float]] = field(default_factory=list)
    pose_keypoints: list[list[dict[str, float]]] = field(default_factory=list)
    pose_scores: list[float] = field(default_factory=list)


@dataclass
class RawSegmentation:
    person_mask_ratio: float = 0.0

    @property
    def foreground_ratio(self) -> float:
        """Compatibility alias; facts must use the VOC person semantics."""

        return self.person_mask_ratio


class TorchVisionBackend(Protocol):
    def detect_pose(self, image_bytes: bytes) -> RawPoseDetections: ...

    def segment(self, image_bytes: bytes, role: TorchVisionRole) -> RawSegmentation: ...

    def unload(self, role: TorchVisionRole | None = None) -> None: ...

    @property
    def resident_roles(self) -> set[TorchVisionRole]: ...

    def runtime_attestation(self) -> dict[str, Any]: ...


def _sha256_hex(data: bytes) -> str:
    return hashlib.sha256(data).hexdigest()


class FakeTorchVisionBackend:
    """Deterministic test backend with the same lifecycle and data shape."""

    def detect_pose(self, image_bytes: bytes) -> RawPoseDetections:
        bucket = int(_sha256_hex(image_bytes)[:8], 16) % 3
        boxes: list[dict[str, float]] = []
        keypoints: list[list[dict[str, float]]] = []
        scores: list[float] = []
        for i in range(bucket):
            boxes.append(
                {"x_min": 40.0 + i * 10, "y_min": 30.0, "x_max": 200.0 + i * 10, "y_max": 300.0}
            )
            keypoints.append(
                [
                    {"x": 100.0 + i * 10 + k, "y": 120.0 + k * 2.0, "score": 0.91 - (k % 5) * 0.01}
                    for k in range(17)
                ]
            )
            scores.append(round(0.88 - i * 0.02, 4))
        return RawPoseDetections(boxes, keypoints, scores)

    def segment(self, image_bytes: bytes, role: TorchVisionRole) -> RawSegmentation:
        del role
        ratio = (int(_sha256_hex(image_bytes)[8:16], 16) % 1000) / 1000.0
        return RawSegmentation(person_mask_ratio=round(ratio, 6))

    def unload(self, role: TorchVisionRole | None = None) -> None:
        del role

    @property
    def resident_roles(self) -> set[TorchVisionRole]:
        return set()

    def runtime_attestation(self) -> dict[str, Any]:
        return {
            "device": "cpu",
            "dtype": "float32",
            "cuda_available": False,
            "fallback": False,
        }


class RealTorchVisionBackend:
    """Load only exact approved cache payloads; no constructor can download."""

    def __init__(
        self,
        cache_root: Path,
        subdirs: dict[TorchVisionRole, str],
        *,
        device: str = "cpu",
    ) -> None:
        self._cache_root = Path(cache_root)
        self._subdirs = subdirs
        self._models: dict[TorchVisionRole, Any] = {}
        self._torch: Any = None
        self._tv: Any = None
        if device not in {"cpu", "cuda"}:
            raise ValueError(f"unsupported TorchVision device: {device!r}")
        self._requested_device = device
        self._device: Any = None
        self._fallback = False
        self._last_input_device = "unknown"
        self._last_output_device = "unknown"

    def _ensure_torch(self) -> tuple[Any, Any]:
        if self._torch is not None:
            if self._requested_device == "cuda":
                if not self._torch.cuda.is_available() or self._torch.cuda.device_count() < 1:
                    raise RuntimeError("N2B2_GPU_RUNTIME_UNAVAILABLE: CUDA is unavailable")
                if self._device is None:
                    self._device = self._torch.device("cuda:0")
            return self._torch, self._tv
        try:
            import torch  # noqa: PLC0415
            import torchvision  # noqa: PLC0415
        except Exception as exc:  # pragma: no cover - environment dependent
            raise RuntimeError("torch/torchvision unavailable for N2B2 real execution") from exc
        self._torch = torch
        self._tv = torchvision
        if self._requested_device == "cuda":
            if not torch.cuda.is_available():
                raise RuntimeError("N2B2_GPU_RUNTIME_UNAVAILABLE: CUDA is unavailable")
            if torch.cuda.device_count() < 1:
                raise RuntimeError("N2B2_GPU_RUNTIME_UNAVAILABLE: no CUDA device")
            self._device = torch.device("cuda:0")
        else:
            self._device = torch.device("cpu")
        return torch, torchvision

    @property
    def resident_roles(self) -> set[TorchVisionRole]:
        return set(self._models)

    def runtime_attestation(self) -> dict[str, Any]:
        torch, _ = self._ensure_torch()
        cuda_available = bool(torch.cuda.is_available())
        return {
            "requested_device": self._requested_device,
            "effective_device": str(self._device),
            "dtype": "torch.float32",
            "torch_version": str(getattr(torch, "__version__", "unknown")),
            "torchvision_version": str(getattr(self._tv, "__version__", "unknown")),
            "cuda_available": cuda_available,
            "cuda_device_name": (torch.cuda.get_device_name(0) if cuda_available else None),
            "fallback": self._fallback,
            "input_device": self._last_input_device,
            "raw_output_device": self._last_output_device,
            "serialization_device": "cpu",
        }

    def _weight_path(self, role: TorchVisionRole) -> Path:
        _, filename = ROLE_MODEL_MAP[role]
        path = self._cache_root / self._subdirs[role] / filename
        if not path.is_file():
            raise FileNotFoundError(
                f"TorchVision CACHE_MISS for {role.value}: {filename}; downloads are forbidden"
            )
        return path

    def _load(self, role: TorchVisionRole) -> Any:
        if role in self._models:
            return self._models[role]
        torch, torchvision = self._ensure_torch()
        path = self._weight_path(role)
        if role is TorchVisionRole.POSE_BASELINE_SMOKE:
            model = torchvision.models.detection.keypointrcnn_resnet50_fpn(
                weights=None, weights_backbone=None
            )
        elif role is TorchVisionRole.SEGMENTATION_PRIMARY:
            model = torchvision.models.segmentation.lraspp_mobilenet_v3_large(
                weights=None, weights_backbone=None
            )
        else:
            model = torchvision.models.segmentation.deeplabv3_mobilenet_v3_large(
                weights=None, weights_backbone=None, aux_loss=True
            )
        state_dict = torch.load(path, map_location="cpu", weights_only=True)
        if isinstance(state_dict, dict) and "state_dict" in state_dict:
            state_dict = state_dict["state_dict"]
        model.load_state_dict(state_dict)
        model.eval()
        model.to(self._device)
        if any(parameter.device != self._device for parameter in model.parameters()):
            raise RuntimeError(
                "N2B2_GPU_RUNTIME_UNAVAILABLE: model parameters did not move to requested device"
            )
        self._models[role] = model
        return model

    def unload(self, role: TorchVisionRole | None = None) -> None:
        if role is None:
            self._models.clear()
        else:
            self._models.pop(role, None)
        gc.collect()
        if self._torch is not None and self._torch.cuda.is_available():
            self._torch.cuda.synchronize()
            self._torch.cuda.empty_cache()
            self._torch.cuda.synchronize()

    def detect_pose(self, image_bytes: bytes) -> RawPoseDetections:
        torch, _ = self._ensure_torch()
        model = self._load(TorchVisionRole.POSE_BASELINE_SMOKE)
        tensor = self._decode_image(torch, image_bytes, self._device)
        self._last_input_device = str(tensor.device)
        with torch.no_grad():
            out = model([tensor])[0]
        if self._device.type == "cuda":
            torch.cuda.synchronize()
        raw_device = str(out["boxes"].device)
        boxes = out["boxes"].detach().cpu().tolist()
        scores = out.get("scores", torch.empty(0, device=self._device)).detach().cpu().tolist()
        keypoints = (
            out.get("keypoints", torch.empty((0, 17, 3), device=self._device))
            .detach()
            .cpu()
            .tolist()
        )
        self._last_output_device = raw_device
        detections = RawPoseDetections()
        # Filter all three arrays by the same source index. Incomplete keypoint
        # groups are not emitted as detections, so counts can never diverge.
        for index, (box, score) in enumerate(zip(boxes, scores, strict=False)):
            if float(score) < POSE_SCORE_THRESHOLD or index >= len(keypoints):
                continue
            person_kps = keypoints[index]
            if len(person_kps) != 17:
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
            detections.pose_keypoints.append(
                [
                    {"x": float(point[0]), "y": float(point[1]), "score": round(float(point[2]), 4)}
                    for point in person_kps
                ]
            )
        return detections

    def segment(self, image_bytes: bytes, role: TorchVisionRole) -> RawSegmentation:
        torch, _ = self._ensure_torch()
        model = self._load(role)
        tensor = self._decode_image(torch, image_bytes, self._device)
        self._last_input_device = str(tensor.device)
        with torch.no_grad():
            output = model(tensor.unsqueeze(0))["out"][0]
        if self._device.type == "cuda":
            torch.cuda.synchronize()
        self._last_output_device = str(output.device)
        person_ratio = (
            (output.argmax(0) == VOC_PERSON_CLASS_ID).float().mean().detach().cpu().item()
        )
        return RawSegmentation(person_mask_ratio=round(float(person_ratio), 6))

    @staticmethod
    def _decode_image(torch: Any, image_bytes: bytes, device: Any) -> Any:
        from io import BytesIO  # noqa: PLC0415

        from PIL import Image  # noqa: PLC0415

        image = Image.open(BytesIO(image_bytes)).convert("RGB")
        from torchvision import transforms  # noqa: PLC0415

        return transforms.ToTensor()(image).to(device)


def verify_cache_hit(cache_root: Path, subdirs: dict[TorchVisionRole, str]) -> list[dict[str, str]]:
    """Confirm all exact payload names exist without invoking download code."""

    entries: list[dict[str, str]] = []
    root = Path(cache_root).resolve(strict=True)
    for role, (artifact_id, filename) in ROLE_MODEL_MAP.items():
        path = root / subdirs[role] / filename
        if not path.is_file() or path.is_symlink():
            raise FileNotFoundError(f"TorchVision CACHE_MISS for {artifact_id} at {path}")
        entries.append({"artifact_id": artifact_id, "role": role.value, "path": str(path)})
    return entries


def load_backend(
    backend: str,
    cache_root: Path,
    subdirs: dict[TorchVisionRole, str],
    *,
    device: str = "cpu",
) -> TorchVisionBackend:
    if backend == "fake":
        return FakeTorchVisionBackend()
    if backend == "real":
        return RealTorchVisionBackend(cache_root, subdirs, device=device)
    raise ValueError(f"unknown backend: {backend!r}")
