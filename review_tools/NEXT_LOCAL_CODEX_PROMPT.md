# Local Codex handoff - bounded B-source fetcher repair

Repository: `Jovifei/nightly-photo-intelligence-pipeline`
Review branch: `chatgpt/n2b1p-b-source-fetcher-20261001`
Repair parent: `7622d7ae4a5d4a2d78882f07df275b550768508f`

The final repair HEAD is the commit containing this document. Verify its exact
HEAD/tree against the remote ChatGPT handoff after fetch. This remains an
executor-code review candidate and does not authorize a live download.

## Repaired local and independent-review findings

This successor addresses the complete reported set:

- legacy network-control tests now understand the
  `CONTROL_PLANE_AND_EXECUTOR_CODE_ONLY` class and
  `B_SOURCE_NETWORK_REACQUISITION_V1_EXECUTOR_CODE_ONLY` scope while still
  requiring `execution_authority=NOT_AUTHORIZED` and `network_access=DENY`;
- the exact-SHA receipt remains executor-scope only; an earlier
  `CONTROL_PACKET_ONLY` receipt is explicitly rejected;
- root MANIFEST coverage is refreshed for every file added/changed on the fetcher
  lineage, including all new schemas, tests and executor files;
- the reported Ruff/mypy defects are repaired: UP037, jsonschema untyped import,
  read-only response status Protocol, unsafe identity typing, terminal-result typing
  and redundant casts;
- the fixed quarantine path is passed lexically to the Windows handle helper without
  `Path.resolve()`, so original parent/final junctions remain visible to per-component
  reparse rejection;
- after handle binding, the approved object identity is checked again, the
  handle-observed final path must be the exact direct child of the separately bound
  fixed Download parent, and it must not overlap separately bound Route-B or
  historical cache roots;
- `NpiError` / `PromotionPathSafetyError` from handle-bound operations is converted
  into structured fail-closed terminal results. A pre-request path failure records
  zero requests; a post-request publication failure preserves the actual request count;
- every aggregate acquisition terminal result must be persisted with exclusive
  handle-bound creation at logical ref
  `E_CLAUDE_ALLOW_DOWNLOAD/npi-c2c-evidence-20260930/b-source-network-acquisition-result-v1.json`.
  CLI stdout contains the logical ref and SHA-256, not an unrestricted output path;
- tests cover lexical non-resolution, handle-observed moved-under-cache rejection,
  injected parent-junction/path-safety failure, post-request path-safety failure,
  old-receipt rejection and CLI terminal-result persistence.

## Remote execution status

Pytest, Ruff, mypy, Windows junction creation and the executor itself are **NOT_RUN**
remotely because the GitHub connector has no repository execution terminal.

No DONE receipt was created. No request to `download.pytorch.org` or any model URL
was made. Cache promotion, model/CUDA, photo/EXIF, SQLite/Real20, Bundle/Pilot/App,
main merge and release remain NOT_RUN / independently gated.

## Required clean local validation

Run from the exact final branch HEAD in the qualified Python 3.12 environment:

```text
git status --short
git diff --check
python -m pytest tests/test_n2b1p_b_source_fetcher.py tests/test_n2b1p_b_source_network_reacquisition_v1.py tests/test_review_candidate_governance.py -q
python tools/verify_review_candidate.py
python -m ruff check src/nightly_photo_intelligence_pipeline/n2b1p_b_source_fetcher.py src/nightly_photo_intelligence_pipeline/n2b1p_b_source_network.py src/nightly_photo_intelligence_pipeline/cli.py tests/test_n2b1p_b_source_fetcher.py tests/test_n2b1p_b_source_network_reacquisition_v1.py
python -m ruff format --check src/nightly_photo_intelligence_pipeline/n2b1p_b_source_fetcher.py src/nightly_photo_intelligence_pipeline/n2b1p_b_source_network.py src/nightly_photo_intelligence_pipeline/cli.py tests/test_n2b1p_b_source_fetcher.py tests/test_n2b1p_b_source_network_reacquisition_v1.py
python -m mypy src/nightly_photo_intelligence_pipeline
python tools/sensitive_file_scan.py
python -m pytest -q
python tools/verify_handoff.py
```

Recompute both manifests. The historical missing-cache quality/handoff failures must
remain truthful until cache recovery; do not weaken those gates.

If local validation passes, return this same exact HEAD/tree for another exact-SHA
review. Only after that review explicitly accepts this final executor-code SHA may a
new DONE receipt be materialized with
`review_scope=B_SOURCE_NETWORK_REACQUISITION_V1_EXECUTOR_CODE_ONLY`.

Any receipt bound to `2ed5ec0...`, `7622d7a...`, the earlier control-only scope,
or another ancestor/sibling remains invalid. Even a future valid receipt still
requires exact-payload absence evidence and the fixed quarantine handle/location
checks immediately before transport creation. Successful acquisition stops at
`B_SOURCE_BYTES_READY_AWAITING_EXTERNAL_REVIEW`; Gate B cache promotion is separate.
