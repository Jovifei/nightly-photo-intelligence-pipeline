# N2B0.5 Transport Gate Test Evidence

Status: local verification complete. This evidence concerns only no-I/O policy
validation; no model, photo, network request, or quarantine path was opened.

The regression set covers a correct final filename; wrong and case-mismatched
names; redirect name substitution; directory and empty basenames; query and
fragment handling; legal percent and Unicode normalization; encoded slash,
backslash, and NUL rejection; missing expected filename; required/invalid
Owner caps; exact-at-cap success; expected or final Content-Length over cap;
exact-size mismatch; and denial of an incomplete future N2B1-Q approval.

The gates remain fail-closed. A passing transport-metadata unit test does not
grant weights rights, commercial use, immutable revision, official SHA-256,
N2B1-Q, N2B1-P, N2B2, G2, or G3 authorization.

## Clean-commit verification

- Focused governance and transport suite: 75 passed, exit 0.
- Full suite: 316 passed, exit 0.
- `ruff check .`, `ruff format --check .`, and strict mypy: each exit 0.
- `tools/run_quality.py`: 7 PASS, 0 FAIL, 0 NOT_AVAILABLE, 0 SKIPPED; exit 0.
- `tools/sensitive_file_scan.py`: 0 violations, exit 0.
- `npi preflight`: 15 PASS, 0 FAIL, 0 NOT_AVAILABLE, 0 SKIPPED; exit 0.
- `tools/scan_json_duplicates.py`: 50 tracked JSON files, 2 expected invalid
  duplicate fixtures, 0 production duplicates, 0 malformed; exit 0.
- `git diff --check`: exit 0.

All test data is synthetic metadata. Model-download bytes: 0; model execution:
0; real-photo reads: 0; payload deserialization: 0; ZIP extraction: 0.

## Composed-gate coverage

The successor contract replaces public split approval/transport calls with one
strict-JSON composed entry. Focused tests cover immutable non-authorizing results;
caller override rejection; artifact, filename, request URL, request/final
domain, redirect-chain, exact-size, Owner-cap, and quarantine-fingerprint
mismatches; expiry/equality/not-yet-valid/revocation/timezone cases; rights
snapshot and project-state digest invalidation; unknown commercial/weights and
READY=FAIL rejection; duplicate approval JSON; host downgrade, user-info,
default-port, trailing-dot, Unicode-host, and subdomain rejection; and the
locked production N2B1-Q state. All are synthetic future-state fixtures, never
an authorization to alter the production project state.

## Composed-gate verification

- Composed approval/transport file: 52 focused tests collected: 4 valid
  metadata-only future-fixture cases and 48 negative test entries. Two of the
  negative entries each make two independent denial assertions, for at least
  50 exercised denial scenarios.
- Combined N2B0.5 governance/composition suite: 81 passed, exit 0.
- Full repository suite: 322 passed, exit 0.
- `ruff check .`, `ruff format --check .`, strict mypy, `run_quality.py`,
  `sensitive_file_scan.py`, `npi preflight`, `scan_json_duplicates.py`, and
  `git diff --check`: each exit 0.
- Quality gate: 7 PASS, 0 FAIL, 0 NOT_AVAILABLE, 0 SKIPPED. Preflight: 15
  PASS, 0 FAIL, 0 NOT_AVAILABLE, 0 SKIPPED. Strict JSON scan: 50 tracked,
  2 isolated expected-invalid duplicate fixtures, 0 production duplicates,
  and 0 malformed files.

## Schema and trust-boundary remediation verification

- The public composed validator accepts only raw approval, qualification
  snapshot, and project-state document bytes plus actual transport metadata and
  an explicit time. It rejects duplicate members first, then validates each
  document against a fixed catalog-listed Schema before any digest, rights,
  stage, or transport semantic check.
- Regression coverage now includes absent/unknown versions, missing required
  fields, boolean-as-size, invalid enums, unknown properties, matching-digest
  invalid documents, duplicate documents, identity/filename mismatch,
  READY-with-UNKNOWN-rights, schema-before-semantic ordering, and an assertion
  that invalid state never invokes transport validation.
- `_VALIDATION_TOKEN` was removed. Direct construction, `object.__new__`,
  `object.__setattr__`, and successful `isinstance` of a frozen result value do
  not authorize cache promotion; no public gate accepts the result as a
  credential.
- Focused governance/transport/Schema suite: 103 passed, exit 0. Final clean
  repository suite: 344 passed, exit 0. Ruff, format, strict mypy,
  `run_quality.py` (7 PASS), `sensitive_file_scan.py` (0 violations), `npi
  preflight` (15 PASS), `scan_json_duplicates.py` (52 tracked, two expected
  invalid fixtures, zero production duplicate/malformed), and `git diff
  --check` each exited 0.
- No model, photo, network request, cache/quarantine write, archive extraction,
  payload deserialization, push, merge, or release was performed.

## Revision/hash/time contract coverage

The composed no-I/O gate now validates all three raw documents in strict
duplicate-member and fixed-Schema order before a digest, state, or transport
check. The qualification snapshot is a closed evidence object: a PASS revision
requires an allowed non-floating revision kind/value/official source, and a
PASS hash requires an actual lower-case 64-hex SHA-256 plus official source.
Approval revision and expected SHA-256 must exactly match snapshot evidence;
the canonical snapshot digest independently detects a stale re-signed pair.

Focused synthetic regressions cover missing/null/empty/unknown/floating/non-
official revision evidence; status/evidence consistency; missing/null/short/
long/non-hex/upper-case/ETag/MD5/non-official hash evidence; approval mismatch
and digest invalidation for both fields; READY evidence consistency; required
`not_before`, malformed/naive timestamps, invalid time ranges, UTC-equivalent
offsets, equality boundaries, caller omission/override rejection, and schema
precedence over rights/state/transport. Existing direct-DTO and forged-object
tests confirm that descriptive output remains non-authorizing.

All evidence is future synthetic JSON and metadata. Model-download bytes,
model execution, real-photo reads, cache/quarantine writes, ZIP extraction,
payload deserialization, push, merge, and release remain 0. This amendment's
final clean-worktree verification was: focused N2B0.5 suite 147 passed; full
pytest 384 passed; `ruff check .`, `ruff format --check .`, and strict mypy
each exit 0; `tools/run_quality.py` exit 0 (7 PASS, 0 FAIL, 0 NOT_AVAILABLE,
0 SKIPPED); sensitive scan exit 0 (0 violations); `npi preflight` exit 0
(15 PASS, 0 FAIL, 0 NOT_AVAILABLE, 0 SKIPPED); strict JSON scan exit 0
(52 tracked, 2 isolated expected-invalid duplicate fixtures, 0 production
duplicates, 0 malformed); and `git diff --check` exit 0. Prior clean-commit
counts above are historical and are not reused as PASS for this amendment.
