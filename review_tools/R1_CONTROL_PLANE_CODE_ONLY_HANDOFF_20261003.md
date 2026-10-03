# R1 trusted bootstrap / native probe / pre-opened-handle helper — code-only handoff

Date: 2026-10-03

Status: **REMOTE_CODE_PACKAGE_COMPLETE_AWAITING_LOCAL_VALIDATION**.

This is a code-only handoff. It is not an Owner machine-execution receipt, not a native proof, not a Real20 credential, not a production unlock, and not DONE.

## Exact lineage

Review branch: `chatgpt/npi-fetcher-lease-crash-state-20261001`.

Work-package contract base: `6cbd579a21e2aa79beb0375a0597a2a9cb0f198d`.

During remote implementation the same authorized review branch fast-forwarded through concurrent/local code commits. The remote agent re-read and audited the resulting complete tree instead of overwriting it. The complete implementation was then repaired at `eb6bacf388f3081f2bfd6d333cd32cf0047f92d5`, tree `c1c0eb58ed97cd76d81f83145d9d9b815ea0a9f8`.

The final handoff/manifest commits are documentation-only successors of that implementation tree.

## Delivered code scope

The package implements the complete R1 code-only work package:

1. **Strict trusted plan**
   - uses strict `load_n2b1p_runtime_configuration()`;
   - derives fixed `real20-execution-ledger` and `real20-ledger-acl-probe` children;
   - does not add arbitrary Real20 paths to the N2B1P runtime configuration;
   - rejects runtime/work/cache/probe/ledger overlap.

2. **Fixed-path bootstrap**
   - separately gated by Git-external Owner authority;
   - creates only fixed ledger/probe roots and fixed bootstrap evidence;
   - records handle-bound object identities and read-only security-policy digests;
   - exact evidence-bound state is idempotent;
   - partial/conflicting existing state fails closed;
   - no ACL write/repair.

3. **Synthetic inheritance probe**
   - binds the real ledger and isolated probe root;
   - verifies production-ledger mutation denial;
   - compares live ledger/probe policy digests;
   - creates the synthetic claim only below the probe root;
   - binds a random probe nonce, runner identity, probe object, real-ledger object and policy digests;
   - verifies directory/file AccessCheck rights;
   - never creates a synthetic claim in the production ledger.

4. **Restricted cleanup helper**
   - parent pre-opens the exact synthetic claim and releases that handle for inheritance;
   - helper has no filesystem path API;
   - child process receives the inherited handle, cleanup capability and nonce only;
   - helper verifies nonce/object/helper identity and expiry;
   - only the expected reservation/terminal files may exist;
   - no recursion, sibling traversal or ACL mutation;
   - code uses the existing handle-delete primitives and returns a redacted cleanup proof;
   - no second Windows account is required by the selected design.

5. **Runtime identity v3**
   - successful probe + cleanup binds `ledger_acl_probe` and `cleanup_capability`;
   - proof remains non-eligible when cleanup is not verified;
   - v2 remains historical/low-level evidence only and cannot satisfy v3-required public admission.

6. **Live admission attestation**
   - reads current token identity fingerprint, security-policy digest and object identity from the already-bound production-ledger handle;
   - public `run_real20()` still exposes no caller attestor override;
   - v3/live mismatch fails before reservation.

7. **CLI**
   - `real20 ledger-bootstrap-check`: read-only;
   - `real20 ledger-bootstrap`: fixed bootstrap, separate authority required;
   - `real20 ledger-probe`: fixed synthetic probe + helper orchestration, separate authority required;
   - `real20 ledger-probe-clean`: inherited-handle helper entry; no path option.

8. **Contracts and governance**
   - strict bootstrap authority schema;
   - strict bootstrap evidence schema;
   - strict probe-result schema;
   - draft task contract;
   - `DRAFT_NOT_AUTHORIZED` Owner authority template;
   - docs 44/45 updated to the selected cleanup-capability / pre-opened-handle route.

## Remote review and repair

