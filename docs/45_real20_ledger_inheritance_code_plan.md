# Real20 trusted bootstrap / probe / helper — code plan and acceptance

Status: active code-only R1 implementation contract, 2026-10-03.

This plan supersedes the older pre-provision + separate-cleanup-account implementation route. The selected route is:

```text
strict N2B1P runtime configuration
-> fixed-path bootstrap
-> synthetic inheritance probe
-> pre-open exact cleanup handle
-> restricted helper
-> cleanup proof
-> runtime identity v3
-> live admission attestation
```

No second Windows account is required.

## P0 — Immutable boundaries

Keep unchanged: current R0 cache/source resource gates, `PROJECT_STATE.json` production N2B2 lock, source read-only policy, one-shot reservation semantics, 20 entries / 19 unique inference limit, credential/anchor binding, and all model/photo/EXIF/SQLite restrictions.

Do not weaken handoff/preflight to make a code-only candidate green.

## P1 — Trusted plan

Use only strict `load_n2b1p_runtime_configuration()`.

Fixed children are `real20-execution-ledger`, `real20-ledger-acl-probe`, and `real20-control-plane-bootstrap.json`.

Reject arbitrary caller paths, overlaps, reparse objects and runtime-configuration digest drift. The existing N2B1P runtime schema remains unchanged.

## P2 — Bootstrap

After a separately materialized Owner authority, code may bind runtime parent, create only the two fixed directories, record object identities and read-only policy digests, write fixed bootstrap evidence, accept exact evidence-bound idempotent state, and reject partial/unbound/conflicting existing state.

No ACL write or repair is permitted.

## P3 — Probe producer

Under actual runner identity: bind production ledger append-only/security-check handle; bind synthetic probe root append-only/security-check handle; require root policy digest equality; verify production-ledger mutation denial; generate nonce; create synthetic claim only under probe root; validate directory/file rights; write bounded synthetic reservation/terminal markers; close runner-side claim handles.

Never create a production-ledger probe claim.

## P4 — Cleanup helper

Parent orchestration opens the exact synthetic probe using the fixed probe root, then transfers only the handle.

Helper accepts inherited/pre-opened handle, cleanup capability, expected nonce and current time. Helper does not accept a filesystem path.

It verifies object/nonce/helper identity and expiry, deletes only the two expected synthetic files, requires an otherwise empty directory, then deletes only that bound directory. No recursion, sibling traversal or ACL mutation.

## P5 — Runtime identity v3 and live attestation

Runtime identity v3 includes `runtime_observation`, nonce-bound `ledger_acl_probe`, and `cleanup_capability`. Public admission requires v3.

Live attestation is computed from the already-bound production-ledger handle using current token identity digest, security-policy digest and handle object identity digest. Any mismatch fails before reservation.

## P6 — CLI

Supported code surfaces:

- `real20 ledger-bootstrap-check`: read-only;
- `real20 ledger-bootstrap`: fixed bootstrap, future Owner authority required;
- `real20 ledger-probe`: fixed synthetic probe + pre-opened helper orchestration, future Owner authority required;
- `real20 ledger-probe-clean`: restricted inherited-handle helper entry, no path option.

All outputs are redacted structured status/evidence.

## P7 — Tests

Synthetic tests cover fixed path derivation, no arbitrary path option, draft authority does not execute, exact idempotent bootstrap, partial/conflicting bootstrap rejection, policy mismatch, unknown AccessCheck, nonce binding, cleanup failure => NOT_ADMISSION_ELIGIBLE, helper exact-child deletion only, sibling content rejection, helper API contains no path, invalid v3 control => reservation/backend/image counts all zero, and live attestation missing => fail closed.

Windows-native tests cover security-policy digest stability, token identity fingerprint availability, release/adopt inherited handle, and exact cleanup with no path reopen. Native tests do not themselves prove Owner runtime qualification.

## P8 — Contracts and review

Repository artifacts include strict bootstrap authority schema, strict bootstrap evidence schema, strict probe-result schema, runtime identity v3 schema, draft task, `DRAFT_NOT_AUTHORIZED` Owner authority, docs 44/45, handoff and manifests.

The draft authority is never a receipt and never unlocks production state.

## P9 — Local validation after remote handoff

Local Codex runs supported Python 3.12 focused control-plane tests, Real20 suite, Windows-native tests where applicable, Ruff, format, mypy, schema, sensitive scan, full pytest / `tools/run_quality.py`, `verify_handoff`, `verify_review_candidate`, and `git diff --check`.

Any native resource action remains separately Owner-gated.

## Exit

Remote code exit requires exact branch/head/tree, complete manifests, code self-review and NOT_RUN disclosure for native actions.

Local quality PASS still does not authorize bootstrap/native probe/Real20. Machine execution requires the separate approved authority and later exact evidence/review.
