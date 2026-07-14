# N2 Detailed Plan (forward-looking only; NOT implemented)

N2 is LOCKED. This plan is forward-looking; no N2 work is started. N2 requires
Owner authorization (PROJECT_STATE N2 AUTHORIZED) + a model-download approval
record per `OWNER_INPUTS_REQUIRED.md`.

## Goal

Benchmark and adopt offline Pose and person-segmentation model interfaces on
the N1 data底座, still on G0 fixtures until G1 is authorized. Pose coordinates
must come from a professional Pose model or deterministic geometry, never from
a text VLM.

## Prerequisites (Owner decisions)

1. N1 Owner approval + independent Reviewer PASS_FOR_OWNER_REVIEW.
2. Model-download approval records (per `approvals/model_download_approval_TEMPLATE.yaml`):
   candidate name, exact repo/revision, file list + size + SHA-256, license,
   training-data limitations, download target dir, network domain whitelist,
   rollback method, approved data gate + expiry.
3. G1 decision (real 20-image calibration) - optional for N2 model benchmarking
   on fixtures, but required before production thresholds.
4. 12GB VRAM single-heavy-model policy confirmed.

## Work packages (planned, not started)

1. `pose_adapter` interface: professional Pose model (MMPose/RTMPose/RTMW
   candidates) OR deterministic geometry; reject VLM keypoints. Record
   model_id, model_revision, prompt_version, schema_version, code_commit.
2. `segmentation_adapter`: lightweight-first, fine upgrade.
3. Benchmark protocol (per `research/benchmark_protocol.md`): quality, latency,
   VRAM peak, on the 3 fixtures first; do not extrapolate to 500-600.
4. `deterministic_facts`: size, position, color, brightness, structure.
5. Fact reconciliation layer (deterministic vs model).
6. N2 security/safety tests: pose-not-from-VLM, model provenance, no cloud,
   no fabricated EXIF/copyright/focal-length/psychology/safe-distance.

## N2 still forbids

- Production perceptual-hash threshold freeze (needs G1 20 images + benchmark).
- 100/full-library (G2/G3).
- Cloud, OpenClaw, main-App, push/merge.
- VLM visible-facts (N3 scope).
- Story/director prompts (N3/N4 scope).

## Exit evidence for N2

- Pose/segmentation candidates benchmarked on fixtures; adoption recorded with
  provenance + license.
- Pose coordinates never from VLM (test-enforced).
- Model downloads only per approval records; no cloud inference.
- N1底座 unchanged in semantics; migrations versioned.
- G1 remains LOCKED unless Owner separately authorizes.
