# R1 v3 local validation - 2026-10-03

Exact remote candidate: e9e2923fcce31486bb605a668b5e2440dcac38bf.
Tree: 93592b3c6571fd12838fc9b3432fb1adf6e68962.
Python: 3.12.10, isolated pinned runtime/dev dependencies.

Actual validation:
- Cleanup/runtime identity/admission/runner suite: 45 passed.
- Review lifecycle plus full manifest binding: 15 passed.
- Focused Ruff and format: PASS; 18 files already formatted.
- Real20 mypy: PASS; 15 source files.
- Full quality: 1018 passed, 2 failed, 1 skipped, 95 subtests passed.
- Remaining failures: current handoff verifier and current preflight authorization/cache gate.
- Full schema, sensitive scan, Ruff, format and mypy: PASS.
- git diff --check: PASS; worktree clean before evidence commit.

Code inspection confirms mandatory expected nonce/object/helper bindings, rejection of naive clock input, runtime identity v3 control digest integration, public admission requiring v3, and negative reservation-order tests.

Result: code candidate locally qualified with OPEN R0 resource gates. No full-quality PASS or phase acceptance is claimed. R0 remains 2/9; no DONE. Native bootstrap/probe/helper handles, cleanup proof, live attestation, credential/anchor and Real20 remain NOT_RUN/LOCKED. No model/CUDA/photo/EXIF/SQLite/cache mutation, main merge or release.

This evidence is bound to e9e2923; the report-only successor does not imply its full quality was rerun.
