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

## N2B0 model artifact qualification — 2026-07-23

Owner approved immutable N2A `f79d2df504622ff82aa5e53d1486310bbea9985a`
and local tag `n2a-approved-2026-07-22`. Only N2B0 qualification is authorized.

### Plan

- [x] Create the N2A completion approval and N2B0 contract/state gates.
- [x] Record official-source-only Pose and segmentation proposals, license/supply-chain gaps,
  external cache/quarantine design, N2B1 download plan, N2B2 benchmark plan, and Owner packet.
- [x] Create a non-authorizing draft artifact allowlist and schema; all incomplete fields fail closed.
- [x] Run full regression/quality matrix (236 pytest), create exactly one N2B0 local commit, and stop for independent review.

### Review

- Child A timed out twice; Child B/C/D each timed out once. None is PASS evidence.
- No model artifact, dependency, Docker image, runtime database, or real-photo access was created.

## N2B0 RTMW metadata remediation - 2026-07-23

- [x] Preserve the original N2B0 commit in local-only `backup/n2b0-before-rtmw-metadata-fix-be9f900`.
- [x] Replace the RTMW fallback typo `dw-l_m` with the official `dw-l-m` filename and URL in every tracked derived reference.
- [x] Verify the wrong URL is HTTP 404 and the corrected official URL is HTTP HEAD 200 with final domain, Content-Length, ETag, and Last-Modified; no artifact body was requested.
- [x] Keep RTMW `INCONCLUSIVE` / `N2B0_ARTIFACT_QUALIFICATION_BLOCKED`; HTTP 200 does not authorize download, commercial use, or inference.
- [x] Add fixture-only regression coverage for the corrected filename, URL, fail-closed status, and absence of the old typo.
- [x] Amend the sole N2B0 commit after the full quality matrix and stop for external review.

## N2B0.5 artifact rights and provenance closure - 2026-07-24

### Plan

- [x] Fix local-only `n2b0-approved-2026-07-24` at the Owner-approved N2B0 SHA
  and create the N2B0 completion approval bound to N2A/N2B0/Reviewer/Owner.
- [x] Dispatch bounded read-only Child-Claude research; retain three explicit
  MMPose timeout diagnostics and use parent official-source fallback evidence.
- [x] Verify exact Pose and Segmentation filenames, official URLs, code vs
  weight rights, HEAD metadata, zero redirects, and draft domains without any
  payload GET or model execution.
- [x] Add fail-closed four-artifact rights matrix, upstream questions, draft
  allowlist, quarantine/cache/rollback plans, and locked N2B1/N2B2 plans.
- [x] Run the full quality matrix, create exactly one N2B0.5 commit, and stop
  at Owner approval.

### Review

- Current disposition is `N2B0_5_RIGHTS_CLARIFICATION_BLOCKED`: all four exact
  artifact identities, official URLs, HEAD sizes, and code licenses are
  recorded, but weight/model licenses, commercial use, immutable revisions, and
  official SHA-256 values remain UNKNOWN.
- Model download bytes, model execution, and real-photo reads remain zero.

## N2B0.5 governance remediation - 2026-07-26

### Plan

- [x] Preserve the rejected sole N2B0.5 commit with local-only recovery ref
  `backup/n2b0-5-before-state-negative-tests-ec13450`; retain a six-commit,
  no-merge topology and amend only this N2B0.5 successor.
- [x] Remove the duplicate `data_scope.N2B0_MODEL_ARTIFACT_QUALIFICATION`
  member so the sole value is `APPROVED_COMPLETE`; explicitly retain N2B1-Q,
  N2B1-P, N2B2, G2, and G3 locks.
- [x] Add one strict JSON raw-byte parser before Schema and semantic checks;
  it returns `NPI_DUPLICATE_JSON_MEMBER` without leaking a source path or
  payload, while YAML remains at its existing parser boundary.
- [x] Add zero-I/O future-artifact policy tests for rights, HTTPS redirect and
  exact length metadata, quarantine/cache approvals, execution isolation, and
  ZIP/PTH metadata safety; do not download or run a model.
- [x] Run all required quality commands, strict tracked-JSON scan, exact Git
  topology checks, then amend the one N2B0.5 commit and stop for review.

### Review

- In progress. The previous Child-Claude A package had three watchdog timeouts;
  this closely coupled governance remediation was completed directly in the
  parent. No timeout is treated as review evidence or PASS.
- The four artifact verdicts remain fail-closed: `weights_license=UNKNOWN`,
  immutable revision/official SHA-256 unknown, commercial evidence unknown
  with disposition `REQUIRES_OWNER_DECISION`, and all four `READY=FAIL`.
- Clean-candidate evidence before the final task-record amend: 286 pytest
  passed; Ruff, formatting, mypy, quality 7/7, sensitive scan, preflight
  15/15, diff check, and strict JSON scan all exited 0. The scan reported
  49 tracked JSON files, 2 explicit invalid duplicate fixtures, and 0
  production duplicate or malformed JSON files.

## N2B0.5 transport gate remediation - 2026-07-26

### Plan

- [x] Preserve the reviewer-targeted sole N2B0.5 candidate using the local-only
  recovery ref `backup/n2b0-5-before-transport-gate-fix-5052463`.
- [x] Bind final-response URL basenames exactly to the approved artifact
  filename, including query/fragment isolation, one-time percent decoding,
  Unicode normalization, case-sensitive comparison, and escape rejection.
- [x] Add explicit Owner byte-ceiling validation to the typed transport
  contract; reject missing, invalid, expected-over-cap, and final-response
  over-cap values before any future quarantine action.
- [x] Define a future-only N2B1-Q approval schema whose required fields bind
  the artifact, filename, request URL, final domains, exact size, Owner cap,
  redirect budget, quarantine fingerprint, expiry, and Owner decision.
- [x] Add focused negative tests and redacted report/Owner-packet evidence;
  retain the draft as `DRAFT_NOT_AUTHORIZED` with no executable Owner cap.
- [x] Run focused and full quality gates, record actual exit codes, amend only
  the sole N2B0.5 commit, and stop for external review.

### Review

- In progress. Child A and Child B were not dispatched: the bounded policy,
  tests, schema, and reports are tightly coupled, while the prior comparable
  Child-Claude package reached three watchdog timeouts. This is recorded as
  `NOT_DISPATCHED_PARENT_DIRECT`, not PASS.
- No model-download bytes, model execution, real-photo reads, payload
  deserialization, ZIP extraction, push, merge, or release occurred.
- Clean-commit evidence: focused 75 passed; full pytest 316 passed; Ruff,
  formatting, mypy, unified quality 7/7, sensitive scan, preflight 15/15,
  strict JSON scan, and diff check all exited 0. The strict scan found 50
  tracked JSON files, 2 expected invalid duplicate fixtures, 0 production
  duplicates, and 0 malformed files.

## N2B0.5 composed quarantine-gate remediation - 2026-07-26

### Plan

- [x] Preserve `582797e` with local-only recovery ref
  `backup/n2b0-5-before-composed-quarantine-gate-582797e`.
- [x] Replace production split approval/transport validation with one strict
  composed no-I/O entry and non-authorizing immutable result values.
- [x] Bind approval-derived request/final domains, redirect chain, final
  filename, expected size, Owner cap, fingerprint, rights snapshot,
  project-state digest, N2B0.5 baseline, owner decision, and expiry.
- [x] Add fail-closed Schema/semantic/domain/time/rights/state/direct-API
  negative tests using explicit future synthetic state only.
- [x] Record final quality evidence, amend the sole N2B0.5 commit, and stop
  for external review without opening N2B1-Q/P, N2B2, or G2.

### Review

- Child A composition audit reached three 90-second timeouts with
  `Success=false`, `TimedOut=true`, and no partial result. Child B is
  `NOT_DISPATCHED_PARENT_FALLBACK_AFTER_CHILD_A_TIMEOUTS`; neither is PASS.
- Current production N2B1-Q/P, N2B2, and G2 remain locked. Model downloads,
  model execution, real-photo reads, payload deserialization, ZIP extraction,
  push, merge, and release remain 0 or not performed.
- Final local evidence: composed file 52 focused tests (48 negative test
  entries and two additional denial branches); combined focused suite 81
  passed; full pytest 322 passed; Ruff, formatting, mypy, quality 7/7,
  sensitive scan, preflight 15/15, strict JSON scan, and diff check all exit 0.

## N2B0.5 schema/trust-boundary remediation - 2026-07-26

Owner accepted Reviewer conclusion `CHANGES_REQUIRED` for the sole N2B0.5
commit `c6be529e0de7ae6d06c416b6022fa1134e0d3b56`. This bounded remediation may
amend only that commit. N2B1-Q/P, N2B2, G2/G3, model payloads/dependencies,
model execution, real-photo reads, cache/quarantine writes, push, merge, and
release remain prohibited.

### Plan

- [x] Verify the exact six-commit, no-merge topology; preserve the reviewed
  candidate in local-only `backup/n2b0-5-before-schema-trust-boundary-fix-c6be529`.
- [x] Audit the Reviewer findings: `_VALIDATION_TOKEN` is importable and the
  composed gate lacks formal qualification-snapshot and project-state Schema
  validation.
- [x] Remove token/factory authority: a frozen result DTO is output only and
  no public future gate accepts it as a credential.
- [x] Add a fixed, closed qualification-snapshot Schema and catalog entry; use
  the fixed current project-state Schema rather than a caller-supplied path.
