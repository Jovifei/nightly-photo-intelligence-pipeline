# G1 Remediation Todo

Owner: Jovi
Started: 2026-07-15
Scope: `G1_CALIBRATION_20_REMEDIATION` only. N2-N8 and G2-G3 remain locked.
Target commit: amend the existing G1 commit only; no push, merge, or PR.

## Guardrails

- [x] Read the Owner remediation authorization as UTF-8 and restate the exact scope.
- [x] Run the archival handoff verifier and record its truthful failure boundary.
- [x] Verify the immutable N0/N1 SHAs, tags, three-commit topology, and clean start tree.
- [x] Create local-only recovery ref `backup/g1-before-remediation-c6a4e9` at the rejected G1 SHA.
- [x] Keep real-photo access frozen until every code/contract/synthetic gate is green.
- [x] Never enumerate the real source directory, inspect off-manifest assets, modify source ACLs,
  or create probe files in the source tree.

## Remediation Plan

- [x] Repair approval and state contracts: valid scoped G1 remediation approval, N0/N1 complete,
  N2-N8 locked, G1 authorized, G2/G3 locked, max 20, and all sensitive permissions denied.
- [x] Split the completed N1 engineering contract from a dedicated G1 data-gate contract; update
  `tasks/index.json`, schemas/examples where required, documentation, and consistency tests.
- [x] Implement a fail-closed Windows effective-access capability check for source root and each
  authorized manifest entry without writes, ACL changes, rename/delete attempts, or probe files.
- [x] Keep `OS_ENFORCED_READ_ONLY_VERIFIED` separate from
  `SOURCE_CONTENT_UNCHANGED_PRE_POST` in code, evidence, and reports.
- [x] Remove path/filename leakage at the lowest layer; safely wrap OS, Pillow/EXIF, and SQLite
  failures; retain CLI redaction as defense in depth.
- [x] Extend `sensitive_file_scan.py` for Windows absolute, UNC, WSL mount, and sensitive EXIF
  patterns with narrow explicit synthetic allowlists.
- [x] Make SQLite claim, heartbeat, retry, recovery, and release transactional and stage-safe;
  enforce one RUNNING row per asset/stage, retry ceilings, owner/expiry checks, and duration audit.
- [x] Add two-connection concurrency and failure tests for claim/recovery/release plus restart
  consistency and stable error codes.
- [x] Separate archival handoff verification from current-stage `npi preflight`; validate immutable
  hashes and mutable auth state via schema, semantic binding, baselines, task, manifest metadata,
  runtime policy, and OS read-only capability.
- [x] Bind approval to a normalized runtime-parent fingerprint and allow distinct non-escaping
  child runtimes under that parent; reject outside, overlap, reparse/junction, and raw-path leaks.
- [x] Replace the N0-era Git count assumption with exact N0 -> N1 -> one G1 stage-aware checks,
  including tags, ancestry, no merge commits, and clean-tree behavior.

## Synthetic Quality Gate

- [x] Use only packaged synthetic fixtures and temporary directories for remediation tests.
- [x] Run pytest, Ruff check, Ruff format check, mypy, unified quality, sensitive scan, and
  synthetic/current-stage preflight; record real exit codes with no skipped-as-pass claims.
- [x] Run `git diff --check`, inspect the complete G1 diff, and verify no sensitive/runtime files.

## Conditional Real G1 Gate

- [x] Verify only the frozen manifest file's SHA-256, count, and uniqueness before any photo open.
- [x] Verify approval/state/baselines/data cap/task/runtime-parent/child/source separation.
- [x] Run the non-mutating OS capability check on source root and all 20 authorized entries.
- [x] If OS read-only is FAIL or NOT_VERIFIED, do not read/hash any real photo; stop with
  `G1_REMEDIATION_CODE_COMPLETE_BLOCKED_ON_SOURCE_READ_ONLY`.
- [x] Evaluate the real-run condition. It is false because OS read-only failed; preserve old
  evidence and do not execute a new real G1 run.
- [x] Record real G1 integrity/idempotency/duplicate/EXIF/output revalidation as NOT RUN because
  the mandatory pre-content read-only gate failed.

## Closeout

- [x] Update the G1 report to distinguish rejected historical evidence, remediation evidence,
  OS read-only capability, content integrity, synthetic results, real results, and unknowns.
