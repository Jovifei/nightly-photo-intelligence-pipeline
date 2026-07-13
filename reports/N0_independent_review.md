# N0 Independent Review (Claude Code Reviewer)

> **Historical-status note (added during single-commit remediation).** This
> report is retained as historical evidence of the independent review process.
> It initially reviewed a content-equivalent prior implementation commit
> (preserved only in a local-only backup branch, NOT part of the delivery
> history). The report and its `PASS_FOR_OWNER_REVIEW` conclusion have been
> merged into the final single N0 commit. That `PASS_FOR_OWNER_REVIEW` applied
> to the prior content; it does NOT constitute a final review of the amended
> single commit's new SHA, does NOT equal Owner approval of N0, and does NOT
> authorize N1. The amended single commit still requires a fresh external final
> independent review of its own SHA. The original review content follows
> unchanged below.

- Reviewer: Claude Code (independent N0 Reviewer, not the implementer)
- Review date (UTC): 2026-07-13
- Commit under review: `229be0859968ba878ac0ac9387baf698f5aab7f9`
  - Message: `chore(n0): scaffold safe local pipeline foundation`
  - `git rev-list --count HEAD` == 1
  - `git status --porcelain` == clean
  - Tracked files: 211
- Authorized scope reviewed: N0 / G0_THREE_SYNTHETIC_FIXTURES
- Reviewer role: advisory only. This report does NOT approve N0, does NOT modify
  `PROJECT_STATE.json`, and does NOT authorize N1. Only the Owner may approve a gate.

## How this review was conducted

I read `README_FIRST.md`, `CLAUDE.md`, `MASTER_EXECUTION_CONTRACT.md`,
`PROJECT_STATE.json`, `tasks/phase_n0_environment_scaffold.yaml`,
`docs/24_definition_of_done.md`, `docs/11_cli_contract.md`,
`CLAUDE_REVIEW_CHECKLIST.md`, and the four N0 reports, then ran read-only
checks and the quality commands myself with the project-local `.venv`
(CPython 3.12.10). I did not trust the implementer's report text where I could
verify directly. I did not access real photos, download models, or connect to
the cloud.

## Commands actually run by the Reviewer (Python 3.12.10 venv)

| # | Command | Result |
|---|---|---|
| 1 | `.venv/Scripts/python.exe -m pytest -q` | 33 passed |
| 2 | `.venv/Scripts/python.exe -m ruff check src tests tools/run_quality.py tools/sensitive_file_scan.py` | All checks passed! |
| 3 | `.venv/Scripts/python.exe -m ruff format --check ...` | 33 files already formatted |
| 4 | `.venv/Scripts/python.exe -m mypy src/nightly_photo_intelligence_pipeline` | Success: no issues found in 22 source files |
| 5 | `.venv/Scripts/python.exe tools/run_quality.py` | 7 pass, 0 fail, 0 not_available, 0 skipped; QUALITY_GATE_PASSED |
| 6 | `.venv/Scripts/python.exe tools/sensitive_file_scan.py` | 0 violation(s); exit 0 |
| 7 | `.venv/Scripts/python.exe tools/verify_handoff.py` | diverges post-implementation (scans `.venv/`); see finding N2 |
| 8 | `npi preflight` | 13 pass, 0 not_available, 1 skipped, 0 fail |
| 9 | `npi status` (empty DB) | exit 0; no absolute paths |
| 10 | `npi ingest --input <fixtures> --dry-run` (run twice) | byte-identical; database_mutated: False |
| 11 | `npi ingest --input <fixtures>` (no --dry-run) | exit 8; `error_code: NPI_GATE_NOT_AUTHORIZED` |
| 12 | `pytest tests/test_state_db.py::test_at_n0_db_01_pragma_baseline_delete_full_fk` | PASS |
| 13 | `pytest tests/test_security.py::test_at_n0_sec_03_fixture_unchanged_after_read` | PASS |
| 14 | `pytest tests/test_security.py::test_at_n0_log_01_fixture_root_redacted` | PASS |
| 15 | `pytest tests/test_schema.py` (SCHEMA-01, SCHEMA-02) | 2 passed |
| 16 | `pytest tests/test_git.py::test_at_n0_git_01_*` | PASS |
| 17 | `pytest tests/test_handoff.py::test_at_n0_gate_02_*` (3 tests) | 3 passed |
| 18 | `git ls-files \| grep -iE '\.(db\|sqlite\|log\|pem\|key\|pt\|pth\|ckpt\|safetensors\|onnx\|engine\|npy\|npz\|env)$\|token\|secret'` | 0 matches |
| 19 | `grep` for write/move/delete/chmod APIs in `src/` | 0 matches |
| 20 | `grep` for network/download libs in `src/` | 0 matches (only `subprocess.run` in preflight, read-only) |
| 21 | Reviewer-computed SHA-256 of the 3 fixtures | match `fixtures/fixture_manifest.json` |
| 22 | SHA-256 of `PROJECT_STATE.json` vs `MANIFEST.sha256` | identical (`95362eff...`); unchanged by N0 |

