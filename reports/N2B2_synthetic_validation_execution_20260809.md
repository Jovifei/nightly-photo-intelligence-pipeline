# N2B2 Synthetic Model-Stack Execution — 2026-08-09

## Result

`PARTIAL`

Stop state:

`N2B2_SYNTHETIC_FIXTURE_CAPABILITY_INSUFFICIENT`

The run stopped after the 3-case smoke gate. The 20-case validation was not
started because the smoke set produced no person-positive Keypoint R-CNN fact.

## Scope and authorization

- Owner Jovi authorized this named N2B2 synthetic-only continuation.
- Model: local Ollama `qwen3.5:9b`, `Q4_K_M`, vision capability present.
- Deterministic vision: Keypoint R-CNN, LRASPP, and DeepLabV3 from the three
  existing evidence-bound TorchVision cache payloads.
- Qwen3-VL-2B was not downloaded, loaded, or used.
- No project state unlock, G1 renewal, real-photo access, or adjacent phase was
  performed.

## Gate evidence

| Gate | Status | Evidence |
|---|---|---|
| N2B1P evidence binding | PASS_FOR_THIS_RUN | Evidence record has `review_verdict=PASS`; Owner continuation received |
| TorchVision cache | PASS | Three approved entries reported `CACHE_HIT` |
| Ollama identity | PASS | `qwen3.5:9b`, Q4_K_M, vision, local digest recorded |
| Synthetic fixture freeze | PASS | External deterministic S3=3 and S20=20 manifests; S3 includes one negative control |
| S3 Pose capability | FAIL | All three procedural probe images returned `person_count=0` |
| S20 validation | NOT_PERFORMED | Required S3 gate did not pass |

## Hard counters

```text
REAL_PHOTO_READ_COUNT=0
REAL_EXIF_READ_COUNT=0
G1_SOURCE_ACCESS=0
SQLITE_WRITE_COUNT=0
APP_WRITE_COUNT=0
OBSIDIAN_WRITE_COUNT=0
MODEL_DOWNLOAD_BYTES=0
```

Qwen schema/provenance checks in the bounded repository-fixture attempt had
zero forbidden fields and valid fact-digest/fact-id checks. That does not
override the failed person-positive S3 gate.

## Runtime changes

Only N2B2 runtime binding defects were corrected:

- Bind the approved Git-external cache root and exact evidence-bound filenames.
- Correct the DeepLab cache directory; the unrelated Qwen3-VL-2B cache entry
  was not used.
- Load cached TorchVision state dictionaries without a download-capable model
  constructor path and release each model before the next family.
- Read Ollama capabilities from `/api/show`.
- Add an external S3 manifest input matching the existing S20 manifest input.
- Mark unrun quality gates and unmeasured GPU VRAM as `NOT_PERFORMED` /
  `NOT_MEASURED` rather than claiming runtime PASS.

## Verification

- Focused N2B2 tests: `21 passed`, then `25 passed` with N2B1P integrity tests.
- Ruff check and format check: PASS for changed N2B2 files.
- `git diff --check`: PASS.
- Full pytest: `493 passed, 3 failed`; the three failures were the clean-tree
  and current MANIFEST.sha256 governance checks caused by the uncommitted
  in-scope changes and retained user handoff zip.
- Unified quality gate: `5 PASS, 2 FAIL`; Ruff, format, mypy, schema, and
  sensitive scan passed; pytest and contract-integrity failed at that same
  governance boundary.
- No commit, push, merge, release, or phase-state self-unlock.

Next action is external review of this partial result and a future approved
synthetic fixture capable of producing real person-positive Pose facts. No
real-photo substitute is permitted.

## N2B2 synthetic fixture remediation v3 - 2026-08-09

### Runtime result

`N2B2_SYNTHETIC_SMOKE_VALIDATION_COMPLETE_AWAITING_OWNER_REVIEW`

Git governance remains:

`N2B2_GIT_GOVERNANCE_TRANSITION_REQUIRED`

Overall result: `PARTIAL` because this worktree cannot update the historical
N2B1P MANIFEST/topology and no commit was created.