- [x] Make the one public no-I/O gate accept raw document bytes and validate in
  deterministic duplicate -> parse -> Schema -> digest/semantic -> transport order.
- [x] Add direct-forgery, malformed/duplicate/schema/order/no-transport tests;
  update reports, plans, and lessons without overstating independent review.
- [x] Amend only the existing N2B0.5 commit; run all required quality commands,
  topology checks, and stop for external review.

### Review

- Child A/B are `NOT_DISPATCHED_PARENT_DIRECT`: comparable
  read-only Child-Claude packages already exhausted the three-attempt timeout
  policy, and no timeout may be described as PASS.
- Focused N2B0.5 governance, transport, Schema, order, and forgery suite:
  103 passed, exit 0. It includes direct DTO, `object.__new__`,
  `object.__setattr__`, and `isinstance` non-authorization checks.
- Final clean-commit suite: 344 passed, exit 0. Ruff check, Ruff format check,
  strict mypy, unified quality (7 PASS, 0 FAIL, 0 NOT_AVAILABLE, 0 SKIPPED),
  sensitive scan, current-stage preflight (15 PASS), strict JSON scan, and
  `git diff --check` all exited 0.
- Strict JSON scan covered 52 tracked JSON documents, two isolated expected
  duplicate-member fixtures, zero production duplicates, and zero malformed
  production documents. Model-download bytes, model execution, real-photo
  reads, cache/quarantine writes, archive extraction, and deserialization are 0.

## N2B0.5 revision/hash/time contract remediation - 2026-07-26

Owner accepted the external Reviewer conclusion `CHANGES_REQUIRED` for the
sole N2B0.5 candidate `5c9f4ef11a6d911478c0ce71daf8670e4b160abe`. This repair
may amend only that candidate. N2B1-Q/P, N2B2, G2/G3, all model downloads and
execution, real-photo access, cache/quarantine writes, archive extraction,
push, merge, and release remain prohibited.

### Plan

- [x] Record the correction lesson and retain the local-only pre-remediation
  recovery ref.
- [x] Require closed, non-floating immutable revision evidence and an
  official lower-case SHA-256 in the qualification snapshot when status is
  `PASS`.
- [x] Require an exactly matching revision and expected SHA-256 in the future
  N2B1-Q approval, and require a timezone-aware `not_before` time window.
- [x] Add deterministic schema, digest, semantic, ordering, and no-I/O tests
  using only future synthetic artifact evidence.
- [x] Update redacted plans, decision packet, and test evidence; run all
  required checks; amend only the sole N2B0.5 commit; stop for external review.

### Review

- Complete. Child A/B are `NOT_DISPATCHED_PARENT_DIRECT`: three comparable
  Child-Claude attempts already reached their watchdog timeout cap, so direct
  parent implementation and review is required. This is not a PASS result.
- Closed revision/hash evidence, exact snapshot/approval equality, canonical
  digest binding, and required RFC-3339 `not_before` time-window validation
  are implemented with future synthetic no-I/O tests only.
- Final clean-worktree evidence: focused N2B0.5 suite 147 passed; full pytest
  384 passed; Ruff, format, strict mypy, quality 7/7, sensitive scan,
  preflight 15/15, strict JSON scan, and `git diff --check` exited 0. No
  download, model execution, photo read, cache/quarantine write, push, merge,
  or release was performed.

## N2B0.6 license-clear alternative candidate research - 2026-07-26

N2B0.5 commit `5ad9f8d7d0d6fa267df02d90ef25957bc679e232` is Owner-approved
and immutable. N2B0.6 is authorized only for metadata-only research of at most
two new Pose and two new lightweight person-segmentation candidates. No model
payload, dependency, runtime, cache/quarantine write, photo read, message,
push, merge, or later-stage operation is authorized.

### Plan

- [x] Create the local N2B0.5 approval tag and completion-approval record;
  extend only versioned, closed state and task-contract surfaces needed for
  N2B0.6.
- [x] Verify at most two official Pose candidates and two official segmentation
  candidates using official text/API metadata and HTTP HEAD only.
- [x] Record a fail-closed qualification matrix, preserve the four historical
  candidates as READY FAIL, and draft but do not send upstream questions.
- [x] Add candidate-cap, evidence, authorization-lock, and negative tests;
  update sanitized Owner reports and plans.
- [x] Run all required quality checks, create exactly one N2B0.6 commit, and
  stop for independent review without entering N2B1-Q/P, N2B2, or G2.

### Review

- Research and focused validation complete. Any missing weights license,
  commercial grant, immutable revision, official SHA-256, official source, or
  HTTPS evidence is a fail-closed qualification failure, never an inferred
  PASS. Final clean-worktree quality evidence: 404 pytest passed; Ruff,
  formatting, mypy, unified quality 7/7, sensitive scan, preflight 15/15,
  strict JSON scan, and `git diff --check` all exited 0. No model payload,
  model execution, archive extraction, real-photo read, cache write, push, or
  merge occurred.

## N2B0.6 bundle-evidence remediation - 2026-07-26

Owner accepted an independent Reviewer `CHANGES_REQUIRED` conclusion for
`bb15eb53517c588d82f8e11a2ec395792058262a`. This remediation may amend only
that N2B0.6 candidate; N2B0.5 and earlier approved history remain immutable.
The candidate pool remains exactly two Pose and two segmentation records.
Model payload/range requests, installs, conversion, execution, archive/cache
writes, real-photo reads, N2B1-Q/P, N2B2, G2/G3, push, merge, and release are
prohibited.

### Plan

- [x] Audit the exact seven-commit topology and create the local-only recovery
  reference `backup/n2b0-6-before-bundle-evidence-fix-bb15eb5`.
- [x] Re-enumerate each selected official OMZ bundle from its fixed revision,
  including every required file, direct URL, size, checksum, and HEAD metadata.
- [x] Derive and record the complete MODNet source-and-conversion dependency
  bundle from the fixed conversion command and imported source files.
- [x] Replace the shallow candidate Schema and readiness-only validator with
  closed, always-on per-file/bundle validation and recomputed matrix rules.
- [x] Add negative bundle, MODNet, readiness-fail, candidate-limit, and gate
  tests; update only the necessary sanitized reports and records.
- [x] Amend the sole N2B0.6 commit, run all Owner-required quality and locked
  benchmark commands, then stop for a new independent review.

### Review

- A final `READY=FAIL` is not a reason to skip evidence validation: every
  required bundle file is independently checked before an intermediate
  qualification status can be PASS.
- Complete static evidence: 4 candidate records, 7 required payload files,
  all direct/zero-redirect HTTPS target and SHA-384 records complete. All four
  `OFFICIAL_SHA256_CONFIRMED=FAIL`; all four final readiness values are FAIL.
- MODNet source-and-conversion closure records its checkpoint, config,
  converter, import closure, fixed source identities, commands, and only
  `NOT_GENERATED` outputs. No conversion or model execution occurred.
- Clean-amend evidence: pytest 403 passed; Ruff, format, mypy, quality 7/7,
  sensitive scan, preflight 15/15, strict JSON scan, benchmark plans/status,
  and diff check all exited 0. Benchmark run was deliberately denied with
  `NPI_MODEL_NOT_AUTHORIZED`, exit 8, for both profiles; this is recorded as
  expected denial, not PASS.

## N2B0.6 evidence-binding remediation - 2026-07-26

Owner accepted an independent Reviewer `CHANGES_REQUIRED` conclusion for the
sole current N2B0.6 candidate `d740efce0ca8d8e29b0382b3f3d3d4302205f199`.
This is a metadata-only, single-amend remediation: the candidate pool,
SHA-384 facts, MODNet closure, phase locks, and all zero-action counters must
remain unchanged. Downloads, payload/range requests, model work, photo access,
N2B1/N2B2/G2, push, merge, and release remain prohibited.

### Plan

- [x] Audit the exact candidate/parent/baseline topology, verify clean start,
  and create `backup/n2b0-6-before-evidence-binding-fix-d740efc`.
- [x] Obtain two bounded read-only audits of the URL/revision and license
  evidence gaps; both returned `CHANGES_REQUIRED`, not PASS.
- [x] Bind every payload filename to its fixed direct and final HTTPS URL,
  including canonical basename rejection for encoded separators and path-like
  values.
- [x] Make the production schema/API require typed, immutable evidence with
  exact OMZ `model.yml` project/revision/path binding and bi-directional
  per-payload source/checksum/license references.
- [x] Replace license string inference with typed evidence-ID decision objects,
  add taxonomy/negative fixtures, update sanitized reports, and mark this
  review evidence with actual command outcomes.
- [x] Amend the sole N2B0.6 candidate, rerun the complete Owner quality and
  locked-stage matrix, and stop for external review.

## N2B0.6 current-stage handoff integrity remediation - 2026-07-29

Independent read-only review of `03f110296d256ce896eebd0bf9afb5b2a01b57e6`
returned `CHANGES_REQUIRED`. The candidate evidence remains metadata-only and
fail-closed, but the historical N0 verifier, stale entry contracts, and stale
manifest could not prove current-stage handoff integrity. No N2B0.6 completion
approval/tag may be created until this candidate is remediated and freshly
reviewed.

### Plan

- [x] Preserve N0/N1/G1/N2A/N2B0/N2B0.5 immutable tags and verify the clean
  N2B0.6 candidate before editing.
- [x] Replace the N0-only executable verifier with a current-stage verifier
  that binds the active task, phase locks, immutable baselines, exact tracked
  file set, and current manifest.
