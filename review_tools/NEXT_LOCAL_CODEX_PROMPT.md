# Local Codex handoff - B-source lease crash-state hardening

Repository: `Jovifei/nightly-photo-intelligence-pipeline`
Review branch: `chatgpt/npi-fetcher-lease-crash-state-20261001`
Implementation tip before this handoff: `49b1a7c5bf25e76f5523daabdfd493d950d88c1b`
Exact reviewed predecessor: `b96457115477128254e7f3aab33a2f19efe6784b`

## Completed bounded remediation

This branch implements only the previously reviewed one-shot crash-state repair.

- `OneShotExecutionClaim` now stores the handle-observed lease identity digest
  and a 128-bit random nonce.
- The reservation binds nonce, lease identity, reviewed HEAD/tree and
  `retry_authorized=false`.
- Reservation and terminal are no longer direct create/write records. Each is
  written beneath `BoundStagingTransaction`, flushed and reread while staged,
  then atomically published by handle-bound rename as:
  - `reservation-v1/reservation.json`
  - `terminal-v1/terminal.json`
- Terminal persistence reopens the fixed evidence parent/lease using the existing
  handle-bound primitives, then verifies lease identity plus reservation
  HEAD/tree/identity/nonce before terminal publication.
- Existing lease state is explicit:
  - no valid atomic reservation => `INCOMPLETE_CLAIM`
  - valid reservation, no valid terminal => `CLAIMED`
  - valid reservation + completed terminal => `COMPLETED`
- All three existing states fail before transport construction. Incomplete and
  completed states therefore perform zero new HTTP and never overwrite durable
  evidence.
- A crash after reservation validation but before terminal publication leaves
  the valid reservation intact. The next call reports `CLAIMED` and consumes
  zero HTTP.
- A normal in-process network failure is terminalized in the same invocation and
  returned as `one_shot_state=COMPLETED`.

## Legacy executor concurrency boundary

No extra cross-version coexistence mechanism was added. This is intentional and
bounded by existing reviewed admission rules:

1. the review receipt schema fixes
   `review_scope=B_SOURCE_NETWORK_REACQUISITION_V1_EXECUTOR_CODE_ONLY`;
2. admission compares the receipt to the exact current HEAD and tree;
3. the existing regression rejects the earlier
   `B_SOURCE_NETWORK_REACQUISITION_V1_CONTROL_PACKET_ONLY` scope;
4. no DONE receipt or real B-source acquisition has ever been issued/run for the
   earlier unreviewed executor.

Therefore an old CLI has no authorized receipt with which to cross its network
gate. If that governance fact changes, a separately reviewed shared cross-version
mutex is required before coexistence.

## Local validation required

Remote GitHub tooling has no repository execution terminal. The following are
**NOT_RUN_REMOTE** and must be run from the exact final branch HEAD using the
qualified Python 3.12 environment:

```text
git status --short
git diff --check
python -m pytest tests/test_n2b1p_b_source_fetcher.py tests/test_n2b1p_b_source_network_reacquisition_v1.py tests/test_review_candidate_governance.py -q
python tools/verify_review_candidate.py
python -m ruff check src/nightly_photo_intelligence_pipeline/n2b1p_b_source_fetcher.py tests/test_n2b1p_b_source_fetcher.py
python -m ruff format --check src/nightly_photo_intelligence_pipeline/n2b1p_b_source_fetcher.py tests/test_n2b1p_b_source_fetcher.py
python -m mypy src/nightly_photo_intelligence_pipeline
python tools/sensitive_file_scan.py
python -m pytest -q
python tools/verify_handoff.py
```

Historical canonical-cache / current-authorization readiness failures must remain
truthful and must not be weakened.

No DONE receipt was created. No live network request, payload download, cache
promotion, model/CUDA execution, photo/EXIF access, SQLite/Real20 action, main
merge or release was performed or authorized.
