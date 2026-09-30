# Local Codex handoff - B-source exact-SHA admission review

Repository: `Jovifei/nightly-photo-intelligence-pipeline`  
Review branch: `chatgpt/n2b1p-final-review-20260930`  
Original pushed candidate: `5f9fd53b752551fd678bc3ecde0814b656b80dd1`  
Original candidate tree: `3904fc13884f073645ebac7a5c639639b02c1e7e`  
Remote implementation commit: `ede711176479568343c20e0c266faf09c0fbde82`  
Remote implementation tree: `ff5af34ec70d815997540d1615e7803169c894d5`

The final handoff commit is the commit containing this document. Resolve the review
branch HEAD after fetch and cross-check it with the exact final HEAD/tree reported
by remote ChatGPT. Do not substitute the implementation SHA for that final receipt
binding.

## Remote review verdict and findings

The B_SOURCE control packet itself correctly remains pre-download and fail-closed:
exactly three historical TorchVision URLs under `download.pytorch.org`, exact
historical byte/SHA targets, fresh external quarantine binding, network denied
before external exact-SHA review, existing Route-B cache promotion still separate,
and model/CUDA/photo/EXIF/SQLite/Real20 unchanged.

The exact candidate review found two governance defects and one missing next-stage
gate:

1. `tools/verify_review_candidate.py` used ordinary YAML loading, so duplicate
   mapping keys were not independently rejected.
2. `review_candidate.allowed_change_categories` was declared but the actual
   candidate path range was not checked against it.
3. The external exact-SHA review receipt had a schema but no executable read-only
   admission that rebound the receipt to the exact current HEAD/tree/MANIFEST/task/
   Owner/runtime/review-report state before any later download.

The generic immutable-baseline / linear no-merge design is retained. No per-commit
`HEAD^` exception was reintroduced. Full handoff/cache readiness remains a
separate truth surface and may still fail on the historical missing cache.

## Remote changes

The review branch adds/hardens:

- duplicate-key rejection in the generic review-eligibility YAML path;
- closed nine-category review scope plus actual path classification from the
  active B_SOURCE task introduction commit through current HEAD;
- rejection of delete/rename or unrelated paths in that review range;
- a stronger `EXTERNAL_EXACT_SHA_REVIEW_RECEIPT_V1` schema binding the tracked
  review report as well as exact candidate/evidence hashes;
- `validate_external_exact_sha_review_receipt` and a fail-closed wrapper;
- `npi n2b1p network-admission --review-receipt ...`, which performs only
  read-only exact-SHA admission and returns zero network requests;
- Windows receipt-parent enforcement for
  `E:\\Claude_allow\\Download\\npi-c2c-evidence-20260930`;
- negative tests for duplicate YAML, unrelated review paths, stale/non-DONE
  receipts, and network-disabled CLI admission;
- root MANIFEST updates.

No downloader, cache promoter, model runner, CUDA path, photo reader, SQLite/Real20
action, Pilot action or App mutation was added or executed remotely.

## Test and execution evidence

Remote GitHub read/write capability: PASS. The exact candidate was read from GitHub,
an independent review branch was created, and the commits above were written by the
GitHub connector.

Remote repository test execution: **NOT_RUN**. The GitHub connector available to
remote ChatGPT does not provide a repository execution environment. Do not treat the
remote static/code review as pytest/Ruff/mypy PASS.

The last local evidence supplied by Jovi applies to original candidate
`5f9fd53...`, not to the remote changes:

- generic review eligibility PASS;
- full pytest: 946 passed, 2 known missing-cache failures, 1 Windows skip,
  95 subtests;
- full handoff still blocked by the historical N2B1P canonical-cache absence.

No network download, cache promotion, model load, CUDA execution, photo/EXIF access,
SQLite/Real20 action or main merge/release was performed by remote ChatGPT.

## Required local validation

Fetch the review branch without resetting or merging `main`, verify the exact final
HEAD/tree against the remote ChatGPT handoff, and run in the already-qualified Python
3.12 quality environment:

