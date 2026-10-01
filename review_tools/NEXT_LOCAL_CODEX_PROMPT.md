# Local Codex handoff - B-source one-shot executor repair

Repository: `Jovifei/nightly-photo-intelligence-pipeline`
Review branch: `chatgpt/npi-fetcher-one-shot-20261001`
Implementation commit: `5e784fb21bf159af891880314d032b3ad14b4f12`
Reviewed predecessor: `8089b48df29fe0a4ba72559b56e699b40ee3e6c7`

## Exact review verdict on predecessor

`8089b48d...` is **CHANGES_REQUIRED** for one substantive one-shot execution
gap. Its `retry_authorized=false` value was descriptive: the CLI persisted the
fixed terminal result only after acquisition returned. A first-request failure
could leave the quarantine empty and permit the same reviewed HEAD/receipt to
construct transport and issue another request before persistence discovered the
existing terminal file.

## Repair in this branch

- The executor now claims a permanent handle-bound lease at
  `E_CLAUDE_ALLOW_DOWNLOAD/npi-c2c-evidence-20260930/b-source-network-acquisition-one-shot-v1`.
- Claim occurs only after DONE-receipt validation, exact-payload absence evidence,
  exact-three binding and quarantine handle/location validation, but before
  transport construction.
- A flushed `reservation.json` binds reviewed HEAD/tree and
  `retry_authorized=false`.
- Existing lease or legacy terminal evidence rejects the invocation before any
  transport construction. The lease is never deleted, preventing ABA/retry.
- The first attempt's schema-valid terminal result is exclusive-created as
  `terminal.json` inside the lease before the executor returns.
- CLI no longer performs a separate post-action persistence step.
- Same-runtime regression coverage asserts: first injected network failure
  consumes exactly one request and preserves its terminal; the second call
  consumes zero new requests and cannot overwrite the first terminal.
- Task, Owner approval and closed schemas bind the permanent lease, pre-request
  claim, retry denial and lease-bound terminal persistence.

## Required local validation

Remote GitHub tooling has no repository execution terminal, therefore these are
**NOT_RUN_REMOTE** for the successor:

```text
git status --short
git diff --check
python -m pytest tests/test_n2b1p_b_source_fetcher.py tests/test_n2b1p_b_source_network_reacquisition_v1.py tests/test_review_candidate_governance.py -q
python tools/verify_review_candidate.py
python -m ruff check src/nightly_photo_intelligence_pipeline/n2b1p_b_source_fetcher.py src/nightly_photo_intelligence_pipeline/cli.py tests/test_n2b1p_b_source_fetcher.py
python -m ruff format --check src/nightly_photo_intelligence_pipeline/n2b1p_b_source_fetcher.py src/nightly_photo_intelligence_pipeline/cli.py tests/test_n2b1p_b_source_fetcher.py
python -m mypy src/nightly_photo_intelligence_pipeline
python tools/sensitive_file_scan.py
python -m pytest -q
python tools/verify_handoff.py
```

Expected historical readiness failures remain the canonical-cache /
synthetic-authorization blockers. Do not weaken them.

No DONE receipt was created. No live B-source request, cache promotion,
model/CUDA execution, photo/EXIF access, SQLite/Real20 activity, main merge or
release was run or authorized by this repair.