Remote exact-tree review found one concrete implementation defect in the inherited package: `cleanup_helper.cleanup_from_environment()` referenced `os` and `strict_json` without importing them. Commit `eb6bacf388f3081f2bfd6d333cd32cf0047f92d5` repairs those imports and adds a test that exercises environment-only inherited-handle payload parsing.

No additional code finding remained in the static exact-tree review after that repair.

One item intentionally remains a **native qualification risk, not a claimed PASS**: the final restrictive Windows ACL must permit the authorized parent/orchestrator to obtain the exact cleanup-only handle while runner-side probe rights remain appropriately denied. The code does not weaken DELETE/WRITE_DAC/WRITE_OWNER denial to manufacture success. Local Windows qualification must establish that the final policy and pre-opened-handle mechanism work under the separately approved runtime setup.

## Test coverage present in the tree

Synthetic tests cover:

- fixed trusted path derivation and overlap rejection;
- exact authority binding and repository draft non-authority;
- bootstrap fixed-object creation, exact idempotence and partial-state refusal;
- policy mismatch and unknown AccessCheck fail-closed;
- random nonce/probe-object/ledger-object/helper identity binding;
- production ledger claim namespace remains untouched by the probe;
- cleanup failure remains `NOT_ADMISSION_ELIGIBLE`;
- helper exact expected-child deletion and sibling-content rejection;
- helper API has no path/project-root argument;
- child helper process inherits only the selected handle;
- unbound cleanup proof rejected;
- environment-only helper input parsing;
- strict schemas;
- public live attestation from an already-bound ledger;
- bad nonce/object/helper/expiry/stale proof causes reservation/backend/image call counts all to remain zero;
- Windows-native tests for policy/token digests and inherited-handle adopt/cleanup.

Remote execution of these tests: **NOT_RUN**.

Native Windows bootstrap/probe/helper execution: **NOT_RUN**.

## Required local validation

```bash
python -m pytest -q tests/test_real20_control_plane.py tests/test_real20_ledger_bootstrap.py tests/test_real20_runtime_identity.py tests/test_real20_admission.py tests/test_real20_review_lifecycle.py
python -m unittest tests.test_real20_control_plane_native_unittest
python -m unittest tests.test_real20_native_ledger_unittest
python -m ruff check src/nightly_photo_intelligence_pipeline/real20 src/nightly_photo_intelligence_pipeline/windows_bound_promotion.py tests/test_real20_control_plane.py tests/test_real20_control_plane_native_unittest.py tests/test_real20_ledger_bootstrap.py tests/test_real20_runtime_identity.py
python -m ruff format --check src/nightly_photo_intelligence_pipeline/real20 src/nightly_photo_intelligence_pipeline/windows_bound_promotion.py tests/test_real20_control_plane.py tests/test_real20_control_plane_native_unittest.py tests/test_real20_ledger_bootstrap.py tests/test_real20_runtime_identity.py
python -m mypy src/nightly_photo_intelligence_pipeline/real20
python tools/run_quality.py
python tools/sensitive_file_scan.py
python tools/verify_handoff.py
python tools/verify_review_candidate.py
git diff --check
```

Local native tests are code/runtime validation only. They do not themselves authorize the real runtime bootstrap or constitute Owner resource acceptance.

## Resource gates unchanged

Still not authorized or not performed by this handoff:

- actual trusted-runtime bootstrap on the Owner machine;
- actual production ledger/probe creation;
- actual native inheritance qualification on the intended runtime ACL;
- actual cleanup-helper launch against Owner runtime resources;
- runtime proof sealing;
- Owner runtime-identity-v3 materialization;
- credential/anchor issuance;
- Real20 reservation;
- model/CUDA/photo/EXIF/SQLite;
- R0 cache/source recovery;
- main merge/tag/release.

The repository Owner authority file remains `DRAFT_NOT_AUTHORIZED`; the executable path requires separately materialized Git-external approved authority bound to the exact reviewed candidate.

`PROJECT_STATE.json` is not unlocked. R0 remains **2/9 with open resource gates**. No DONE is created.
