# Local Codex handoff - bounded B-source fetcher final receive candidate

Repository: `Jovifei/nightly-photo-intelligence-pipeline`
Review branch: `chatgpt/n2b1p-b-source-fetcher-20261001`
Remote predecessor: `28dcaaa0ad7cbb47fd31091502694b5b54a88873`

The final candidate is the commit containing this document. Confirm the exact
HEAD/tree from the remote ChatGPT handoff after fetch.

## Last local evidence received

For the byte-identical tree carried by `30b3743bc8c16b14b0241742421ce3f09f0d7bc7`
and the later empty `28dcaaa0ad7cbb47fd31091502694b5b54a88873` commit,
Jovi reported:

- focused tests: 75 PASS;
- Ruff check: PASS;
- mypy: 103 source files PASS;
- sensitive scan: 0 violations;
- git diff --check: PASS;
- strict review eligibility: FAIL only because root `MANIFEST.sha256`
  contained a pseudo path named `VERSION\\n` while Git tracks `VERSION`;
- Ruff format --check: four files still require reformatting.

This successor fixes the governance-byte mismatch by binding the real tracked
`VERSION` path, restores the todo status line to a real EOF newline, refreshes
both manifests, and removes obsolete connector-setup wording from this handoff.

## Important remaining validation

Remote GitHub write tooling has no repository execution terminal, and the
available isolated runtime has no cached Ruff 0.15.21. Therefore this handoff
does **not** claim that Ruff format now passes. Local Codex must run the exact
project formatter on these four files and, if it changes bytes, commit those
formatter-only bytes and recompute both manifests before returning the final
exact SHA:

```text
src/nightly_photo_intelligence_pipeline/n2b1p_b_source_fetcher.py
src/nightly_photo_intelligence_pipeline/n2b1p_b_source_network.py
tests/test_n2b1p_b_source_fetcher.py
tests/test_n2b1p_b_source_network_reacquisition_v1.py
```

Then run:

```text
git diff --check
python -m pytest tests/test_n2b1p_b_source_fetcher.py tests/test_n2b1p_b_source_network_reacquisition_v1.py tests/test_review_candidate_governance.py -q
python tools/verify_review_candidate.py
python -m ruff check src/nightly_photo_intelligence_pipeline/n2b1p_b_source_fetcher.py src/nightly_photo_intelligence_pipeline/n2b1p_b_source_network.py tests/test_n2b1p_b_source_fetcher.py tests/test_n2b1p_b_source_network_reacquisition_v1.py
python -m ruff format --check src/nightly_photo_intelligence_pipeline/n2b1p_b_source_fetcher.py src/nightly_photo_intelligence_pipeline/n2b1p_b_source_network.py tests/test_n2b1p_b_source_fetcher.py tests/test_n2b1p_b_source_network_reacquisition_v1.py
python -m mypy src/nightly_photo_intelligence_pipeline
python tools/sensitive_file_scan.py
python tools/verify_handoff.py
```

Historical missing-cache failures remain truthful and must not be weakened.

No DONE receipt is issued by this handoff. No B-source download, cache promotion,
model/CUDA execution, photo/EXIF access, SQLite/Real20 activity, main merge or
release is authorized or run.
