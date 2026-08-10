"""Generate the bounded, synthetic-only Case 17 remediation candidates."""

from __future__ import annotations

import json
import os
import socket
import subprocess
from contextlib import suppress
from pathlib import Path
from typing import Any

from tools.generate_n2b2_s20_fixtures import (
    CHECKPOINT,
    VAE,
    _request,
    _sha,
    _stop_server,
    _submit,
    _wait_output,
    _wait_ready,
    _workflow,
)

from nightly_photo_intelligence_pipeline.n2b2_synthetic.s20_manifest import (
    S20_CASE17_GENERATOR_VERSION,
    S20_CASE17_REMEDIATION_SEEDS,
)

CASE_ID = "n2b2-s20-17"
WIDTH = 1024
HEIGHT = 768
PROMPT = (
    "synthetic computer-generated realistic photograph, exactly one adult person "
    "standing upright at small scale near the left third of a large empty light-gray "
    "studio, entire head hands legs and feet visible, body clearly separated from "
    "background, large blank wall and floor creating generous negative space, "
    "no furniture, no props, no mirrors, no reflections, natural anatomy, "
    "coherent lighting, sharp focus, no readable text, no logo, no watermark"
)
NEGATIVE = (
    "second person, extra person, multiple people, crowd, face in background, "
    "mannequin, statue, portrait, reflection, mirror, chair, stool, table, desk, "
    "furniture, cropped subject, missing head, missing hands, missing feet, "
    "extra limbs, malformed anatomy, fused bodies, duplicate body parts, text, logo, watermark"
)


def _assert_port_free() -> None:
    with socket.socket(socket.AF_INET, socket.SOCK_STREAM) as sock:
        sock.setsockopt(socket.SOL_SOCKET, socket.SO_REUSEADDR, 1)
        try:
            sock.bind(("127.0.0.1", 7865))
        except OSError as exc:
            raise RuntimeError(
                "N2B2_S20_FIXTURE_GENERATION_BLOCKED_ENVIRONMENT: COMFYUI_PORT_7865_UNAVAILABLE"
            ) from exc


def _start_server(root: Path) -> tuple[subprocess.Popen[str], Path]:
    python_value = os.environ.get("NPI_COMFY_PYTHON")
    base_value = os.environ.get("NPI_COMFY_BASE_DIRECTORY")
    if not python_value or not base_value:
        raise RuntimeError(
            "N2B2_S20_FIXTURE_GENERATION_BLOCKED_ENVIRONMENT: "
            "NPI_COMFY_PYTHON and NPI_COMFY_BASE_DIRECTORY are required"
        )
    python_exe = Path(python_value)
    base_dir = Path(base_value)
    comfy_root = (
        Path.home()
        / "AppData"
        / "Local"
        / "Programs"
        / "@comfyorgcomfyui-electron"
        / "resources"
        / "ComfyUI"
    )
    if not python_exe.is_file() or not (comfy_root / "main.py").is_file():
        raise RuntimeError(
            "N2B2_S20_FIXTURE_GENERATION_BLOCKED_ENVIRONMENT: ComfyUI install missing"
        )
    if not (base_dir / "models" / "checkpoints" / CHECKPOINT).is_file():
        raise RuntimeError("N2B2_S20_FIXTURE_GENERATION_BLOCKED_ENVIRONMENT: checkpoint missing")
    if not (base_dir / "models" / "vae" / VAE).is_file():
        raise RuntimeError("N2B2_S20_FIXTURE_GENERATION_BLOCKED_ENVIRONMENT: VAE missing")
    _assert_port_free()
    output_dir = root / "comfy-output"
    for name in ("comfy-input", "comfy-temp", "comfy-user", "logs", "candidates"):
        (root / name).mkdir(parents=True, exist_ok=True)
    output_dir.mkdir(parents=True, exist_ok=True)
    log = (root / "logs" / "comfyui.log").open("w", encoding="utf-8")
    command = [
        str(python_exe),
        str(comfy_root / "main.py"),
        "--listen",
        "127.0.0.1",
        "--port",
        "7865",
        "--base-directory",
        str(base_dir),
        "--input-directory",
        str(root / "comfy-input"),
        "--output-directory",
        str(output_dir),
        "--temp-directory",
        str(root / "comfy-temp"),
        "--user-directory",
        str(root / "comfy-user"),
        "--front-end-root",
        str(comfy_root.parent / "desktop-ui"),
        "--database-url",
        "sqlite:///:memory:",
        "--disable-all-custom-nodes",
        "--disable-metadata",
        "--disable-auto-launch",
        "--disable-api-nodes",
    ]
    creationflags = getattr(subprocess, "CREATE_NO_WINDOW", 0)
    process = subprocess.Popen(
        command,
        stdout=log,
        stderr=subprocess.STDOUT,
        text=True,
        creationflags=creationflags,
    )
    _wait_ready(60)
    return process, output_dir


