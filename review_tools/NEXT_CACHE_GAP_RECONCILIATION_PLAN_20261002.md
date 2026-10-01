# N2B1P cache gap reconciliation plan

Base reviewed HEAD: `de2926044e29710226af3a6cb6b850edea588718`

## Current finding

N2B1P remains the only active execution scope. Historical cache-hit evidence must be reconciled with current fixed-path availability. This document does not authorize search, download, path creation, or evidence fabrication.

## Required reconciliation

Owner decision A: restore approved N2B1R quarantine payload to the fixed approved location and validate exact hashes.

Owner decision B: create a separate narrowly scoped exact download authorization task. Do not reuse N2B1P copy-only authorization.

## Verification after authorization

- verify fixed quarantine parent;
- verify fixed cache root;
- verify artifact identities and hashes;
- run `python tools/verify_handoff.py`;
- run `python tools/verify_review_candidate.py`.

## Stop conditions

Stop on missing payloads, hash mismatch, missing Owner authorization, missing canonical cache, or any attempt to broaden N2B1P into download/model/photo/GPU/SQLite work.

## Future qualification order (planning only)

1. TorchVision baseline artifact qualification.
2. MMPose approved pose backend qualification.
3. SAM2 segmentation qualification.
4. Qwen3-VL bounded reasoning evaluation.

Each requires separate artifact, schema, data and phase gates.