- [x] Reconcile current entry contracts so they name N2B0.6 and its
  metadata-only restrictions rather than N0-only scope.
- [x] Regenerate the full tracked-file manifest, add negative verifier tests,
  run the full quality suite, and amend only the N2B0.6 candidate.
- [ ] Request a fresh independent review of the amended clean candidate; do
  not create an N2B0.6 completion approval/tag until it returns a valid
  conclusion.

### Hard boundary

This remediation authorizes no new artifact candidate, model download, model
execution, dependency install, source-photo access, cache/quarantine write,
N2B1/N2B2/N3/G2/G3 action, push, merge, or release.

## N2B0.7 RTX 4070 SUPER native artifact qualification - 2026-07-29

N2B0.6 candidate `eb2eaeb61f1c21923d131a115d63edbcdebd8cb2` passed fresh
local independent review and was approved with the local-only tag
`n2b0-6-approved-2026-07-29`. The Owner's bounded continuous instruction
activates only N2B0.7 now; N2B1-Q/P, N2B2, and N3A remain conditional and
locked until each predecessor hard gate passes.

### Plan

- [x] Record the immutable N2B0.6 completion approval, local tag, and bounded
  continuation authorization without opening downloads or real-photo access.
- [x] Verify Windows/Python/GPU availability read-only and inspect official
  TorchVision v0.22.1 source, artifact identity, wheel availability, and
  code/weight/dataset/commercial terms separately.
- [x] Record the Pose variant/filename mismatch and the unknown pretrained
  weights/commercial-use status without substituting a local hash or a legacy
  variant.
- [x] Produce a sanitized owner decision packet and future-only quarantine,
  cache, delete, and rollback design; do not implement or exercise it.
- [x] Run full quality gates, create one N2B0.7 local commit, and stop at the
  exact qualification result. Final evidence: 424 tests passed; Ruff, mypy,
  quality, sensitive scan, strict JSON scan, preflight, handoff, and Git diff
  checks exited 0.

### Hard boundary

No model payload download or Range request, wheel/dependency install, model
load/inference, real-photo read, source snapshot open, quarantine/cache write,
mask/skeleton/cutout/thumbnail, system configuration change, push, merge, or
release is authorized in N2B0.7.

## N2B0.7 library-level real-photo denial remediation - 2026-07-29

Independent review of `94b6eb6845c8f3caa23a7f15892f7e56e7c1730c` found that
the historical G1 approval could still be loaded under state schema 1.5 and
used through a direct library path. Jovi authorized a bounded remediation only:
do not read a source photo, model payload, or snapshot; do not open N2B1/N2B2/N3.

### Plan

- [x] Inventory every G1 permit, runner, EXIF, and SQLite library entry point
  using code and tests only; identify the earliest common denial boundary.
- [x] Represent the current N2B0.7 real-photo-I/O prohibition explicitly in
  the authorization snapshot without changing the immutable historical G1
  approval record.
- [x] Reject current N2B0.7 state before permit creation, source opening,
  EXIF read, or SQLite mutation; retain the historical G1 path only for a
  future explicitly authorized real-photo execution phase.
- [x] Add synthetic-only negative tests for permit, runner, source-open, EXIF,
  and SQLite non-reachability; add the precise missing artifact evidence refs
  and identity assertions from the independent review.
- [x] Run complete quality gates, amend only the unapproved N2B0.7 commit,
  and request a fresh independent review. Stop with N2B1/Q/P, N2B2, N3,
  G2, and G3 locked.

## Local research 20-photo execution - 2026-07-29

Owner Jovi selected the local-research edition and explicitly requested execution
through a 20-item director-prompt result.  The formal target is strictly local,
research-only output; it is not a commercial-rights conclusion, a model
redistribution authorization, a Bundle export, G2/G3 expansion, or an App change.

### Plan

- [x] Obtain a fresh independent read-only review of the N2B0.7 remediation
  candidate `f2b1c38301d71da52b855f73de8a67908cb525ef`: `PASS_FOR_OWNER_REVIEW`.
- [x] Create the local-only immutable `n2b0-7-approved-2026-07-29` tag at that
  exact reviewed candidate.
- [x] Record the N2B0.7 completion approval and a versioned research-only
  continuation contract before any download, install, model execution, or photo read.
- [x] Implement a separate research-only artifact policy and register-bound
  quarantine downloader with HEAD-before-GET, byte caps, local SHA-256 reread,
  path-redacted external manifests, and one-time library-level preflight permits;
  do not weaken the existing commercial-grade fail-closed N2B1 policy.
- [x] Run the approved downloader against each registered official artifact and
  independently verify its locally acquired manifest and SHA-256; three of three
  passed. Stop before cache promotion, installation, model loading, or photo
  access, as required by the N2B1R mandatory stop.
- [ ] Build and verify the isolated CUDA environment only after all approved
  local-research acquisitions validate; cache promotion remains a separately
  gated phase.
- [ ] Implement GPU Pose, person-segmentation, and local VLM backends with
  synthetic tests and one-model-per-process VRAM release evidence.
- [ ] Revalidate protected snapshot ACL/manifest/source integrity and run only its
  20 authorized entries (19 unique plus one duplicate reference) twice.
- [ ] Produce redacted JSON/HTML/Obsidian evidence, run all quality gates, and
  stop for independent N5 report review.

### Hard boundary

- Do not open any source photo before N2B2 has an explicit active capability,
  OS read-only/manifest/source-runtime gates pass, and the model stages pass.
- Treat pretrained TorchVision weight commercial rights as `UNKNOWN`: use is
  local research only, with no distribution or commercial-clearance claim.
- Never save original images, masks, overlays, thumbnails, cutouts, Base64,
  GPS, identities, real filenames, or absolute source paths in Git/reports.

## N2B1P local-research cache promotion - 2026-07-29

Owner Jovi explicitly authorized `N2B1P_CACHE_PROMOTION_ONLY` after the three
N2B1R quarantined artifacts passed transfer and local SHA-256 verification.
This is not a model-execution or photo-analysis authorization.

### Plan

- [x] Bind a new N2B1P Owner record, task, state schema, and action boundary to
  only the three exact N2B1R evidence SHA-256 values; replace the prior
  circular cache-promotion prerequisite with completed N2B1R evidence.
- [x] Implement a separate research-only promotion library that revalidates all
  raw control documents at the action boundary, rejects reparse/path escape and
  source/cache overlap, and never weakens the commercial N2B1 policy.
- [x] Copy only the verified quarantine bytes into an external content-addressed
  cache using an exclusive staging directory, streaming SHA-256, TOCTOU checks,
  atomic final rename, and a path-redacted cache manifest.
- [x] Prove idempotent cache hits, hash/size/manifest mismatch denial, forged
  caller/spec denial before file access, symlink/junction denial, and no model,
  CUDA, photo, EXIF, SQLite, or derivative-output reachability.
- [x] Run full quality gates, record redacted evidence, amend/create one local
  N2B1P commit, then stop before any environment installation, model load, or
  real-photo access.

### Review

- [x] Completed N2B1P copy-only promotion for the three evidence-bound artifacts;
  first-pass promotion and cache-hit verification were both recorded without
  model execution, CUDA, photo/EXIF access, SQLite writes, or derivatives.
- [ ] Awaiting independent review and separate Owner authorization before N2B2.

## N2B1P reviewer remediation - 2026-08-01

Scope: `N2B1P_REMEDIATION_ONLY`. Amend the sole N2B1P commit only; do not
enter N2B2, load a model, invoke CUDA, read photos/EXIF, write SQLite, or alter
the three external cache payloads/manifests.

- [x] Confirm the reviewed N2B1P HEAD and parent, clean start, no merge/remote,
  and create the local-only pre-remediation backup branch.
- [x] Capture a redacted, read-only cache baseline before code changes.
- [x] Replace path-based promotion with Windows handle-bound reparse-resistant
  staging and publication; add deterministic race and junction tests.
- [x] Bind immutable raw cache manifests to one canonical envelope and one
  validated runtime configuration; add negative integrity/configuration tests.
- [x] Run the read-only cache comparison: three `CACHE_HIT` values and all four
  mutation counters are zero.
- [x] Run final quality gates: 474 tests passed; Ruff, format, mypy, quality
  7/7, sensitive scan, preflight, handoff, and diff checks passed.
- [x] Update the exact tracked-file manifest and amend the sole N2B1P commit;
  no second N2B1P commit, push, merge, or release.

### Review

- Independent review is still required. No Reviewer PASS is claimed here.
- `tools/print_authorization.py`, `docs/02`, `docs/24`, `docs/31`, and Obsidian
  are deferred and unmodified in this remediation.

## Delivery-readiness ledger - 2026-08-01

Scope: establish a truthful, continuously maintained path from the completed
N2B1P remediation to the eventual local research delivery. This ledger is not
an authorization for N2B2, model/CUDA execution, real-photo access, SQLite
writes, N3--N5, G2/G3, push, merge, or release.

### Plan

- [x] Reconcile `PROJECT_STATE.json`, the active N2B1P contract, the amended
  N2B1P commit, and the existing task/Obsidian records before assessing
  delivery readiness.
- [x] Map the final delivery milestones, verified completions, and exact
  remaining hard gates from the current contracts rather than historical notes.
- [x] Run only no-side-effect, currently permitted landing-test readiness gates
  and distinguish their result from a real model/photo benchmark.
