# N2B1P Remediation Report

## Status

`N2B1P_REMEDIATION_COMPLETE_AWAITING_EXTERNAL_REVIEW`

The original copy-only promotion predates this remediation. This work did not
download, copy, rewrite, or delete any cache payload or cache manifest. It
repairs the N2B1P control plane, path boundary, and integrity binding only.

## Cache preservation baseline

The initial read-only baseline is recorded in
`research/N2B1P_remediation_cache_baseline.json`. It records three approved
payloads, their path-redacted relative locations, byte sizes, SHA-256 values,
manifest byte hashes, attributes, reparse states, and last-write times. The
cache tree baseline has six files, zero reparse points, and no absolute external
path or payload content in Git.

The final read-only comparison is recorded in
`research/N2B1P_remediation_cache_revalidation.json`: all three are
`CACHE_HIT`; the payload, manifest, tree, reparse, attribute, and timestamp
comparisons are unchanged; all four mutation counters are zero.

## Remediated findings

- P1-A: N2B1P uses one Windows handle-bound layer. Existing roots and
  descendants are opened relative to live native directory handles, with
  reparse-tag, final-path, volume, and file-identity checks. Staging uses a
  random exclusive directory; publication is a handle-relative NT rename.
  There is no path-based `mkdir`, `open`, or `os.replace` fallback after root
  binding.
- P1-B: `n2b1p_integrity.py` provides the single canonical JSON-byte builder,
  strict raw-byte loader, and SHA-256 function. Existing immutable external
  manifests remain untouched. A Git-side canonical envelope binds each raw
  manifest hash to artifact, evidence, payload, size, relative location,
  cache-root identity, completion time, and runtime-configuration digest.
- P2: `approvals/n2b1p_runtime_configuration.json` is the one strict runtime
  and cache configuration source. Its Schema and canonical digest are checked
  by the loader, direct API, preflight, evidence validator, and handoff
  verifier. Cache/runtime/work overlap variants fail closed; the snapshot field
  is an explicit N2B1P no-access sentinel.

## Verification coverage

The focused regression suite covers real temporary NTFS junction rejection,
root/ancestor reparse checks, five deterministic handle-bound race seams,
identity/volume/reparse/rename failure, transaction-owned-only cleanup,
canonical JSON ambiguity, envelope field tampering, runtime-config drift and
overlap, and direct API override denial. These tests use pytest temporary
directories only.

## Local verification result

- Focused N2B1P remediation tests: `27 passed`.
- Full suite: `474 passed`.
- Ruff check and format check: pass; mypy: `51` source files, no issues.
- Unified quality gate: `7 PASS`, `0 FAIL`, `0 NOT_AVAILABLE`, `0 SKIPPED`.
- Sensitive-file scan: `0` violations.
- Read-only preflight: `15 PASS`, `0 FAIL`.
- Current-stage handoff verifier: `5 PASS`, `0 FAIL`.
- The final external-cache field comparison found `0` artifact mismatches;
  cache file count remained `6` and reparse count remained `0`.

These are local verification results, not an independent Reviewer conclusion or
an Owner authorization for N2B2.

## Deferred, out-of-scope items

- `DEFERRED_POST_N2B1P_NON_BLOCKING_TOOLING_DRIFT`:
  `tools/print_authorization.py` remains untouched.
- `DEFERRED_POST_N2B1P_DOCUMENTATION_DRIFT`: `docs/02`, `docs/24`, and
  `docs/31` remain untouched.
- `DEFERRED_POST_N2B1P_OBSIDIAN_SYNC`: Obsidian remains untouched.

N2B2, model loading/inference, CUDA, real-photo/EXIF access, SQLite ingest
writes, derivative creation, push, merge, release, and external review approval
remain outside this remediation.
