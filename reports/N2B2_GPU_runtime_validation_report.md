# N2B2 GPU Runtime Validation — 2026-08-09

## Current stop

`N2B2_GPU_RUNTIME_VALIDATION_COMPLETE_AWAITING_OWNER_REVIEW`

This is a bounded synthetic runtime validation result and is not N2B2 phase
completion. `PROJECT_STATE.json` remains unchanged and `N2B2=LOCKED`.

## Authoritative v2 evidence

The following Git-external evidence was rehashed before closure. Paths are
intentionally redacted as `EXTERNAL_RUNTIME_WORK/...`:

| Evidence | Bytes | SHA-256 |
|---|---:|---|
| `EXTERNAL_RUNTIME_WORK/retry_summary.json` | 25297 | `e48bf9091efffc2e1100a025636b5ea347687044f1dc00acd160153434ccbbcd` |
| `EXTERNAL_RUNTIME_WORK/gpu/gpu_runtime_metrics.json` | 47126 | `e3498356d1f867e3b908c41c1dc329b816aeaed654c55b8c6fc226da59eee9bf` |
| `EXTERNAL_RUNTIME_WORK/s3-run/validation_summary.json` | 67260 | `226d6f5b1525da025d8800c85eaab799415c93e1574a39f310e10a51530427ef` |
| `EXTERNAL_RUNTIME_WORK/ollama/ollama_identity.json` | 1367 | `2a736b4b81ce2cbd5a2d7caecf526ffb4a872bf0365e6e74c9bc0f944604f7c0` |
| `EXTERNAL_RUNTIME_WORK/ollama/ollama_ps_samples.jsonl` | 53507 | `3e2630b15607811faf875976357954fe36f24c2ffa2f4a9b006435f9b7e44536` |
| `EXTERNAL_RUNTIME_WORK/cleanup/cleanup_evidence.json` | 461 | `fc07117027d01ea6f4dc606b359839b57225d75bb0339ba1c2a05434235ae758` |
| `EXTERNAL_RUNTIME_WORK/process/process_evidence.json` | 89209 | `91d32dadfab51d4a0c1275fe9df014036bfde7a41ac3e885bef3554ad7ad1ab3` |
| `EXTERNAL_RUNTIME_WORK/selected/fixture_manifest.json` | 3967 | `d1f90db50e0a3c7da911ce25861fdfbe0f454427cf760b52e46e334532a7a2be` |

The metrics file passes `n2b2_gpu_runtime_metrics.schema.json`. The frozen
selected fixture hashes remain:

- A: `b6283220300ff1cf5edff74624939c0717c0043e21edbd18858bff617aa2914d`
- B: `2dc3fa1cf72b23fd1230c0a2509f6a04e8b47378b2949151a6203e60e405942e`
- C: `ac425446fa89f192a78d24fd3d9f88687c5e7b5bbec3815f3a06f7523e52669a`

## GPU result

- GPU: RTX 4070 SUPER, 12282 MiB.
- Admission: `2928 MiB <= 10476 MiB`.
- Driver-reported CUDA: `13.2`; PyTorch: `2.7.1+cu128`; TorchVision:
  `0.22.1+cu128`.
- Runtime baseline: `3079 MiB`; total peak: `10111 MiB`; after TorchVision
  unload: `3062 MiB`.
- Keypoint R-CNN, LRASPP and DeepLabV3: requested `cuda`, effective
  `cuda:0`, model/input/raw output on `cuda:0`, `float32`, `fallback=false`.
- Approximate GPU probe peak allocated: Pose `680 MiB`, LRASPP `172 MiB`,
  DeepLab `245 MiB`. Each model was explicitly unloaded before the next
  stage and no TorchVision role remained for Qwen.

## Qwen result

- Model: `qwen3.5:9b`.
- Digest:
  `6488c96fa5faab64bb65cbd30d4289e20e6130ef535a93ef9a49f42eda893ea7`.
- Quantization: `Q4_K_M`; vision capability: present.
- Residency: 93 samples; `size_vram=5880141577 bytes`.
- Schema: PASS; fact-digest echo: PASS; valid fact IDs: PASS; forbidden
  fields: `0`; explicit unload and `/api/ps` empty-state confirmation: PASS.

## Historical failed attempt

The first GPU admission attempt remains part of the evidence history:

`N2B2_GPU_RUNTIME_UNAVAILABLE: INSUFFICIENT_EXCLUSIVE_HEADROOM`

Its measured baseline was `11066 MiB`, above the `10476 MiB` admission
threshold. No unrelated process was stopped and no model was loaded in that
attempt. It is not overwritten by the v2 result.

## Boundaries and counters

```text
REAL_PHOTO_READ_COUNT=0
REAL_EXIF_READ_COUNT=0
G1_SOURCE_ACCESS=0
SQLITE_WRITE_COUNT=0
APP_WRITE_COUNT=0
OBSIDIAN_WRITE_COUNT=0
MODEL_DOWNLOAD_BYTES=0
S20_TECHNICAL_PREPARATION=READY
S20_EXECUTION_STATUS=NOT_PERFORMED
S20_FIXTURE_MANIFEST_INSTANCE=NOT_CREATED
S20_EXTERNAL_REVIEW_AND_OWNER_APPROVAL_REQUIRED=true
N2B2_STATE=LOCKED
```

No real photos, EXIF, G1, SQLite ingest, App, Obsidian, S20, model download,
push, merge, release or PROJECT_STATE mutation occurred. The review-candidate
commit is created only after the clean candidate quality gates pass.