def main() -> int:
    import argparse
    import hashlib

    parser = argparse.ArgumentParser()
    parser.add_argument("--out", required=True, type=Path)
    args = parser.parse_args()
    root = args.out.resolve()
    if root.exists():
        raise RuntimeError("N2B2_S20_CASE17_REMEDIATION_RUNTIME_ALREADY_EXISTS")
    root.mkdir(parents=True)
    process: subprocess.Popen[str] | None = None
    try:
        process, output_dir = _start_server(root)
        checkpoint_path = (
            Path(os.environ["NPI_COMFY_BASE_DIRECTORY"]) / "models" / "checkpoints" / CHECKPOINT
        )
        vae_path = Path(os.environ["NPI_COMFY_BASE_DIRECTORY"]) / "models" / "vae" / VAE
        entries: list[dict[str, Any]] = []
        for index, seed in enumerate(S20_CASE17_REMEDIATION_SEEDS, start=1):
            print(f"[{index}/4] generating {CASE_ID} seed={seed}", flush=True)
            prompt_id = _submit(_workflow(CASE_ID, seed, WIDTH, HEIGHT, PROMPT, NEGATIVE))
            image = _wait_output(prompt_id, output_dir)
            target = root / "candidates" / f"case17-seed-{seed}.png"
            target.write_bytes(image.read_bytes())
            entries.append(
                {
                    "case_id": CASE_ID,
                    "seed": seed,
                    "filename": target.relative_to(root).as_posix(),
                    "image_sha256": _sha(target),
                    "width": WIDTH,
                    "height": HEIGHT,
                    "generator_version": S20_CASE17_GENERATOR_VERSION,
                    "generation_parameters": {
                        "prompt": PROMPT,
                        "negative_prompt": NEGATIVE,
                        "sampler": "dpmpp_2m",
                        "scheduler": "karras",
                        "steps": 30,
                        "cfg": 6.0,
                        "denoise": 1.0,
                        "checkpoint": CHECKPOINT,
                        "checkpoint_sha256": hashlib.sha256(
                            checkpoint_path.read_bytes()
                        ).hexdigest(),
                        "vae": VAE,
                        "vae_sha256": hashlib.sha256(vae_path.read_bytes()).hexdigest(),
                        "comfyui_version": "0.19.5",
                        "port": 7865,
                        "prompt_id": prompt_id,
                    },
                }
            )
        (root / "case17_candidates.json").write_text(
            json.dumps(
                {
                    "schema_version": "n2b2-s20-case17-candidates-v1",
                    "synthetic_only": True,
                    "candidate_count": len(entries),
                    "candidates": entries,
                },
                sort_keys=True,
                indent=2,
            ),
            encoding="utf-8",
        )
        print(f"candidate_manifest: {root / 'case17_candidates.json'}", flush=True)
    finally:
        with suppress(Exception):
            _request("/free", {"unload_models": True, "free_memory": True})
        _stop_server(process)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
