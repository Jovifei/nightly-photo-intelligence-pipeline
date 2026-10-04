#!/usr/bin/env python3
"""Write photographer-spoken directions for the owner G1 reference set.

Reads F:\\npi_g1_source_ro in place. Does not copy photos into the repo.
Uses the local TorchVision keypoint weights and Ollama qwen3.5:9b, falling
back to qwen3.5:4b only when 9b fails on that image. Does not download models.
"""

from __future__ import annotations

import base64
import gc
import hashlib
import json
import sys
import time
import traceback
import urllib.request
from datetime import datetime
from io import BytesIO
from pathlib import Path
from typing import Any

from PIL import Image

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "src"))

from nightly_photo_intelligence_pipeline.direction.spoken import (  # noqa: E402
    spoken_direction_request,
    validate_spoken,
    qualitative_pose_cues,
    SPOKEN_RESPONSE_SCHEMA,
)
from nightly_photo_intelligence_pipeline.n2b2_synthetic.config import N2B2RunConfig  # noqa: E402
from nightly_photo_intelligence_pipeline.n2b2_synthetic.torchvision_loader import (  # noqa: E402
    load_backend,
)

SOURCE_DIR = Path(r"F:\npi_g1_source_ro")
CACHE_ROOT = Path(r"E:\Claude_allow\Download\npi-model-cache")
OUT_MD = Path(r"F:\npi_runtime\work\g1_pose_directions_20261004.md")
OUT_JSON = Path(r"F:\npi_runtime\work\g1_pose_directions_20261004.json")
OLLAMA = "http://127.0.0.1:11434"
PRIMARY = "qwen3.5:9b"
FALLBACK = "qwen3.5:4b"
CHANGED = [
    "src/nightly_photo_intelligence_pipeline/direction/__init__.py",
    "src/nightly_photo_intelligence_pipeline/direction/spoken.py",
    "tools/run_g1_spoken_directions.py",
    "tests/test_spoken_direction.py",
]


def anonymize(name: str, index: int) -> str:
    digest = hashlib.sha256(name.encode("utf-8", errors="replace")).hexdigest()[:8]
    return f"img-{index:02d}-{digest}"


def ollama(method: str, path: str, body: dict[str, Any] | None = None, timeout: int = 420) -> Any:
    url = f"{OLLAMA}{path}"
    data = json.dumps(body).encode("utf-8") if body is not None else None
    req = urllib.request.Request(url, data=data, method=method)
    req.add_header("Content-Type", "application/json")
    with urllib.request.urlopen(req, timeout=timeout) as resp:
        raw = resp.read().decode("utf-8")
    return json.loads(raw) if raw else {}


def unload(model: str) -> None:
    try:
        ollama("POST", "/api/generate", {"model": model, "prompt": "", "stream": False, "keep_alive": 0}, timeout=60)
    except Exception:
        pass


def image_b64(data: bytes, max_side: int = 1024) -> str:
    image = Image.open(BytesIO(data)).convert("RGB")
    image.thumbnail((max_side, max_side))
    buf = BytesIO()
    image.save(buf, format="JPEG", quality=85)
    return base64.b64encode(buf.getvalue()).decode("ascii")


def people_from_pose(pose: Any) -> list[dict[str, Any]]:
    people: list[dict[str, Any]] = []
    for box, keypoints in zip(pose.person_boxes, pose.pose_keypoints):
        people.append({"box": box, "keypoints": keypoints})
    return people


def reason(case_id: str, photo_b64: str, cues: list[str], model: str, keep_alive: int) -> dict[str, Any]:
    prompt = spoken_direction_request(case_id=case_id, pose_cues=cues)
    payload = {
        "model": model,
        "prompt": prompt,
        "images": [photo_b64],
        "stream": False,
        "think": False,
        "format": SPOKEN_RESPONSE_SCHEMA,
        "keep_alive": keep_alive,
        "options": {"num_ctx": 8192, "num_predict": 900, "temperature": 0.2, "seed": 20261004},
    }
    out = ollama("POST", "/api/generate", payload, timeout=420)
    text = out.get("response", "")
    if isinstance(text, str) and text.strip():
        parsed = json.loads(text)
    elif isinstance(text, dict):
        parsed = text
    else:
        raise ValueError("empty VLM response")
    parsed.pop("thinking", None)
    for key in ("spoken_direction", "simpler_alternative"):
        value = parsed.get(key)
        if not isinstance(value, str):
            continue
        kept = []
        for line in value.splitlines():
            low = line.strip().lower()
            if low.startswith("simpler_alternative") or low.startswith("spoken_direction"):
                continue
            kept.append(line)
        parsed[key] = "\n".join(kept).strip()
    error = validate_spoken(parsed, case_id=case_id)
    if error:
        raise ValueError(error)
    return parsed


def detect_all(blobs: list[bytes]) -> list[Any]:
    import torch

    device = "cuda" if torch.cuda.is_available() else "cpu"
    cfg = N2B2RunConfig(
        project_root=ROOT,
        cache_root=CACHE_ROOT,
        fixtures_dir=ROOT / "fixtures",
        runtime_out_dir=OUT_JSON.parent,
        backend="real",
        device=device,  # type: ignore[arg-type]
    )
    backend = load_backend("real", cfg.cache_root, cfg.cache_subdirs, device=device)
    results = []
    try:
        for blob in blobs:
            results.append(backend.detect_pose(blob))
    finally:
        backend.unload()
        gc.collect()
        if torch.cuda.is_available():
            torch.cuda.empty_cache()
    return results