- [x] Add a review section with exact commands, exit codes, hashes, blockers, and non-blockers.
- [x] Amend all valid remediation changes into the existing G1 commit; create no second commit.
- [x] Re-run final gates after amend; prove clean tree, total commits=3, N1..HEAD=1, unchanged
  N0/N1 SHAs/tags, no merge commits, and provide the exact SHA for independent review.

## Review

- Status: historical remediation evidence below is superseded for final G1
  acceptance by the protected-snapshot execution recorded in the next section.
- Archival handoff baseline: FAIL as expected for a post-N1 implementation tree; retained as an
  archival check only, not accepted as current-stage preflight evidence.
- Historical real G1 execution: retained for audit only and not treated as final passing evidence.
- Real photo access during remediation so far: NOT USED.
- Frozen manifest file: SHA-256
  `29eee5fdb8e16c85649752501c4b722d2b4d071950c8a989add040e895a75c47`, count 20,
  unique 20, all PASS. No manifest entry was printed.
- Formal current-stage preflight: exit 3; 14 PASS, 1 FAIL. The sole failure was
  `NPI_SOURCE_READ_ONLY_NOT_VERIFIED`.
- OS capability check: 20 authorized entries checked, 0 indeterminate categories, FAIL because
  the current account has effective directory create/delete/ACL/attribute and file
  write/append/delete/ACL/attribute capabilities.
- Real photo content opened/hashed/parsed during remediation: 0.
- Source ACL, permissions, files, and directory entries changed by remediation: 0.
- `.venv/Scripts/python.exe -m pytest -q`: exit 0, 190 passed.
- `.venv/Scripts/python.exe -m ruff check .`: exit 0, all checks passed.
- `.venv/Scripts/python.exe -m ruff format --check .`: exit 0, 44 files formatted.
- `.venv/Scripts/python.exe -m mypy src/nightly_photo_intelligence_pipeline`: exit 0,
  26 source files, no issues.
- `.venv/Scripts/python.exe tools/run_quality.py`: exit 0, 7 hard gates PASS, 0 FAIL,
  0 NOT_AVAILABLE, 0 SKIPPED.
- `.venv/Scripts/python.exe tools/sensitive_file_scan.py`: exit 0, 0 violations.
- Legal synthetic CLI preflight test: exit 0.
- Formal owner-frozen configuration preflight: exit 3, 14 PASS, 1 FAIL; sole failure
  `NPI_SOURCE_READ_ONLY_NOT_VERIFIED`.
- Concurrency/migration coverage: claim, heartbeat, retry ceiling, recovery, owned release,
  restart, nested rollback, v1-to-v3 migration, forged-history rejection, and frozen-DDL
  attestation all included in the 190 passing tests.
- A pre-final quality run correctly detected stale mutable-state hashes after whitespace cleanup;
  the four hashes were recomputed, the approval was rebound, and the complete matrix then passed.
- Blocking finding: the current account retains mutating rights on the owner-frozen source.
- Non-blocking findings: Python 3.11 and production perceptual-hash thresholds remain outside G1.

## Resume Audit — 2026-07-15

The prior `CODE COMPLETE` conclusion is reopened after the Codex desktop restart. The rejected
G1 backup ref remains fixed at `c6a4e9149e681565a88b7e50a980f7cc63ff2f29`; the current amended
candidate is being re-audited and must not be treated as final evidence yet.

- [x] Reconfirm clean start tree, three-commit topology, immutable N0/N1 tags, and local backup ref.
- [x] Re-run the archival handoff checker and retain its expected post-delivery failure separately.
- [x] Re-run the synthetic pytest suite: 94 passed, exit 0.
- [x] Re-run Ruff check, Ruff format check, mypy, unified quality, and sensitive scan: exit 0.
- [x] Load retry ceilings from the versioned retry policy inside `StateStore`; callers must not
  choose `max_attempts`, and exhaustion must persist a stable terminal error code.
- [x] Add explicit SUCCEEDED and FAILED heartbeat rejection coverage and align the error taxonomy.
- [x] Resolve every remaining contract, privacy, read-only, runtime, and preflight audit finding.
- [x] Re-run the complete synthetic quality matrix after the corrections.
- [x] Run formal G1 preflight with the approved source, manifest, runtime parent, and a fresh child;
  this may inspect only manifest metadata and OS capabilities until read-only is verified.