- HEAD: `9b3d5a1cc4a6f81467ad98034ca8994d1ebab043`
- Branch: `codex/n2b2-fixture-remediation`
- Commit SHA: `NOT_CREATED`
- Original stash: preserved and not re-applied during this continuation
- External runtime: `EXTERNAL_RUNTIME_WORK/n2b2-fixture-remediation-20260809-v3`
- ComfyUI: Desktop 0.19.5 source, isolated loopback port `7865`
- Old v2 runtime and `OLD_FIXTURE_SET: INSUFFICIENT_FOR_POSE` evidence: preserved

### Selected fixtures

| Case | Seed | SHA-256 | Pose |
|---|---:|---|---|
| `n2b2-s3-01` single person | 2026080901 | `b6283220300ff1cf5edff74624939c0717c0043e21edbd18858bff617aa2914d` | 1 person, 1 complete 17-point group |
| `n2b2-s3-02` multi/occluded | 2026080911 | `2dc3fa1cf72b23fd1230c0a2509f6a04e8b47378b2949151a6203e60e405942e` | 2 people, 2 complete 17-point groups |
| `n2b2-s3-03` negative control | 2026080921 | `ac425446fa89f192a78d24fd3d9f88687c5e7b5bbec3815f3a06f7523e52669a` | 0 people, no keypoints |

Generator: `npi-comfyui-0.19.5-sdxl-base-1.0-s3-v3`. The selected manifest
SHA-256 is recorded in the external `selected_capability_report.json`.

### S3 evidence

- Pose: A `person_count=1`, B `person_count=2`, C `person_count=0`; all
  positive detections have complete 17-point keypoint groups.
- LRASPP person ratios: A `0.005129`, B `0.198349`, C `0.0`.
- DeepLab comparator person ratios: A `0.018611`, B `0.203776`, C `0.0`.
- Facts: repeated canonical facts are byte-identical and digest-stable.
- Qwen: `qwen3.5:9b`, Q4_K_M, vision capability, schema `PASS`, digest echo
  `true`, valid fact IDs `true`, forbidden field count `0`.
- Stage order: Pose batch/unload, LRASPP batch/unload, DeepLab batch/unload,
  repeated vision chain, Qwen batch/unload.
- S20: `NOT_PERFORMED_S3_ONLY`.

### GPU and process evidence

- Pre-generation desktop baseline: `3886 MiB`; post-ComfyUI stop: `3551 MiB`.
- S3 summary: baseline `3777 MiB`, peak `3777 MiB`, after TorchVision unload
  `3896 MiB`; Ollama reported VRAM `0` and `/api/ps` was clear after unload.
- The repository RealTorchVisionBackend does not move models to CUDA, so this
  run does not prove CUDA residency for Pose/Seg. ComfyUI generation used the
  local RTX 4070 SUPER, but generation peak was not sampled and is therefore
  `NOT_MEASURED`.
- User-owned ComfyUI port `8000` remained running. Luna stopped only its own
  ComfyUI `7865` and Ollama `11434` processes.

### Quality gates

- Focused remediation tests: `26 passed`.
- Full pytest: `497 passed / 4 governance failures`.
- Ruff: `PASS`.
- Ruff format: `PASS`.
- Mypy: `PASS`.
- `tools/run_quality.py`: `5 PASS / 2 FAIL`; failures were pytest and
  contract-integrity at the same governance boundary.
- Sensitive scan: `PASS`, `0 violations`.
- Preflight: `13 PASS / 2 FAIL`; failures were archival handoff baseline and
  git-stage baseline, not runtime S3 behavior.
- Main worktree handoff: `5 PASS / 0 FAIL`.
- Remediation worktree handoff: `4 PASS / 1 FAIL`; historical MANIFEST hashes
  do not include the uncommitted N2B2 candidate changes.
- `git diff --check`: `PASS`.

### Hard boundaries

```text
REAL_PHOTO_READ_COUNT=0
REAL_EXIF_READ_COUNT=0
G1_SOURCE_ACCESS=0
SQLITE_WRITE_COUNT=0
APP_WRITE_COUNT=0
OBSIDIAN_WRITE_COUNT=0
COMFYUI_PERSISTENT_DB_WRITE=0
N2B2_STATE=LOCKED
```

No PROJECT_STATE, phase lock, model, threshold, verifier, or historical
N2B1P commit was amended. No S20, G1 renewal, RTMW, SAM2, App, SQLite ingest,
push, merge, release, or real-photo access was performed.

## N2B2 GPU runtime continuation — 2026-08-09

