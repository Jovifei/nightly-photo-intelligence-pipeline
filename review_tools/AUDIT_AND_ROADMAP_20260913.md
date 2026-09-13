# Remote audit and product gap review — 2026-09-13

## Evidence boundary

Inspected runtime candidate: `da638bab6a61fe6fc466521cc60abcacfea9120a`.
Parent: `d83f96271f754763d61cedcc314fc725c840c86f`.
The GitHub comparison shows one new commit, no behind commits and 21 changed files.
`main` was still `d83f9627` when read. This is substantive implementation, not an
empty commit: the new CLI adds runtime revalidation, a strict version-transition
permit, tests, schemas, a receipt and GPU ceilings. The user's local summary reports
560 tests, 7/7 quality, 8/8 handoff and complete external artifacts. Those local
artifacts were not available to the remote agent and were not independently hashed
here. No formal runtime PASS or phase completion is issued by this document.

The code additions here are tested review tools, not an extension of the consumed
one-shot runtime lease. The original runtime candidate remains separately reviewable.

## Findings

### F1 — Directional composition facts do not measure direction (product blocker)

At the pinned commit, `src/nightly_photo_intelligence_pipeline/n2b2_synthetic/vision_facts.py`,
`_negative_space()` sums person-box areas, clamps the sum and assigns the same
`fg_ratio / 4` value to left/right/top/bottom. Two photos with the same box area but
opposite subject positions therefore receive identical directional values. Overlap
is also double-counted before clamping. A no-person frame gets zero for each direction
but total_negative_ratio=1. This must not be presented to a photographer as measured
left/right free space. It is not resolved by passing JSON Schema or repeating facts.

Delivered: pure, bounded, clipped rectangle-union reference algorithm with explicit
half-frame denominators and 15 test methods, including 100 randomized pixel-oracle
comparisons. Not integrated into the frozen runner. Integration must version the
producer/semantics and regenerate fact digests only in a new approved run. Do not
claim bbox empty area is aesthetic negative space; other objects are unmeasured.

### F2 — One-shot authorization is not persisted as consumption (execution blocker)

`runtime_identity_revalidation.py` verifies max_fresh_s3_runs/max_fresh_s20_runs equal
one. The new CLI checks fresh directories but has no receipt-keyed atomic consumption
record. A different empty output can satisfy the same checks again. The declaration
alone does not enforce one-shot use. Before any repeat execution, introduce an
external atomic reservation keyed by receipt digest and finalized source candidate,
with durable STARTED/COMPLETE/FAILED transitions and no release of a consumed permit
on failure. Existing completed runs are not retroactively invalidated, but the old
permit must not be reused. This overlay does not execute or materialize a new lease.

### F3 — Output/path safety is incomplete (execution blocker)

`validate_fresh_output()` checks Git, cache and old evidence overlap, but does not
check the three new outputs against one another or against the synthetic fixture
input roots. `snapshot_tree()` resolves the root before testing `is_symlink()`, which
loses a root-symlink indication. Windows reparse points need native consideration.
Before another run, check all input/output/protected roots as a set, and reject links
before resolution. Cover same paths, parent/child overlaps, junctions, hardlinks and
nonexistent children of protected roots. Do not scan real source directories to
perform this check. The new offline reader rejects reparse ancestors before reading;
this is not a fix to the frozen runtime path guard.

### F4 — Evidence presence is not full acceptance (review completeness)

The new CLI writes `quality_matrix.json` as only `{"runtime_gate":"PASS"}` and creates
a one-line `remediation_result.md`. Local follow-up may have enriched these files;
inspect actual bytes before concluding either completeness or absence. A reviewer
still needs commands, versions, exit codes, candidate/tree, artifact anchors, five
identity observations, and fresh no-op-resume evidence. `_hard_counts()` returns
literal zeros; these are declarations, not instrumentation proving prohibited calls
were impossible. Report the distinction. Do not synthesize missing command logs.

### F5 — GPU verifier type gap (defense in depth)

`s20_bundle.py::_validate_complete_layout()` rejects a high peak only when peak_mib
is an int. Missing, string, or floating-point values can avoid this particular
comparison. The runtime writer has an additional ceiling check, but the independent
artifact verifier should require a present, finite, non-boolean numeric measurement
and reject values above the limit regardless of numeric representation. The new
standalone audit tool exercises these cases; the frozen writer is not modified here.

### F6 — Source provenance and current Git identity must remain separate

The runtime source manifest covers a selected list, not every imported module or
control file. In particular, the new runtime_identity_revalidation gate is not added
to that selected list by the 12-line S20 runner delta. Independently bind the entire
final Git tree and all relevant receipts; do not infer equivalence from one partial
source digest alone. This overlay verifies every original tracked file unchanged.
The earlier bce1906→d83f9627 operation was a metadata-only, non-fast-forward ref rewrite,
not a product feature or an ordinary merge. Do not repeat it for cosmetic tidiness.

