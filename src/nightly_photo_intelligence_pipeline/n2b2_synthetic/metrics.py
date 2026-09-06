"""Best-effort GPU/CPU metric collection for N2B2 (CODEX §12).

All sampling is lazy and defensive: if ``torch``/CUDA is unavailable in the
active interpreter the collector records zeros rather than failing. The
orchestrator uses the collected peaks to enforce the hard ``<= 11500 MiB``
ceiling and the post-unload baseline-return check.
"""

from __future__ import annotations

import subprocess
import time
from dataclasses import dataclass, field
from typing import Any


@dataclass
class MetricsCollector:
    gpu_baseline_mib: int = 0
    gpu_peak_mib: int = 0
    gpu_after_unload_mib: int = 0
    ollama_size_vram: int = 0
    cpu_rss_peak: int = 0
    cold_load_duration_s: float = 0.0
    per_image_duration_s: float = 0.0
    unload_duration_s: float = 0.0
    _torch: Any = field(default=None, repr=False)
    _early_peak_exceeded: bool = False
    stage_records: list[dict[str, Any]] = field(default_factory=list)
    nvidia_samples: list[dict[str, Any]] = field(default_factory=list)
    ollama_ps_samples: list[dict[str, Any]] = field(default_factory=list)
    ollama_gpu_peak_mib: int = 0

    @staticmethod
    def _mib(value: int) -> int:
        return int(value // (1024 * 1024))

    def torch_cuda_snapshot(self) -> dict[str, int]:
        torch = self._torch_mod()
        if torch is None or not torch.cuda.is_available():
            return {
                "memory_allocated_mib": 0,
                "memory_reserved_mib": 0,
                "max_memory_allocated_mib": 0,
                "max_memory_reserved_mib": 0,
            }
        return {
            "memory_allocated_mib": self._mib(torch.cuda.memory_allocated()),
            "memory_reserved_mib": self._mib(torch.cuda.memory_reserved()),
            "max_memory_allocated_mib": self._mib(torch.cuda.max_memory_allocated()),
            "max_memory_reserved_mib": self._mib(torch.cuda.max_memory_reserved()),
        }

    def sample_nvidia(self, label: str) -> dict[str, Any]:
        sample = {
            "label": label,
            "timestamp_monotonic": time.monotonic(),
            "memory_used_mib": self._nvidia_smi_used_mib(),
        }
        self.nvidia_samples.append(sample)
        memory_used = sample["memory_used_mib"]
        self.note_gpu_peak(memory_used if isinstance(memory_used, int) else 0)
        return sample

    def begin_stage(self, *, role: str, model_name: str, device: str, dtype: str) -> dict[str, Any]:
        torch = self._torch_mod()
        if torch is not None and device.startswith("cuda") and torch.cuda.is_available():
            torch.cuda.synchronize()
            torch.cuda.reset_peak_memory_stats()
        record: dict[str, Any] = {
            "role": role,
            "model_name": model_name,
            "device": device,
            "dtype": dtype,
            "before_torch": self.torch_cuda_snapshot(),
            "before_nvidia": self.sample_nvidia(f"{role}:before"),
            "started_monotonic": time.monotonic(),
            "inference_seconds": [],
            "input_devices": [],
            "raw_output_devices": [],
        }
        self.stage_records.append(record)
        return record

    def note_stage_inference(
        self,
        record: dict[str, Any],
        *,
        seconds: float,
        input_device: str,
        raw_output_device: str,
    ) -> None:
        record["inference_seconds"].append(seconds)
        record["input_devices"].append(input_device)
        record["raw_output_devices"].append(raw_output_device)
        self.sample_nvidia(f"{record['role']}:inference")

    def end_stage(self, record: dict[str, Any], *, unload_seconds: float) -> None:
        record["inference_total_seconds"] = time.monotonic() - record["started_monotonic"]
        record["unload_seconds"] = unload_seconds
        record["after_torch"] = self.torch_cuda_snapshot()
        record["after_nvidia"] = self.sample_nvidia(f"{record['role']}:after_unload")
        record["peak_torch"] = self.torch_cuda_snapshot()

    def sample_baseline(self) -> int:
        self.gpu_baseline_mib = self._gpu_allocated_mib()
        self.gpu_peak_mib = self.gpu_baseline_mib
        return self.gpu_baseline_mib

    def note_gpu_peak(self, mib: int | None = None) -> None:
        value = mib if mib is not None else self._gpu_allocated_mib()
        self.gpu_peak_mib = max(self.gpu_peak_mib, value)

    def note_cpu_rss(self, bytes_: int | None = None) -> None:
        value = bytes_ if bytes_ is not None else self._rss_bytes()
        self.cpu_rss_peak = max(self.cpu_rss_peak, value)

    def note_ollama_vram(self, mib: int) -> None:
        self.ollama_size_vram = mib

    def note_ollama_snapshot(self, snapshot: list[dict[str, Any]]) -> None:
        """Record the redacted Ollama residency view during inference."""

        self.ollama_ps_samples.append(
            {
                "timestamp_monotonic": time.monotonic(),
                "models": snapshot,
            }
        )
        total = 0
        for model in snapshot:
            value = model.get("size_vram", 0)
            try:
                numeric = int(value)
            except (TypeError, ValueError):
                continue
            total += numeric // (1024 * 1024) if numeric > 100000 else numeric
        self.ollama_gpu_peak_mib = max(self.ollama_gpu_peak_mib, total)
        self.note_ollama_vram(total)

    def note_cold_load(self, seconds: float) -> None:
        self.cold_load_duration_s = seconds

    def note_per_image(self, seconds: float) -> None:
        self.per_image_duration_s = seconds

    def note_unload(self, seconds: float) -> None:
        self.unload_duration_s = seconds

    def sample_after_unload(self) -> int:
        self.gpu_after_unload_mib = self._gpu_allocated_mib()
        return self.gpu_after_unload_mib

    # -- private samplers ------------------------------------------------
    def _torch_mod(self) -> Any | None:
        if self._torch is not None:
            return None if self._torch is False else self._torch
        try:  # pragma: no cover - env dependent
            import torch  # noqa: PLC0415

            self._torch = torch
        except Exception:
            self._torch = False
        return self._torch or None

    def _gpu_allocated_mib(self) -> int:
        nvidia = self._nvidia_smi_used_mib()
        torch = self._torch_mod()
        torch_value = 0
        try:  # pragma: no cover - env dependent
            if torch is not None and torch.cuda.is_available():
                torch_value = int(torch.cuda.memory_allocated() // (1024 * 1024))
        except Exception:
            torch_value = 0
        return max(nvidia, torch_value)

    @staticmethod
    def _nvidia_smi_used_mib() -> int:
        try:  # pragma: no cover - hardware dependent
            completed = subprocess.run(
                [
                    "nvidia-smi",
                    "--query-gpu=memory.used",
                    "--format=csv,noheader,nounits",
                ],
                capture_output=True,
                text=True,
                timeout=5,
                check=True,
            )
            values = [int(line.strip()) for line in completed.stdout.splitlines() if line.strip()]
            return max(values, default=0)
        except (OSError, ValueError, subprocess.SubprocessError):
            return 0

    @staticmethod
    def _rss_bytes() -> int:
        try:  # Unix / macOS
            import resource  # noqa: PLC0415

            return int(resource.getrusage(resource.RUSAGE_SELF).ru_maxrss * 1024)  # type: ignore[attr-defined]
        except ImportError:
            # Windows fallback via kernel32 GetProcessMemoryInfo.
            try:  # pragma: no cover - platform dependent
                import ctypes
                from ctypes import wintypes

                class _PROCESS_MEMORY_COUNTERS_EX(ctypes.Structure):
                    _fields_ = [
                        ("cb", wintypes.DWORD),
                        ("PageFaultCount", wintypes.DWORD),
                        ("PeakWorkingSetSize", ctypes.c_size_t),
                        ("WorkingSetSize", ctypes.c_size_t),
                        ("QuotaPeakPagedPoolUsage", ctypes.c_size_t),
                        ("QuotaPagedPoolUsage", ctypes.c_size_t),
                        ("QuotaPeakNonPagedPoolUsage", ctypes.c_size_t),
                        ("QuotaNonPagedPoolUsage", ctypes.c_size_t),
                        ("PagefileUsage", ctypes.c_size_t),
                        ("PeakPagefileUsage", ctypes.c_size_t),
                        ("PrivateUsage", ctypes.c_size_t),
                    ]

                counters = _PROCESS_MEMORY_COUNTERS_EX()
                counters.cb = ctypes.sizeof(counters)
                kernel32 = ctypes.windll.kernel32
                if kernel32.GetProcessMemoryInfo(
                    kernel32.GetCurrentProcess(),
                    ctypes.byref(counters),
                    counters.cb,
                ):
                    return int(counters.WorkingSetSize)
            except Exception:
                pass
            return 0
        except Exception:
            return 0

    @property
    def rss_mib(self) -> int:
        return int(self.cpu_rss_peak // (1024 * 1024))
