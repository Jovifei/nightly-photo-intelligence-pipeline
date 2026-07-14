# G1 Calibration Remediation Report

Updated: 2026-07-18

## Decision Boundary

- Scope: `G1_CALIBRATION_20_REMEDIATION` only.
- N0 baseline: `72a81f5984838b74304d23263ac450ea4b5a3a9a`.
- N1 baseline: `ca812cb71c4a09d273f64d9a6f2747ac3facf4cc`.
- N0 and N1 remain `APPROVED_COMPLETE` and immutable.
- G1 is the only authorized data gate, capped at 20 owner-frozen entries.
- N2 through N8 and G2/G3 remain locked.
- Model downloads, cloud processing, OpenClaw, system changes, main-app changes,
  push, merge, and release remain unauthorized.

## Historical G1 Evidence

The 2026-07-14 real G1 execution is retained for audit only. It reported 20 source
entries, 19 canonical assets, one exact-duplicate relationship, an idempotent
second pass, zero outputs, and matching pre/post content hashes. Those results are
not final acceptance evidence because the execution preceded the independent
Reviewer findings and did not prove OS-enforced read-only access.

That historical execution is not used as acceptance evidence for the current
remediation. The current acceptance evidence below is a separate run against the
Owner-provided, ACL-protected snapshot and its frozen manifest.

## Reviewer Findings

The rejected G1 commit had blocking defects in these areas:

- source read-only status was inferred from application behavior rather than
  effective OS permissions;
- approval, project state, N1 task, and G1 data-gate semantics were inconsistent;
- formal preflight treated legitimate mutable authorization files as archival
  hash failures and did not validate the complete current-stage chain;
- runtime approval bound an implementation child instead of an approved parent;
- path and filename leakage remained possible in low-level exceptions and tracked
  evidence;
- stage claims, leases, retry ceilings, recovery, and terminal release lacked
  sufficient atomicity and ownership enforcement;
- Git acceptance still assumed the N0-era commit shape.

The earlier statement that there were no blocking findings is withdrawn.

## Remediation Evidence

- Added a non-mutating Windows effective-access probe using access-only
  `CreateFileW` requests. Any granted mutating right fails; any indeterminate
  result returns `NOT_VERIFIED` and fails closed.
- The probe covers the source root, all 20 authorized files, file write/append,
  attributes, extended attributes, delete, ACL write, ownership, directory create,
  and parent `DELETE_CHILD` rights. It never writes a probe file or changes ACLs.
- Added a pre-content `G1ExecutionPermit`; real ingest cannot begin without a
  matching manifest and verified read-only result.
- Split completed N1 engineering state from the independent G1 data-gate contract;
  added current-stage schemas, semantic validation, mutable-state hash bindings,
  Owner binding, expiry, exclusions, and exact baseline checks.
- Bound the runtime parent by canonical fingerprint. Distinct child runtimes are
  allowed only inside that parent and are rejected on escape, overlap, or reparse
  points.
- Added low-layer path-safe errors and drive, UNC, WSL, filename, and sensitive EXIF
  scanning with narrow synthetic-test allowlists.
- Added SQLite schemas v2-v3 with one active RUNNING claim per asset/stage, mandatory
  lease data, owned heartbeats and releases, atomic recovery, bounded retries,
  duration audit, nested rollback safety, fixed error-code catalog guards, and
  migration-history artifact attestation. A forged history row cannot skip or
  substitute the frozen schema artifacts.
- Retry semantics are loaded from a SHA-256-bound v1.1 policy. Unknown codes and
  policy tampering fail closed; non-retryable codes terminate without incrementing
  retry count; exhaustion uses the stable terminal code.
- Runtime validation rejects reparse points in the approved parent's complete
  existing ancestor chain, and the G1 CLI uses one captured runtime root for both
  policy validation and database placement.
- Frozen manifest entries reject POSIX absolute, Windows absolute, root-relative,
  drive-relative, parent-traversal, duplicate, and over-cap forms before source open.
- Replaced Git acceptance with exact N0/N1 tags and ancestry, exactly one G1 commit,
  no merge commits, clean worktree, and sensitive tracked-file checks.

## Independent Integrity Results

`OS_ENFORCED_READ_ONLY_VERIFIED` and `SOURCE_CONTENT_UNCHANGED_PRE_POST` are
separate claims:

- The previously inspected source remains historical evidence only; its failed
  access-control result is not carried forward as a pass.
