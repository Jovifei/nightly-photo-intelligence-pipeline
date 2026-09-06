# N2B2 S20 Synthetic Validation Plan

Status: `N2B2_S20_SYNTHETIC_VALIDATION_COMPLETE_AWAITING_EXTERNAL_REVIEW`

Execution continuation on 2026-08-09 was attempted after the bounded runtime
review fallback PASS and conditional Owner receipt. The first run stopped at
strict-case acceptance; after the bounded Case 17 replacement, the visual chain
passed but two clean Qwen runs reproduced the same fact-digest echo contract
failure. This document remains the contract and does not claim S20 completion.

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

Historical preparation snapshot before the continuation attempt:

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

The technical preparation was ready before the continuation attempt. The
following execution-attempt section is authoritative for the current S20
status.

## S20 execution attempt — 2026-08-09

Status: `N2B2_S20_SYNTHETIC_VALIDATION_FAILED`

- Fixed manifest: 20 synthetic PNGs, one generation per case, no retries.
- Generator: local ComfyUI 0.19.5 / SDXL Base 1.0, text-only EmptyLatent
  workflow, isolated runtime, port 7865; ComfyUI was stopped after generation.
- Visual chain reached both deterministic passes and stopped before Qwen and
  bundle writing.
- Strict failure: `n2b2-s20-17` expected `person_count=1`, actual
  `person_count=2`.
- No prompt, seed, threshold, model, or fixture was changed after detection.
- Qwen: `NOT_PERFORMED_AFTER_STRICT_ACCEPTANCE_FAILURE`.
- Bundle count: `0`; production Bundle v1: `NOT_CREATED`.
- External failure evidence: `EXTERNAL_RUNTIME_WORK/s20-run/failure_summary.json`.

The fixed fixture set is retained as failure evidence. Per the contract, no
additional seed or prompt iteration is allowed in this run.

```text
S20_TECHNICAL_PREPARATION=READY
S20_EXECUTION_AUTHORIZATION=CONDITIONAL_OWNER_AUTHORIZED
S20_EXECUTION_STATUS=FAILED_STRICT_ACCEPTANCE
S20_FIXTURE_MANIFEST_INSTANCE=CREATED_EXTERNAL_ONLY
S20_EXTERNAL_REVIEW_AND_OWNER_APPROVAL_REQUIRED=true
N2B2_STATE=LOCKED
```

## Post-run quality record — 2026-08-09

- Focused S20/remediation/runtime tests: `40 passed`.
- Full pytest: `512 passed / 3 governance failures`; failures were the dirty
  worktree and stale MANIFEST/handoff checks, so no candidate tree was created.
- Ruff check, format check, mypy, sensitive scan and `git diff --check`: PASS.
- `run_quality.py`: `5 pass / 2 fail` for the same pytest and MANIFEST contract
  gates. This is recorded as a failed quality gate, not converted to PASS.
- Obsidian post-run knowledge sync: 6 notes; runtime Obsidian write count: 0.

## Case 17 remediation and S20 v2 continuation — 2026-08-10

The original v1 failure evidence remains unchanged: Case 17 expected one person
but Pose detected two. A bounded remediation generated four candidates using
the predeclared seeds `2026082117`–`2026082120`; the first seed was selected
because it passed the unchanged strict Pose and segmentation capability checks.
The v2 manifest preserves the other 19 fixture bytes and replaces only Case 17.

The v2 visual chain completed both deterministic rounds for all 20 cases. Case
17 passed strict acceptance, Case 19 remained the negative control, and Case 20
remained an unsupported observation. No prompt, seed, model, threshold or
strict acceptance rule was changed during S20.

Two clean Qwen attempts then reproduced the same deterministic contract error
on `n2b2-s20-03`: the returned `input_fact_digest` did not equal the immutable
vision-facts digest. Qwen was therefore not allowed to produce bundles. This is
a Qwen fact-contract failure, not a Case 17 fixture failure.

```text
S20_TECHNICAL_PREPARATION=READY
S20_EXECUTION_AUTHORIZATION=CONDITIONAL_OWNER_AUTHORIZED
S20_EXECUTION_STATUS=FAILED_QWEN_FACT_DIGEST_ECHO
S20_FIXTURE_MANIFEST_INSTANCE=CREATED_EXTERNAL_ONLY
S20_BUNDLE_COUNT=0
S20_NO_OP_RESUME=NOT_PERFORMED_INCOMPLETE_RUN
S20_EXTERNAL_REVIEW_AND_OWNER_APPROVAL_REQUIRED=true
N2B2_STATE=LOCKED
```

The retry evidence is Git-external. GPU peak was approximately `9594 MiB`,
post-unload GPU usage was approximately `2347 MiB`, the Luna-owned Ollama
service was stopped, and TorchVision resident roles were empty. No S20
candidate commit was created or advanced.

### Final verification record

- Focused S20/remediation/runtime tests: `46 passed`, exit `0`.
- Full pytest: `518 passed / 3 governance failures`, exit `1`; failures were
  the intentionally uncommitted worktree and stale MANIFEST/handoff bindings.
- Ruff check: exit `0`; format check: exit `0` (`106 files already formatted`).
- Mypy: exit `0`, 66 source files.
- Sensitive scan: exit `0`, `0 violations`.
- `run_quality.py`: exit `1`, `5 PASS / 2 FAIL`; the failures were pytest and
  contract-integrity at the same clean-tree/MANIFEST boundary.
- Preflight: exit `0`, `15 PASS / 0 FAIL`.
- Handoff verifier: exit `1`, `5 PASS / 1 FAIL`; the only failure was the
  expected MANIFEST hash mismatch for the post-run report/task updates.