## Per-check results

### 1. Only N0/G0 authorized; N1-N8 locked — PASS

- `PROJECT_STATE.json` SHA-256 (`95362eff1bc09dbb7919bb14a016b0425b92977298c9813e32c02a32405695c3`)
  matches `MANIFEST.sha256` exactly. The N0 implementation did NOT modify it.
- `PROJECT_STATE.json` content: phase N0 AUTHORIZED, data_gate
  G0_THREE_SYNTHETIC_FIXTURES AUTHORIZED, `real_photo_access=NOT_AUTHORIZED`,
  `large_model_downloads=NOT_AUTHORIZED`, `cloud_image_processing=FORBIDDEN`,
  `openclaw_activation=NOT_AUTHORIZED`; `locked.phases` = N1-N8,
  `locked.data_gates` = G1/G2/G3; `required_stop_after` = N0,
  `WAIT_FOR_OWNER_APPROVAL`.
- `test_at_n0_gate_02_*` (3 tests) PASS: N1-N8 task files LOCKED, authorization
  snapshot is N0-only.

### 2. No real photo access, no 4th image, no model download, no cloud — PASS

- Tracked image files: exactly the 3 synthetic fixture PNGs under
  `fixtures/three_image_smoke_set/`. No 4th image.
- `npi ingest --dry-run` over the fixture set reports `files_scanned: 3`.
- `src/` contains NO `requests`/`urllib`/`httpx`/`socket`/`aiohttp`/`urlopen`/
  `urlretrieve`/`huggingface_hub`/`transformers`/`torch.hub`/`pip install`
  imports. The only `subprocess.run` is in `preflight.py` and runs read-only
  observational commands (`git --version`, `docker version`, `nvidia-smi`,
  `wsl --status`) with `capture_output=True`, `check=False`, 10s timeout.
- No model weights (`.pt/.pth/.ckpt/.safetensors/.onnx/.engine`) tracked.
- `.venv` contains only pinned lightweight dev tools (typer, pydantic, pyyaml,
  pillow, pytest, ruff, mypy, jsonschema). No heavy model deps.

### 3. SQLite default is DELETE/FULL/foreign_keys=ON, NOT WAL — PASS

- `src/.../persistence/sqlite.py` `StateStore.open()` executes, in autocommit:
  `PRAGMA foreign_keys = ON`, `PRAGMA busy_timeout = <ms>`,
  `PRAGMA journal_mode = DELETE`, `PRAGMA synchronous = FULL`.
- The `journal_mode_candidate="WAL"` parameter is annotated `# noqa: ARG002 -
  documented future candidate, NOT adopted in N0` and is never used. WAL is
  explicitly not adopted.
- `test_at_n0_db_01_pragma_baseline_delete_full_fk` PASS: asserts
  `journal_mode == "delete"`, `synchronous == 2` (FULL), `foreign_keys == 1`.
- `config/execution_defaults.yaml` documents `journal_mode_candidate: "WAL"`
  as a candidate only; the code does not adopt it. Consistent with the report.

### 4. Source protection before any read; no write/move/delete/chmod path — PASS