- The current snapshot check ran under a non-elevated, Medium-integrity token.
  The snapshot root and all authorized child files are owned by LocalSystem; root
  ACL inheritance is protected, and every child strictly inherits the root ACL.
- The non-mutating `CreateFileW` effective-access probe covered the root and all
  20 authorized entries. File write, append, attribute mutation, ACL mutation,
  ownership mutation, rename/delete-related rights, directory create, and parent
  delete-child were all denied. No capability result was indeterminate.
- `OS_ENFORCED_READ_ONLY_VERIFIED`: `PASS` for the snapshot. The check did not
  create, write, rename, delete, or alter ACLs on any source item.
- `SOURCE_CONTENT_UNCHANGED_PRE_POST`: `PASS` for all 20 authorized snapshot
  entries. Independently computed SHA-256 values matched before and after both
  ingest passes.

## Synthetic Verification

- Current contracts and schemas: passing targeted validation and tamper-negative
  tests.
- Legal 20-entry synthetic preflight: exit 0 in the CLI test path.
- Runtime parent/child policy: two legal children pass; outside, overlap, and
  junction cases fail.
- Windows read-only probe: all-denied verifies; any grant, unknown result, or missing
  entry fails closed; native writable-temp check makes no source changes.
- SQLite concurrency and migration: two-connection claim/recovery/release,
  heartbeat ownership/expiry, retry ceiling, restart, nested rollback, and v1-to-v2
  migration pass.
- Path confidentiality: drive, UNC, WSL, Unicode filename, low-level OS error, DB,
  log, stderr, and report guards are covered by synthetic tests.

Final clean-tree verification completed with 190 pytest cases passing, Ruff check passing,
Ruff format check passing, mypy passing for 26 source files, sensitive scan at
zero violations, and the unified quality command at seven hard-gate passes with
no fail, unavailable, or skipped result. Exact command evidence is recorded in
`tasks/todo.md`.

## Synthetic Soak — 2026-07-16

The Owner-authorized soak used only generated synthetic assets and an untracked
runtime child beneath the approved runtime parent. It did not load the real G1
manifest or access any real-photo content.

- SQLite state-machine rounds: 1,000 two-worker claims; 1,400 heartbeat cases;
  500 complete retry lifecycles; 500 two-worker recoveries; 500 owned/two-worker
  releases; 100 independent migration lifecycles; and 9 crash/fault scenarios.
- Every state-machine round ran SQLite integrity, foreign-key, duplicate-running,
  duration, retry-ceiling, and terminal-lease invariants, for 4,102 invariant
  checks with no violation.
- Manifest fuzz: 1,000 cases, comprising 389 deterministic valid loads and 611
  fail-closed rejects across count, duplicate, encoding, path, and hash variants.
- Confidentiality corpus: 1,000 synthetic Windows, UNC, WSL, URI, Unicode,
  control-character, Pillow/OSError, and SQLite-style error cases with no raw
  path or filename retained.
- Runtime policy: 500 combinations; 125 approved children passed and 375 parent,
  outside, or overlap cases were rejected. The regression suite separately
  exercises symlink/junction and ancestor-reparse rejection.
- Read-only probe: 100 deterministic capability-disposition combinations plus
  one native writable synthetic-source check. Verified, granted, indeterminate,
  malformed, and exception outcomes were classified fail closed; source hashes
  remained unchanged.
- Authorization preflight: 200 tamper rounds (100 single-field and 100 double-field),
  with every mutation rejected and every restored control returning PASS.
- Resource evidence: 132.259 seconds combined soak time, 3.884 MiB maximum Python
  traced memory, 872,448-byte maximum SQLite database, 6.860 ms mean successful
  claim latency, 18.216 ms mean successful release latency, 198.454 ms slowest
  migration, one intentionally injected busy/locked event, and complete temporary
  database/security-work cleanup.

The soak found four G1 defects and added minimal regressions: unknown future
migration history was accepted; SQLite busy/locked could expose a native error;
zero available disk was reported as PASS; and a runtime child removed after the
first permit check could be recreated by database open. The fixes reject unknown
migrations before stamping, safely classify transaction unavailability, enforce
a 1 GiB preflight safety floor, and revalidate runtime policy immediately before
opening the G1 database.

## Real G1 Status

The Owner-authorized remediation run used only the protected snapshot and its
frozen 20-entry manifest. It did not access the original photo library, enumerate
the snapshot directory, or open an entry outside the manifest.

