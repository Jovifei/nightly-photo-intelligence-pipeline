# R1 runtime identity v3 code handoff — 2026-10-03

Status: code-only candidate for local validation. This is not an Owner resource receipt and does not authorize bootstrap, native cleanup, Real20, model/CUDA, photo/EXIF, SQLite, production state change, merge, release, or branch deletion.

## Baseline and R0 evidence

Implementation lineage starts from `e1213df220c5c6d74ac7ccac0e32e785cd4612b3` on `chatgpt/npi-fetcher-lease-crash-state-20261001`.

The exact R0 code review remains PASS. Local Codex reported supported-environment full quality on `8bffaac5fad6d0de4e596943d709448ac40546de` as **1002 passed / 2 failed / 1 skipped / 95 subtests**; the remaining failures are the known current handoff/current-preflight cache resource gates. Schema, sensitive scan, Ruff, format and mypy were reported PASS. This file records that local evidence; the remote agent did not rerun it.

R0 remains **2/9**. Cache target/source recovery decisions and machine execution remain separate Owner gates. No DONE exists.

## R1 code delivered

This candidate closes the code-level runtime-v3 binding gaps while leaving machine resources locked:

- strict `schemas/n2b2_real20_runtime_identity_v3.schema.json`;
- v2 remains historical evidence; public Real20 admission now explicitly requires v3;
- v3 binds `runtime_observation`, a nonce-bound `ledger_acl_probe`, and `cleanup_capability` in one canonical control digest;
- v3 probe contract requires `probe_nonce_sha256`;
- cleanup capability validation requires expected nonce, probe-object identity and cleanup-helper identity; those arguments cannot be omitted;
- naive `datetime` values fail closed rather than inheriting the host local timezone;
- public admission validates v3 plus live runner/policy/ledger-object attestation before any reservation;
- low-level runner validation rejects malformed v3 cleanup binding before `_reservation()`;
- the cleanup identity hash is a helper/capability fingerprint for the restricted pre-opened-handle cleanup path. It does not require a second Windows account.

No helper process is launched and no cleanup handle is opened by this code-only package. No runtime proof is fabricated.

## Synthetic test coverage

Updated tests cover:

- v3 schema validity;
- control digest versus observation digest;
- v2 rejection when v3 is required;
- nonce/object/helper binding drift;
- malformed and expired cleanup capability;
- naive-time rejection;
- invalid v3 cleanup binding failing before reservation with reservation call count zero;
- existing invalid ledger proof failing before reservation;
- admission lifecycle fixture upgraded to v3.

Remote execution status: **NOT_RUN**.
Native Windows bootstrap/probe/helper execution: **NOT_RUN**.

## Local validation commands

```bash
python -m pytest -q tests/test_real20_cleanup_capability.py tests/test_real20_runtime_identity.py tests/test_real20_review_lifecycle.py tests/test_real20_admission.py
python -m ruff check src/nightly_photo_intelligence_pipeline/real20/cleanup_capability.py src/nightly_photo_intelligence_pipeline/real20/runtime_identity.py src/nightly_photo_intelligence_pipeline/real20/admission.py src/nightly_photo_intelligence_pipeline/real20/runner.py tests/test_real20_cleanup_capability.py tests/test_real20_runtime_identity.py tests/test_real20_review_lifecycle.py
python -m ruff format --check src/nightly_photo_intelligence_pipeline/real20/cleanup_capability.py src/nightly_photo_intelligence_pipeline/real20/runtime_identity.py src/nightly_photo_intelligence_pipeline/real20/admission.py src/nightly_photo_intelligence_pipeline/real20/runner.py tests/test_real20_cleanup_capability.py tests/test_real20_runtime_identity.py tests/test_real20_review_lifecycle.py
python -m mypy src/nightly_photo_intelligence_pipeline/real20
python tools/run_quality.py
python tools/verify_handoff.py
python tools/verify_review_candidate.py
python tools/sensitive_file_scan.py
git diff --check
```

Expected resource limitation: R0 current handoff/preflight may remain RED until the selected cache/source recovery route is executed. Do not weaken either steady-state gate to make this code package green.

## Remaining R1 machine gates

Still LOCKED / NOT_RUN:

- trusted-runtime bootstrap execution;
- native ACL inheritance probe;
- restricted cleanup helper with a real pre-opened cleanup handle;
- cleanup proof generation;
- live attestation;
- Owner-bound runtime identity materialization;
- one-shot credential/anchor issuance;
- Real20 reservation and photo/EXIF/model execution.

Any native proof must be generated locally under its specific Owner gate. This code candidate does not fabricate it.