- `grep` for `os.(chmod|chown|remove|unlink|rename|replace|rmdir|mkdir|makedirs|
  write|truncate)`, `shutil.(move|copy|copyfile|copy2|rmtree)`,
  `open(...,"w"/"wb"/"wx")`, `Path.(write_text|write_bytes|unlink|rename|
  replace)`, `os.utime`, `os.link`, `os.symlink` across `src/` → **0 matches**.
  (The only `mkdir` is `path.parent.mkdir(...)` on the SQLite DB parent in the
  runtime/state area, not on source photos. Acceptable.)
- `ingest/source_guard.py` `open_source_file()` ordering:
  1. check allowed extension;
  2. reject reparse point/symlink (`is_reparse_point` checks `is_symlink()` AND
     `st_file_attributes & 0x400` for NTFS junctions on win32);
  3. reject realpath escape via containment (`_is_descendant`);
  4. pre-stat on path;
  5. `open(cand, "rb")` (binary read-only — the only open mode in the guard);
  6. `capture_fd_identity()` TOCTOU check (fstat vs pre-stat);
  7. `post_fingerprint()` on close (size/mtime re-check).
  All validation precedes the read; integrity is checked before, during, and
  after.
- `cli.py` `ingest()` calls `auth.require_ingest_authorized(...)` FIRST, then
  `validate_roots(...)` (overlap), then `run_dry_run_ingest(...)`. Gate fails
  closed before any source/DB access.
- `test_at_n0_sec_03_fixture_unchanged_after_read` PASS: pre/post size, mtime_ns,
  sha256 identical for all 3 fixtures.
- Reviewer-computed fixture SHA-256/size match `fixture_manifest.json` and the
  report's integrity table.

### 5. Dry-run writes no asset rows; repeated dry-run is deterministic/idempotent — PASS

- Two consecutive `npi ingest --dry-run` runs produced byte-identical stdout:
  `files_scanned: 3`, `unique_assets: 2`, `duplicate_groups: 1`,
  `database_mutated: False`.
- `ingest/runner.py` `run_dry_run_ingest()` never imports or opens
  `StateStore`; it returns `IngestDryRunResult(database_mutated=False)` with
  `database_mutated` hardcoded `False` on a frozen dataclass. No DB connection
  is created.
- No `.npi_runtime/` directory or `.db`/`.log` file was created in the repo by
  the dry-run (only `.mypy_cache/3.11/*.db` cache files exist, gitignored).
- `test_at_n0_idem_01_dry_run_idempotent_and_db_unchanged` PASS.

### 6. SHA-256, perceptual hash, state machine, recovery, Schema tests are real — PASS

- `test_at_n0_hash_01_streaming_sha_matches_manifest` / `_duplicate_pair_identical`
  PASS: streamed SHA-256 == manifest hash for all 3 fixtures; duplicate pair
  byte-identical.
- `test_at_n0_hash_02_*` PASS: perceptual hash carries `algorithm=dhash-8x8`,
  `implementation_version=npi-0.1.0`, lowercase-hex; deterministic.
- `test_at_n0_state_01_invalid_transitions_rejected` PASS: INGESTED→APPROVED
  rejected; non-human APPROVED rejected; terminal EXPORTED has no outgoing
  transitions.
- `test_at_n0_rec_01_interrupted_run_recoverable` PASS: RUNNING run with
  expired lease identified after reopen; recovery marks INTERRUPTED; no outputs
  invented; asset state unchanged.
- `test_at_n0_schema_01_valid_example_passes` and
  `test_at_n0_schema_02_invalid_examples_fail` PASS: valid item passes core
  rules + jsonschema Draft 2020-12; absolute-path / auto-approved / vlm-pose
  items each fail their expected core rule.
- All 19 required `AT-N0-*` IDs from the task contract are covered by 33 real
  tests (mapped 1:1 via `pytest --collect-only`). No stubs observed in the
  security/git/state/schema tests I inspected.

### 7. pytest / Ruff / mypy / format-check are actual runs; no NOT_AVAILABLE-as-PASS — PASS

- All four ran on CPython 3.12.10 in `.venv` with real output (commands 1-5
  above). `ruff 0.15.21` and `mypy 2.3.0` are installed in `.venv` and were
  executed.
- `tools/run_quality.py` reports `7 pass, 0 fail, 0 not_available, 0 skipped`
  and `QUALITY_GATE_PASSED`.