- [x] Update this ledger's review, `tasks/lessons.md`, and the project Obsidian
  memory with the same status, next action, and task-tracking rule.

### Tracking rule

For every future task, create or update a bounded plan in this file before
execution; record the actual result, commands, and blockers in its review; and
synchronize the corresponding project Obsidian progress note before handoff.
Never turn an unrun, blocked, or externally pending step into `[x]`.

### Review

- Current code candidate: `b819e2c48229cacbf62e399d2b4130cde55cf48a`.
  N0/N1/G1/N2A/N2B0/N2B0.5/N2B0.6/N2B0.7 are immutable approved baselines;
  N2B1R acquisition and N2B1P cache promotion/remediation are complete. The
  required current status remains
  `N2B1P_REMEDIATION_COMPLETE_AWAITING_EXTERNAL_REVIEW`.
- The bounded local-research delivery still needs N2B2 -> N3A -> N4R -> N5R.
  A full 500--600-photo product additionally needs G2/N6 -> N7 -> N8/G3,
  human-approved Bundle acceptance, separate App scope, and separately
  authorized OpenClaw activation.
- `git diff --check` exited 0. Static checks during this ledger task passed:
  Ruff check, Ruff format, mypy (51 source files), and sensitive scan (0
  violations). After synchronizing `MANIFEST.sha256`, the final full pytest was
  472 passed / 2 failed; both failures assert the deliberately non-clean
  worktree and its resulting handoff denial. No implementation or manifest
  binding test failed.
- After manifest synchronization, `npi benchmark status`, both metadata-only
  plans, and fake Pose/segmentation validation exited 0; each fake profile
  reported 20/20 PASS, `synthetic_only=true`, `ready_for_real_benchmark=false`,
  and no artifacts. This is readiness evidence only, not a model/CUDA/photo
  result.
- Current `verify_handoff` (4 PASS, 1 FAIL) and `npi preflight` (14 PASS, 1
  FAIL) correctly reject the uncommitted tracking changes as a non-clean
  worktree. Their failure is `worktree is not clean` / `git_stage_baselines`,
  not a permission to bypass the N2B1P external-review stop. No commit was
  created by this tracking task.
- `N2B2` and later remain locked. Before any real-photo/model test, obtain an
  external N2B1P review, renew the expired G1 approval (expired
  `2026-07-31T23:59:59+08:00`), and bind a separate N2B2 task/approval to the
  frozen manifest, read-only source/runtime separation, isolated CUDA runtime,
  exact model/runtime identity, resource stop thresholds, output retention, and
  quality gates.

## N2B1P independent pre-review - 2026-08-01

Scope: read-only independent pre-review of
`b819e2c48229cacbf62e399d2b4130cde55cf48a` against its parent. This is not the
required external review and cannot unlock N2B2. Do not modify code/contracts,
touch cache payloads, load models, invoke CUDA, access photos/EXIF, write
SQLite, push, merge, or release.

### Plan

- [x] Bind the review to the exact candidate and parent, separate it from this
  uncommitted tracking-only worktree, and preserve the N2B1P stop boundary.
- [ ] Independently inspect the Windows handle-bound promotion path, manifest
  integrity/configuration binding, public verification entry, and negative-test
  coverage for reviewer-level bypasses.
- [ ] Record a `PASS_FOR_EXTERNAL_REVIEW`, `CHANGES_REQUIRED`, or
  `INCONCLUSIVE` verdict with evidence; do not substitute it for an external
  reviewer conclusion.
- [ ] Synchronize the review result to this ledger and Obsidian before any
  follow-on authorization decision.

### Interim review

- Status: `INCONCLUSIVE`. The independent read-only pre-review was time-bounded
  before it produced a complete verdict. It confirmed the candidate/parent
  binding and found no confirmed reparse/TOCTOU or canonical-manifest bypass in
  the inspected handle-bound path, but it did not finish validating every
  public verification/evidence call chain.
- This is not a `PASS_FOR_EXTERNAL_REVIEW`, does not satisfy the required
  external review, and does not authorize a code change or N2B2. A future
  reviewer must independently close the public `verify_promoted_artifact`
  cache-root-identity negative case as well as the complete report/evidence
  chain.

## N2B2 local-research benchmark activation plan - 2026-08-01

Scope: planning only. The executable plan is
`docs/superpowers/plans/2026-08-01-n2b2-local-research-benchmark.md`; it is the
fastest compliant path to a night-time run of the frozen 20-entry snapshot and
ends at N2B2 evidence review. It does not itself authorize a model, CUDA,
source-photo, EXIF, SQLite, N3--N5, G2/G3, App, OpenClaw, push, merge, or
release action.

### Plan

- [x] Map the current code/contract gap and write the N2B2-only implementation
  plan, including external review, renewed data gate, strict permit, adapters,
  serial runner, smoke, night run, evidence, and mandatory stop.
- [x] Complete the independent N2B1P review cycle. The initial `b819e2c`
  review returned `CHANGES_REQUIRED`; its two-stage remediation produced clean
  isolated candidate `259304c67636d05c29f9ad746ef7b2d9b1ea1698`, passed the
  full matrix, and recorded `PASS_FOR_OWNER_N2B2_DECISION` in Git-external
  evidence. This is not an N2B2 authorization.
- [ ] Obtain Jovi's fresh G1 renewal and signed N2B2 approval/runtime contract.
- [ ] Implement and test the signed N2B2 control plane, permit, real adapters,
  runner/CLI/report, and isolated runtime smoke exactly as planned.
- [ ] Run only the signed 20-entry serial N2B2 benchmark and its deterministic
  rerun; record redacted evidence and stop for the next review.

### Review

- Plan status: `READY_FOR_OWNER_REVIEW`, not `AUTHORIZED_FOR_EXECUTION`.
- Night-run Go/No-Go is explicitly included in the plan. With the present
  locked state and expired G1 approval, tonight's real-photo analysis remains
  `BLOCKED_AWAITING_OWNER_DECISION`.
- Task 1 review result: `COMPLETED_WITH_CHANGES_REQUIRED`. The external report
  now includes all six expected/actual SHA-256 values and accurately attributes
  them to inherited manifest debt. The second-stage quality review also found
  a P1: `tools/verify_handoff.py` reaches public Git-external cache verification
  before it validates the tracked-file manifest. This does not unlock N2B2;
  the bounded remediation task below must close both issues and repeat review.

## N2B1P external-review remediation - 2026-08-01

Scope: repair only the detached-review findings for
`b819e2c48229cacbf62e399d2b4130cde55cf48a`: (1) make
`tools/verify_handoff.py` reject an invalid tracked-file manifest before any
public cache-verification import/call, and (2) eliminate a deterministic
line-ending ambiguity in the six manifest entries. `.gitattributes` mandates
LF but the pre-existing main checkout retains CRLF for those files; the old
verifier hashed raw worktree bytes, while a fresh detached checkout hashes the
canonical LF Git blobs. The repair must bind canonical Git blob bytes only
after a clean-worktree check, then rebind exactly the six rows to those blobs.
This is a source and governance-integrity repair under Jovi's direct
authorization; it does not change phase/data authorization, access any
payload, photo, EXIF, SQLite, network, CUDA, or model, and it does not enter
N2B2.

### Plan

- [x] Record the external report and its two-stage review: the report is
  `CHANGES_REQUIRED`; all six digest mismatches are inherited manifest debt;
  the verifier-ordering defect is P1. Plan review additionally requires a
  terminal manifest gate, binary Git-blob reads, a clean-CRLF regression, and
  an exact rebind allowlist.
- [x] In an isolated remediation worktree based exactly on `b819e2c`, add
  focused tests proving: an invalid manifest returns before
  `check_current_authorization()` can import or verify cache code; and the
  manifest binds clean tracked Git blob bytes rather than checkout-dependent
  text line endings.
- [x] Reorder and short-circuit `verify_handoff.main()` so required-file,
  clean-worktree, and canonical-manifest checks happen before
  authorization/cache verification. If any of those gates adds an error,
  immediately emit the normal nonzero result and return without calling
  `check_current_authorization()`. Retain the existing final output contract.
- [x] Add a dedicated binary `HEAD:<path>` Git-blob reader (never the existing
  text/strip `git()` helper) and make the verifier and manifest test hash those
  unmodified bytes after confirming a clean worktree. Add a regression with a
  Git-clean, text-filtered CRLF checkout whose raw digest differs from its
  canonical LF blob.
- [x] Close the second-stage review P1 before any amend: pin one verified
  commit OID before reading manifest blobs; a binary reader must explicitly
  accept that OID and read every blob only as `<oid>:<path>` (never
  `HEAD:<path>` after pinning). Immediately before
  `check_current_authorization()` may load cache-verification code, re-read
  `HEAD`, require it to equal the captured OID, and require clean status. Add a
  regression that simulates HEAD movement and proves the handoff stops before
  authorization/cache verification.
- [x] Obtain a fresh plan review for the HEAD-movement remediation. It approved
  the captured-OID reader, explicit HEAD equality recheck, clean recheck, and
  no-amend boundary.
- [x] Rebind only this exact canonical-blob digest allowlist in
  `MANIFEST.sha256`: `reports/child-claude-n2b05-a-attempt1.json`,
  `reports/child-claude-n2b05-a-attempt2.json`,
  `reports/child-claude-n2b05-a-attempt3.json`,
  `research/N2B0_6_candidate_records.json`,
  `schemas/n2b0_7_artifact_qualification_v1.schema.json`, and
  `schemas/project_state_v1_5.schema.json`; plus the verifier and test rows
  changed by this task. Do not alter any other inherited manifest row.
