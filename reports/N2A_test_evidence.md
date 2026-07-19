# N2A Test Evidence

## Positive evidence

- N2A focused tests after remediation: 23 passed.
- Contract tests: 27 passed.
- Current-stage preflight tests: 15 passed.
- Full suite after the remediation amend: 213 passed, exit 0.
- Ruff check: exit 0, all checks passed.
- Ruff format check: exit 0, 62 files already formatted.
- mypy: exit 0, no issues in 43 source files.
- `tools/run_quality.py`: exit 0, 7 PASS, 0 FAIL, 0 NOT_AVAILABLE, 0 SKIPPED.
- `tools/sensitive_file_scan.py`: exit 0, 0 violations.
- `npi preflight`: exit 0, 15 PASS, 0 FAIL, 0 NOT_AVAILABLE, 0 SKIPPED.
- `git diff --check`: exit 0; final worktree clean.

## Covered boundaries

- finite coordinate/confidence validation and VLM producer rejection;
- mirror twice restoration, left/right swaps, deterministic angles, missing and
  zero-length vectors;
- stable fake pose and segmentation outputs;
- metadata-only mask contract and no-artifact markers;
- fixed 20-case plan and no real-photo flag;
- CLI plan/status and fail-closed model execution;
- N2A schema positive/negative cases;
- historical N0/N1/G1 approval-chain regression tests.

The model execution command was also checked: `npi benchmark run --profile
pose` exited 8 with `NPI_MODEL_NOT_AUTHORIZED`. No result marked
NOT_AVAILABLE or SKIPPED is treated as PASS.

## Reviewer-remediation evidence

- Added 23 focused N2A tests for strict Schema field omission/extra-property
  rejection, VLM/fake/real provenance confusion, explicit side labels,
  normalized bbox/mask-path rejection, measurement attestation, deterministic
  mismatch classification, fake-provenance mismatch, and direct real-run gate.
- The product fake harness validates 20 Pose and 20 Segmentation synthetic cases
  through its runner, per-case Schema validator, aggregator, and report DTO.
  It records no hardware metric as measured; all resource metric values remain
  null with `NOT_MEASURED` status.
- Child A schema parity: `INCONCLUSIVE` after one malformed structured result
  and two 90-second timeouts. Child B benchmark path: `INCONCLUSIVE` after
  three malformed structured results. Child C returned
  `PROVENANCE_MEASUREMENT_CHANGES_REQUIRED`; its findings were independently
  checked and incorporated as shared provenance, explicit serialization, and
  validation improvements. No child result is recorded as PASS.

Final clean-tree remediation matrix: pytest 213 passed; Ruff, format, and mypy
exit 0; quality gate 7 PASS/0 FAIL/0 NOT_AVAILABLE/0 SKIPPED; sensitive scan 0
violations; preflight 15 PASS; Pose and Segmentation fake validation each exit
0; and real `benchmark run --profile pose` exited 8 with
`NPI_MODEL_NOT_AUTHORIZED`. This is implementation evidence only and does not
predeclare a new Reviewer PASS.

## Finite/taxonomy remediation evidence — 2026-07-21

This section supersedes prior current-candidate N2A claims; historical results
above remain audit context only. The updated focused suite contains 44 passing
N2A tests before the unique amend. It adds construction-time finite rejection,
strict in-memory Schema finite rejection, strict JSON serialization, aggregate
rate rejection, BBox Schema/DTO parity, derived-field rejection, closed
measurement/status/error matrices, and three explicit zero-length geometry
cases. No test was skipped, xfailed, deleted, or loosened.

Pre-amend static checks actually passed: Ruff check exit 0, Ruff format check
exit 0, and mypy exit 0. The pre-amend full suite recorded 233 passed and one
expected existing clean-worktree failure; that result is not represented as a
PASS and must be re-run after the required single amend. The functional CLI
probe passed for both plans, status, and both fake validators; each real
`benchmark run` returned the expected exit 8. `preflight` was exit 3 only
because its Git-baseline check correctly rejects a dirty implementation tree;
it is also re-run after amend.

