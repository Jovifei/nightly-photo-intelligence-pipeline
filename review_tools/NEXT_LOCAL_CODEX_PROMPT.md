# Local Codex handoff - bounded B-source fetcher repair

Repository: `Jovifei/nightly-photo-intelligence-pipeline`
Review branch: `chatgpt/n2b1p-b-source-fetcher-20261001`
Remote repair base: `df2d49bd62bc3fe7c4f9efd404bd7b711a272791`

The final review candidate is the commit containing this document. Verify its exact
HEAD/tree against the remote ChatGPT response after fetch. This is still an
executor-code review candidate; it is not a live-download authorization.

## Local evidence received before this successor

Jovi locally validated `df2d49bd62bc` and reported:

- focused tests: collection failed because prior GitHub API edits had written literal
  backslash-n text into four Python files;
- the remaining behavioral target was
  `test_network_failure_is_terminal_and_not_retryable`, which must enter the
  production-exact-three execution path before injecting its first-request I/O failure;
- the UNC/device-path negative fixture still needed dynamic construction for the
  sensitive scanner;
- Ruff format still required the four fetcher/network Python files;
- verify-review remained blocked by the root MANIFEST exact tracked-set binding.

Earlier local evidence on `4bda7c8873e800cdf2959091efb2e64b6b8d3dde`
included review-eligibility PASS, mypy 103 files PASS, Ruff check PASS, diff-check
PASS, and 74 focused passes / 1 focused failure.

## This remote successor

This successor is intentionally narrow:

1. removes every accidental literal backslash-n syntax token while preserving
   legitimate string literals that intentionally contain a newline escape;
2. preserves production `_execution_specs` strict exact-three enforcement;
3. changes the remaining network-failure test to a legal three-artifact binding,
   then lets the first exact URL raise the injected I/O failure and asserts
   `network_request_count == 1` and the exact attempted URL;
4. builds the moved-under-cache synthetic path from runtime components instead of
   embedding a UNC/device prefix;
5. restores top-level/EOF formatting in the four changed Python files and normalizes
   them to LF with one final newline;
6. refreshes the root MANIFEST plus the review-tools MANIFEST and this handoff.

The previously reviewed production safety semantics remain unchanged: fixed lexical
quarantine path before handle binding, handle-observed approved-location check before
identity classification, exact three HTTPS URLs, bounded redirect/domain policy,
stream byte/SHA checks, handle-bound staging/atomic publication/reread, NpiError
terminalization, durable Git-external aggregate result, and separate Gate B.

## Remote execution status

GitHub read/write was used to update this branch. The available remote environment
does not contain Ruff and cannot resolve GitHub for a checkout, and no repository
workflow run exists for this branch commit. Therefore:

- focused pytest: **NOT_RUN_REMOTE**
- Ruff check: **NOT_RUN_REMOTE**
- Ruff format check: **NOT_RUN_REMOTE**
- mypy: **NOT_RUN_REMOTE**
- verify-review / verify-handoff: **NOT_RUN_REMOTE**
- sensitive scan: **NOT_RUN_REMOTE**

No DONE receipt was created. No model-weight request or other live network acquisition
was executed. Cache promotion, model/CUDA, photo/EXIF, SQLite/Real20, Bundle/Pilot/App,
main merge and release remain NOT_RUN / independently gated.

## Required clean local validation

Run against the exact final HEAD in the qualified Python 3.12 environment:

```text
git status --short
git diff --check
python -m pytest tests/test_n2b1p_b_source_fetcher.py tests/test_n2b1p_b_source_network_reacquisition_v1.py tests/test_review_candidate_governance.py -q
python tools/verify_review_candidate.py
python -m ruff check src/nightly_photo_intelligence_pipeline/n2b1p_b_source_fetcher.py src/nightly_photo_intelligence_pipeline/n2b1p_b_source_network.py tests/test_n2b1p_b_source_fetcher.py tests/test_n2b1p_b_source_network_reacquisition_v1.py
python -m ruff format --check src/nightly_photo_intelligence_pipeline/n2b1p_b_source_fetcher.py src/nightly_photo_intelligence_pipeline/n2b1p_b_source_network.py tests/test_n2b1p_b_source_fetcher.py tests/test_n2b1p_b_source_network_reacquisition_v1.py
python -m mypy src/nightly_photo_intelligence_pipeline
python tools/sensitive_file_scan.py
python -m pytest -q
python tools/verify_handoff.py
```

Recompute and verify both manifests. Historical missing-cache failures remain expected
until the separately gated cache recovery completes; do not weaken those gates.

If the final candidate passes locally, return the same exact HEAD/tree for another
exact-SHA review. Only after that review explicitly accepts the executor-code SHA may
a new DONE receipt be materialized with
`review_scope=B_SOURCE_NETWORK_REACQUISITION_V1_EXECUTOR_CODE_ONLY`.

Real B-source download remains NOT_RUN now. Gate B cache promotion, model/CUDA,
photos/EXIF, SQLite/Real20 and later Pilot/App work remain separate gates.