- [x] Obtain a fresh plan review. It approved the terminal gate, binary blob
  reader, CRLF regression, exact allowlist, and unchanged privilege boundary.
- [x] For the isolated full suite only, create an ignored `.venv` junction to
  the already existing project virtual environment; install nothing and leave
  the candidate worktree clean. This addresses two tests that intentionally
  invoke a worktree-local interpreter.
- [x] Amend (do not append to) the isolated branch's `b819e2c` candidate with
  `--no-edit`, creating `259304c67636d05c29f9ad746ef7b2d9b1ea1698`. The
  baseline still has exactly one commit from `d3628e2` to `HEAD`; `master` was
  not altered, and nothing was pushed, merged, or released.
- [x] Run the focused regression, complete suite, Ruff check/format, mypy,
  sensitive scan, handoff verifier, CLI preflight, and whitespace diff check
  in the clean isolated candidate. Actual result: 477 passed; Ruff check/format
  0/0; mypy 0; sensitive scan 0; handoff 5 pass/0 fail; preflight 15 pass/0
  fail; diff check 0; clean status; and one N2B1P commit.
- [x] Have fresh subagents perform specification compliance and code-quality
  review. After the OID-movement remediation, both approved the exact
  three-file diff with no P0/P1/P2; the remaining matrix must run only after
  the isolated candidate is made clean.
- [x] Synchronize the exact review result to this ledger, Obsidian, and
  Git-external evidence (`N2B1P_REMEDIATION_REVIEW_259304c.md`), then stop at
  the unchanged N2B2 authorization gate.

### Review

- Status: `COMPLETED_PASS_FOR_OWNER_N2B2_DECISION`. The original ordering P1
  and the OID-movement P1 are both remediated. Fresh specification and quality
  reviews approved the exact three-file diff with no P0/P1/P2. The amended
  isolated candidate `259304c67636d05c29f9ad746ef7b2d9b1ea1698` passed every
  stated check with zero exit codes. This closes the N2B1P remediation review;
  it does not activate N2B2 or real-photo analysis.

## Owner N2B2 intent receipt and design gate - 2026-08-03

Scope: record Jovi's direct confirmation before creating an executable N2B2
control plane. This section does not change `PROJECT_STATE.json`, renew G1,
load a model, invoke CUDA, access a photo or EXIF, write SQLite, create a
runtime, or run a benchmark.

### Plan

- [x] Record Jovi's confirmed N2B2 boundary: the frozen 20 entries only,
  read-only source access, existing cached Pose and segmentation artifacts,
  isolated CUDA, no retained original/EXIF/mask/skeleton, no SQLite, redacted
  reports only, then one deterministic rerun and stop.
- [x] Record Jovi's explicit authorization to merge the independently reviewed
  `259304c67636d05c29f9ad746ef7b2d9b1ea1698` N2B1P remediation candidate into
  `master`; preserve the currently dirty tracking records and do not push.
- [x] Complete a read-only audit of the three already cached N2B2 model
  candidates against their fixed TorchVision identities, local-research rights
  boundary, output-retention prohibition, and serial RTX 4070 SUPER fit. No
  new weight is required for N2B2.
- [ ] Confirm the exact segmentation candidate set and deterministic fallback
  policy: lightweight candidate primary, higher-accuracy candidate as the only
  preapproved fallback, or lightweight candidate only.
- [ ] Present the N2B2 design, including thresholds, runtime/report identity,
  expiry, retention, failure handling, merge procedure, and final delivery
  milestones; obtain Jovi's design approval.
- [ ] Only after design approval, materialize and test the renewed G1 and N2B2
  control plane, safely merge the reviewed candidate, and execute the approved
  task-by-task implementation plan.

### Review

- Jovi's direct authorization was received on 2026-08-03. The active checked
  state remains `N2B1P`; G1 remains expired and `N2B2_REAL_BENCHMARK` remains
  `LOCKED` until the signed documents, current-state binding, and negative
  authorization tests exist and pass.
- No code, state, approval, cache, runtime, source-photo, EXIF, SQLite, CUDA,
  model, download, merge, push, or benchmark action occurred while recording
  this design gate.
- Model-audit recommendation: retain the registered Pose candidate as the sole
  N2B2 Pose model; use the lightweight registered person-segmentation candidate
  as primary. The registered higher-accuracy segmentation candidate is viable
  on the serial 12 GiB device but should run only under a signed deterministic
  fallback rule. All outputs remain metadata-only; the audit neither proves
  runtime performance nor activates N2B2.

## N2B model payload reconciliation and download-if-missing - 2026-08-04

Scope: execute Jovi's direct
`N2B_MODEL_PAYLOAD_RECONCILIATION_AND_DOWNLOAD_IF_MISSING` authorization only.
The three fixed TorchVision artifacts are reconciled through the repaired
N2B1P verifier. Download is conditional on an artifact actually missing and a
separately active N2B1Q gate; this record does not activate that gate. This
task prohibits model/CUDA execution, photo/EXIF reads, SQLite writes, N2B2,
promotion unless its separate conditions are true, merge, push, and Obsidian
updates.

### Plan

- [x] Capture the current `master` Git state and record its dirty tracking
  boundary without staging, stashing, merging, or cleaning it.
- [x] Read and bind the current N2B1P contract, owner approval, promotion
  evidence, report, state, and the three-artifact register.
- [x] Confirm the independently reviewed remediation candidate and use only its
  clean worktree for strict read-only cache verification; do not merge it.
- [x] Verify every cache entry and manifest with the repaired public verifier,
  including strict JSON, canonical manifest binding, SHA-256, byte size,
  identity, reparse safety, and runtime/cache separation.
- [x] All three verified `CACHE_HIT`; made no network request or mutation and
  stopped with `N2B_MODEL_PAYLOADS_ALREADY_AVAILABLE_NO_DOWNLOAD_PERFORMED`.
- [x] No artifact was absent, so the N2B1Q download branch was not entered.
  Current state also keeps `N2B1_Q` locked, which independently forbids a
  HEAD, GET, Range request, or quarantine write.
- [x] Run the stated non-model quality matrix in the clean verification
  worktree, record actual exits and counters, and document the final status in
  this ledger only. Do not update Obsidian for this task.

### Review

- Final status: `N2B_MODEL_PAYLOADS_ALREADY_AVAILABLE_NO_DOWNLOAD_PERFORMED`.
  The current `master` remains `b819e2c48229cacbf62e399d2b4130cde55cf48a`
  and is intentionally dirty only in task/lesson/manifest/planning records.
  The reviewed remediation candidate `259304c` was read only and is not merged.
- The repaired public verifier, run in clean `259304c`, returned all three
  cache entries as `CACHE_HIT`; `tools/verify_handoff.py` returned 5 PASS and
  0 FAIL. It validates the external cache through strict JSON, canonical raw
  manifest digest, approved identity/byte/digest binding, handle-bound
  non-reparse paths, and runtime/cache separation. No cache path is recorded.
- No network request, HEAD, GET, Range, download, quarantine write, cache write,
  promotion, payload/manifest/timestamp mutation, model execution, CUDA call,
  source-photo/EXIF read, SQLite write, push, merge, or Obsidian update was
  performed. All mutation and execution counters are 0.
- Quality evidence in clean `259304c`: direct pytest 477 passed (0); Ruff check
  0; Ruff format 0; mypy 51 files/0; quality gate 7 PASS/0 FAIL/0 SKIPPED;
  sensitive scan 0 violations; handoff 5 PASS/0 FAIL; source-module preflight
  15 PASS/0 FAIL; `git diff --check` 0; clean status; one N2B1P commit from
  `d3628e2`.
- The exact requested `.venv\\Scripts\\npi.exe preflight` exited 1 with 13 PASS
  and 2 FAIL. Investigation proved that its reused editable console environment
  imported the main worktree source rather than the isolated candidate; the
  candidate-source module preflight passed 15/0. This is an environment-binding
  drift, not a cache/integrity finding. It was not repaired because this task
  forbids installs and environment changes. Do not report the exact console
  command as passing.

## N2B2 model-stack alignment and controlled preparation - 2026-08-04

Scope: record Jovi's overall architecture roadmap: deterministic visual facts
plus a local Qwen3-VL photography-reasoning layer. The first version is planned
as controlled model preparation, synthetic smoke, then a separately gated
frozen-20 validation. This record is not an activation of N2B2, N3/N4/N5,
real-photo access, App deployment, production release, or a model download.

### Plan

- [x] Record the Owner-confirmed first-version model roles, staged synthetic
  then frozen-20 validation sequence, and future six-model upgrade roadmap in
  project Obsidian without storing model payloads, source paths, hashes, or
  real-photo information.
- [x] Audit the Qwen3-VL official weight source at read-only level: GitHub is
  implementation documentation only; controlled preparation requires a pinned
  official model snapshot with a complete multi-file manifest and local
  per-file SHA-256 binding.
- [x] Record Jovi's explicit approval to use the audited official Qwen model
  snapshot source and fixed revision for a future controlled quarantine
  acquisition; this approval does not bypass the required task contract,
  complete-file manifest, integrity checks, or synthetic-only data gate.
- [ ] Resolve the new task-contract fields that determine the data gate, exact
  Qwen snapshot/format/runtime lock, GPU/token limits, report retention,
  deterministic-fact immutability, and research-only Director Prompt status.