Child A: `FINITE_SCHEMA_PARITY_INCONCLUSIVE`; Child B:
`BENCHMARK_TAXONOMY_INCONCLUSIVE`. Each exhausted three fresh 90-second
read-only attempts with `Success=false`, `TimedOut=true`, no turns, and no
accepted output. These outcomes are not PASS evidence.

The exact N2A review target SHA is supplied externally after commit creation.
The report is bound to the immutable G1 parent SHA and current repository content.

## Required clean-candidate command matrix

- `.venv\Scripts\python.exe -m pytest -q`: exit 0, 234 passed.
- `.venv\Scripts\python.exe -m ruff check .`: exit 0.
- `.venv\Scripts\python.exe -m ruff format --check .`: exit 0, 63 files formatted.
- `.venv\Scripts\python.exe -m mypy src\nightly_photo_intelligence_pipeline`:
  exit 0, 44 source files checked.
- `.venv\Scripts\python.exe tools\run_quality.py`: exit 0, 7 PASS, 0 FAIL,
  0 NOT_AVAILABLE, 0 SKIPPED.
- `.venv\Scripts\python.exe tools\sensitive_file_scan.py`: exit 0, 0 violations.
- `.venv\Scripts\npi.exe preflight`: exit 0, 15 PASS, 0 FAIL, 0 NOT_AVAILABLE,
  0 SKIPPED.
- Both benchmark plans, status, and fake validators: exit 0. Pose and
  Segmentation each completed 20/20 synthetic PASS cases with 0 artifacts.
- Both real benchmark runs: expected exit 8 with `NPI_MODEL_NOT_AUTHORIZED`.
- `git diff --check`: exit 0.

These are actual command results. The post-evidence-amend clean-tree rerun is
still required and is reported separately to the Owner; no NOT_AVAILABLE or
SKIPPED state is represented here as a PASS.

## Scope-purity and stability remediation evidence — 2026-07-21

- The sole Reviewer scope finding was remediated by generalizing one named
  out-of-scope reference in `tasks/lessons.md`; no code, Schema, task contract,
  or authorization state was broadened.
- Parent scans of the current tracked tree and the G1-to-working-tree N2A diff:
  zero Owner-specified cross-project identifier matches, zero other-project
  path/package/build artifacts, zero model/cache/runtime-DB/derived-image
  artifacts, and exactly three pre-existing synthetic fixture images.
- `.venv\\Scripts\\python.exe -m pytest -q tests\\test_n2a.py`: exit 0,
  44 passed; this includes finite-number, BBox, taxonomy, measurement,
  provenance, additional-property, mask-path, and zero-length counterexamples.
- Synthetic CLI stability: Pose fake validation 100 runs and Segmentation fake
  validation 100 runs. Every run returned 20/20 PASS, 0 FAIL, 0 ERROR, 0
  deterministic mismatch, 20 Schema passes, 0 artifacts, `NOT_CALIBRATED`, and
  `ready_for_real_benchmark=false`; each profile had one byte-identical report
  digest across its 100 runs.
- Direct metadata-only fake-person ordering check: 100 runs, stable order
  `(0, 1)` for the two-person synthetic case.
- Authorization stress: real Pose run 20/20 and real Segmentation run 20/20
  returned the expected exit 8 and `NPI_MODEL_NOT_AUTHORIZED`; no backend,
  network request, model artifact, or real-photo read was introduced.
- First clean-candidate matrix after the scope-only amend: full pytest 234
  passed, Ruff check/format and mypy exit 0, quality gate 7 PASS/0 FAIL/0
  NOT_AVAILABLE/0 SKIPPED, sensitive scan 0 violations, preflight 15 PASS,
  both plans/status/fake validators exit 0, both real runs exit 8, and
  `git diff --check` exit 0.
- Child A scope review: two 90-second timeouts; Child B Schema/DTO review: one
  90-second timeout; Child C benchmark review: one 90-second timeout; Child D
  governance review: no accepted structured result. All are INCONCLUSIVE and
  are not PASS evidence. Parent verification supplied the deterministic local
  checks above.
- `tools/verify_handoff.py` remains an archival N0-oriented verifier and exited
  1 against the current authorized N2A state and local virtual-environment
  contents. It is not reported as a quality PASS or as current-stage preflight.