- Manifest validation: approved SHA-256, count 20, uniqueness 20, safe relative
  entries, and deterministic frozen order all passed before content access.
- Formal current-stage preflight: exit 0; 15 PASS and 0 FAIL, including source/
  runtime separation, asset cap, reparse/overlap checks, approval/state/task
  bindings, manifest binding, and OS-enforced read-only capability.
- First ingest: 20 authorized entries scanned, 19 canonical assets created, one
  exact-duplicate relationship observed, and zero near-duplicate candidates.
- Second ingest: 20 authorized entries scanned, zero assets created, 20 duplicate
  observations, and zero near-duplicate candidates. This is the idempotency
  result; the canonical-asset total remained 19.
- The database reported schema version 3, zero integrity or foreign-key issues,
  zero derived-media records, and zero model artifacts. Resume reclaimed zero
  interrupted work; status reported 19 `INGESTED` assets and no interrupted runs.
- Actual non-sensitive EXIF result: all 20 files had no readable EXIF block. No
  EXIF field was inferred or fabricated, no parse error occurred, and no GPS,
  location, or identity value entered the database, logs, or this report.
- The database and logs contained neither a real absolute source path nor a
  manifest filename. The report uses no real filename or path.
- Post-run scanning of the approved runtime found zero derivative image files and
  zero model files. No thumbnail, mask, cutout, embedding, or model output was
  generated.
- Two synthetic, manifest-external references were rejected by the membership
  gate before any source content was opened; the authorized manifest itself was
  not opened for that rejection check.

## Blocking And Non-Blocking Findings

- Blocking: none for the real G1 execution itself; source integrity, privacy,
  and all quality gates passed. Final closure is blocked by the required
  independent review chain: A, B, C, and D each exhausted three fresh
  90-second attempts with `Success=false`, `TimedOut=true`, `Turns=null`, no
  launch error, and zero stdout/stderr. The final Reviewer attempt also timed
  out. These results are INCONCLUSIVE and cannot be converted to PASS.
- Non-blocking for G1 remediation: Python 3.11 is not independently exercised on
  this host.
- Non-blocking for G1 remediation: production perceptual-hash thresholds remain a
  future, separately authorized phase decision.
- The archival handoff verifier remains an original-package validator. Current
  preflight validates its immutable subset and validates all authorized mutable
  state through replacement schema, semantic, binding, and stage checks.

## Night Continuation Evidence — 2026-07-18

The Owner-authorized continuation was executed under the same protected snapshot
and exact frozen manifest. No source-directory enumeration occurred, and no
manifest-external entry was opened.

- Formal preflight: exit 0; 15 PASS, 0 NOT_AVAILABLE, 0 SKIPPED, 0 FAIL;
  `OS_ENFORCED_READ_ONLY_VERIFIED` remained PASS under a non-elevated,
  Medium-integrity token.
- Source integrity: 20/20 entries rehashed after the two ingest passes; every
  before/after SHA-256 matched. Total bytes were 2,449,457 and the opaque
  aggregate SHA-256 was `3f9eddcc606600004e3ae19f3f2e23739288df726cd797489f1228ab9efb7812`.
- Idempotency: first pass scanned 20 entries, created 19 canonical assets, and
  observed one exact duplicate; second pass scanned 20, created 0 assets, and
  observed 20 duplicate relationships. Near-duplicate candidates remained 0.
- State recovery: `resume` reclaimed 0 interrupted runs; `status` and `report`
  both exited 0, with schema v3, 19 `INGESTED` assets, and no interrupted runs.
- EXIF privacy: all 20 images were parseable with no readable EXIF block;
  0 parse errors, 0 allowed fields, 0 GPS detections, and 0 sensitive-field
  values retained. No EXIF value was inferred or fabricated.
- Database/output hygiene: SQLite integrity and foreign-key checks passed;
  20 source rows, 19 asset rows, 0 duplicate-candidate rows, 0 output rows;
  no absolute path or manifest-name leak was detected; 0 derivative images and
  0 model artifacts were present.
- Boundary rejection: a synthetic manifest-external reference and a synthetic
  over-cap (21st) reference were both rejected before any source open.
- Final quality matrix: pytest 190 passed; Ruff check, Ruff format check,
  mypy, unified quality, and sensitive-file scan each exited 0. Unified quality
  reported 7 PASS, 0 FAIL, 0 NOT_AVAILABLE, and 0 SKIPPED.