- [x] If OS-enforced read-only remains unverified, keep real-photo reads at zero and close out with
  `G1_REMEDIATION_CODE_COMPLETE_BLOCKED_ON_SOURCE_READ_ONLY`.
- [x] Amend the existing single G1 commit again, verify a clean tree, and publish the new Reviewer SHA.

## G1 Synthetic Soak — 2026-07-16

- [x] Protect the clean `39ab277` starting point and keep real-photo reads at zero.
- [x] Run 1,000 claim, 1,400 heartbeat, 500 retry, 500 recovery, 500 release, and
  100 migration lifecycle rounds with 4,102 SQLite invariant checks.
- [x] Run 1,000 manifest fuzz, 1,000 path/error redaction, 500 runtime-boundary,
  100 capability-probe plus one native-probe, and 200 preflight-tamper cases.
- [x] Reproduce and fix unknown future migration acceptance, native SQLite busy
  leakage, zero-free-disk acceptance, and runtime-child disappearance TOCTOU.
- [x] Keep all soak artifacts outside Git and clean temporary database/work trees.
- [x] Re-run the full clean-tree quality matrix after the single G1 amend.
- [x] Re-run legal synthetic preflight and current real-source non-content preflight;
  keep the real G1 ingest blocked when OS-enforced read-only is not verified.

Soak summary: 6,811 primary scenario rounds plus 4,102 per-round SQLite invariant
checks; 132.259 seconds combined wall time; peak traced Python memory 3.884 MiB;
maximum SQLite database 872,448 bytes; all soak assertions passed. One harness
attempt was discarded after a command-wrapper timeout and restarted from round 1.

## Protected Snapshot G1 Execution — 2026-07-17

- [x] Validate a non-elevated, Medium-integrity token before content access.
- [x] Validate LocalSystem ownership, protected root inheritance, strict child
  inheritance, and all-denied mutating capabilities without source mutations.
- [x] Verify the approved manifest SHA-256, 20-entry count, uniqueness, order,
  source/runtime separation, cap, and reparse/overlap boundaries.
- [x] Run formal current-stage preflight: exit 0, 15 PASS, 0 FAIL.
- [x] Hash all 20 authorized snapshot entries before and after processing; all
  SHA-256 values matched.
- [x] Run the first frozen-manifest ingest: 20 scanned, 19 canonical assets, one
  exact duplicate, zero near-duplicate candidates, zero derivative/model output.
- [x] Run the second frozen-manifest ingest: zero new assets; canonical count
  remained 19, proving idempotency.
- [x] Verify the actual non-sensitive EXIF result: no readable EXIF blocks among
  the 20 entries; no inferred fields and no GPS/location/identity leakage.
- [x] Verify resume/status/report, database integrity/foreign keys, and manifest
  membership rejection before source content access for out-of-manifest requests.
- [x] Run the final clean-tree quality matrix after the single G1 amend.

Snapshot execution summary: `OS_ENFORCED_READ_ONLY_VERIFIED=PASS`; formal
preflight exit 0; 20/20 pre/post source SHA-256 unchanged. The original photo
library was not accessed by this execution, and no actual filename or absolute
path is retained in tracked evidence.

## Night continuation audit — 2026-07-18

- [x] Revalidated the current amended HEAD provenance against the immutable N0/N1
  baselines; no merge, push, or extra phase commit was introduced.
- [x] Revalidated the Owner snapshot ACL boundary with a non-elevated,
  Medium-integrity token and no source mutation; all mutating capabilities were
  denied and the formal preflight exited 0 (15 PASS, 0 FAIL).
- [x] Rehashed all 20 frozen entries before/after the two ingest passes; all
  source SHA-256 values matched (2,449,457 total bytes).
- [x] Re-ran resume/status/report: all exited 0; 0 interrupted runs remained.
- [x] Rejected synthetic manifest-external and over-cap references before source
  open; no directory rescan was used.
- [x] Confirmed no readable EXIF, no inferred/fabricated fields, no GPS/location/
  identity retention, no absolute-path or manifest-name leak, and no derivative
  or model output.
