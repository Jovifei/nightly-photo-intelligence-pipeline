# Master Execution Contract

Normative status: **REQUIRED**
Project: `nightly-photo-intelligence-pipeline`

## Mission and permanent boundaries

Build a local-first, auditable, resumable photo-intelligence pipeline that turns
an Owner-controlled photography collection into structured photography knowledge.
The pipeline is independent of `ai-photography-director-app`; it must never
share its database or change its source code.

- Original photos are read-only: never modify, move, rename, delete, or change
  their permissions.
- Cloud image processing, image upload, OpenClaw, Docker/WSL/driver changes,
  App changes, push, merge, remote release, G2, and G3 are prohibited unless a
  later explicit Owner record authorizes them.
- No real filename, absolute source path, GPS, exact location, identity field,
  original photo, thumbnail, Base64, mask, overlay, cutout, or model artifact
  may enter Git, reports, or Obsidian notes.
- A data gate and a phase gate are independent. Passing code/tests does not
  enlarge data scope or authorize a later phase.
- Pose comes only from its approved pose backend, never from VLM text. VLM must
  not fabricate EXIF, copyright, exact focal length, psychology, or intent.

## Current authorization: N2B1P

The current and only executable task is
[`tasks/phase_n2b1p_local_research_cache_promotion.yaml`](tasks/phase_n2b1p_local_research_cache_promotion.yaml),
bound to the completed N2B1R transfer evidence and:

- [`approvals/phase_completion_N2B0_7.yaml`](approvals/phase_completion_N2B0_7.yaml)
  at immutable tag `n2b0-7-approved-2026-07-29`;
- [`approvals/owner_n2b1p_cache_promotion.yaml`](approvals/owner_n2b1p_cache_promotion.yaml);
- [`research/N2B1R_acquisition_evidence.json`](research/N2B1R_acquisition_evidence.json);
- [`research/N2B1R_local_research_artifact_register.json`](research/N2B1R_local_research_artifact_register.json);
- [`PROJECT_STATE.json`](PROJECT_STATE.json), schema `1.7`.

N2B1P permits only a content-addressed, Git-external copy and verification of
the three exact local-SHA-256 payloads already recorded by N2B1R. It does not
permit network access, dependency installation, model load/inference, CUDA,
source-photo access, EXIF read, SQLite ingest writes, derivative images, or
photo analysis. The quarantine is retained.

The selected pretrained TorchVision weights have no verified commercial grant.
Their use is therefore **local research/evaluation on this Owner-controlled
machine only**. Local SHA-256 proves acquired-byte integrity; it is neither a
weight license nor commercial clearance. Weight redistribution and any report
claiming commercial clearance are prohibited.

## Required N2B1P gate

Before every copy, strict-load the state, approval, task, N2B1R evidence, and
artifact register. For each artifact, require its exact approved filename,
revision, byte count, local SHA-256, and completed N2B1R transfer-manifest
SHA-256. The quarantine/cache must be non-reparse, outside Git and runtime,
and may not overlap source or each other. Copy through exclusive staging, then
stream-hash and reread the promoted payload before atomically publishing its
path-redacted cache manifest.

At the end of N2B1P, stop. N2B2 model execution and real-photo analysis, N3A
deterministic analysis, N4R director prompts, and N5R report rendering each
remain conditional on their own contract and hard gate. The only eventual
source is the protected G1 snapshot and its frozen 20-entry manifest; 19
unique assets may be inferred and one duplicate is a reference only.

## Verification discipline

Every stage must report reproducible commands, actual exit codes, failure/
unknown states, artifact hashes, dependency/model/schema versions, source-data
gate result, and unresolved issues. `PASS`, `FAIL`, `BLOCKED`, `NOT_AVAILABLE`,
and `SKIPPED` are distinct. Never present an unrun action or a denied command as
passing evidence.

On any ACL, manifest, path, integrity, schema, privacy, resource, quality, or
rights gate failure, stop at that phase. Do not perform a system repair, source
mutation, broadened download, or data read as a workaround.
