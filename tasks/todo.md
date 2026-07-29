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