- [x] Re-ran the complete quality matrix: 190 pytest cases passed; Ruff check,
  Ruff format check, mypy, unified quality, and sensitive scan all exited 0.
- [x] Independent child review chain was attempted with three fresh 90-second
  sessions for each of A/B/C/D; all returned `Success=false`, `TimedOut=true`,
  `Turns=null`, no launch error, and zero stdout/stderr. The final Reviewer
  attempt also timed out. All are recorded as INCONCLUSIVE and cannot be
  reported as PASS.

Night continuation evidence is complete for the real G1 run, but final closure
is INCONCLUSIVE because the independent review chain produced no accepted
result. Owner approval is still required; N2, G2, and all later stages remain
locked.

## N2A model-free preparation — 2026-07-19

Owner has approved immutable G1 `4a807dbbcd147a106b02b7e3899aa701c2028d83`
and authorized only N2A Pose/Segmentation Benchmark Preparation. G1 must not be
amended, and N2B model download/inference remains locked.

### Plan

- [x] Create local-only `g1-approved-2026-07-19` tag pointing exactly to G1.
- [x] Run three bounded, read-only child research/review packages; unsuccessful
  structured results and one retry timeout were recorded truthfully; parent
  completed the directions from official sources.
- [x] Add N2A capability/state/schema and G1 completion approval without changing
  N0/N1/G1 history.
- [x] Implement typed pose/segmentation contracts, synthetic fake backends,
  deterministic geometry, benchmark result structures, and model fail-closed CLI.
- [x] Add research provenance, license/candidate ledgers, N2B artifact request,
  tests, and N2A reports without downloading weights or reading real photos.
- [x] Run the complete quality matrix plus N2A preflight/model fail-closed tests:
  pytest 201 passed; all required quality commands and preflight exit 0; model
  run exits 8 with NPI_MODEL_NOT_AUTHORIZED.
- [x] Create exactly one local N2A commit, verify G1 tag/SHA unchanged, and stop
  for Owner approval; do not push, merge, enter N2B, or run inference.

### N2A review handoff

- N2A commit: `365bbd37fef1f13b11c95fd16a619e4e64762d0e` before evidence-only
  amend; final SHA is reported by the parent after the last amend.
- G1 tag remains immutable and N2B/G2/N3-N8 remain locked.

## N2A minimal reviewer remediation — 2026-07-20

Owner accepted independent Reviewer conclusion `CHANGES_REQUIRED` for N2A
`5dc07f125de5117522c439c750848465fcb8ceb6`. Scope is limited to amending that
single N2A commit; N2B/G2, model downloads/inference, and real-photo reads stay
locked.

- [x] Audit the four-commit topology and create local-only recovery ref
  `backup/n2a-before-review-remediation-5dc07f`.
- [x] Run bounded read-only child reviews. Child A/B remained INCONCLUSIVE;
  Child C returned `PROVENANCE_MEASUREMENT_CHANGES_REQUIRED`; no result was
  treated as PASS.
- [x] Replace permissive N2A Schema with closed Pose/Segmentation/Benchmark
  document variants and measurement/provenance conditionals.
- [x] Add shared provenance matrix, explicit side enum/mirror mapping, and
  strict Python validation parity.
- [x] Add production `benchmark validate --backend fake` path with runner,
  per-case result, aggregate, Schema checks, deterministic rerun, and no-artifact
  attestation for exactly 20 synthetic cases per profile.
- [x] Add positive/negative regression tests without weakening historical tests.
- [x] Run final quality matrix from an amended clean worktree and record actual
  exit codes: pytest 213 passed; Ruff/format/mypy exit 0; quality 7/7 PASS;
  sensitive scan 0; preflight 15 PASS; fake validate exit 0; real run exit 8.
  Do not claim new Reviewer PASS.

## N2A finite/taxonomy remediation — 2026-07-21

Owner accepted a subsequent independent-review `CHANGES_REQUIRED` conclusion for
the sole N2A commit `de5fb48dd3a92da31bee3442942480b54956fc77`. Scope is limited
to finite-number rejection, strict Schema/DTO parity, canonical BBox, closed
status/error taxonomy, measurement attestation, and related regression evidence.
N2B/G2, real-photo reads, model downloads/inference, push, merge, and release
remain prohibited.

