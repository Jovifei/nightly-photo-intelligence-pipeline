# R1 trusted bootstrap + native probe + restricted pre-opened-handle helper — complete next work package

Status: authorized for remote code development on the existing review branch. Machine/resource execution remains separately gated.

Base for implementation: the exact reviewed R1 v3 candidate accepted by `R1_V3_EXACT_REVIEW_RECEIPT_20261003.md`.

## 1. Objective

Complete the remaining R1 control-plane **code** so a later Owner-authorized local run can:

```text
strict trusted N2B1P runtime configuration
  -> derive fixed Real20 ledger/probe locations
  -> bootstrap fixed ledger/probe control-plane objects
  -> run native synthetic inheritance probe
  -> pre-open the exact cleanup handle
  -> launch restricted cleanup helper with that handle only
  -> produce nonce/object/helper-bound cleanup proof
  -> assemble runtime identity v3
  -> perform live pre-reservation attestation
```

The code package must not itself execute those machine actions remotely and must not unlock Real20.

## 2. Existing implementation to reuse

Do not create a parallel control plane.

Reuse:

- `real20/runtime_identity.py` and runtime identity v3;
- `real20/cleanup_capability.py`;
- `real20/admission.py` and its live-attestation seam;
- `real20/ledger_bootstrap.py`;
- `real20/ledger_probe.py`;
- `windows_bound_promotion.py` bound-handle identity, access-check and deletion primitives;
- existing append-only ledger code and native tests;
- strict `load_n2b1p_runtime_configuration()` as the trust root for `runtime_parent`.

Important correction: the strict N2B1P runtime configuration does **not** allow arbitrary extra Real20 fields. The next implementation must therefore remove the current assumption in `ledger_probe.load_probe_configuration()` that Real20 probe fields can be inserted into `approvals/n2b1p_runtime_configuration.json`. Do not broaden that schema to make the probe work.

## 3. Trusted configuration and fixed paths

Implement one module-owned Real20 bootstrap plan derived only from the strict N2B1P runtime configuration and fixed leaf names.

Required derived paths:

- ledger: `<runtime_parent>/real20-execution-ledger`;
- probe root: `<runtime_parent>/real20-ledger-acl-probe`.

No public API or CLI may accept arbitrary ledger/probe/cleanup paths.

The plan must carry at least:

- source runtime-configuration digest;
- fixed leaf names;
- expected no-overlap properties;
- code/helper contract version.

If a separate Git-external control document is required for freshness/candidate binding, it must bind the strict runtime-configuration digest and fixed leaf names; it must not replace the current approved N2B1P runtime configuration.

## 4. Bootstrap implementation

Refactor `real20/ledger_bootstrap.py` from read-only/preprovision-only semantics into code that can be invoked later under a separate Owner execution gate.

Code requirements:

1. derive parent/ledger/probe solely from the trusted plan;
2. bind the runtime parent before child creation;
3. reject reparse points, path overlap and unexpected pre-existing objects;
4. create only the fixed ledger/probe roots;
5. never modify source, cache, output or system ACLs;
6. never create a Real20 reservation;
7. return redacted object-identity evidence;
8. idempotence must distinguish exact already-bootstrapped objects from conflicting objects;
9. no model/photo/EXIF/SQLite activity.

Remote tests use fake/bound-handle doubles. Actual Windows creation remains NOT_RUN remotely.

## 5. Native probe implementation

Implement the real code path behind `real20/ledger_probe.py`.

The probe must:

- operate only below the fixed probe root;
- generate a cryptographically random nonce and bind `probe_nonce_sha256`;
- create one synthetic claim and only the allowed reservation/terminal-style files;
- never create a claim in the production ledger;
- capture handle-bound probe-object and real-ledger-object identities separately;
- obtain effective-rights results from live handles;
- compute/read a stable DACL/security-policy digest without changing ACLs;
- verify the probe policy digest equals the ledger policy digest;
- keep runner identity and helper identity fields separately bound;
- produce a candidate proof that is not `ADMISSION_ELIGIBLE` until cleanup succeeds.

If `windows_bound_promotion.py` lacks a read-only security-descriptor/policy digest primitive, add the smallest bound-handle read-only primitive there. Do not add an ACL-write primitive.

## 6. Restricted cleanup helper

Add a dedicated Real20 cleanup helper module.

Hard rule: the helper receives **only a pre-opened/inherited handle plus capability data**. It must not accept a filesystem path to the probe object and must not perform path discovery.

Required behavior:

- adopt/validate the inherited handle;
- verify live object identity against the cleanup capability;
- verify nonce and helper-identity binding;
- verify capability expiry;
- allow deletion of exactly the bound synthetic probe object after its expected children are closed/empty;
- no recursive cleanup;
- no sibling traversal;
- no source/cache/output/production-ledger handles;
- no ACL change;
- return a redacted cleanup proof.

If safe inherited-handle adoption is absent, add a minimal `windows_bound_promotion.py` primitive that wraps an already-open handle and revalidates its identity/reparse status. Do not add a generic path-opening fallback.

No second Windows account is required by this architecture.

