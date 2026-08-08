"""Best-effort GPU/CPU metric collection for N2B2 (CODEX §12).

All sampling is lazy and defensive: if ``torch``/CUDA is unavailable in the
active interpreter the collector records zeros rather than failing. The
orchestrator uses the collected peaks to enforce the hard ``<= 11500 MiB``
ceiling and the post-unload baseline-return check.
"""

from __future__ import annotations

from dataclasses import dataclass, field
from typing import Any


@dataclass
class MetricsCollector:
    gpu_baseline_mib: int = 0
    gpu_peak_mib: int = 0
    ollama_size_vram: int = 0
    cpu_rss_peak: int = 0
    cold_load_duration_s: float = 0.0
    per_image_duration_s: float = 0.0
    unload_duration_s: float = 0.0
    _torch: Any = field(default=None, repr=False)
    _early_peak_exceeded: bool = False

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

    def note_cold_load(self, seconds: float) -> None:
        self.cold_load_duration_s = seconds

    def note_per_image(self, seconds: float) -> None:
        self.per_image_duration_s = seconds

    def note_unload(self, seconds: float) -> None:
        self.unload_duration_s = seconds

    # -- private samplers ------------------------------------------------
    def _torch_mod(self) -> Any | None:
        if self._torch is not None:
            return self._torch
        try:  # pragma: no cover - env dependent
            import torch  # noqa: PLC0415

            self._torch = torch
        except Exception:
            self._torch = False
        return self._torch or None

    def _gpu_allocated_mib(self) -> int:
        torch = self._torch_mod()
        if torch is None:
            return 0
        try:  # pragma: no cover - env dependent
            if torch.cuda.is_available():
                return int(torch.cuda.memory_allocated() // (1024 * 1024))
        except Exception:
            return 0
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
