# N2B2 Owner Inputs and Limits

**Owner:** Jovi
**Date:** 2026-08-05
**Authorization:** N2B2_SYNTHETIC_MODEL_STACK_VALIDATION
**Owner decision:** Choice A

---

## 1. Model stack decision

| Layer | Model | Role | Runtime |
|---|---|---|---|
| Deterministic vision | Keypoint R-CNN ResNet-50 FPN COCO V1 | POSE_BASELINE_SMOKE | Native Windows PyTorch |
| Deterministic vision | LRASPP MobileNetV3-Large | SEGMENTATION_PRIMARY | Native Windows PyTorch |
| Deterministic vision | DeepLabV3 MobileNetV3-Large | SEGMENTATION_QUALITY_COMPARATOR | Native Windows PyTorch |
| Photography reasoning | qwen3.5:9b | PHOTOGRAPHY_REASONING_MODEL | Local Ollama loopback (Q4_K_M) |

### Superseded

| Model | Status |
|---|---|
| Qwen/Qwen3-VL-2B-Instruct | SUPERSEDED_FOR_N2B2_SYNTHETIC_VALIDATION / NOT_DOWNLOADED / NOT_EXECUTED |

### Prohibited model operations

- `ollama pull` — prohibited
- Downloading any Qwen model — prohibited
- `ollama create` — prohibited
- `ollama copy` / `ollama delete` — prohibited
- TorchVision automatic download — prohibited
- Dual-model A/B (9B vs 2B) — not performed this round
- Describing Q4_K_M as BF16 — prohibited

---

## 2. Runtime limits

### 2.1 Ollama endpoint

- Only `http://127.0.0.1:11434`
- No cloud, remote host, proxy, or non-loopback port
- Image transport: in-memory base64 bytes, no absolute path

### 2.2 Request parameters

| Parameter | Value |
|---|---|
| stream | false |
| think | false |
| format | strict JSON Schema |
| single image | true |
| temperature | 0 |
| num_ctx | 8192 |
| num_predict | ≤ 1200 |
| image long side | ≤ 1024 |
| seed | fixed stage seed if supported; else SEED_NOT_AVAILABLE |

### 2.3 Model residency

- Qwen may stay loaded during S3/S20 serial execution
- After stage: `keep_alive=0`
- Verify unload via `/api/ps` + GPU baseline
- TorchVision and Qwen must never co-reside

### 2.4 Identity requirements

| Field | Required value |
|---|---|
| model_name | qwen3.5:9b |
| vision capability | present |
| quantization_level | Q4_K_M |

Must record from actual `/api/tags`, `/api/show`, `ollama show`:
model_name, full_local_digest, size_bytes, format, family, parameter_size,
quantization_level, capabilities, license, modified_at, ollama_version.

---

## 3. GPU and resource thresholds

| Metric | Limit |
|---|---|
| Absolute GPU used | ≤ 11,500 MiB |
| Pose single image | ≤ 60 s |
| Segmentation single image | ≤ 60 s |
| Qwen cold load | ≤ 180 s |
| Qwen steady single image | ≤ 120 s |

### Unload verification (within 60 s)

- `/api/ps` no longer lists qwen3.5:9b
- GPU used ≤ pre-Qwen baseline + 1,024 MiB

### Stop on any

OOM, timeout, system memory exhaustion, model unload failure, GPU not falling
back, Ollama queue/503, fact inconsistency.

---

## 4. Data gate

| Counter | Value |
|---|---|
| REAL_PHOTO_READ_COUNT | 0 |
| REAL_EXIF_READ_COUNT | 0 |
| G1_SOURCE_ACCESS | 0 |
| SQLITE_WRITE_COUNT | 0 |
| APP_WRITE_COUNT | 0 |
| OBSIDIAN_WRITE_COUNT | 0 |

### Prohibited data access

- G1 Snapshot
- Billfish
- Real collection images
- User photos
- EXIF
- SQLite real task data
- App data
- Obsidian sync

### Synthetic fixture gate

- S3: 3 images (single-person, multi-person/occlusion, no-person negative)
- S20: 20 images (fixed case matrix, frozen fields)
- All synthetic images and outputs in Git-external controlled runtime

---

## 5. Qwen output contract

### Allowed output fields

- input_fact_digest
- reasoning_based_on_fact_ids
- photographic_interpretation
- story_candidates (safe, narrative, dynamic)
- director_prompts (standard, dramatic, plan_b, technical)
- uncertainties

### Forbidden output fields (count must be 0)

- person_count
- bbox
- keypoints
- mask
- pose_confidence
- segmentation_confidence
- EXIF
- exact_focal_length
- exact_camera_distance
- copyright_status
- real_mental_state

### Validation rules

- `output.input_fact_digest == input fact_digest`
- All referenced fact_ids exist
- Forbidden field count == 0
- Conflicts must enter `uncertainties`, not overwrite facts

---

## 6. Boundary: what N2B2 does NOT authorize

- Real 20-photo benchmark
- G1 renewal
- RTMW
- RTMDet
- SAM2
- App deployment
- Obsidian sync
- G2
- N3
- Push, merge, PR, release
- Self-approving N2B1P

---

## 7. Stop conditions

| Condition | Status string |
|---|---|
| Success | N2B2_SYNTHETIC_MODEL_STACK_VALIDATION_COMPLETE_AWAITING_EXTERNAL_REVIEW |
| N2B1P not approved (current) | N2B2_EXECUTION_BLOCKED_N2B1P_NOT_APPROVED |
| Qwen identity mismatch | N2B2_LOCAL_QWEN_IDENTITY_MISMATCH |
| Vision capability missing | N2B2_LOCAL_QWEN_VISION_CAPABILITY_MISSING |
| Fixture insufficient | N2B2_SYNTHETIC_FIXTURE_CAPABILITY_INSUFFICIENT |
| GPU exceeded | N2B2_GPU_LIMIT_EXCEEDED |
| Fact immutability violation | N2B2_FACT_IMMUTABILITY_VIOLATION |
| Schema/provenance failure | N2B2_QWEN_SCHEMA_OR_PROVENANCE_FAILED |
| Model unload failure | N2B2_MODEL_UNLOAD_FAILED |
| Changes required | N2B2_CHANGES_REQUIRED |
