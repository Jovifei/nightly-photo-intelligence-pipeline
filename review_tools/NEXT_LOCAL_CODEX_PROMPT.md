# Local Codex handoff — B-source crash-auditable one-shot lease

Repository: `Jovifei/nightly-photo-intelligence-pipeline`
Local implementation branch: `codex/npi-fetcher-lease-crash-20261002`
Implementation commit: `45d92b2155aeb179d86d6c26399c6a3c99f9e4c7`
Implementation tree: `dabc661441ffd46d91ce0b88d07a1a0f1161421f`
Base commit: `b96457115477128254e7f3aab33a2f19efe6784b`

## Review request

Review the complete linear candidate against the prior execution plan and this
handoff. Confirm whether the crash-auditable one-shot repair closes each prior
finding, check the code and evidence at the exact pushed SHA, and review the
model-adapter/GPU direction against the project goal. If you find a code defect,
fix it on the same review branch, test it, and commit the repair with an updated
handoff. If the candidate passes, give the next gated implementation plan. Do
not create a DONE receipt unless the exact reviewed SHA and all code-only gates
pass; no receipt authorizes cache promotion, GPU, photo, SQLite, Bundle, App or
Pilot work.

## Prior exact-SHA review findings

The remote review of base `b96457115477128254e7f3aab33a2f19efe6784b` returned
`CHANGES_REQUIRED: ONE_SHOT_LEASE_CRASH_STATE_NOT_AUDITABLE`:

1. Lease-directory creation and reservation writing were separate. A process
   crash could leave a permanent empty lease without an audit record.
2. Terminal result creation and writing were separate. A crash could leave a
   partial terminal file that looked present but was not auditable.
3. The claim closed handles and reopened lease/reservation by path, without
   pinning the lease, reservation object identity and nonce across execution.
4. The old executor's control-only receipt did not bind its exact executor
   HEAD. The external DONE path is absent/CHANGES_REQUIRED, so the old process
   is not admitted. Do not claim a cross-version shared lock; reassess only if
   a valid older exact-HEAD receipt becomes possible.

## Repair in the local implementation

- Build the reservation under a fixed staging directory; write, flush, reread
  and hash it before an exclusive handle-relative rename publishes the lease.
- Bind reviewed HEAD/tree, lease identity, reservation-file identity, nonce,
  content hash and open handles to the live claim.
- Stage terminal result and binding together, flush and reread both, verify
  claim identities, then publish the terminal directory by a non-overwriting
  handle-relative rename.
- On recovery, validate closed schemas, exact directory entries, reservation
  and result hashes, lease/reservation identities, nonce binding and matching
  HEAD/tree. Incomplete or replaced state is classified as incomplete and
  blocks before transport construction.
- Reject terminal results whose HEAD/tree differ from the claim.
- Add crash-stage, identity replacement, completed/corrupt recovery and
  zero-network second-invocation regressions.

## Local evidence on the implementation commit

- Focused fetcher tests: `28 passed`.
- Focused fetcher/network/route-B/review-governance/contracts tests:
  `123 passed`.
- Ruff check: PASS; Ruff format: PASS (`179 files`); mypy: PASS
  (`103 source files`); JSON Schema validation: PASS; sensitive scan: PASS
  (`0 violations`).
- `tools/verify_review_candidate.py`: PASS.
- `tools/verify_handoff.py`: `8 PASS / 1 FAIL`; the only failure is the
  pre-existing absent canonical model cache (`FileNotFoundError`).
- Unified `tools/run_quality.py`: `979 passed, 2 failed, 1 skipped,
  95 subtests passed`; 5 checks PASS and 2 FAIL. The two failures are the
  missing canonical cache and `current_authorization_contracts` preflight.
  Both exact failing tests were rerun on clean base `b964571...` and fail there
  as well. Do not relabel this full quality gate PASS.

No download, network request, dependency installation, cache promotion,
model/CUDA execution, photo/EXIF read, SQLite operation, Real20, Bundle, App,
Pilot, main merge or release was performed.
