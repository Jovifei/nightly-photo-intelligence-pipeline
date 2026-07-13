# N0 Environment Report

- Run ID: npi-20260713-n0-remediation
- Date/time (UTC): 2026-07-13
- Agent: Claude Code (N0 implementation agent)
- Authorized phase/data gate: N0 / G0_THREE_SYNTHETIC_FIXTURES
- Project root (redacted): `<PROJECT_ROOT>`
- No system changes statement: No driver, WSL, Docker, NVIDIA, or system configuration changes were made. No system Python was modified. A project-local virtual environment (`.venv/`, gitignored) was created with Python 3.12.10 and lightweight dev dependencies were pip-installed into it (per Owner remediation instruction #2). No model weights were downloaded. No real photos were accessed. No cloud connections were made beyond the PyPI install of pinned lightweight dev tools.

## Three verification levels (distinct, not conflated)

Per Owner remediation instruction #5, the N0 evidence distinguishes:

1. **Original delivery package integrity** (historical, pre-implementation): `python tools/verify_handoff.py` was run BEFORE any implementation. Result: 16 pass, 0 warn, 0 fail, `HANDOFF_VALID`. This is a historical fact. The current working directory no longer matches the original `MANIFEST.sha256` because N0 added implementation files and `git init` created `.git/`. The original `MANIFEST.sha256` and `tools/verify_handoff.py` are left unchanged as handoff artifacts.
2. **N0 implementation code quality**: pytest, ruff check, ruff format --check, mypy strict, jsonschema validation, security negative tests - all run on Python 3.12.10 in the project-local venv. See `reports/N0_test_evidence.md`.
3. **Current Git commit content**: `git ls-files` sensitive scan (0 violations), one isolated commit, clean working tree, only the 3 fixture PNGs tracked as images. See `reports/N0_test_evidence.md`.

## Summary

| Check | Status | Evidence |
|---|---|---|
| OS / WSL | PASS | Windows 11 Pro 10.0.22631, 64-bit; WSL2 (docker-desktop distro) present |
| Python (test interpreter) | PASS | CPython 3.12.10 in project-local `.venv` (contract-preferred 3.11/3.12) |
| Python (system 3.14) | NOT_USED for N0 | 3.14.2 present but NOT used for N0 verification; no 3.13/3.14 compatibility claimed |
| Git | PASS | git 2.52.0.windows.1 |
| Docker | PASS | Docker 29.5.3 (query only) |
| Docker Compose | PASS | Docker Compose v5.1.4 |
| NVIDIA / nvidia-smi | PASS | RTX 4070 SUPER, driver 595.97, 12282 MiB (matches charter 12GB target) |
| GPU container test | SKIPPED | Must not pull an image in N0 |
| Disk | PASS | Project drive free ~348.6 GiB |
| Repo independence | PASS | No parent `.git`; `ai-photography-director-app` is a sibling, not a parent |
| Source/runtime separation | SKIPPED | NPI_SOURCE_ROOT / NPI_RUNTIME_ROOT not configured for real photos (N1 concern) |
| Original handoff integrity | PASS (historical) | Pre-implementation `verify_handoff.py`: 16 pass, 0 warn, 0 fail, HANDOFF_VALID |
| Contract files unchanged | PASS | All 171 files listed in MANIFEST.sha256 still hash-match (subset check) |
| SQLite | PASS | sqlite3 3.50.4; N0 baseline journal_mode=DELETE, synchronous=FULL, foreign_keys=ON (WAL NOT adopted) |
| ruff | PASS | ruff 0.15.21 installed in `.venv`; `ruff check` and `ruff format --check` pass |
| mypy | PASS | mypy 2.3.0 installed in `.venv`; strict mode passes (22 source files, no issues) |
| pytest | PASS | pytest 9.1.1; 32 passed on 3.12 (GIT-01 passes post-commit) |
| jsonschema | PASS | jsonschema 4.26.0 + referencing 0.37.0; Draft 2020-12 validation runs |
| Pillow | PASS | pillow 12.3.0; used for the N0 lightweight perceptual hash |

## Project-local virtual environment (`.venv/`)

Created with `C:\Users\<USER_REDACTED>\...\Python312\python.exe -m venv .venv` (Python 3.12.10, contract-preferred). The `.venv/` directory is gitignored. No system Python was modified. Pinned lightweight dev dependencies installed via pip (typer==0.26.8, pydantic==2.13.4, pyyaml==6.0.3, pillow==12.3.0, pytest==9.1.1, ruff==0.15.21, mypy==2.3.0, jsonschema==4.26.0, referencing==0.37.0). No model or large dependencies. The package was installed editable (`pip install -e . --no-deps`) to provide the `npi` console script.

## Commands run (read-only or venv-local, redacted)

All commands were observational or confined to the project-local venv. No command installed, upgraded, pulled, or mutated system state.

| Command | Rationale | Redacted output | Exit |
|---|---|---|---|
| `python --version` (3.12 venv) | Test interpreter | `Python 3.12.10` | 0 |
| `npi preflight` | CLI preflight (read-only) | 13 pass, 0 not_available, 1 skipped, 0 fail | 0 |
| `npi status` | CLI status (empty DB) | not present; phase=N0 AUTHORIZED | 0 |
| `npi ingest --input <fixtures> --dry-run` | Dry-run preview | 3 files, 2 unique, 1 dup group, DB not mutated | 0 |
| `npi ingest --input <fixtures>` | Non-dry-run gate | exit 8, NPI_GATE_NOT_AUTHORIZED | 8 |
| `python -m pytest -q` | Unit/integration tests | 32 passed (1 skipped pre-commit) | 0 |
| `python -m ruff check src tests tools/...` | Lint | All checks passed! | 0 |
| `python -m ruff format --check ...` | Format check | 33 files already formatted | 0 |
| `python -m mypy src/nightly_photo_intelligence_pipeline` | Type check (strict) | Success: no issues found in 22 source files | 0 |
| `python tools/verify_handoff.py` (pre-impl, historical) | Original package integrity | 16 pass, 0 warn, 0 fail, HANDOFF_VALID | 0 |
| `python tools/sensitive_file_scan.py` | Commit content scan | 0 violation(s) | 0 |

## Environment issues

1. **Python 3.11 not available on this machine.** Only 3.12.10 and 3.14.2 are installed. N0 was tested on 3.12.10 (contract-preferred). 3.11 is the targeted lower bound (`requires-python = ">=3.11,<3.13"`) but could not be tested here; 3.11 compatibility is not claimed as verified, only targeted. No 3.13/3.14 compatibility is claimed (per Owner instruction #3).
2. **`tools/verify_handoff.py` exact-set manifest check diverges post-implementation (by design).** The verifier does `ROOT.rglob("*")` exact-set matching and was meant for the pristine package; after `git init` + N0 files + `.git/` it diverges. Original package verified pre-implementation (16 pass - historical). Post-implementation, the quality command runs a contract-files-unchanged subset check (all MANIFEST.sha256-listed files intact; new files allowed), which passes. `MANIFEST.sha256` and `verify_handoff.py` left unchanged.
3. **WAL not adopted.** No Owner-approved exception to use WAL exists. N0 uses the safe baseline `journal_mode=DELETE`, `synchronous=FULL`, `foreign_keys=ON`. WAL remains a future candidate requiring a Benchmark, an ADR, and Owner approval. (`config/execution_defaults.yaml` still documents `journal_mode_candidate: "WAL"` as a candidate; the code does not adopt it.)

## Actions explicitly not taken

- No driver changes (NVIDIA driver left at 595.97).
- No WSL/Docker system configuration changes.
- No system Python install/upgrade/modification (only a project-local `.venv`).
- No model/image downloads; no `docker run` that pulls.
- No real photo access (only the 3 synthetic fixtures).
- No cloud access (only PyPI install of pinned lightweight dev tools into `.venv`).
- No OpenClaw integration or activation.
- No modification to `ai-photography-director-app`.
- No push, merge, or remote.
- PROJECT_STATE.json phase authorization unchanged (N0 only; N1-N8 LOCKED).
