# N2A Implementation Summary

Date: 2026-07-20

## Authorization

- G1 immutable baseline: `4a807dbbcd147a106b02b7e3899aa701c2028d83`
- N2A capability: `N2A_POSE_SEGMENTATION_BENCHMARK_PREPARATION` AUTHORIZED
- N2B model download/inference: LOCKED
- Data: synthetic metadata only; real-photo reads: none

## Delivered

- Typed Pose contracts and backend protocol with provenance, visibility,
  normalized/pixel coordinates, mirror strategy, and synthetic fake backend.
- Deterministic left/right mirror transforms, stable person ordering, joint
  angle calculation, missing/zero-length handling, and fail-closed validation.
- Typed Segmentation metadata contract and synthetic fake backend with no mask
  bytes or derived image artifact.
- Fixed 20-case synthetic benchmark plan, closed metric-attestation semantics,
  redacted report DTOs, and `benchmark plan/status/run` CLI commands.
- `benchmark run` returns `NPI_MODEL_NOT_AUTHORIZED` while N2B is locked.
- N2A state/task/schema contracts, G1 completion binding, error taxonomy v1.2,
  candidate/license ledgers, and N2B artifact request draft.

## Reviewer remediation — 2026-07-20

The Owner accepted the independent Reviewer conclusion `CHANGES_REQUIRED` for
the original N2A commit and authorized only this N2A remediation. The following
three blocking areas were corrected without entering N2B:

- Schema v1.1 is now a fail-closed union of Pose case, Segmentation case,
  Benchmark plan, and Benchmark report documents. Every object is closed with
  `additionalProperties: false`; required identity, person/keypoint, bbox,
  mask-metadata, provenance, uncertainty, and measurement-attestation fields
  are explicit.
- Shared provenance semantics now enforce the synthetic/producer matrix in
  Python and Schema. Fake results use `FAKE_BACKEND`, real-model provenance
  requires identity/revision/artifact hash, and VLM producers are excluded.
  Pose side labels use an enum and an explicit keypoint mapping; mirror no
  longer infers side changes from arbitrary free text.
- `npi benchmark validate --profile <pose|segmentation> --backend fake` is the
  only executable N2A path. It invokes the fake backend, product runner,
  per-case evaluator, deterministic rerun, JSON Schema validation, aggregator,
  and report DTO for all 20 synthetic metadata cases. `benchmark run` still
  fails closed before any real backend is constructed.

All fake outputs remain metadata-only, artifact-free, synthetic, and excluded
from real-model benchmark claims. Threshold status is `NOT_CALIBRATED` and
`ready_for_real_benchmark=false`.

## Explicit non-actions

No model dependency, weight, checkpoint, real photo, source path, runtime DB,
skeleton, mask, cutout, contour, embedding, or VLM output was created.

## Finite/taxonomy remediation — 2026-07-21

The Owner accepted a subsequent independent-review `CHANGES_REQUIRED` finding
for the sole N2A candidate and authorized only the following four blocking
remediations. N2B remains locked.

1. Public Python DTOs and the common public Schema entrypoint now reject
   `NaN`, `Infinity`, and `-Infinity` with `NPI_NON_FINITE_NUMBER`; strict JSON
   rendering uses `allow_nan=False` and Draft 2020-12 has a finite-number type
   checker plus recursive semantic guard.
2. The public normalized BBox is only `x`, `y`, `width`, and `height`.
   `right`/`bottom` are Python-derived properties, never public input. Bounds
   violations use `NPI_INVALID_BOUNDING_BOX` or
   `NPI_INCONSISTENT_BOUNDING_BOX`.
3. Benchmark case status, error code/category, and measurement status are
   closed enums with construction-time consistency matrices. `PASS` cannot
   carry an error; `MEASURED` requires finite evidence; `NOT_MEASURED` is all
   null; and `UNAVAILABLE` requires a stable reason.
4. Explicit regression coverage now proves each zero-length geometry case
   returns `UNDEFINED_ZERO_LENGTH` without a division error, fake angle, or
   non-finite result. The parametrized Schema/DTO matrix covers the same BBox
   counterexamples at both public boundaries.

The fixed fake product path remains unchanged: each profile runs exactly 20
synthetic cases through fake backend, evaluator, strict validator,
deterministic rerun, aggregate, and report DTO. It produces no image or model
artifact and does not read a real photo.

Child A finite/Schema/DTO review: `FINITE_SCHEMA_PARITY_INCONCLUSIVE` after
three independent 90-second read-only attempts timed out. Child B
taxonomy/benchmark review: `BENCHMARK_TAXONOMY_INCONCLUSIVE` after the same
three-attempt bounded policy. All six attempts returned no accepted structured
result and none is treated as PASS.

The exact N2A review target SHA is supplied externally after commit creation.
The report is bound to the immutable G1 parent SHA and current repository content.

## Clean-candidate verification

Before the evidence-only final amend, the clean candidate completed the full
required matrix: 234 pytest cases passed; Ruff check, format check, and mypy
exited 0; the unified quality gate reported 7 PASS, 0 FAIL, 0 NOT_AVAILABLE,
and 0 SKIPPED; sensitive scan reported 0 violations; preflight reported 15
PASS and exit 0. Both fake validators processed 20/20 synthetic cases with 0
failures, 0 errors, 0 deterministic mismatches, 20 Schema passes,
`NOT_CALIBRATED`, `ready_for_real_benchmark=false`, and 0 artifacts. Both real
run commands correctly exited 8 with `NPI_MODEL_NOT_AUTHORIZED`.

## Scope-purity remediation — 2026-07-21

The Owner authorized a narrow remediation for the independent Reviewer's sole
scope-purity finding: one out-of-scope named reference in `tasks/lessons.md`.
The reference was generalized into a repository-agnostic scope-control lesson;
the surrounding lessons, N2A contracts, code, and phase state were not changed
for this remediation.

Parent scope audit of both the current tracked tree and the G1-to-working-tree
N2A diff found zero matches for the Owner-specified cross-project identifiers,
zero other-project path/package/build artifacts, and zero model, cache, runtime
database, or derived-image artifacts. The repository retains only its three
pre-existing synthetic fixture images. No real photo was read and no model was
downloaded or run.

Four bounded read-only Child-Claude packages were dispatched for scope,
Schema/DTO, benchmark, and governance review. Child A exhausted two fresh
90-second attempts; Child B and Child C each exhausted one 90-second attempt;
Child D ended without an accepted structured result. These are all recorded as
INCONCLUSIVE, never as PASS. The parent independently completed the requested
deterministic checks.

The synthetic stability run invoked the CLI fake-validation product path 100
times per profile. Pose and Segmentation each produced byte-identical redacted
reports across all 100 runs: 20/20 PASS per run, zero FAIL, zero ERROR, zero
deterministic mismatches, zero artifacts, `NOT_CALIBRATED`, and
`ready_for_real_benchmark=false`. The two-person fake ordering was stable for
100 direct metadata-only checks. The real CLI run gate was exercised 20 times
per profile and each call returned exit 8 with `NPI_MODEL_NOT_AUTHORIZED`.

N2B remains `N2B_NOT_READY_FOR_OWNER_APPROVAL`: exact artifact identity,
revision, size, weights terms, source, hash, cache/deletion policy, and real
resource and quality measurements remain unresolved. This implementation
evidence does not predeclare an external Reviewer conclusion.
