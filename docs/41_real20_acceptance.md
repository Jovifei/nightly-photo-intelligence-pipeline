# Real20 acceptance and next execution worksheet

## Current evidence boundary

The published first R1 commit (2ae0d76) passed its existing tests but was not a
complete Real20 admission or photography-quality implementation. Its completion
claim is superseded. The current successor adds fixed Owner controls, native
control/source reads, sequential weight loading, CUDA operator probe code,
photographic EXIF and local fact-bound Qwen reasoning. These require independent
review and a new execution record before actual data processing.

R0's original frozen G1 input was historically a newline entry list, while its
metadata tool expects JSON with hashes/sizes. R0 end-to-end requests have NOT
been generated; do not fabricate a replacement with the pinned digest.

## Execution worksheet

Fill final commit/tree/all-tracked-source SHA from the clean candidate, not this
document's parent or the H3 source. Store the completed worksheet outside Git.

| Binding | Required value |
| --- | --- |
| Frozen original manifest SHA | 29eee5fdb8e16c85649752501c4b722d2b4d071950c8a989add040e895a75c47 |
| H3 executed candidate | ffc4130823c1308f089b835c766e341ec2173e82 |
| H3 runtime review SHA | 820f76ba48c5d55fd66b83f158afe7b12b62aad0315df710a57163ea407ffc33 |
| Selection | Same ordered 20 names; 19 unique assets and one reference |
| Source fingerprint | Recomputed exact approved protected root; not a caller assertion |
| Worker | Python 3.12; Torch 2.7.1+cu128; TorchVision 0.22.1+cu128 |
| Native operators | Actual worker CUDA NMS and ROI Align before reservation |
| Models | Existing three content-addressed weights plus observed local Qwen identity |
| EXIF | ExposureTime, FNumber, ISOSpeedRatings, FocalLength, Flash, WhiteBalance; numeric only |
| Output/ledger/cache | Exact Owner-bound path-plan digest; new external empty output |
| Limits | One run; failure consumes; production N2B2 remains LOCKED |
| Proposed UTC window | 2026-09-22T10:00:00Z to 2026-09-23T10:00:00Z; proposal only |

If review finishes after this proposed window, replace the proposal with a fresh
window. Never backdate approval or run using this document.

## Required external controls

The existing runtime configuration selects the runtime parent. Under its
Owner-approvals directory the public entry reads fixed filenames:

- real20_lease.json, real20_manifest.json, real20_runtime_identity.json and
  real20_model_identity.json: exact requested control inputs; arbitrary caller
  locations are rejected before reading them.

- real20_execution_anchor.json: approved lease hash, exact final commit/tree/full
  source SHA, data_receipt_sha256, code_review_sha256, quality_sha256,
  h3_review_sha256, path_plan_sha256; never issued by prepare.
- real20_data_receipt.json: distinct npi-real20-data-receipt-v1, Owner Jovi,
  APPROVED, UTC not-before/expiry, frozen_manifest_sha256, enriched
  manifest_sha256, source_root_fingerprint, explicit real_photo_read and
  real_exif_read, max_assets=20, max_unique_inferences=19, production_n2b2=LOCKED.
- real20_code_review.json: PASS_FOR_REAL20_EVALUATION bound to final candidate,
  tree and source; an actual independent review.
- real20_quality.json: final candidate, PASS, python_supported and the full
  project's quality_matrix check records with real log hashes and exit codes.
- real20_frozen_manifest.txt: original frozen bytes, not regenerated JSON.

Owner controls must deny executor mutation. The fixed real20-execution-ledger
must deny deletion and ACL/ownership changes while supporting claim creation.
The program probes these properties without changing ACLs. Absence or unknown
protection denies admission. No genuine Owner documents or source images are
stored in Git.

The enriched manifest remains separately hash-bound; its ordered paths must
match the frozen list. Preparation cannot derive original content hashes without
existing control evidence or separately authorized source access.

## Product completion after Real20

Actual inference is followed by human calibration of person count, pose,
segmentation, composition, unsupported claims, useful advice and editing time.
Human decisions remain PENDING until entered by the Owner. A separately
qualified export may include APPROVED items only. Independent App import,
display, rejection and rollback still need their own actual integration proof.
No test result here represents any of those human or App outcomes.