- [ ] Present and obtain approval for the bounded model-stack design before
  creating schemas, control-plane code, acquisition records, or runtime files.
- [ ] Build and test the approved control plane, obtain/publish only approved
  model bytes through quarantine and cache promotion, then run synthetic smoke.
- [ ] Permit the protected real-20 validation only after the separate G1/N2B2
  gate and all current-stage tests are green; stop for Owner review without
  App deployment or production release.

### Owner scope confirmation — synthetic-only

- [x] Bind this first N2B2 validation to `SYNTHETIC_ONLY_DATA_GATE`: exactly
  20 synthetic images from generated tests or existing synthetic fixtures;
  `REAL_PHOTO_READ_COUNT=0`, `REAL_EXIF_READ_COUNT=0`, and
  `G1_SOURCE_ACCESS=0` are mandatory final assertions.
- [x] Bind the four allowed roles: Qwen3-VL-2B-Instruct for non-authoritative
  photography reasoning, Keypoint R-CNN only as a COCO pose smoke baseline,
  LRASPP as the segmentation baseline, and DeepLabV3 only as a quality
  comparator rather than an OOM/timeout fallback.
- [x] Bind the Fact Contract: deterministic vision facts are immutable inputs
  to Qwen; its structured output may contain interpretation, advice, and a
  research Director Prompt candidate but cannot replace or modify any fact.
- [x] Bind the required redacted research outputs: `analysis.json`,
  `vision_facts.json`, `director_prompt.json`, and `reference_bundle.json`;
  each requires strict Schema and provenance validation.
- [x] Bind serial model lifetime on RTX 4070 SUPER: Pose, then Segmentation,
  then Qwen; each model loads, infers, emits redacted data, and unloads before
  the next. No model may remain resident or run in parallel.
- [x] Keep RTMW, RTMDet, SAM2, all other OpenMMLab candidates, real-photo
  experiments, SQLite knowledge writes, App deployment, and Obsidian syncing
  prohibited for this task.
- [ ] Resolve the remaining deterministic runtime and control-plane values,
  then review the N2B2 synthetic-stack design before implementation.

### Review

- In progress at the design and source-audit boundary. No Qwen model byte,
  runtime dependency, CUDA call, source photo, EXIF record, SQLite write,
  Bundle, App action, or cloud operation has occurred.
- The existing three deterministic vision payloads remain verified cache hits
  and must not be downloaded again. RTMDet-nano, RTMW-l, and SAM2.1 Tiny remain
  future-only and must not be requested or downloaded in this task.
- Owner scope confirmation received. No runtime, code, schema, approval,
  registry, cache, model artifact, CUDA operation, synthetic inference, or
  output Bundle has been created under the new synthetic-only task yet.

## N2B2 synthetic model stack validation — control plane - 2026-08-05

Scope: create N2B2 control-plane contracts, schemas, and plan reports only.
Owner Jovi authorized N2B2_SYNTHETIC_MODEL_STACK_VALIDATION with Choice A
(qwen3.5:9b supersedes Qwen3-VL-2B; SYNTHETIC_ONLY_DATA_GATE; S3 then S20).
This is control-plane-only because N2B1P has not passed independent external
review. No model execution, CUDA, real-photo, EXIF, SQLite, App, or Obsidian
access. No push, merge, or release.

### Plan

- [x] Reconcile disk state: HEAD=b819e2c, N2B1P=AWAITING_EXTERNAL_REVIEW,
  N2B1P review verdict=NONE (pre-review was INCONCLUSIVE), three
  TorchVision cache=CACHE_HIT, N2B2_REAL_BENCHMARK=LOCKED,
  real_model_execution=NOT_AUTHORIZED.
- [x] Confirm blocking condition: N2B2 contract Section 2 requires N2B1P
  independent review PASS before model execution. Not met. Only
  non-overstepping control-plane checks permitted. Stop at
  N2B2_EXECUTION_BLOCKED_N2B1P_NOT_APPROVED.
- [x] Create `tasks/phase_n2b2_synthetic_model_stack_validation.yaml` task
  contract with Owner Choice A, runtime architecture, execution sequence,
  vision fact contract, Qwen reasoning contract, GPU gates, forbidden list,
  and mandatory stop rules.
- [x] Create `schemas/n2b2_synthetic_model_stack.schema.json` (validation
  summary), `schemas/n2b2_vision_fact_contract.schema.json` (deterministic
  facts), `schemas/n2b2_photography_reasoning.schema.json` (Qwen output with
  forbiddenProperties), `schemas/reference_bundle_v1_synthetic.schema.json`
  (synthetic Bundle v1 variant).
- [x] Create `reports/N2B2_synthetic_validation_plan.md` and
  `reports/N2B2_owner_inputs_and_limits.md`.
- [x] Update `model_registry/candidates.yaml`: add qwen3.5:9b entry; mark
  vlm-qwen3-vl-2b-class as SUPERSEDED_FOR_N2B2.
- [ ] Deferred: update PROJECT_STATE.json (requires new schema v1.8 +
  preflight update + test update — cannot do without risking N2B1P stop
  boundary enforcement).
- [ ] Deferred: update tasks/index.json (same risk).
- [ ] Deferred: update preflight.py and error_taxonomy (code changes requiring
  test updates).
- [ ] Awaiting: N2B1P independent external review PASS_FOR_EXTERNAL_REVIEW.

### Review

- Current code candidate: `b819e2c48229cacbf62e399d2b4130cde55cf48a`.
- N2B1P required stop remains
  `N2B1P_REMEDIATION_COMPLETE_AWAITING_EXTERNAL_REVIEW`. This control-plane
  task does NOT change that stop boundary and does NOT self-approve N2B1P.
- Control-plane files created: 1 task YAML, 4 JSON schemas, 2 reports.
- Tracking files updated: `tasks/todo.md` (this section),
  `model_registry/candidates.yaml`.
- PROJECT_STATE.json, tasks/index.json, preflight.py, and error_taxonomy were
  NOT modified because `project_state_v1_7.schema.json` has
  `additionalProperties: false` at every level; adding N2B2 fields requires a
  new schema version and preflight/test updates that risk breaking the N2B1P
  stop-boundary enforcement. These changes are documented in
  `reports/N2B2_synthetic_validation_plan.md` Section 3.3 for batch execution
  when N2B1P is approved.
- No model was loaded, no CUDA was invoked, no real photo or EXIF was read,
  no SQLite write occurred, no App or Obsidian access happened, no download
  occurred, and no push/merge/release was performed.
- Comet CLI was non-functional in this environment (path resolution failure);
  the project's own MASTER_EXECUTION_CONTRACT is the authoritative governance
  source and was followed.
- Next action: Owner arranges N2B1P independent external review. When
  PASS_FOR_EXTERNAL_REVIEW is on disk, execute the deferred state changes and
  proceed with N2B2 model execution per the plan.

## N2B2 synthetic model-stack execution — 2026-08-09

Owner Jovi explicitly authorized continuation for the named
`N2B2_SYNTHETIC_MODEL_STACK_VALIDATION` task only. Real photos, G1, EXIF,
SQLite, App, Obsidian, RTMW, SAM2, G2, N3, downloads, and remote writes remain
out of scope.

### Plan

- [x] Re-read the current contract, state, N2B1P evidence/report, task YAML,
  handoff prompt, and current HEAD.
- [x] Verify the three approved TorchVision cache entries and local Ollama
  `qwen3.5:9b` identity without download or pull.
- [x] Correct only the N2B2 cache/API runtime bindings needed to use the
  already-approved external cache and `/api/show` capability record.
- [x] Freeze Git-external deterministic synthetic S3/S20 fixture manifests.
- [x] Run the real 3-case smoke path and verify the zero-data counters.
- [ ] Run S20; not performed because S3 had no person-positive Pose result.

### Review

- Status: `PARTIAL` / stopped at
  `N2B2_SYNTHETIC_FIXTURE_CAPABILITY_INSUFFICIENT`.
- All three TorchVision payloads were `CACHE_HIT`; local Qwen identity was
  `qwen3.5:9b`, `Q4_K_M`, vision-capable, with no Qwen3-VL-2B use.
- The real Keypoint R-CNN smoke result was `person_count=0` for all three
  repository abstract fixtures. A separate external procedural fixture probe
  also returned zero persons for all three cases. No Pose fact was fabricated.
- `REAL_PHOTO_READ_COUNT=0`, `REAL_EXIF_READ_COUNT=0`, `G1_SOURCE_ACCESS=0`,
  `SQLITE_WRITE_COUNT=0`, `APP_WRITE_COUNT=0`, and `OBSIDIAN_WRITE_COUNT=0`.
- S20, RTMW, SAM2, App, G2, and N3 were not performed. No download, pull,
  push, merge, or release occurred.
- Redacted runtime evidence: `EXTERNAL_RUNTIME_WORK/n2b2-execution-20260809-s3`.
- Source changes remain uncommitted for Owner review; `PROJECT_STATE.json` and
  phase locks were not self-unlocked.
- Full pytest: `493 passed, 3 failed`; failures were the clean-tree and
  current MANIFEST.sha256 governance checks caused by the uncommitted in-scope
  changes and retained user zip.
- Unified quality gate: `5 PASS, 2 FAIL`; Ruff, format, mypy, schema, and
  sensitive scan passed; pytest and contract-integrity failed at that same
  governance boundary.

## N2B2 synthetic fixture remediation - 2026-08-09 (revised execution)

### Plan