## What is still missing for the actual product

The target is useful, reviewed photography knowledge from 500–600 local photos,
consumed by a separate photography-director App. It is not a perpetual synthetic
model benchmark. There is no supported basis for reporting a numeric completion %.

1. Close the pinned synthetic review using actual external artifacts, and resolve
   the concrete geometry/lease/path findings in an explicitly bounded remediation.
2. Owner accepts the exact reviewed candidate; create a fresh Real20 authorization,
   frozen manifest, protected source identity, allowed operations and expiration.
   Historical G1 does not authorize reuse; do not assume a new set must be 19+1.
3. Real20: manually evaluate person count, visible pose, segmentation, composition
   facts, grounded explanation, actionable prompts, p50/p95 end-to-end latency,
   GPU usage, failures and human correction effort. Unknown/occluded is not zero.
4. N3/N4/N5: separate deterministic facts, interpretations and creative suggestions;
   persist human approve/edit/reject and export APPROVED-only Bundle v1. The next
   product milestone is ONE genuinely useful, reviewed item exported and consumed.
5. Verify the App consumer against the actual versioned Bundle, including hash and
   schema rejection, atomic import, rollback and offline display. This review does
   not establish the state of all App branches or its complete consumer integration.
6. A 100-photo pilot, interruption/recovery drills and measured review cost precede
   full 500–600-photo authorization. Only then add scheduled unattended execution.

Do not upgrade Pose/SAM/embeddings/vector databases to avoid measuring these gaps.
Current baseline remains Keypoint R-CNN, LRASPP, DeepLab comparator, local Qwen.
Do not confuse latency targets with measured end-to-end performance. Measurement
must include preprocessing, all stages, retries, persistence and model residency costs.

## Open-source research: borrow mechanisms, not a new platform

Official sources checked on 2026-09-13. No upstream code, models, plugins or services
were installed or imported into the product by this change.

- FiftyOne: per-sample evaluation and error slicing against ground truth, rather than
  just one global pass count. Borrow for Real20/pilot review views and bad-case groups.
  https://docs.voxel51.com/user_guide/evaluation/detections.html
  https://github.com/voxel51/fiftyone
- Label Studio Community: predictions remain read-only while human annotations are
  separate objects; preserve stable region IDs when editing. Borrow for future N5
  edit history. Export is NOT an APPROVED-only publication policy: canceled records
  can appear in export, so this project must implement its own explicit approval gate.
  https://labelstud.io/guide/predictions
  https://labelstud.io/guide/export
  https://github.com/HumanSignal/label-studio
- CVAT: skeleton points have visibility/occlusion and explicit labels, with COCO
  Keypoints interchange. Borrow for pose ground truth; do not expand to 133 points
  until current 17-point failure cases demonstrate the need.
  https://docs.cvat.ai/docs/manual/advanced/skeletons/
  https://docs.cvat.ai/docs/dataset_management/formats/format-coco-keypoints/
  https://github.com/cvat-ai/cvat
- MLflow: evaluation of static predictions without rerunning a model; explicit
  dataset digest, lineage and run metadata. Borrow this separation for audit vs
  live-resume verification; do not deploy another tracking/database stack yet.
  https://mlflow.org/docs/latest/ml/evaluation
  https://mlflow.org/docs/latest/dataset/
  https://github.com/mlflow/mlflow
- PhotoPrism: originals separated from storage/sidecars and an explicit read-only
  mode. Borrow independent output storage, not broad scanning, GPS enrichment or
  face identity features, which conflict with this project's privacy boundary.
  https://docs.photoprism.app/getting-started/faq/
  https://docs.photoprism.app/user-guide/backups/folders/
  https://github.com/photoprism/photoprism

## Acceptance of this source delivery

The overlay tests run entirely against generated numeric/JSON/Git fixtures. They
are not measurements of the Owner's S20 outputs. Python 3.13.5/Linux was available;
Ruff and mypy were not installed. No cloud full-project 560-test run or native GPU
validation is claimed. Local Codex must report the frozen candidate's matrix and
the overlay's matrix separately. The new geometry code is ready for targeted
integration, but its production contract has deliberately not been changed here.

## Publication outcome

The complete GitHub source write was blocked by the platform. No new commit or
branch update was made. This delivery is a tested local patch based on da638bab.
A partial unreferenced Git tree object is not a commit and must not be used as the
review target. Apply the complete ten-file patch locally, verify it and publish a
normal fast-forward child on the user-specified branch; do not rewrite history.