def main() -> int:
    OUT_MD.parent.mkdir(parents=True, exist_ok=True)
    files = sorted(SOURCE_DIR.glob("*.jpg"), key=lambda p: p.name.encode("utf-8", "replace"))
    if len(files) != 19:
        print(f"expected 19 jpg, found {len(files)}", file=sys.stderr)
        return 2
    metas: list[dict[str, Any]] = []
    blobs: list[bytes] = []
    for index, path in enumerate(files, start=1):
        data = path.read_bytes()
        with Image.open(BytesIO(data)) as image:
            width, height = image.size
        metas.append({"case_id": anonymize(path.name, index), "width": width, "height": height})
        blobs.append(data)
    print(f"[pose] {len(blobs)} images", flush=True)
    poses = detect_all(blobs)
    items: list[dict[str, Any]] = []
    for index, (meta, blob, pose) in enumerate(zip(metas, blobs, poses), start=1):
        cues = qualitative_pose_cues(people_from_pose(pose), meta["width"], meta["height"])
        photo = image_b64(blob)
        keep = 300 if index < len(metas) else 0
        print(f"[qwen {index}/{len(metas)}] {meta['case_id']}", flush=True)
        model_used = PRIMARY
        error = None
        parsed: dict[str, Any] | None = None
        started = time.perf_counter()
        try:
            parsed = reason(meta["case_id"], photo, cues, PRIMARY, keep)
        except Exception as exc9:
            print(f"  9b failed: {exc9}; fallback 4b", flush=True)
            traceback.print_exc()
            unload(PRIMARY)
            try:
                parsed = reason(meta["case_id"], photo, cues, FALLBACK, keep)
                model_used = FALLBACK
                error = f"9b_failed:{type(exc9).__name__}:{exc9}"
            except Exception as exc4:
                error = f"9b:{exc9}; 4b:{exc4}"
                print(f"  4b failed: {exc4}", flush=True)
        seconds = round(time.perf_counter() - started, 1)
        item = {
            "case_id": meta["case_id"],
            "spoken_direction": (parsed or {}).get("spoken_direction"),
            "simpler_alternative": (parsed or {}).get("simpler_alternative"),
            "model": model_used if parsed else None,
            "seconds": seconds,
            "error": error,
            "internal": {"pose_cues": cues},
        }
        items.append(item)
        OUT_JSON.write_text(
            json.dumps({"partial": True, "items": items}, ensure_ascii=False, indent=2),
            encoding="utf-8",
        )
    unload(PRIMARY)
    unload(FALLBACK)
    finished = datetime.now().astimezone().isoformat(timespec="seconds")
    ok9 = sum(1 for item in items if item["model"] == PRIMARY)
    ok4 = sum(1 for item in items if item["model"] == FALLBACK)
    failed = sum(1 for item in items if not item["spoken_direction"])
    document = {
        "schema_version": "g1-spoken-direction-v1",
        "generated_at": finished,
        "source": "F:/npi_g1_source_ro read-only; filenames anonymized",
        "product": "photographer-spoken direction",
        "not_product": ["person_count", "pose_score", "mask_ratio"],
        "models": {"pose": "torchvision-keypointrcnn-resnet50-fpn-coco-v1", "vlm_primary": PRIMARY, "vlm_fallback": FALLBACK},
        "counts": {"images": len(items), "qwen9": ok9, "qwen4": ok4, "failed": failed},
        "repo_changes_uncommitted": CHANGED,
        "items": items,
    }
    OUT_JSON.write_text(json.dumps(document, ensure_ascii=False, indent=2), encoding="utf-8")
    lines = [
        "# G1 拍摄口播方向（2026-10-04）",
        "",
        f"- 生成时间: {finished} (Asia/Shanghai)",
        "- 源目录只读: `F:/npi_g1_source_ro`。正文只有匿名 case_id，没有原文件名。",
        "- 产品是摄影师可以口头说出来的指导，让模特照着做。人数、姿态分数、遮罩占比不是产品，不写进口播。",
        "- 姿态关键点来自本地 TorchVision 权重（未下载）。口播来自 Ollama `qwen3.5:9b`，单张失败才回退 `qwen3.5:4b`。",
        f"- qwen3.5:9b 成功 {ok9}，回退 4b {ok4}，失败 {failed}。",
        "- 未启动 Real20 生产解锁。未改 `MASTER_EXECUTION_CONTRACT.md` 和 `PROJECT_STATE.json`。未把照片复制进 git。",
        "- 仓库工作区改动（未提交）:",
    ]
    for rel in CHANGED:
        lines.append(f"  - `{rel}`")
    lines.append("- 运行入口: `tools/run_g1_spoken_directions.py`。它复用 `direction/spoken.py` 和现有 TorchVision loader，不改 N2B2 合同。")
    lines.append("")
    for item in items:
        lines.append(f"## {item['case_id']}")
        lines.append("")
        if item["spoken_direction"]:
            lines.append(item["spoken_direction"].strip())
            lines.append("")
            lines.append(f"如果做不到：{item['simpler_alternative'].strip()}")
        else:
            lines.append(f"（这张没有生成口播：{item['error']}）")
        lines.append("")
        lines.append(f"模型: {item['model'] or '无'}")
        lines.append("")
    OUT_MD.write_text("\n".join(lines), encoding="utf-8")
    print(f"Wrote {OUT_MD}")
    print(f"qwen9={ok9} qwen4={ok4} failed={failed}")
    return 0 if failed == 0 else 1


if __name__ == "__main__":
    raise SystemExit(main())