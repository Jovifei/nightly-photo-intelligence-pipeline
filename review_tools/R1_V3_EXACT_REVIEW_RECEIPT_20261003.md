# R1 v3 exact review receipt — 2026-10-03

Receipt type: remote code-review evidence only. It is **not** an Owner resource receipt, execution credential, phase-completion receipt, or DONE.

## Reviewed identities

Repository: `Jovifei/nightly-photo-intelligence-pipeline`

Review branch: `chatgpt/npi-fetcher-lease-crash-state-20261001`

Code range reviewed: `e1213df220c5c6d74ac7ccac0e32e785cd4612b3..e9e2923fcce31486bb605a668b5e2440dcac38bf`

Reviewed code HEAD: `e9e2923fcce31486bb605a668b5e2440dcac38bf`

Reviewed code tree: `93592b3c6571fd12838fc9b3432fb1adf6e68962`

Local-validation evidence successor: `4ea7862fa1501964e2359279b0ebe075f07c37b8`

Evidence tree: `af06363d93fea4aa231c6a2f5be45cce4e5451f8`

The evidence successor has exactly one parent, the reviewed code HEAD, and changes only `reports/R1_v3_local_validation_20261003.md` plus the root manifest. Its report explicitly states that full quality was run on the reviewed code HEAD, not on the report-only successor.

## Verdict

`CODE_PASS_WITH_OPEN_RESOURCE_GATES`

Open code findings: **none**.

This verdict accepts the R1 runtime-identity-v3 code candidate for the reviewed scope. It does not accept or authorize machine resources.

## Findings reviewed and closed

The review checked the previously identified R1 binding gaps:

1. `probe_nonce_sha256` is no longer only syntax-checked. Runtime identity v3 requires the nonce in ledger proof v2 and the cleanup capability must match that exact nonce.
2. Cleanup-capability expected nonce, probe-object identity, and cleanup-helper identity are mandatory validator parameters; omission is no longer a valid call shape.
3. Naive `datetime` values fail closed in cleanup-capability validation, runtime-identity validation, and the low-level Real20 runner clock path.
4. Cleanup capability is no longer an isolated object: runtime identity v3 binds `runtime_observation`, nonce-bound `ledger_acl_probe`, and `cleanup_capability` in one canonical control digest.
5. Public Real20 admission requires v3 and live runner/policy/real-ledger-object attestation before the reservation path.
6. Negative tests assert malformed v3 cleanup binding fails before `_reservation()` with reservation call count zero.
7. Runtime identity v2 remains historical/low-level compatibility evidence; it cannot satisfy public admission when v3 is required.
8. The cleanup-identity digest is interpreted as the restricted helper/capability identity, not as a requirement for a second Windows account.

No regression was found that would justify weakening current R0 handoff or preflight cache gates.

## Local validation evidence

Local Codex reported on the exact reviewed code HEAD:

- cleanup/runtime/admission/runner focused suite: **45 passed**;
- lifecycle + manifest suite: **15 passed**;
- Ruff: **PASS**;
- format: **PASS**;
- Real20 mypy: **PASS**;
- full quality: **1018 passed / 2 failed / 1 skipped / 95 subtests**;
- full schema: **PASS**;
- sensitive scan: **PASS**;
- full Ruff/format/mypy: **PASS**.

The two remaining full-quality failures are the existing current handoff and current preflight/cache resource gates. They are open R0 resource conditions, not findings in this R1 v3 code candidate.

Remote Python execution: **NOT_RUN**.
Native Windows bootstrap/probe/helper execution: **NOT_RUN**.

## Gate state

R0 remains **2/9**. Cache target/source recovery remains separately Owner-gated.

R1 code candidate: **PASS_WITH_OPEN_RESOURCE_GATES**.

Still LOCKED / NOT_RUN:

- trusted-runtime bootstrap machine execution;
- native ledger/probe inheritance execution;
- restricted helper with a real pre-opened cleanup handle;
- cleanup proof generation;
- live native attestation;
- Owner-bound runtime-identity-v3 materialization;
- one-shot credential/anchor issuance;
- Real20 reservation;
- model/CUDA/photo/EXIF/SQLite execution.

No production state is unlocked. No DONE is created.
