# N2B2 S20 Synthetic Validation Plan

Status: `PREPARATION_ONLY_PENDING_GPU_VALIDATION`

This document defines the future synthetic-only S20 contract. It does not
create fixture images, load an S20 manifest, invoke an S20 model path, read
real photos or EXIF, access G1, write SQLite, or unlock `PROJECT_STATE.json`.

## Required manifest

- `schema_version`: `n2b2-s20-fixture-manifest-v1`
- exactly 20 entries, with IDs `n2b2-s20-01` through `n2b2-s20-20`
- relative PNG paths only; no absolute path, `..`, symlink or reparse escape
- `synthetic=true`, SHA-256, dimensions, seed, generator version, complete
  generation parameters, expected person count, processability and tags
- no real-photo, EXIF or G1 source fields

The repository schema is
`schemas/n2b2_s20_fixture_manifest.schema.json`. The schema is a contract
only; an instance is intentionally `NOT_CREATED` in this task.

## Case matrix

| IDs | Coverage |
| --- | --- |
| 01–04 | single-person full-body, half-body, seated, prop interaction |
| 05–08 | two people separated, close, partial occlusion, mirror/reflection composition |
| 09–11 | low-light single person, low-light people, night silhouette |
| 12–14 | complex interior, complex exterior, distracting multi-person background |
| 15–16 | strong backlight, silhouette |
| 17–18 | large negative space, offset composition |
| 19 | no-person negative control |
| 20 | synthetic collage/screenshot unsupported control |

## Runtime budget

- Pose, LRASPP and DeepLab: at most 60 seconds per image each
- complete deterministic visual chain: two rounds
- Qwen cold load: at most 180 seconds
- Qwen steady state: at most 120 seconds per image
- each unload confirmation: at most 60 seconds
- total GPU ceiling: 11500 MiB
- hard total plan ceiling: 10800 seconds
- models are strictly serial; no TorchVision/Qwen co-residency

Acceptance requires the GPU probe, CUDA S3 repeatability and schema tests to
pass first. Then the status may be recorded as:

```text
S20_PREPARATION_STATUS=READY_FOR_S20_EXECUTION
S20_EXECUTION_STATUS=NOT_PERFORMED
S20_FIXTURE_MANIFEST_INSTANCE=NOT_CREATED
S20_SEPARATE_EXECUTION_AUTHORIZATION_REQUIRED=true
```

## Current authorization state

```text
S20_TECHNICAL_PREPARATION=READY
S20_EXECUTION_AUTHORIZATION=LOCKED
S20_EXECUTION_STATUS=NOT_PERFORMED
S20_FIXTURE_MANIFEST_INSTANCE=NOT_CREATED
S20_EXTERNAL_REVIEW_AND_OWNER_APPROVAL_REQUIRED=true
```

The technical preparation is ready because the bounded GPU probe and CUDA S3
repeatability evidence passed. S20 execution remains separately locked and
was not performed in this task.
