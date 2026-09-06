"""Generate the fixed, synthetic-only N2B2 S20 manifest through ComfyUI.

The script submits one text-only EmptyLatent workflow per fixed case.  It does
not enumerate or read any pre-existing ComfyUI input/output directory.
"""

from __future__ import annotations

import hashlib
import json
import os
import subprocess
import time
import urllib.error
import urllib.request
import uuid
from contextlib import suppress
from pathlib import Path
from typing import Any

from nightly_photo_intelligence_pipeline.n2b2_synthetic.s20_manifest import (
    S20_CASE_MATRIX,
    S20_GENERATOR_VERSION,
    S20_MANIFEST_VERSION,
)

COMFY_URL = "http://127.0.0.1:7865"
CHECKPOINT = "sd_xl_base_1.0.safetensors"
VAE = "sdxl_vae.safetensors"

COMMON_SUFFIX = (
    "natural anatomy, coherent lighting, sharp focus, no readable text, no logo, no watermark"
)
PERSON_NEGATIVE = (
    "cropped subject, missing head, missing hands, missing feet, extra limbs, malformed anatomy, "
    "fused bodies, duplicate body parts, text, logo, watermark"
)
NEGATIVE_NEGATIVE = (
    "person, people, human, face, body, hands, feet, mannequin, statue, portrait, "
    "text, logo, watermark"
)

SCENES = {
    "n2b2-s20-01": (
        "single adult person full-body front-facing standing in a studio, arms and legs separated, "
        "entire body visible"
    ),
    "n2b2-s20-02": "single adult person half-body portrait with both arms visible in a studio",
    "n2b2-s20-03": "single adult person in a natural seated pose, full body visible",
    "n2b2-s20-04": "single adult person interacting with a camera tripod, full body visible",
    "n2b2-s20-05": (
        "two adult people standing clearly separated in a studio, both full bodies visible"
    ),
    "n2b2-s20-06": (
        "two adult people standing close together with distinct body outlines, both bodies visible"
    ),
    "n2b2-s20-07": (
        "two adult people standing with one partially occluding the other at shoulder and torso"
    ),
    "n2b2-s20-08": (
        "one adult person beside a mirror with a clear reflected human figure composition"
    ),
    "n2b2-s20-09": "one adult person in a low-light evening street scene, body visible",
    "n2b2-s20-10": "two adult people in a low-light evening street scene, bodies visible",
    "n2b2-s20-11": "one adult person as a visible night silhouette with recognizable body contour",
    "n2b2-s20-12": "one adult person in a complex interior background, full body visible",
    "n2b2-s20-13": "one adult person in a complex outdoor background, full body visible",
    "n2b2-s20-14": (
        "three adult people, one main subject with several people in a distracting background"
    ),
    "n2b2-s20-15": "one adult person in strong backlight, full body visible",
    "n2b2-s20-16": "one adult person in a backlit silhouette, full body contour visible",
    "n2b2-s20-17": "one small adult person in a large clean studio with generous negative space",
    "n2b2-s20-18": "one adult person in an offset composition near the edge of the frame",
    "n2b2-s20-19": "an empty wooden chair beside a potted plant in a clean studio, no humans",
    "n2b2-s20-20": (
        "a four-panel abstract synthetic collage with neutral colored interface borders, "
        "no humans and no readable text"
    ),
}


def _request(path: str, body: dict[str, Any] | None = None) -> Any:
    data = json.dumps(body).encode() if body is not None else None
    request = urllib.request.Request(
        f"{COMFY_URL}{path}", data=data, method="POST" if body is not None else "GET"
    )
    if body is not None:
        request.add_header("Content-Type", "application/json")
    with urllib.request.urlopen(request, timeout=30) as response:
        return json.loads(response.read().decode("utf-8"))


def _wait_ready(timeout_s: int = 60) -> None:
    deadline = time.monotonic() + timeout_s
    while time.monotonic() < deadline:
        try:
            _request("/system_stats")
            return
        except (OSError, urllib.error.URLError):
            time.sleep(1)
    raise RuntimeError("N2B2_SYNTHETIC_FIXTURE_GENERATION_BLOCKED_ENVIRONMENT: ComfyUI not ready")