## 7. Cleanup capability and proof assembly

Parent orchestration must generate a cleanup capability bound to:

- probe nonce;
- exact probe object identity;
- exact restricted-helper implementation/contract identity;
- short expiry.

Only after helper cleanup succeeds may proof assembly produce:

- `cleanup_status=CLEANUP_PASS`;
- `status=ADMISSION_ELIGIBLE`.

Failed cleanup must preserve the truthful probe result but remain not admission eligible.

Final runtime identity v3 assembly must bind the proof and cleanup capability in the full control digest before credential/anchor issuance.

## 8. Live attestation

Implement the existing `admission._live_ledger_attestation()` seam without adding a caller-controlled override to public `run_real20()`.

It must derive from the already-bound real-ledger handle:

- runner/process identity fingerprint;
- ledger policy digest;
- real ledger object identity.

Admission compares those values to the finalized v3 proof before reservation. Unknown or unavailable native results fail closed.

No photo or model access may occur to obtain this attestation.

## 9. CLI surface

Wire the existing Real20 control-plane commands to real implementations, but keep execution fail-closed unless the future resource authority is present.

Expected command roles:

- `real20 ledger-bootstrap`: fixed trusted-plan bootstrap only;
- `real20 ledger-probe`: synthetic probe only;
- `real20 ledger-probe-clean`: orchestration/helper cleanup only.

No path argument for ledger/probe object selection.

Output must be redacted JSON/status evidence only.

## 10. Contract and governance artifacts

The same code package must add/update:

- code contract/schema for bootstrap evidence;
- probe and cleanup-proof schema as needed;
- task contract for R1 control-plane bootstrap/probe/helper machine execution;
- Owner approval **draft/template**, never a signed receipt;
- docs 44/45 to replace the obsolete “second cleanup Windows identity/account” wording with cleanup-capability + restricted pre-opened-handle helper semantics;
- schema catalog;
- handoff and manifests.

Do not modify `PROJECT_STATE.json` to unlock N2B2/Real20.

## 11. Required synthetic tests

At minimum:

### Trusted-plan/bootstrap

- arbitrary path injection rejected;
- runtime-config digest drift rejected;
- fixed path derivation exact;
- reparse/overlap rejected;
- conflicting existing object rejected;
- exact idempotent state accepted without creating extra objects;
- zero production reservation/source/model operations.

### Probe

- nonce generated and included in proof;
- probe and real-ledger identities remain distinct fields;
- policy mismatch rejected;
- unknown AccessCheck fails closed;
- cleanup failure leaves proof non-eligible;
- probe never touches production ledger claim namespace.

### Helper

- path argument does not exist in helper API;
- wrong inherited-handle identity rejected;
- wrong nonce rejected;
- wrong helper identity rejected;
- expired capability rejected;
- helper cannot traverse sibling/root paths;
- successful fake-handle cleanup returns bound proof;
- no recursive cleanup.

### Admission ordering

For missing/stale/mismatched probe, failed cleanup, wrong nonce/object/helper identity, and unavailable live attestation:

- `_reservation()` call count = 0;
- backend construction count = 0;
- source-image open count = 0.

### Compatibility

- existing R0 promotion/recovery/security tests remain unchanged;
- historic v2 can still be interpreted as evidence but cannot satisfy v3-required public admission.

## 12. Native tests

Add Windows-native tests for:

- inherited-handle adoption;
- real object identity preservation;
- access-check matrix;
- security-policy digest stability;
- actual empty-object cleanup through the inherited handle;
- no path-based reopening by the helper.

These tests are **NOT_RUN** remotely. On a local machine without the separately authorized runtime setup they must report NOT_AVAILABLE/fail closed according to the project’s established policy; mocks cannot be used to claim native inheritance proof.

## 13. Code-only exit criteria

Before remote handoff:

- implementation and synthetic tests complete;
- no open code findings in self-review;
- manifests synchronized;
- no state unlock;
- no Owner receipt generated;
- native/resource execution marked NOT_RUN;
- exact branch/head/tree supplied.

Local Codex then runs supported Python 3.12 focused/full quality and returns exact evidence for independent review.

## 14. Machine execution gate after code acceptance

Even after code review PASS, none of the following is authorized by the code package itself:

- bootstrap creation on the Windows runtime;
- native ACL probe;
- launching cleanup helper with a real inherited handle;
- proof materialization;
- runtime identity v3 sealing;
- credential/anchor issuance;
- Real20/model/photo/EXIF work.

Those operations require their separately materialized Owner resource/execution authority.

## 15. Stop rules

Stop and preserve evidence on:

- runtime-config mismatch;
- arbitrary path input;
- reparse/overlap;
- unexpected existing object identity;
- unknown AccessCheck/security descriptor result;
- nonce/object/helper mismatch;
- cleanup failure;
- helper path traversal capability;
- attempted ACL modification;
- production-ledger probe claim;
- any source/cache/model/photo/SQLite side effect;
- schema/quality/security/manifest failure.

Never repair a failed native proof by widening ACLs, deleting evidence, changing paths, or inventing a proof.
