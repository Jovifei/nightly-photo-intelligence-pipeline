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

## Remote and local validation

Remote GitHub tooling had no repository execution terminal; its checks remain
**NOT_RUN_REMOTE**. Local Codex received and tested the exact implementation
commit below using the already installed Python 3.12 quality environment:

```text
branch: chatgpt/npi-fetcher-lease-crash-state-20261001
remote handoff: 06c464a2069b761b2bd7f7866cac5c972c1eec6d
locally formatted implementation: 1cf07466082db54a8212c727285618191b760000
implementation tree: 5555c8fcb2c1012d1a7f10a0e802c80059e0af5d
parent: 06c464a2069b761b2bd7f7866cac5c972c1eec6d
```

Local verification on that clean implementation candidate:

```text
focused pytest: 112 passed, exit 0
ruff check src tests tools: PASS, exit 0
ruff format --check src tests tools: PASS, 179 files formatted, exit 0
mypy src/nightly_photo_intelligence_pipeline: PASS, 103 files, exit 0
tools/verify_review_candidate.py: PASS, exit 0
tools/sensitive_file_scan.py: PASS, 0 violations, exit 0
tools/verify_handoff.py: 8 PASS / 1 FAIL, exit 1
tools/run_quality.py: FAIL, exit 1; 968 passed, 2 failed, 1 skipped, 95 subtests
```

The handoff failure is the existing canonical-cache `FileNotFoundError`. Full
quality failures are `tests/test_handoff.py::test_current_handoff_verifier_passes`
(same missing canonical cache) and
`tests/test_preflight_current_stage.py::test_cli_preflight_exits_zero_with_legal_synthetic_execution_config`
(`current_authorization_contracts=FAIL`). These remain blockers and were not
weakened or relabeled as PASS. The format-only correction changes no runtime
behavior; tests that require a clean tree were rerun after its exact commit.

No DONE receipt was created. No live network request, payload download, cache
promotion, model/CUDA execution, photo/EXIF access, SQLite/Real20 action, main
merge or release was performed or authorized.

## Remote exact-SHA review — 2026-10-02

The existing Project chat reviewed exact HEAD `54a078fdd0c63d9e989547dd45bd39f0ee027787` and returned `CHANGES_REQUIRED: DURABLE_ONE_SHOT_RECOVERY_BINDING_INCOMPLETE`. It confirmed zero-HTTP and the handle-bound atomic-write direction, while identifying incomplete restart validation: reservation identity/nonce/HEAD/tree were not fully rechecked; a minimal three-field terminal was accepted as `COMPLETED`; reservation-only restart was classified `CLAIMED`; the final lease name was created before reservation publication; terminal lacked a durable binding to lease/reservation objects and content digests; and `persist_terminal()` did not enforce result HEAD/tree against its live claim.

The local repair is limited to the existing executor code/test/schema/task/Owner/handoff scope. It stages the entire initial claim before atomic lease publication; classifies every reservation-only or incomplete staging restart as `INCOMPLETE_CLAIM`; requires a schema-valid terminal result and sibling binding that checks the actual lease, reservation, terminal directory/file identities, nonce digest, HEAD/tree and content digests; and rejects result HEAD/tree mismatch before persistence. No execution authority or data scope is expanded.

The next local handoff will bind the final Codex successor SHA/tree, focused/static/full quality results, and remaining cache/auth blockers. Do not create DONE or run the network/download/model/photo/SQLite path.

## Exact-SHA review of the previous local receipt

Remote review of `54a078fdd0c63d9e989547dd45bd39f0ee027787` returned
`CHANGES_REQUIRED: DURABLE_ONE_SHOT_RECOVERY_BINDING_INCOMPLETE`. Findings: (1) restart classification
accepted structural reservation/terminal fields without comparing actual lease and file identities,
nonce, HEAD/tree, and content digests; (2) a minimal three-field terminal could become `COMPLETED`;
(3) reservation-only restart incorrectly returned `CLAIMED`; (4) the final lease directory was
created before reservation publication; and (5) the persistence boundary did not reject a result
whose HEAD/tree differed from its live claim.

The remote plan requires an initial complete lease to be staged and atomically renamed into place;
reservation-only and any malformed or identity/hash-mismatched recovery state become
`INCOMPLETE_CLAIM`; terminal result and binding publish atomically together; and only a schema-valid
terminal whose identity/nonce/HEAD/tree/content binding agrees with the current lease becomes
`COMPLETED`. The old executor-only exact-SHA admission boundary and zero-HTTP second-call behavior
remain unchanged.

## Local repair progress

Local TDD reproduced the defects on the reviewed implementation before the repair. The current
uncommitted successor implements the bounded state/binding repair and adds reservation, terminal
binding, identity-drift, content-digest, reservation-only restart, result-HEAD mismatch, and staging
crash regressions. Preliminary local checks: fetcher crash tests 41 passed; contract tests 28 passed;
115 Draft 2020-12 schemas validated and task/Owner YAML validated; Ruff check/format, mypy (103
files), sensitive scan, and diff-check pass. Exact successor SHA and full quality results will be
added after the clean candidate is committed and tested. Known canonical-cache and current
authorization failures remain open.
