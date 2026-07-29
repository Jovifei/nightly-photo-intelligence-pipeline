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

## Current authorization: N2B1R

The current and only executable task is
[`tasks/phase_n2b1r_local_research_model_acquisition.yaml`](tasks/phase_n2b1r_local_research_model_acquisition.yaml),
bound to:

- [`approvals/phase_completion_N2B0_7.yaml`](approvals/phase_completion_N2B0_7.yaml)
  at immutable tag `n2b0-7-approved-2026-07-29`;
- [`approvals/owner_local_research_execution_N2B1R_to_N5R.yaml`](approvals/owner_local_research_execution_N2B1R_to_N5R.yaml);
- [`research/N2B1R_local_research_artifact_register.json`](research/N2B1R_local_research_artifact_register.json);
- [`PROJECT_STATE.json`](PROJECT_STATE.json), schema `1.6`.

N2B1R permits only register-bound official model payload/dependency acquisition
to a Git-external quarantine and installation into a Git-external isolated
runtime. It does not permit model load/inference, cache promotion, source-photo
access, EXIF read, SQLite ingest writes, derivative images, or photo analysis.

The selected pretrained TorchVision weights have no verified commercial grant.
Their use is therefore **local research/evaluation on this Owner-controlled
machine only**. Local SHA-256 proves acquired-byte integrity; it is neither a
weight license nor commercial clearance. Weight redistribution and any report
claiming commercial clearance are prohibited.

## Required N2B1R gate

Before any payload request, strict-load the state, approval, task, and artifact
register. For each artifact, require its exact approved filename, revision,
official URL/domain, bounded Content-Length, exclusive quarantine destination,
streaming SHA-256, post-write reread, and a redacted transfer manifest. The
quarantine/cache must be outside Git and may not overlap source or runtime.

At the end of N2B1R, stop. N2B1P cache promotion, N2B2 model execution and
real-photo analysis, N3A deterministic analysis, N4R director prompts, and
N5R report rendering each remain conditional on their own contract and hard
gate. The only eventual source is the protected G1 snapshot and its frozen
20-entry manifest; 19 unique assets may be inferred and one duplicate is a
reference only.

## Verification discipline

Every stage must report reproducible commands, actual exit codes, failure/
unknown states, artifact hashes, dependency/model/schema versions, source-data
gate result, and unresolved issues. `PASS`, `FAIL`, `BLOCKED`, `NOT_AVAILABLE`,
and `SKIPPED` are distinct. Never present an unrun action or a denied command as
passing evidence.

On any ACL, manifest, path, integrity, schema, privacy, resource, quality, or
rights gate failure, stop at that phase. Do not perform a system repair, source
mutation, broadened download, or data read as a workaround.
