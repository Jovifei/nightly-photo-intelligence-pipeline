# N2B0.7 Library-Level Real-Photo Boundary Remediation Evidence

Candidate under remediation: the unapproved local N2B0.7 candidate descended
from `94b6eb6845c8f3caa23a7f15892f7e56e7c1730c`.

## Scope

This remediation closes the independent review's library-entry concern without
performing any model download, dependency installation, model execution,
source-photo read, EXIF read, cache/quarantine write, push, or merge. It
introduces an active-execution authorization boundary and synthetic-only tests
for permit, runner, CLI ingest, and CLI resume denial paths.

## Verification record

An initial full run exposed eight stale historical synthetic tests that had
implicitly loaded the active N2B0.7 authorization. They were corrected to
construct explicit authorized synthetic N1/G1 snapshots; this record counts
only the final, successful run below.

| Command | Actual result | Exit code |
|---|---|---:|
| `.venv\\Scripts\\python.exe -m pytest -q` | `429 passed` | 0 |
| `.venv\\Scripts\\python.exe -m ruff check .` | all checks passed | 0 |
| `.venv\\Scripts\\python.exe -m ruff format --check .` | 75 files already formatted | 0 |
| `.venv\\Scripts\\python.exe -m mypy src/nightly_photo_intelligence_pipeline` | no issues in 47 source files | 0 |
| `.venv\\Scripts\\python.exe tools/run_quality.py` | 7 pass, 0 fail, 0 not-available, 0 skipped | 0 |
| `.venv\\Scripts\\python.exe tools/sensitive_file_scan.py` | 0 violations | 0 |
| `.venv\\Scripts\\python.exe tools/scan_json_duplicates.py` | production duplicates 0; malformed 0 | 0 |
| `.venv\\Scripts\\python.exe -m nightly_photo_intelligence_pipeline.cli preflight` | 15 pass, 0 fail | 0 |
| `.venv\\Scripts\\python.exe tools/verify_handoff.py` | 6 pass, 0 fail | 0 |
| `git diff --check` | no whitespace errors | 0 |

The new negative coverage verifies that the active N2B0.7 authorization raises
before a G1 permit probes the source, before every public ingest runner can
enumerate/open source content or parse EXIF, before CLI ingest loads a
manifest/config or opens state, and before CLI resume resolves or opens its
database. The tests use only temporary directories and synthetic fixture
objects. No source snapshot or real photo was opened.