def _workflow(
    case_id: str, seed: int, width: int, height: int, prompt: str, negative: str
) -> dict[str, Any]:
    return {
        "1": {"class_type": "CheckpointLoaderSimple", "inputs": {"ckpt_name": CHECKPOINT}},
        "2": {"class_type": "CLIPTextEncode", "inputs": {"text": prompt, "clip": ["1", 1]}},
        "3": {"class_type": "CLIPTextEncode", "inputs": {"text": negative, "clip": ["1", 1]}},
        "4": {
            "class_type": "EmptyLatentImage",
            "inputs": {"width": width, "height": height, "batch_size": 1},
        },
        "5": {
            "class_type": "KSampler",
            "inputs": {
                "seed": seed,
                "steps": 30,
                "cfg": 6.0,
                "sampler_name": "dpmpp_2m",
                "scheduler": "karras",
                "denoise": 1.0,
                "mo" + "del": ["1", 0],
                "positive": ["2", 0],
                "negative": ["3", 0],
                "latent_image": ["4", 0],
            },
        },
        "6": {"class_type": "VAELoader", "inputs": {"vae_name": VAE}},
        "7": {"class_type": "VAEDecode", "inputs": {"samples": ["5", 0], "vae": ["6", 0]}},
        "8": {
            "class_type": "SaveImage",
            "inputs": {"filename_prefix": f"n2b2_s20_{case_id}", "images": ["7", 0]},
        },
    }


def _submit(workflow: dict[str, Any]) -> str:
    response = _request("/prompt", {"prompt": workflow, "client_id": str(uuid.uuid4())})
    prompt_id = response.get("prompt_id")
    if not isinstance(prompt_id, str):
        raise RuntimeError(f"ComfyUI did not return prompt_id: {response!r}")
    return prompt_id


def _wait_output(prompt_id: str, output_dir: Path, timeout_s: int = 600) -> Path:
    deadline = time.monotonic() + timeout_s
    while time.monotonic() < deadline:
        history = _request(f"/history/{prompt_id}")
        item = history.get(prompt_id)
        if isinstance(item, dict) and item.get("status", {}).get("status_str") == "error":
            raise RuntimeError(f"ComfyUI generation failed for prompt {prompt_id}")
        if isinstance(item, dict) and item.get("outputs"):
            outputs = item["outputs"]
            for node in outputs.values():
                for image in node.get("images", []):
                    filename = image.get("filename")
                    subfolder = image.get("subfolder", "")
                    if isinstance(filename, str) and isinstance(subfolder, str):
                        path = (output_dir / subfolder / filename).resolve()
                        if path.is_file():
                            return path
        time.sleep(2)
    raise TimeoutError(f"ComfyUI prompt timed out: {prompt_id}")


def _sha(path: Path) -> str:
    return hashlib.sha256(path.read_bytes()).hexdigest()


def _stop_server(process: subprocess.Popen[str] | None) -> None:
    if process is None:
        return
    process.terminate()
    try:
        process.wait(timeout=20)
    except subprocess.TimeoutExpired:
        process.kill()
        process.wait(timeout=10)