- Skips are honestly labelled: GPU container execution = SKIPPED (must not pull
  an image in N0); `source_runtime_separation` = SKIPPED (env vars unset, N1
  concern); Python 3.11 = not available (documented, not relabeled PASS).
  No `NOT_AVAILABLE` is described as `PASS`.

### 8. Python 3.12 execution evidence; compatibility claim within tested range — PASS

- `.venv` is CPython 3.12.10. All quality commands and tests ran on it.
- `pyproject.toml` `requires-python = ">=3.11,<3.13"`.
- The report explicitly states 3.11 is the targeted lower bound but NOT
  verified by test (only 3.12.10 is installed), and claims NO 3.13/3.14
  compatibility. Claim does not exceed the tested range.
- (Note: `.mypy_cache/3.11/` exists because mypy checks against the 3.11
  stdlib stubs — a static check, not a 3.11 test execution. Not an overclaim.)

### 9. No real absolute paths / tokens / weights / private keys / running DB in logs/db/reports/git — PASS

- `grep` for `C:\Users\` / `E:\project\` / `C:\Users\<A-Z>` across
  `reports/`, `src/`, `tests/`, `tools/` → 0 matches.
- `git ls-files` scanned for `.db/.sqlite*/.log/.pem/.key/.p12/.pfx/.pt/.pth/
  .ckpt/.safetensors/.onnx/.engine/.npy/.npz/.env` and `token/secret/password/
  api_key` patterns → 0 matches.
- No `BEGIN PRIVATE KEY` / `BEGIN RSA PRIVATE KEY` / `BEGIN CERTIFICATE` in
  tracked files.
- Dry-run output redacts source root to `<SOURCE_ROOT>` and runtime to
  `<RUNTIME_ROOT>`.
- `.gitignore` excludes `runtime/`, `state/`, `*.db`, `*.sqlite*`, `*.log`,
  model weights, image derivatives, `.venv/`, secrets, `.env`. The 3 fixture
  PNGs are explicitly allowlisted.

### 10. Four reports consistent with code, tests, and commit — PASS_WITH_MINOR_DISCREPANCY

- `N0_environment_report.md`, `N0_unresolved_issues.md`, `N1_detailed_plan.md`
  are consistent with the code and commit I inspected.
- `N0_test_evidence.md` is consistent on every material safety claim, with ONE
  discrepancy (non-blocking): the report's quality-gate block says
  `32 passed, 0 skipped`, but the actual pytest count is **33 passed**
  (`tools/run_quality.py` itself now reports `33 passed`). The report
  undercounts by one test — conservative direction, not a safety issue, but
  the evidence block is stale. See non-blocking finding N1.

### 11. Working tree clean; N0 has exactly one implementation commit — PASS

- `git rev-list --count HEAD` == 1.
- `git status --porcelain` == clean.
- The single commit `229be08` contains the entire delivery package plus the N0
  implementation (first commit after `git init`). No second implementation
  commit, no amend churn visible in `git log --oneline`.
- `test_at_n0_git_01_one_isolated_commit_no_sensitive_files` PASS (real
  assertions: exactly 1 commit, clean tree, no sensitive tracked files, only
  3 fixture PNGs).

### 12. Implementation did not expand to N1 — PASS

- `cli.py` registers only `preflight`, `status`, `ingest` — the three N0
  commands. No `run`, `resume`, `report`, `export` commands (those are N1+).
- `persistence/sqlite.py` includes `identify_interrupted_runs()` and
  `recover_interrupted_runs()` (mark INTERRUPTED). This is the N0
  reopen/recovery scope required by `AT-N0-REC-01` and the task contract's
  `reopen/recovery test` requirement — not N1 `npi resume` reclaim logic.
- `ingest/runner.py` is dry-run only; no real ingest path.
- `N1_detailed_plan.md` is forward-looking only and states "N1 is LOCKED until
  the Owner updates `PROJECT_STATE.json`" and "No N1 work is started."
- No model/VLM/SAM/Pose/embedding code. No cloud/OpenClaw/App integration.

## Blocking findings

None. Every safety hard-constraint in `MASTER_EXECUTION_CONTRACT.md` §3 and
the N0 task contract is evidenced by code I inspected and tests I ran:

- Source read-only protection with no write/move/delete/chmod API (grep-verified).
- Source/runtime overlap and symlink/junction-escape rejection (incl. NTFS
  `st_file_attributes & 0x400`).
- Dry-run non-mutation and deterministic idempotency.
- Gate fail-closed (exit 8) before any source/DB access.
- SQLite DELETE + FULL + foreign_keys=ON baseline (WAL not adopted).
- Original contract files intact (171-file subset check); `PROJECT_STATE.json`
  byte-identical to manifest.

## Non-blocking findings

**N1 (report accuracy — stale test count).** `reports/N0_test_evidence.md`
quality-gate block states `32 passed, 0 skipped`, but the actual pytest result
is `33 passed` (confirmed by `tools/run_quality.py`, which prints `33 passed`).
The report undercounts by one test. Direction is conservative (more tests pass
than claimed), so it does not inflate any safety claim, but the evidence block
should be regenerated so the report matches reality. Recommended fix: re-run
`tools/run_quality.py` and paste the current output into the report, or note
the count was 32 at first write-up and 33 at final commit.

**N2 (`tools/verify_handoff.py` diverges post-implementation).** Running
`tools/verify_handoff.py` now produces FAILs because it does `ROOT.rglob("*")`
exact-set matching including `.venv/` and `.git/`, and its heuristic flags
`.venv` binaries (ruff.exe, mypyc/pyd/PIL `.pyd` > 5 MiB) and pytest source
files as "possible secret or personal absolute path". This is documented in
`N0_unresolved_issues.md` issue #3 as an Owner-decision item, and the N0
quality gate substitutes a contract-files-unchanged subset check (171 files
intact) which PASSes. The report's "historical 16 pass pre-implementation"
claim is plausible but not independently reproducible after the fact. Owner
should confirm the subset-check interpretation; N1 may refine
`verify_handoff.py` to exclude `.git` and gitignored paths from the exact-set
check. Not a blocker for N0 because the subset check preserves the original
contract-file integrity guarantee.

**N3 (Python 3.11 not verified).** Only 3.12.10 (used) and 3.14.2 (not used)
are installed. 3.11 is the contract's preferred lower bound
(`requires-python = ">=3.11,<3.13"`) but is not tested. Documented as an
Owner-decision in `N0_unresolved_issues.md` issue #1. No 3.13/3.14
compatibility is claimed. Owner must decide: accept 3.12-only verification or
require a 3.11 test run before N1.

**N4 (preflight `catalog_version=unknown`).** `npi preflight` reports
`catalog_version=unknown` because `schemas/schema_catalog.json` lacks an
explicit `catalog_version` field. Cosmetic; the item schema itself validates
correctly (SCHEMA-01/02 PASS).

**N5 (`source_runtime_separation` SKIPPED in preflight).** `NPI_SOURCE_ROOT` /
`NPI_RUNTIME_ROOT` are unset, so preflight reports SKIPPED. Expected for N0
(no real photo root); the guard code that enforces separation is tested and
PASSes (SEC-01). N1 must configure these and re-verify.

## Final conclusion

**PASS_FOR_OWNER_REVIEW**

Rationale: the single N0 commit `229be08` stays within the authorized N0/G0
scope. All twelve review points are satisfied with evidence I verified
directly (code inspection + re-run of pytest/ruff/mypy/format-check/quality
gate/CLI commands). No safety hard-constraint is unproven. The five
non-blocking findings are accuracy/hygiene items or documented Owner-decisions;
none of them inflate a safety claim or expand scope. The most material
non-blocking item (N1, stale test count) is conservative and trivially
fixable; N2 (verify_handoff divergence) is already disclosed and handled via
the subset check.

This `PASS_FOR_OWNER_REVIEW` is advisory. It does NOT approve N0, does NOT
modify `PROJECT_STATE.json`, and does NOT authorize N1. Only the Owner may
approve the N0 gate and unlock N1, and only after resolving the Owner-decision
items in `N0_unresolved_issues.md` (3.11 decision, real-photo-root
authorization, G1 manifest, WAL decision, etc.).

Reviewer stops here, awaiting Owner.