- [x] Isolate `codex/n2b2-fixture-remediation` in the dedicated integration
  worktree and apply the preserved preflight stash without popping it.
- [x] Validate the six-field independent N2B1P review gate; record the missing
  phase-completion file as `OWNER_PHASE_COMPLETION_RECORD_NOT_PRESENT` only.
- [x] Implement strict external three-case fixture loading, VOC person-mask
  semantics, aligned Pose filtering, batch stage ordering/unload, repeat facts,
  full-facts Qwen input, and S3-only refusal of S20.
- [x] Add focused contract tests; remediation focused tests pass (`26 passed`).
- [x] Re-run the old three fixtures with real Keypoint R-CNN and preserve the
  external capability report.
- [ ] Generate and select new ComfyUI fixtures: blocked because fixed port
  `127.0.0.1:8199` is in the Windows excluded range `8155-8254`.
- [ ] Run real S3/Qwen smoke: not performed because no selected fixture set
  exists; no fixture capability claim is made.
- [x] Run quality commands and retain governance failures honestly; no commit.

### Review

- Runtime status: `N2B2_SYNTHETIC_FIXTURE_GENERATION_BLOCKED_ENVIRONMENT`.
- Old evidence: `OLD_FIXTURE_SET: INSUFFICIENT_FOR_POSE`; all three legacy
  images had zero Keypoint R-CNN detections and zero keypoint groups.
- New fixture count: `0`; selected hashes: `NOT_CREATED`.
- S3 status: `NOT_PERFORMED`; Qwen status: `NOT_PERFORMED`; S20 status:
  `NOT_AUTHORIZED` / `NOT_PERFORMED`.
- `REAL_PHOTO_READ_COUNT=0`, `REAL_EXIF_READ_COUNT=0`,
  `G1_SOURCE_ACCESS=0`, `SQLITE_WRITE_COUNT=0`, `APP_WRITE_COUNT=0`, and
  `OBSIDIAN_WRITE_COUNT=0`; `N2B2=LOCKED`.
- No `PROJECT_STATE.json`, MANIFEST, verifier, model, threshold, or phase
  lock was changed; no push, merge, or commit was performed.

## N2B2 synthetic fixture remediation - v3 execution review - 2026-08-09

### Plan

- [x] Revalidate the main handoff and remediation worktree without reapplying
  the preserved stash.
- [x] Replace the excluded ComfyUI port 8199 with verified loopback port 7865;
  do not modify Windows excluded ranges.
- [x] Use the specified ComfyUI Desktop source with isolated v3 input/output,
  disabled custom nodes, and in-memory database.
- [x] Generate all 12 fixed-seed candidates and preserve their hashes.
- [x] Select three valid fixtures: single human, multi/occluded human, and
  negative control.
- [x] Freeze the Git-external three-item S3 manifest and validate it across E:
  worktree and F: runtime drives.
- [x] Run the formal real S3-only CLI and verify Pose, VOC person masks,
  repeated facts, Qwen schema/provenance, unloads, and zero sensitive counts.
- [x] Run focused/full tests and quality commands; preserve governance failures
  honestly and do not commit.
- [ ] Run S20; prohibited in this run and remains `NOT_PERFORMED_S3_ONLY`.

### Review

- Runtime status: `N2B2_SYNTHETIC_SMOKE_VALIDATION_COMPLETE_AWAITING_OWNER_REVIEW`.
- Git governance: `N2B2_GIT_GOVERNANCE_TRANSITION_REQUIRED`; overall `PARTIAL`;
  commit `NOT_CREATED`.
- Selected fixture hashes and S3 results are recorded in the remediation report
  and Git-external v3 runtime evidence.
- The first formal CLI attempt exposed a cross-drive `commonpath` bug. The
  manifest loader and CLI external-path guard now treat different Windows
  drives as external while continuing to reject same-drive project paths and
  traversal. The formal CLI was rerun and exited `0`.
- Full pytest: `497 passed / 4 governance failures`; quality tool:
  `5 PASS / 2 FAIL`; main handoff remains `5 PASS / 0 FAIL`; remediation
  handoff is `4 PASS / 1 FAIL` because historical MANIFEST hashes were not
  changed.
- `REAL_PHOTO_READ_COUNT=0`, `REAL_EXIF_READ_COUNT=0`, `G1_SOURCE_ACCESS=0`,
  `SQLITE_WRITE_COUNT=0`, `APP_WRITE_COUNT=0`, `OBSIDIAN_WRITE_COUNT=0`,
  `COMFYUI_PERSISTENT_DB_WRITE=0`; `PROJECT_STATE.json` unchanged and
  `N2B2=LOCKED`.
- The actual RealTorchVisionBackend device policy is CPU; GPU residency for
  Pose/Seg/Qwen is not claimed. This is recorded for Owner review and was not
  changed as model optimization.

## N2B2 GPU runtime validation and synthetic S20 preparation - 2026-08-09

### Plan

- [x] Record the clean main baseline, remediation worktree, retained stash,
  lock state, and forbidden real-photo/G1/SQLite/App boundaries.
- [x] Add failure-first contracts for explicit CUDA selection, fail-closed
  unavailable CUDA, device attestation, GPU metrics, Qwen explicit unload,
  S20 schema, and bounded review-candidate governance.
- [x] Implement CPU comparator plus explicit CUDA TorchVision probe, stage-level
  unload, raw CUDA output attestation, and canonical CPU serialization.
- [x] Implement Qwen keep-alive residency sampling and explicit unload; the
  implementation reports `size_vram=0` as unconfirmed rather than PASS.
- [x] Add the S20 20-case schema and preparation plan only; do not create or
  execute an S20 fixture instance.
- [ ] Re-sample GPU headroom, stop only a freshly verified authorized ComfyUI
  listener if one exists, and run the CUDA probe plus CUDA S3 on the frozen
  three-case manifest.
- [ ] Run the complete quality matrix on a clean candidate tree and verify
  the exact two-commit post-N2B1R / one-commit post-N2B1P topology.
- [ ] Atomically advance the remediation branch only after the detached
  candidate passes every required command; do not amend N2B1P.

### Review

- Focused implementation tests currently pass: `31 passed`.
- The protected GPU admission command ran and stopped before model loading:
  `N2B2_GPU_RUNTIME_UNAVAILABLE: INSUFFICIENT_EXCLUSIVE_HEADROOM`.
- Measured baseline was `11066 MiB`; the admission threshold is `10476 MiB`.
  No authorized listener was present and no unrelated process was stopped.
- Qwen residency proof, CUDA S3 rerun, clean candidate quality matrix, and
  final commit remain pending; no GPU success is claimed.
- `S20_PREPARATION_STATUS` remains pending until GPU probe and CUDA S3 pass;
  `S20_EXECUTION_STATUS=NOT_PERFORMED` is a hard boundary.

## N2B2 runtime validation evidence closure - 2026-08-09

### Plan

- [x] Freeze the main baseline, integration diff, retained stash, selected
  fixture hashes and Git-external v2 GPU/S3 evidence.
- [x] Preserve the historical fixture-capability and GPU-admission failures;
  add the authoritative v2 CUDA/Qwen continuation without exposing runtime
  paths or process details in Git reports.
- [x] Tighten Git candidate-count assertions and add report/state binding
  tests for the CUDA result, v2 hashes, S3 result and S20 lock.
- [x] Run the focused/static matrix on the updated worktree; focused tests
  passed (`40 passed`), ruff/format/mypy/sensitive scan and diff-check passed.
  Candidate MANIFEST was not rebuilt because S20 strict acceptance failed.
- [ ] Validate one detached candidate commit with the complete quality matrix.
- [ ] Atomically advance only the remediation review branch after all gates
  pass; keep `main` at the N2B1P baseline.

### Review

- Runtime source and external v2 evidence are frozen; no GPU rerun is part of
  this closure.
- Current runtime conclusion is
  `N2B2_GPU_RUNTIME_VALIDATION_COMPLETE_AWAITING_OWNER_REVIEW`.
- S20 technical preparation is ready, but execution authorization is locked
  and no S20 instance or run exists.
- `PROJECT_STATE.json` remains unchanged, `N2B2=LOCKED`, and no commit has yet
  been created in this closure step.

## N2B2 Review to S20 Synthetic Validation — 2026-08-09

- [x] Freeze reviewed `49e653b` in a detached read-only worktree and preserve
  child-review timeout evidence without claiming it as an external PASS.
- [x] Record the parent fallback review result and bind its review hash to the
  conditional Owner S20 receipt.
- [x] Add the strict twenty-case manifest loader, checkpoint binding, bundle
  writers, S20 contract, and CUDA-only CLI boundary.
- [x] Generate the fixed twenty synthetic fixtures exactly once through the
  isolated local ComfyUI service.
- [x] Run CUDA S20 visual stages and preserve the strict acceptance failure;
  Qwen, bundle writing, and resume were not entered after the hard stop.
- [ ] Run the complete quality matrix and validate one detached S20 candidate
  commit before advancing only the S20 review branch.
- [x] Synchronize redacted milestone knowledge to Obsidian after runtime
  cleanup; six notes were updated or added and no runtime Obsidian write
  occurred.

### Review

- Current implementation worktree: `codex/n2b2-s20-synthetic-validation`.
- Production state remains `N2B2=LOCKED`; no phase-completion approval is created.
- S20 runtime output, fixtures, model/cache files, and raw process evidence remain
  Git-external by contract.
