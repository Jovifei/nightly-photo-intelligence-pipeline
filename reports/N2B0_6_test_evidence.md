# N2B0.6 Evidence-Binding Local Quality Evidence

Scope: N2B0.6 metadata-only evidence-binding remediation. This is local
validation evidence, not an independent Reviewer verdict, a download approval,
or an authorization to begin N2B1/N2B2/G2.

The initial uncommitted run correctly failed its clean-worktree assertion and
found the stale hash for the Owner-authorized archival-verifier help change.
Those results were not accepted. The manifest was synchronized, the sole
N2B0.6 candidate was amended, and the following commands ran against that
clean amended candidate.

| Command | Actual result |
|---|---|
| `.venv\Scripts\python.exe -m pytest -q` | PASS, exit 0, 419 passed |
| `.venv\Scripts\python.exe -m ruff check .` | PASS, exit 0 |
| `.venv\Scripts\python.exe -m ruff format --check .` | PASS, exit 0, 73 files already formatted |
| `.venv\Scripts\python.exe -m mypy src/nightly_photo_intelligence_pipeline` | PASS, exit 0, 47 source files |
| `.venv\Scripts\python.exe tools/run_quality.py` | PASS, exit 0, 7 pass / 0 fail / 0 not available / 0 skipped |
| `.venv\Scripts\python.exe tools/sensitive_file_scan.py` | PASS, exit 0, 0 violations |
| `.venv\Scripts\npi.exe preflight` | PASS, exit 0, 15 pass / 0 fail / 0 not available / 0 skipped |
| `.venv\Scripts\python.exe tools/scan_json_duplicates.py` | PASS, exit 0, 58 tracked JSON / 2 expected invalid duplicate fixtures / 0 production duplicates / 0 malformed |
| `.venv\Scripts\npi.exe benchmark plan --profile pose` | PASS, exit 0, synthetic metadata-only plan emitted |
| `.venv\Scripts\npi.exe benchmark plan --profile segmentation` | PASS, exit 0, synthetic metadata-only plan emitted |
| `.venv\Scripts\npi.exe benchmark status` | PASS, exit 0, model download and execution remain locked |
| `.venv\Scripts\python.exe tools/verify_handoff.py --help` | Exit 0; `N0_ARCHIVAL_VERIFIER_ONLY`, not a current-stage PASS |
| `.venv\Scripts\npi.exe benchmark run --profile pose` | Expected denial, exit 8, `NPI_MODEL_NOT_AUTHORIZED`; not a PASS result |
| `.venv\Scripts\npi.exe benchmark run --profile segmentation` | Expected denial, exit 8, `NPI_MODEL_NOT_AUTHORIZED`; not a PASS result |
| `git diff --check` | PASS, exit 0 |

Counters: model payload download bytes 0; Range response bytes 0; dependency
installs 0; model execution runs 0; archive extractions 0; real-photo reads 0;
cache/quarantine writes 0; push and merge 0. No unavailable, skipped, archival,
or expected-denial result is labelled PASS.

## Current-stage handoff integrity remediation - 2026-07-29

Scope: current-stage verifier and entry-contract remediation only. This is not
an N2B0.6 completion approval and does not authorize N2B1/N2B2/N3, model
downloads/execution, or real-photo access.

| Command | Actual result | Scope note |
|---|---:|---|
| `.venv\Scripts\python.exe -m pytest -q -k 'not git_worktree_is_clean and not current_handoff_verifier_passes'` | exit 0; 419 passed, 2 deselected | The two clean-worktree assertions require the amended commit. |
| `.venv\Scripts\python.exe -m ruff check .` | exit 0 | PASS |
| `.venv\Scripts\python.exe -m ruff format --check .` | exit 0; 73 files already formatted | PASS |
| `.venv\Scripts\python.exe -m mypy src\nightly_photo_intelligence_pipeline` | exit 0; 47 source files | PASS |
| `git diff --cached --check` | exit 0 | PASS |

The pre-commit verifier intentionally returned exit 1 only because the staged
amend left the worktree unclean. Its authorization, baseline, manifest-content,
and sensitive-path checks passed. The clean candidate must run the complete
suite, `tools/verify_handoff.py`, and the required quality commands before a
new independent review.

### Prohibited-action counters

Model payload downloads: 0. Range-response downloads: 0. Dependency installs:
0. Model executions: 0. Real-photo reads: 0. Cache/quarantine writes: 0.
Archive extraction: 0. Pushes, merges, and releases: 0.

### Clean amended candidate validation

All commands below ran on the clean amendment immediately preceding this
evidence-only append. The final candidate must be freshly independently
reviewed rather than inferred from this local evidence.

| Command | Actual result |
|---|---|
| `.venv\Scripts\python.exe -m pytest -q` | PASS, exit 0, 421 passed |
| `.venv\Scripts\python.exe -m ruff check .` | PASS, exit 0 |
| `.venv\Scripts\python.exe -m ruff format --check .` | PASS, exit 0, 73 files already formatted |
| `.venv\Scripts\python.exe -m mypy src\nightly_photo_intelligence_pipeline` | PASS, exit 0, 47 source files |
| `.venv\Scripts\python.exe tools\run_quality.py` | PASS, exit 0, 7 pass / 0 fail / 0 not available / 0 skipped |
| `.venv\Scripts\python.exe tools\sensitive_file_scan.py` | PASS, exit 0, 0 violations |
| `.venv\Scripts\python.exe tools\scan_json_duplicates.py` | PASS, exit 0, 58 tracked JSON / 2 expected invalid duplicate fixtures / 0 production duplicates / 0 malformed |
| `.venv\Scripts\npi.exe preflight` | PASS, exit 0, 15 pass / 0 fail / 0 not available / 0 skipped |
| `.venv\Scripts\python.exe tools\verify_handoff.py` | PASS, exit 0, current N2B0.6 handoff 5 pass / 0 fail |
| `git diff --check` | PASS, exit 0 |

`tools/verify_handoff.py --archival-n0` is intentionally `NOT_CURRENT_STAGE`,
exit 8, and is not recorded as a pass. The normal verifier now binds every
tracked current-stage file and the approved baseline tags. A fresh independent
review remains required before an Owner completion approval or tag.
