# Real20 ledger inheritance proof — code-only execution plan

Status: design-review candidate, 2026-09-27. The Owner's acceptance of the updated `docs/44_real20_ledger_inheritance_preflight_design.md` is the entry gate for source changes. This plan does not authorize R2, Real20, photo/EXIF reads, model execution, Owner ACL changes, Bundle/App work, or production `N2B2` promotion.

## P0 — Bind the exact candidate and baseline

- Code-stage base: `ca706a67fff61980700c9275353efea62ae8cc81`. Implementation commit: `3abb18d282d4e7f8983c52a70142dbdcd8098bfa`. Review HEAD: `7f497ac9dfc836d3b38f1f06e19fb03141c59f78`, whose direct parent is `3abb18d...`; the two-commit chain is intentional and registered by the topology guards. Work only on `codex/real20-ledger-proof-20260927` in its isolated checkout. Preserve the other chat's checkout and dirty primary `AGENTS.md`.
- `python tools/verify_handoff.py` currently reports 6 PASS / 2 FAIL for the docs-only parent: successor topology and root index manifest are stale. Preserve that result as baseline RED. The final candidate must repair both without weakening historic cases or rewriting published commits.
- Review `MASTER_EXECUTION_CONTRACT.md`, `PROJECT_STATE.json`, `docs/44`, relevant `tasks/lessons.md`, Real20 code/tests and the selected Python 3.12 interpreter. No dependency or model installation.

## P1 — Red tests for semantic binding and admission

Add focused tests in `tests/test_real20_runner.py`, `tests/test_real20_admission.py`, and a dedicated ledger-probe test module. First run them against the parent and capture the expected failure.

- `runtime_observation` equal to the live runtime result passes its digest comparison while the full v2 control contains `ledger_acl_probe`.
- Changing only `ledger_acl_probe` changes the full-control digest but not the observation digest; changing observation changes both.
- v1, unknown v2 fields, missing proof, stale proof, failed cleanup, runner/cleanup identity conflict, policy/object mismatch and credential-bound proof tampering all fail before `_reservation()`, backend construction or image open. Spy on the actual reservation boundary; call count must be zero.
- An Owner-bound finalized control cannot be changed by `ledger-probe` or `ledger-probe-clean` after credential/anchor issuance.

## P2 — Minimal v2 control and runner checks

- Add a strict, versioned v2 parser/schema for `real20_runtime_identity.json`: top-level `schema_version`, `runtime_observation`, `ledger_acl_probe`; require exactly `models`, `worker`, `vision`, `qwen` observation domains and preserve their nested semantics. Historic v1 may be read as evidence but cannot enter new Real20 admission.
- In `src/nightly_photo_intelligence_pipeline/real20/runner.py`, keep the existing whole-control canonical digest for credential/anchor binding and compare `runtime_probe()` only with the nested observation digest. Validate proof structure and live ledger identity/policy before `_reservation()`; retain the post-claim guard and one-shot consumption behavior.
- Admission receives a module-owned live-attestation seam and requires exact runner identity, ledger policy and real-ledger object matches; absent or mismatched attestation fails before reservation, backend construction and image open. The public `run_real20()` API cannot supply an attestor override. The proof keeps separate `probe_object_sha256` (synthetic sibling) and `ledger_object_sha256` (real ledger context).
- Keep `real20/admission.py` fail closed and do not introduce a caller-controlled bypass. Error codes must distinguish missing/invalid/stale proof without exposing private path/SID material.

## P3 — Synthetic probe generation and separate cleanup

- Add narrowly scoped `npi real20 ledger-probe` and `ledger-probe-clean` commands to `cli.py`, backed by a Real20-specific module and existing bound-handle primitives in `windows_bound_promotion.py`.
- Derive the Git-external synthetic probe sibling from trusted configuration. Reject reparse points and overlap with source, cache, output and the actual ledger. A probe under the actual runner identity creates a fresh claim and allowed file names without post-creation ACL repair, records handle-bound identities, effective-rights matrix and DACL policy digest, and writes only redacted, nonce-bound proof.
- Only a separately configured cleanup identity may remove the precise synthetic probe object. The inheritance observation may remain `PROBE_PASS`, but failed or unverified cleanup makes the combined proof `NOT_ADMISSION_ELIGIBLE`. Before reservation, admission compares the proof's runner identity, ledger policy digest and ledger object identity to a live injected attestation; absent or mismatched attestation fails closed. No system user/service, Owner ACL, production ledger or source photo is changed. Without the Owner-preprovisioned policy and cleanup identity, native inheritance qualification is `NOT_AVAILABLE`.

## P4 — Focused and full verification

- Red→green: run the new tests, then existing `tests/test_real20_runner.py`, `tests/test_real20_admission.py`, `tests/test_real20_native_ledger_unittest.py`, `tests/test_real20_review_lifecycle.py` and `tests/test_handoff.py`. Keep synthetic, native and Owner-runtime proof separate.
- Run the supported Python 3.12 full pytest suite, Ruff check/format, mypy, `tools/run_quality.py`, `tools/sensitive_file_scan.py`, CLI preflight and `git diff --check`. Record command, interpreter, cwd, exit code and failing region. No model/photo actions.

## P5 — One direct successor, GitHub, independent review

- Extend exactly the topology guards in `tools/verify_handoff.py`, `src/nightly_photo_intelligence_pipeline/preflight.py` and `tests/test_git.py` for the implementation child and the documented closeout child; retain every existing SHA and no-merge rule. The final review HEAD is two commits after the code-stage base.
- Stage only scoped files; rebuild root `MANIFEST.sha256` from Git-index blobs with `tools/print_index_manifest.py`, stage it, then create one ordinary child commit. Re-run handoff/preflight and the affected quality gates on the clean exact SHA. A RED gate blocks push.
- If authorized by the Owner's current instruction and every gate is green, ordinary-push only this review branch and read back remote SHA; do not move `main`, merge, tag or release. Give the exact SHA and recorded outputs to the bound remote ChatGPT chat for independent code review. A review `DONE` is code-only and leaves R2 `NOT_RUN`, Real20 unperformed and production `N2B2=LOCKED`.

## Stop rules

Unclear or failed authorization, unknown `AccessCheck`, unable-to-clean probe, real-photo/system side effect, malformed control, path overlap, test failure, sensitive scan finding, manifest/topology failure or remote review `CHANGES_REQUIRED` stops advancement. Preserve evidence and correct only within the approved code-only branch; do not retry a real one-shot credential or modify Owner ACLs.