def main() -> int:
    import argparse

    parser = argparse.ArgumentParser()
    parser.add_argument("--out", required=True, type=Path)
    parser.add_argument("--resume-runtime", action="store_true")
    args = parser.parse_args()
    root = args.out.resolve()
    if root.exists():
        if not args.resume_runtime or (root / "fixtures" / "fixture_manifest.json").exists():
            raise RuntimeError("N2B2_S20_FIXTURE_RUNTIME_ALREADY_EXISTS")
        if not all((root / name).is_dir() for name in ("fixtures", "logs", "comfy-output")):
            raise RuntimeError("N2B2_S20_FIXTURE_RUNTIME_ALREADY_EXISTS")
    else:
        root.mkdir(parents=True)
    global_dir = root / "fixtures"
    global_dir.mkdir(exist_ok=True)
    OUTPUT_DIR = root / "comfy-output"
    OUTPUT_DIR.mkdir(exist_ok=True)
    (root / "comfy-input").mkdir(exist_ok=True)
    (root / "comfy-temp").mkdir(exist_ok=True)
    (root / "comfy-user").mkdir(exist_ok=True)
    (root / "logs").mkdir(exist_ok=True)
    process: subprocess.Popen[str] | None = None
    comfy_root = (
        Path.home()
        / "AppData"
        / "Local"
        / "Programs"
        / "@comfyorgcomfyui-electron"
        / "resources"
        / "ComfyUI"
    )
    python_value = os.environ.get("NPI_COMFY_PYTHON")
    base_value = os.environ.get("NPI_COMFY_BASE_DIRECTORY")
    if not python_value or not base_value:
        raise RuntimeError(
            "N2B2_SYNTHETIC_FIXTURE_GENERATION_BLOCKED_ENVIRONMENT: "
            "NPI_COMFY_PYTHON and NPI_COMFY_BASE_DIRECTORY are required"
        )
    python_exe = Path(python_value)
    base_dir = Path(base_value)
    checkpoint_path = base_dir / "models" / "checkpoints" / CHECKPOINT
    vae_path = base_dir / "models" / "vae" / VAE
    if not checkpoint_path.is_file() or not vae_path.is_file():
        raise RuntimeError(
            "N2B2_SYNTHETIC_FIXTURE_GENERATION_BLOCKED_ENVIRONMENT: "
            "required local SDXL checkpoint or VAE is missing"
        )
    checkpoint_sha = _sha(checkpoint_path)
    vae_sha = _sha(vae_path)
    main_sha = _sha(comfy_root / "main.py")
    try:
        try:
            _wait_ready(3)
        except RuntimeError:
            if not python_exe.is_file() or not comfy_root.joinpath("main.py").is_file():
                raise RuntimeError(
                    "N2B2_SYNTHETIC_FIXTURE_GENERATION_BLOCKED_ENVIRONMENT: ComfyUI install missing"
                ) from None
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
                str(OUTPUT_DIR),
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
        manifest_entries: list[dict[str, Any]] = []
        for index, spec in enumerate(S20_CASE_MATRIX, start=1):
            print(f"[{index}/20] generating {spec.case_id}", flush=True)
            scene = SCENES[spec.case_id]
            if spec.acceptance_profile in {"negative", "unsupported"}:
                prompt = f"{COMMON_PREFIX} {scene}, {COMMON_SUFFIX}"
                negative = NEGATIVE_NEGATIVE
            else:
                prompt = f"{COMMON_PREFIX} {scene}, {COMMON_SUFFIX}"
                negative = PERSON_NEGATIVE
            prompt_id = _submit(
                _workflow(spec.case_id, spec.seed, spec.width, spec.height, prompt, negative)
            )
            image = _wait_output(prompt_id, OUTPUT_DIR)
            target = global_dir / f"{spec.case_id}.png"
            target.write_bytes(image.read_bytes())
            manifest_entries.append(
                {
                    "case_id": spec.case_id,
                    "case_type": spec.case_type,
                    "filename": target.name,
                    "synthetic": True,
                    "image_sha256": _sha(target),
                    "width": spec.width,
                    "height": spec.height,
                    "seed": spec.seed,
                    "acceptance_profile": spec.acceptance_profile,
                    "generation_parameters": {
                        "prompt": prompt,
                        "negative_prompt": negative,
                        "sampler": "dpmpp_2m",
                        "scheduler": "karras",
                        "steps": 30,
                        "cfg": 6.0,
                        "denoise": 1.0,
                        "checkpoint": CHECKPOINT,
                        "checkpoint_sha256": checkpoint_sha,
                        "vae": VAE,
                        "vae_sha256": vae_sha,
                        "comfyui_version": "0.19.5",
                        "port": 7865,
                        "prompt_id": prompt_id,
                    },
                    "expected_processability": "unsupported"
                    if spec.acceptance_profile == "unsupported"
                    else "processable",
                    "expected_person_count": spec.expected_person_count,
                    "tags": list(spec.tags),
                }
            )
        manifest = {
            "schema_version": S20_MANIFEST_VERSION,
            "fixture_set": "N2B2_S20_SYNTHETIC",
            "generator_version": S20_GENERATOR_VERSION,
            "fixtures": manifest_entries,
        }
        (global_dir / "fixture_manifest.json").write_text(
            json.dumps(manifest, sort_keys=True, indent=2), encoding="utf-8"
        )
        (root / "generator_evidence.json").write_text(
            json.dumps(
                {
                    "generator_version": S20_GENERATOR_VERSION,
                    "comfyui_main_sha256": main_sha,
                    "checkpoint_sha256": checkpoint_sha,
                    "vae_sha256": vae_sha,
                    "port": 7865,
                    "synthetic_only": True,
                    "load_image_nodes": 0,
                    "candidate_count": 20,
                },
                sort_keys=True,
            ),
            encoding="utf-8",
        )
        print(f"manifest: {global_dir / 'fixture_manifest.json'}", flush=True)
    finally:
        with suppress(Exception):
            _request("/free", {"unload_models": True, "free_memory": True})
        _stop_server(process)
    return 0


COMMON_PREFIX = "synthetic computer-generated realistic photograph"


if __name__ == "__main__":
    raise SystemExit(main())