- `git diff --check`: exit `0`.

No S20 candidate was created because the runtime failed before bundle output and
the final clean-tree governance gate was not satisfied.
## Qwen fact-binding remediation and S20 v3 continuation — 2026-08-10

The v2 digest-echo failure remains historical evidence. The bounded remediation
added request-bound Qwen schemas: each response schema carries the exact
`case_id`, authoritative vision-facts digest and allowed fact-ID enum; the
response is validated before bundle writing and the model output is never
coerced into a different digest. A real artifact-contract mismatch found in
the first v3 bundle attempt was also corrected: `analysis.json` now matches
the established Qwen reasoning contract, including the
`{safe,narrative,dynamic}` story object.

The fixed-source candidate used for the successful run was
`9e50f0057171f62af5cfccc4f8a539453fef14c4`, whose only parent is
`49e653b27884f9ba09d15ca17682e496687dc59f`. The source candidate passed the
full repository quality gates before model execution. Case 17 and the other
19 v2 fixture bytes were not regenerated or modified during this continuation.

The successful external retry completed the full CUDA chain: 20 Pose, LRASPP
and DeepLab cases in two deterministic visual rounds; 20 Qwen cases with
per-case fact-binding evidence; the fixed five-case Qwen repeat set; 20
per-case synthetic Reference Bundles; the top-level index and checksums; and a
no-op `--resume` with exit `0` and byte-for-byte unchanged output files.

```text
N2B2_S20_SYNTHETIC_VALIDATION_COMPLETE_AWAITING_EXTERNAL_REVIEW
S20_TECHNICAL_PREPARATION=READY
S20_EXECUTION_AUTHORIZATION=CONDITIONAL_OWNER_AUTHORIZED
S20_EXECUTION_STATUS=PERFORMED_SYNTHETIC_ONLY
S20_BUNDLE_COUNT=20
S20_NO_OP_RESUME=ALREADY_COMPLETE_VERIFIED
S20_FIXTURE_MANIFEST_INSTANCE=CREATED_EXTERNAL_ONLY
S20_EXTERNAL_REVIEW_AND_OWNER_APPROVAL_REQUIRED=true
N2B2_STATE=LOCKED
PRODUCTION_BUNDLE_RELEASE=NOT_CREATED
```

Runtime metrics: GPU baseline `2517 MiB`, peak `9702 MiB`, after unload
`2779 MiB`, Ollama peak `5607 MiB`; the model peak stayed below the
`11500 MiB` ceiling. Facts were byte- and digest-identical across both visual
rounds. Qwen schema, digest echo, legal fact references and forbidden-field
count all passed. Hard counters remained zero for real-photo reads, EXIF, G1,
SQLite, App, Obsidian runtime writes and model downloads. The Luna-owned
Ollama process was stopped after cleanup; no user ComfyUI process was touched.

The S20 candidate commit and external Reviewer remain separate closure steps.
This result is not a production Bundle v1 release, does not unlock
`PROJECT_STATE.json`, and does not authorize G1, real photos or App work.

## Completion-artifact integrity remediation - 2026-08-11

The v3 directory is retained as historical evidence but is not an acceptable
successful validation set: it contains a COMPLETE checkpoint and twenty
bundles while also carrying a terminal failure summary. Its checksums are
byte-consistent with that contradictory set; they are therefore provenance of
the defect, not proof of a successful S20 outcome.

The authorized replacement contract is synthetic-only and reuses the frozen
v2 fixture manifest. Before v4 executes, its source candidate must enforce an
exact success layout, recomputed checksums, a v2 COMPLETE checkpoint, Qwen
identity hashes in each binding record and a no-op resume that verifies every
artifact before returning success. Any terminal failure remains in its own
output directory and cannot be resumed over or claimed as a later success.

The frozen v4 runtime-source candidate completed one fresh synthetic-only
twenty-case run against the unchanged v2 fixture manifest. Its success layout
contains exactly twenty validation bundles, a COMPLETE v2 checkpoint, a
complete release checksum set, and no terminal failure summary. Recomputed
release verification covers 148 release files, excluding the checksum file
itself.

Both CUDA visual passes produced byte-identical canonical facts and identical
fact digests for all twenty cases. Strict cases met their declared acceptance,
the negative and unsupported controls retained their declared dispositions,
and observation differences are recorded without being promoted to strict
acceptance. Qwen completed the primary twenty cases plus the deterministic
five-case repeat with schema, digest echo, fact-reference and forbidden-field
checks passing. The local identity remained `qwen3.5:9b` / `Q4_K_M` with vision
capability, and every Qwen binding record is connected to that identity.

The v4 metrics record an RTX 4070 SUPER baseline of 3024 MiB, a 10224 MiB total
peak, 3285 MiB after TorchVision unload, and a 5607 MiB Ollama residency peak.
Pose, LRASPP and DeepLab each ran on `cuda:0` in float32 and were explicitly
unloaded before Qwen. A no-op resume recomputed the artifact contract and
returned success with no model load and no file-byte changes.

The redacted external evidence aliases are `EXTERNAL_RUNTIME_WORK/n2b2-s20-v4`
and `EXTERNAL_RUNTIME_SERVICE/n2b2-s20-v4-ollama`. The external success summary
SHA-256 is `aff8b56ce5f5f7a1a6835691ba636070dce185f1f006eb1c248a510d5c9ba022`;
the release checksum SHA-256 is
`b539792c75cb82e0be14424216fee2052c259075e6dec08ebfdc921f32d4412c`.

This is a coherent synthetic validation candidate only. `PROJECT_STATE` is
unchanged, `N2B2=LOCKED`, production Bundle v1 is not created, and an
independent external review remains required before any Owner decision.
