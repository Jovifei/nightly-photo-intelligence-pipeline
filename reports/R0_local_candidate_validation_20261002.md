# R0 local candidate validation - 2026-10-02

Candidate: 2939363ad71721980e35f7b8142e39b224cbab86.
Python: 3.12.10. Runtime/dev requirements installed at repository pinned versions in an isolated environment.

The received tests did not exercise validate_recovery_admission. The capability case expected ValueError but raised AssertionError; other cases raised the expected exception inside the test. Local repair now calls the implementation, checks control-plane loader bindings and failure propagation, and asserts no filesystem mutation in synthetic temporary roots.

Validation:
- Focused pytest: 7 passed.
- Focused Ruff/format: PASS.
- Module mypy: PASS.
- Full pytest with local test changes: 995 passed, 6 failed, 1 skipped, 95 subtests passed.
- Failures: candidate cleanliness, tracked-file manifest, handoff, two exact-head/report admission tests, current preflight. This full run preceded this manifest/report commit; it is not proof of this commit passing full quality.
- First quality run: schema/sensitive scan/full Ruff/format/mypy PASS; pytest/contract integrity FAIL.

Remaining R0 delivery: CLI wiring, actual promotion integration tests, final manifests/handoff, exact review, current physical cache and authorized recovery route. Stage remains 2/9, CHANGES_REQUIRED. No DONE or stage acceptance.

No model, CUDA, real-photo/EXIF, SQLite, payload download, cache mutation, main merge or release was performed.