- Child review dispatch was unavailable after three bounded attempts; the parent
  fallback review is recorded as a distinct evidence layer and must not be
  described as a separate external Reviewer identity.
- S20 stop: `N2B2_S20_SYNTHETIC_VALIDATION_FAILED`; strict case
  `n2b2-s20-17` expected one person and detected two. Fixed fixtures and
  external failure evidence are retained; no retry or candidate commit was made.
- Full quality attempt recorded honestly: `512 passed / 3 governance failures`;
  `run_quality.py` reported `5 pass / 2 fail` because the uncommitted worktree
  cannot satisfy clean-tree and MANIFEST/handoff gates. No S20 candidate was
  created.

## N2B2 S20 Case 17 fixture remediation and v2 continuation - 2026-08-10

### Plan

- [x] Reverify the v1 review, manifest, Case 17 image and failure evidence.
- [x] Generate exactly four predeclared Case 17 candidates and select the first
  strict PASS without changing model, threshold or acceptance semantics.
- [x] Build the v2 manifest with 19 byte-preserved v1 fixtures and one Case 17
  replacement; retain all v1 runtime evidence.
- [x] Validate the 20-case CUDA visual chain twice and preserve diagnostic facts
  before the Qwen stage.
- [x] Run a clean bounded Qwen attempt and one identical retry; stop after the
  same contract error reproduced.
- [x] Verify Qwen unload, GPU recovery, zero sensitive counts and no user
  process termination.
- [ ] Produce Reference Bundles, checksums and a successful no-op resume; these
  remain not performed because Qwen fact-contract validation failed.
- [ ] Create or advance an S20 candidate commit; prohibited after failed S20.

### Review

- Case 17 remediation: `PASS`; selected seed `2026082117`; selected image hash
  is retained in external evidence only.
- Visual chain: `PASS` for all 20 cases in both rounds. Case 17 strict
  acceptance passed; Case 19 and Case 20 retained their declared semantics.
- Qwen: `FAIL`, deterministic `input_fact_digest` echo mismatch on
  `n2b2-s20-03` in both clean attempts. No digest coercion was performed.
- Bundles: `0`; no production Bundle v1; no S20 candidate commit; no no-op
  resume because the run was incomplete.
- Final runtime state: `N2B2_S20_SYNTHETIC_VALIDATION_FAILED` with
  `FAILURE_CLASS=QWEN_FACT_DIGEST_ECHO_MISMATCH`; `PROJECT_STATE.json` is
  unchanged and `N2B2=LOCKED`.
- Final verification: focused `46 passed`; full pytest `518 passed / 3
  governance failures`; `run_quality.py` `5 PASS / 2 FAIL`; Ruff, format,
  mypy, sensitive scan, preflight and diff-check passed; handoff `5 PASS / 1
  FAIL` only because post-run report/task edits were not in MANIFEST.

## N2B2 Qwen fact binding contract remediation plan - 2026-08-10

- [x] Diagnose the next live blocker from repository and external evidence:
  Qwen copied a format-valid but incorrect fact digest twice on Case 03.
- [x] Record the closed implementation plan in
  `tasks/plans/2026-08-10-n2b2-qwen-fact-binding-contract-remediation-and-s20-resume.md`.
- [x] Jovi explicitly authorized implementation; the Qwen fact-binding Owner
  receipt and task contract were created without changing PROJECT_STATE.
## N2B2 Qwen fact-binding remediation and S20 v3 continuation — 2026-08-10

- [x] Preserve the v2 Qwen digest-echo failure and add the bounded Owner
  receipt/task contract without changing `PROJECT_STATE.json`.
- [x] Add request-bound Qwen schemas, per-case binding evidence and regression
  coverage; do not coerce Qwen facts or digest values.
- [x] Correct the S20 analysis artifact schema to match the established Qwen
  reasoning object and add a bundle-schema regression test.
- [x] Build fixed-source candidate `9e50f0057171f62af5cfccc4f8a539453fef14c4`
  from parent `49e653b27884f9ba09d15ca17682e496687dc59f`; full quality gates
  passed before model execution.
- [x] Run Case03 Qwen fact-binding probe: two validation passes, positive
  residency, legal fact references and successful unload.
- [x] Run full CUDA S20 v3: 20 visual cases in two rounds, 20 Qwen cases,
  fixed five-case repeat, 20 bundles, index and checksums.
- [x] Execute no-op resume: exit `0`, no model load and no file hash changes.
- [x] Build and validate the single final S20 review-candidate commit with
  parent `49e653b27884f9ba09d15ca17682e496687dc59f`; branch advanced only
  after the clean candidate passed every quality gate.
- [ ] Wait for independent external Reviewer; do not unlock N2B2 or enter G1,
  real photos, production Bundle v1 or App work.

### Review

- Runtime result: `N2B2_S20_SYNTHETIC_VALIDATION_COMPLETE_AWAITING_EXTERNAL_REVIEW`.
- S20 bundle count: `20`; production bundle release: `NOT_CREATED`.
- Facts repeat: 20/20 byte-identical and digest-identical.
- Qwen: 20/20 contract PASS plus fixed 5-case repeat; forbidden fields `0`.
- GPU: baseline `2517 MiB`, peak `9702 MiB`, after unload `2779 MiB`, Ollama
  peak `5607 MiB`; all below the `11500 MiB` ceiling.
- Hard counters: real photo/EXIF/G1/SQLite/App/Obsidian runtime/model download
  counts all `0`; `N2B2=LOCKED`.
- Historical v1 Case17 strict failure, v2 Qwen digest mismatch and v3 schema
  mismatch are retained as failure evidence; none were rewritten as PASS.
- Final Git state: one reachable S20 candidate child of `49e653b`; main and
  the GPU review branch remain unchanged.

## N2B2 S20 completion-artifact integrity remediation - 2026-08-11

### Plan

- [x] Freeze the contradictory v3 release set and record the independent audit
  finding: checksum coverage alone cannot reconcile COMPLETE with a retained
  terminal failure artifact.
- [x] Add strict success-layout validation, exact checksum verification,
  identity-bound Qwen evidence, terminal-failure refusal and a meaningful
  no-op-resume gate.
- [x] Bind the replacement run to the artifact-integrity Owner receipt without
  changing `PROJECT_STATE.json` or the N2B2 lock.
- [x] Create immutable runtime-source candidate `22c044f` and complete its
  full clean-tree quality matrix (532 tests plus static, quality, preflight and
  handoff gates).
- [x] Run exactly one fresh CUDA S20 v4 against the frozen external v2
  manifest; no fixture, prompt, threshold or model was changed.
- [x] Validate the coherent external set and execute no-op resume: twenty
  bundles, 148 release checksums, byte-identical visual facts and zero file
  changes on resume. A final review candidate and independent review record
  remain pending.
- [ ] Synchronize only redacted completed-state knowledge to Obsidian after
  GPU cleanup and the external review verdict.

### Review

- Current state: v4 runtime result is
  `N2B2_S20_SYNTHETIC_VALIDATION_COMPLETE_AWAITING_EXTERNAL_REVIEW`. The v3
  runtime remains historical and is not reviewable as a successful release.
- v4 evidence records all 20 bundles, coherent checksums, strict COMPLETE
  layout, Qwen identity-bound evidence and a verified no-op resume. No
  real-photo access, G1, EXIF, SQLite, App, production bundle release, phase
  completion or branch advancement has occurred in this remediation entry.

## N2B2 documentation, memory sync, and remote publication — 2026-09-06

### Plan

- [x] Reconcile runtime-source candidate `cbd34f6`, Git remote, external S3/S20 v2
  evidence, and the mapped Obsidian project memory.
- [x] Add an authoritative, redacted N2B2 synthetic validation status document
  and update the stage, quality, DoD, and reading-order documentation.
- [x] Verify documentation claims against the final candidate's fresh quality,
  preflight, handoff, S3/S20 v2 summaries, and locked production state.
- [ ] Run the mapped memory checkpoint and filtered project-document mirror
  through required DryRuns, then record the actual memory result.
- [x] Rebuild MANIFEST, run the full quality matrix on the documentation
  candidate, commit the scoped documentation update, push only the review
  branch to `origin`, and verify the remote SHA.

### Review

- [x] Reconciled candidate `cbd34f6`, final v2 runtime evidence, remote state,
  and mapped Obsidian memory before documentation work.
- [x] Added `docs/38_n2b2_synthetic_validation_status.md` and updated reading
  order, timeline/gates, quality strategy, and N2B2 synthetic DoD.
- [x] Verified all new documentation is UTF-8, contains no absolute runtime or
  private source paths, and labels synthetic validation separately from Real20.
- [x] Memory checkpoint: `MEMORY_UPDATED` for overview, progress, and workflow.
- [ ] Document mirror: `MEMORY_SYNC_BLOCKED`; DryRun proposed mirroring the
  generated `.pytest_cache/README.md`, so Apply was intentionally not invoked.
- [x] Final candidate verification: pytest `540 passed`, unified quality `7/7`,
  preflight `16/0`, handoff `7/0`, sensitive scan `0`, no merge, clean tree.
- [x] Remote review branch was pushed and its SHA was verified before mainline
  integration.
- [ ] Create a linear mainline integration candidate that preserves the N2B1P
  portability remediation, preserves the user-owned `AGENTS.md` working-tree
  edit, rebuilds `MANIFEST.sha256`, and passes the full quality matrix.
- [ ] Fast-forward `main` and push only after the integration candidate passes;
  this does not grant Real20 or production authorization.
