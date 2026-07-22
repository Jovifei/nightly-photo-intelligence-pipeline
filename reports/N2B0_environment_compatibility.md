# N2B0 Environment Compatibility

Read-only observation on 2026-07-23: Windows 11 AMD64, Python 3.12.10, Docker 29.5.3, Docker Compose v5.1.4, WSL status available, and NVIDIA RTX 4070 SUPER (12,282 MiB; driver 595.97) were visible. The project preflight exited 0 with 15 PASS, 0 FAIL, 0 NOT_AVAILABLE, and 0 SKIPPED. Torch, ONNX Runtime, Paddle, MediaPipe, and OpenCV are not installed in the project venv; Pillow is present. No CUDA runtime compatibility, artifact runtime, VRAM, latency, OOM, or model quality is measured by N2B0.

Candidate A is an isolated Python environment outside the pipeline venv, with a pinned lockfile, external cache, and removable quarantine. Candidate B is a future Docker/WSL2 design with an immutable image digest, separate writable runtime/cache mounts, read-only photos only after a later approval, and no Docker socket exposure. Neither is built or pulled in N2B0.

Verdict: `ENVIRONMENT_COMPATIBILITY_READY_FOR_DOWNLOAD` only in the narrow sense that a later Owner-approved N2B1 can perform its own compatibility gate; this is not readiness to download now.
