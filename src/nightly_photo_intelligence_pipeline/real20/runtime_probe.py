"""Probe the executing interpreter and CUDA operators without loading weights."""

from __future__ import annotations

import platform
import sys
from typing import Any

from .contracts import Real20Error


def probe_worker() -> dict[str, Any]:
    if sys.version_info[:2] != (3, 12):
        raise Real20Error("REAL20_WORKER_PYTHON_UNSUPPORTED")
    try:
        import torch
        import torchvision

        if torch.__version__ != "2.7.1+cu128" or torchvision.__version__ != "0.22.1+cu128":
            raise Real20Error("REAL20_WORKER_VERSION_MISMATCH")
        if not torch.cuda.is_available():
            raise Real20Error("REAL20_WORKER_CUDA_UNAVAILABLE")
        boxes = torch.tensor([[0.0, 0.0, 2.0, 2.0]], device="cuda")
        scores = torch.tensor([0.9], device="cuda")
        kept = torchvision.ops.nms(boxes, scores, 0.5)
        features = torch.ones((1, 1, 4, 4), device="cuda")
        aligned = torchvision.ops.roi_align(features, [boxes], (2, 2))
        torch.cuda.synchronize()
        if kept.numel() != 1 or not bool(torch.isfinite(aligned).all().item()):
            raise Real20Error("REAL20_WORKER_OPERATORS_FAILED")
        return {
            "python": platform.python_version(),
            "torch": str(torch.__version__),
            "torchvision": str(torchvision.__version__),
            "cuda": torch.version.cuda,
            "device": torch.cuda.get_device_name(0),
            "nms": "PASS",
            "roi_align": "PASS",
        }
    except Real20Error:
        raise
    except Exception as exc:
        raise Real20Error("REAL20_WORKER_RUNTIME_UNAVAILABLE") from exc