- The explicit CUDA admission command ran against the frozen v3 selected
  manifest and stopped before model load with
  `N2B2_GPU_RUNTIME_UNAVAILABLE: INSUFFICIENT_EXCLUSIVE_HEADROOM`.
- External evidence is in the redacted runtime location
  `EXTERNAL_RUNTIME_WORK/n2b2-gpu-runtime-validation-20260809-v1`.
- GPU baseline was `11066 MiB`; the configured `11500 MiB` ceiling minus the
  required `1024 MiB` reserve gives an admission threshold of `10476 MiB`.
- No `8000`, `7865` or `11434` listener was present at the final check. The
  ComfyUI Electron GPU process was not stopped because there was no verified
  listener and WDDM did not provide safe attributable memory ownership.
- TorchVision CUDA, Ollama residency and CUDA S3 are `NOT_PERFORMED` in this
  attempt; no GPU PASS is claimed and no commit was created.
- S20 remains preparation-only: schema/plan present, instance and execution
  `NOT_CREATED`/`NOT_PERFORMED`.

## N2B2 GPU runtime v2 authoritative continuation — 2026-08-09

### Result

`N2B2_GPU_RUNTIME_VALIDATION_COMPLETE_AWAITING_OWNER_REVIEW`

The result is bounded synthetic runtime evidence only. It does not complete
the N2B2 phase, unlock `PROJECT_STATE.json`, authorize S20, or authorize real
photo access.

### Frozen fixture and S3 result

| Case | Fixture SHA-256 | Pose | Keypoint groups | LRASPP person ratio | DeepLab person ratio |
|---|---|---:|---:|---:|---:|
| A `n2b2-s3-01` | `b6283220300ff1cf5edff74624939c0717c0043e21edbd18858bff617aa2914d` | 1 | 1 | `0.005127` | `0.018644` |
| B `n2b2-s3-02` | `2dc3fa1cf72b23fd1230c0a2509f6a04e8b47378b2949151a6203e60e405942e` | 2 | 2 | `0.198328` | `0.203757` |
| C `n2b2-s3-03` | `ac425446fa89f192a78d24fd3d9f88687c5e7b5bbec3815f3a06f7523e52669a` | 0 | 0 | `0` | `0` |

Every positive Pose detection has a complete 17-point keypoint group. The
two CUDA visual-chain runs produced byte-identical canonical facts and stable
fact digests. Qwen schema validation passed, the digest echo matched, unknown
fact IDs were `0`, and forbidden fields were `0`.

### Runtime evidence

The rehashed Git-external evidence is referenced only through the redacted
root `EXTERNAL_RUNTIME_WORK/...`:

- `retry_summary.json`: 25297 bytes,
  `e48bf9091efffc2e1100a025636b5ea347687044f1dc00acd160153434ccbbcd`.
- `gpu/gpu_runtime_metrics.json`: 47126 bytes,
  `e3498356d1f867e3b908c41c1dc329b816aeaed654c55b8c6fc226da59eee9bf`.
- `s3-run/validation_summary.json`: 67260 bytes,
  `226d6f5b1525da025d8800c85eaab799415c93e1574a39f310e10a51530427ef`.
- `ollama/ollama_identity.json`: 1367 bytes,
  `2a736b4b81ce2cbd5a2d7caecf526ffb4a872bf0365e6e74c9bc0f944604f7c0`.
- `ollama/ollama_ps_samples.jsonl`: 53507 bytes,
  `3e2630b15607811faf875976357954fe36f24c2ffa2f4a9b006435f9b7e44536`.

The GPU was an RTX 4070 SUPER with 12282 MiB; admission was `2928 MiB <=
10476 MiB`, runtime baseline was `3079 MiB`, total peak was `10111 MiB`, and
TorchVision unload returned the sample to `3062 MiB`. Keypoint R-CNN, LRASPP
and DeepLabV3 ran on `cuda:0` with `float32`, raw outputs on `cuda:0`, and no
fallback. Qwen `qwen3.5:9b` remained `Q4_K_M` with vision capability,
`size_vram=5880141577 bytes`, 93 residency samples, and explicit unload
success.

The earlier old-fixture capability failure and v1 GPU headroom failure remain
historical evidence; neither is reinterpreted as a model success or deleted.

### Hard boundaries

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
