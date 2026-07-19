# N2A Pose and Segmentation Research

Date: 2026-07-20

## Scope

This is research only. N2A did not download dependencies or weights, run
inference, read real photographs, or create image derivatives. The G1 commit
`4a807dbbcd147a106b02b7e3899aa701c2028d83` remains immutable.

## Pose

- MMPose is the broadest official candidate: body, multi-person, hand, face,
  and whole-body support are documented in the official repository and
  inference guide. Repository code is Apache-2.0; exact model/checkpoint terms
  and revision remain pending N2B approval.
- rtmlib is a lightweight RTMPose-family wrapper with fewer framework
  dependencies. It remains research-only; exact revision and weights terms are
  pending N2B approval.
- N2A therefore adopts only a typed `PoseBackend` boundary, provenance, fake
  backend, mirror/left-right transforms, deterministic joint geometry, and
  fail-closed validation.

## Segmentation

- MediaPipe Selfie Segmentation is a lightweight baseline for prominent humans
  and close-camera use; its documented fixed tensor sizes and selfie scope make
  multi-person, small-subject, hair, clothing, and translucent-edge behavior
  benchmark questions rather than assumptions.
- PaddleSeg PP-HumanSeg is a candidate for human semantic segmentation; exact
  checkpoint, dependency, and commercial terms must be reviewed per artifact.
- SAM 2 is reserved for a later fine-detail escalation. Code, checkpoint, and
  auxiliary license terms must be separated before any download request.
- N2A therefore adopts only metadata contracts and a fake backend; no mask
  bytes, mask files, cutouts, contours, or background replacements exist.

## Child research evidence

The three bounded child packages were attempted read-only. Initial attempts
returned unsuccessful structured results; retries produced one 90-second timeout
and two unsuccessful null results. They are not PASS. The parent completed the
research from the official sources listed in `source_register.md`.