```text
git status --short
git diff --check
E:\Claude_allow\Download\npi-py312-quality-venv-20260929\Scripts\python.exe tools/verify_review_candidate.py
E:\Claude_allow\Download\npi-py312-quality-venv-20260929\Scripts\python.exe -m pytest tests/test_review_candidate_governance.py tests/test_n2b1p_b_source_network_reacquisition_v1.py tests/test_git.py tests/test_schema.py -q
E:\Claude_allow\Download\npi-py312-quality-venv-20260929\Scripts\python.exe -m ruff check .
E:\Claude_allow\Download\npi-py312-quality-venv-20260929\Scripts\python.exe -m ruff format --check .
E:\Claude_allow\Download\npi-py312-quality-venv-20260929\Scripts\python.exe -m mypy src/nightly_photo_intelligence_pipeline
E:\Claude_allow\Download\npi-py312-quality-venv-20260929\Scripts\python.exe tools/sensitive_file_scan.py
E:\Claude_allow\Download\npi-py312-quality-venv-20260929\Scripts\python.exe -m pytest -q
E:\Claude_allow\Download\npi-py312-quality-venv-20260929\Scripts\python.exe tools/verify_handoff.py
```

Recompute and verify both `MANIFEST.sha256` and
`review_tools/MANIFEST.sha256`. Record actual command exit codes and complete
counts. The historical canonical-cache failure must remain FAIL/BLOCKED until cache
recovery; do not weaken the handoff gate to make it green.

## Materialize the exact-SHA review receipt only after local validation

If the remote branch bytes pass the targeted/static local checks, create this
Git-external file:

`E:\Claude_allow\Download\npi-c2c-evidence-20260930\b-source-network-exact-sha-review-v1.json`

Populate it from independently recomputed local values:

```text
schema_version = 1.0
receipt_type = EXTERNAL_EXACT_SHA_REVIEW_RECEIPT_V1
task_id = N2B1P_B_SOURCE_NETWORK_REACQUISITION_V1
review_scope = B_SOURCE_NETWORK_REACQUISITION_V1_CONTROL_PACKET_ONLY
verdict = DONE
reviewed_head = exact final review-branch HEAD from this handoff
reviewed_tree = git rev-parse HEAD^{tree}
immutable_baseline_commit = candidate_commit from approvals/phase_completion_N2B1P.yaml
current_manifest_sha256 = SHA-256 of current MANIFEST.sha256 bytes
task_sha256 = SHA-256 of tasks/phase_n2b1p_b_source_network_reacquisition_v1.yaml
owner_approval_sha256 = SHA-256 of approvals/owner_n2b1p_b_source_network_reacquisition_v1.yaml
runtime_configuration_sha256 = SHA-256 of approvals/n2b1p_b_source_network_runtime_configuration_v1.json
review_report_ref = review_tools/NEXT_LOCAL_CODEX_PROMPT.md
review_report_sha256 = SHA-256 of this tracked handoff document
reviewed_at_utc = actual UTC materialization timestamp
```

Then run:

```text
npi n2b1p network-admission --project-root <exact-clean-review-worktree> --review-receipt E:\Claude_allow\Download\npi-c2c-evidence-20260930\b-source-network-exact-sha-review-v1.json
```

Required result is
`B_SOURCE_NETWORK_POST_REVIEW_ADMISSION_PASS` with
`network_request_count=0`. Any HEAD/tree/MANIFEST/task/Owner/runtime/report drift,
non-DONE receipt, dirty tree or wrong receipt location must stop before network.

## Next bounded local action

After local validation and receipt admission, revalidate the existing task's
`exact_payloads_missing_under_ref` precondition and fresh-quarantine identity/
attestation immediately before any acquisition.

If the repository does not already contain a reviewed executor that enforces the
exact three URLs, final-domain allowlist, byte ceilings, SHA-256s, quarantine-only
writes, staging/reread and zero model load, **do not use ad-hoc curl/PowerShell as a
substitute**. Prepare that executor as a code-only candidate and return it for remote
exact-SHA review first.

If a reviewed executor is already present and every current gate passes, the only
permitted acquisition scope is the three exact task-bound weights into the bound
fresh quarantine. After acquisition stop at
`B_SOURCE_BYTES_READY_AWAITING_EXTERNAL_REVIEW`.

Gate B quarantine-to-cache promotion remains a separate Owner/review gate. Model/CUDA
continuity is later and separate. Real photos, EXIF, SQLite, Real20, Bundle, Pilot,
App integration, main merge and release remain locked behind their existing gates.

## Product critical path

The intended path toward `PILOT_APP_INTEGRATION_PASS` remains:

```text
B_SOURCE exact bytes
-> external B_SOURCE evidence review
-> separate Gate B cache promotion
-> separate synthetic visual/CUDA continuity
-> separately authorized Real20
-> human quality decision
-> minimal Bundle/App import + rollback validation
-> bounded 100-photo Pilot
-> PILOT_APP_INTEGRATION_PASS
```

Do not skip a gate because the control packet or review eligibility is green.