### Plan

- [x] Confirm the clean four-commit topology and immutable N0/N1/G1 parents;
  create local-only recovery ref
  `backup/n2a-before-finite-taxonomy-remediation-de5fb48`.
- [x] Complete two bounded read-only Child-Claude reviews; unsuccessful results
  remain INCONCLUSIVE and never count as PASS.
- [x] Reject every non-finite public numeric value at DTO construction and at the
  common strict Draft 2020-12 plus finite-semantic validation entrypoint.
- [x] Make normalized `x/y/width/height` the only serialized BBox representation
  and enforce the status/error/measurement consistency matrices.
- [x] Restore explicit zero-length geometry coverage and add Schema/DTO parity
  counterexamples without weakening existing tests.
- [x] Update the five required N2A/N2B reports with actual evidence and blocking
  N2B inputs; do not self-reference the eventual commit SHA.
- [x] Run the complete required quality/CLI matrix, amend the sole N2A commit,
  then verify four commits, one G1-to-HEAD commit, no merge, no push, and a clean tree.

### Review

- In progress. The legacy `tools/verify_handoff.py` exited 1 because its N0/G0
  assumptions intentionally reject the current authorized N2A state and its
  runtime virtual-environment files. It is archival evidence only, not an N2A
  preflight result and is not reported as PASS.
- Child A result: `FINITE_SCHEMA_PARITY_INCONCLUSIVE` after three fresh
  read-only attempts; each timed out at 90 seconds with no structured output.
- Child B result: `BENCHMARK_TAXONOMY_INCONCLUSIVE` after the same three-attempt
  bounded policy. No child result was treated as PASS.
- Focused N2A test evidence: 44 passed after finite/taxonomy changes. The
  pre-amend full suite recorded 233 passed and one expected clean-worktree
  failure; after the required amend, the clean candidate full suite and
  preflight passed as recorded below.
- Clean candidate evidence before the final evidence-only amend: 234 pytest
  passed; Ruff, format, mypy, quality (7 PASS), sensitive scan, preflight (15
  PASS), plans/status/fake validation, and diff check all exited 0. Both real
  runs correctly exited 8 with `NPI_MODEL_NOT_AUTHORIZED`.

## N2A scope-purity remediation — 2026-07-21

- [x] Reconfirm the clean four-commit topology and create local-only recovery
  ref `backup/n2a-before-scope-purity-remediation-8e25c04` at the rejected N2A
  candidate; no push, merge, reset, clean, or second N2A commit.
- [x] Generalize only the named out-of-scope reference in `tasks/lessons.md`;
  retain the reusable scope-drift prevention lesson without adding another
  concrete project name.
- [x] Parent scope audit: current tracked tree and G1-to-working-tree N2A diff
  have zero Owner-specified cross-project identifier matches; no other-project
  path/package/build artifact was found.
- [x] Parent artifact audit: zero model/cache/runtime-DB/derived-image artifact
  paths; exactly three pre-existing synthetic fixture images; no untracked file.
- [x] Child A scope review exhausted two 90-second attempts; Child B Schema/DTO
  and Child C benchmark each timed out once; Child D returned no accepted
  structure. All are INCONCLUSIVE and no child outcome is treated as PASS.
- [x] Run N2A focused counterexamples: 44 passed. Run synthetic CLI stability:
  100 Pose plus 100 Segmentation fake validations, all deterministic and
  artifact-free. Run real authorization gate: 20 Pose plus 20 Segmentation
  calls, all expected exit 8 with `NPI_MODEL_NOT_AUTHORIZED`.
- [x] Run clean-candidate pytest (234), Ruff, format, mypy, quality, sensitive
  scan, preflight, plan/status/fake validate/real gate, and diff checks with
  the actual results preserved in N2A evidence; N2B remains locked.
- [x] Complete the scope-only amend and repeat the final clean-tree quality and
  scope scans for the external Reviewer handoff.
  Evidence: full test, lint, type, quality, sensitive-scan, preflight,
  benchmark-plan/validate, and scope-purity checks completed successfully.
  The immutable G1 parent is `4a807dbbcd147a106b02b7e3899aa701c2028d83`.
  The exact N2A review SHA is supplied externally after commit creation;
  external independent review remains pending.
