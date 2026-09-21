# R0: bridge completed H3 to bounded Real20 work

Date: 2026-09-21. This is a RUNNABLE metadata-preparation tool, not a patch payload,
Real20 image reader, model executor, Owner approval, or production phase transition.
No old synthetic or G1 authorization is reused.

## Audit and correct stop point

Remote main is `ffc4130823c1308f089b835c766e341ec2173e82`, tree
`3b01e26388d131181a8553b4122a9abbaff177b2`. It contains the v3 binding of current
candidate review, historical review and quality evidence. Remote tree inspection
found no Real20 entry point. The locally reported historical preparation object
`49ebb1c` was not resolvable through the remote Contents API; it is not claimed to
have been read or ported. Local Codex must inspect it only if the actual object exists.

The Owner reports one failed H3 attempt (missing torch, consumed FAILED lease)
and a later successful, separately authorized attempt. The successful lease is
`6763dcfe658860a1c0ea76689799d5e0bd92d7d51c9898a47f75c8cee45a99e4`.
The reported review artifact SHA is
`820f76ba48c5d55fd66b83f158afe7b12b62aad0315df710a57163ea407ffc33`.
The cloud audit has NOT read those local artifact bytes, rerun GPU inference,
or independently signed their review. Local R0 recomputes selected file hashes
and consistency; that is not a substitute for the original independent review.

H3 succeeded BEFORE the subsequent general authorization messages. Do not write
that a later authorization was consumed by an already-completed earlier run, and
do not rerun H3 merely to consume another authorization.

The Owner has repeatedly requested Real20. A missing executable is an engineering
work item, not a reason to ask the same yes/no authorization question again.
Implement and qualify the narrowly scoped next stage. Materialize exact data,
code and validity-window bindings locally when they exist; never forge missing
bindings, silently enlarge scope, or call a DRAFT an executable permit.

## Historical G1 binding (reference, not current permission)

`approvals/data_gate_approval_G1.yaml` binds exactly:

- 20 manifest entries; SHA-256
  `29eee5fdb8e16c85649752501c4b722d2b4d071950c8a989add040e895a75c47`;
- source root fingerprint
  `a80ad1f4c5c193211c80fa2b765ec7108a865da22a145bb9238183a617ef4d0a`;
- expiry **2026-07-31T23:59:59+08:00**;
- explicit exclusion of Pose/Seg/VLM for that old authorization.

The manifest may still identify the same selected data after that permission
expired. R0 reads the manifest document only. It validates every relative path
as a STRING and never joins it to the source root or opens an asset. It counts
canonical hashes and emits duplicate references (expected historical 19 + 1),
with neutral R20 ordinal IDs and no original filenames or asset-ref strings.

## How to run now

Use two worktrees: the R0 branch for the tool and a clean detached ffc4130 checkout
for H3 source identity. The H3 baseline stays frozen. Use the existing supported
Python 3.12 interpreter. From the R0 checkout:

```text
python real20_transition/verify_delivery.py
python -m unittest discover -s real20_transition -p test_prepare.py -v
python real20_transition/prepare.py --help
```

Supply every flag shown by --help with already-known, explicit local paths:

```text
--candidate-root       clean detached ffc4130 checkout
--source-root          known protected original-photo root (lexical exclusion only)
--manifest             original frozen G1 manifest JSON, not regenerated
--h3-review            exact reported independent review artifact
--h3-lease             exact successful v3 synthetic lease
--h3-reservation       successful lease reservation.json
--h3-terminal          successful lease terminal.json
--h3-evidence          controlled_execution_evidence.json
--h3-runner            runner_execution_evidence.json
--s20-summary          successful S20 validation_summary.json
--out                  NEW .json path in an existing Git-external work directory
```

Do not scan for files or source photos. If a manifest is inside the protected
photo root, do not read it via a guessed alternative; use its already-controlled
external copy and verify the same pinned digest. Missing exact inputs are reported
as stable errors, never bypassed with new pins. Output cannot overlap input control
roots, Git, or the photo root, and existing output files are never overwritten.
The helper does not create parent directories or an Owner anchor. Use another new
output name for determinism comparison, not delete/rewrite of existing evidence.

The output contains:

1. selected H3 ledger/evidence/runner/summary consistency, with evidence limits;
2. H3 commit/tree/all-tracked-files SHA (same byte domain as the runtime helper),
   separate checkout and Git PROJECT_STATE digests;
3. exactly 20 redacted review rows and a duplicate-reference inference plan;
4. installed package metadata in THIS interpreter, without importing torch;
5. one consolidated blockers list and a non-executable Real20 DRAFT scope.

`R0_METADATA_READY_EXECUTION_BLOCKED` means the plan is written, not Real20-ready.
Environment metadata is not proof of CUDA DLL/operator usability. Test the actual
worker interpreter's CUDA/operators before reserving a NEW execution allowance.
Do not repeat the earlier failure of treating a pytest-only environment as an ML
worker environment. No package installation or model download is done by R0.

## Deliberate scope for R1/R2

Requested evaluation: only the frozen 20 entries; infer each of the 19 canonical
assets once and retain the duplicate as a reference. Original bytes/permissions
unchanged; allow only an explicit photographic EXIF whitelist; never GPS, timestamps,
serials, owner/artist names, MakerNote or comments. No SQLite writes, App modification,
production Bundle, source rename/move/delete, new models, or global phase unlock.
Keep `N2B2=LOCKED` as the production lock while a distinct, versioned bounded Real20
permit governs this evaluation. It must not be satisfied by a synthetic lease.

Real20 output is evaluation evidence, not an APPROVED product Bundle. The first
product milestone remains a real-photo item with correct facts, useful advice,
human review, then an APPROVED-only Bundle consumed by the independent App.

## What is not implemented here

R1 must implement/port the actual Real20 read-only executor into the current runtime
package, add a distinct real-data permit and source guard, and test the REAL default
CLI path with synthetic files and fake model backends. The frozen synthetic runner
must not be tricked into accepting a real-data manifest by relabeling it synthetic.
The new execution candidate SHA is therefore NULL, not guessed as ffc4130. R0 does
not silently make its own tool commit the future inference candidate.

## Branch verification, not another synthetic quality claim

This branch adds only real20_transition/. All prior runtime/source/approvals/state
and root MANIFEST bytes are unchanged. verify_delivery checks the exact added set
and the stage manifest, and rejects changes to original paths. It does not claim
that the old fixed-ancestry runtime verifier accepts this new preparation branch.
Keep full H3 runtime validation on detached ffc4130. When R1 adds real runtime
code, update the root manifest and register its normal code-only ancestry once,
then qualify the final runtime candidate. Never rewrite published history to fit
an old hardcoded commit count or drop a safety test to make a report green.

## Test evidence and limits

Development: CPython 3.13.5 / Linux, 25 unittest tests passed, including actual
Git temp repositories, full parser-to-output CLI, immutable-input checks,
determinism, 20/19+1 selection, ADS/traversal/duplicate rejection, H3 contradictory
metadata, hash binding, symlink rejection, and exclusive output. Test anchors are
explicitly FAKE synthetic data; production pins cannot be overridden by CLI flags.
This is not Windows Python 3.12, full-project, native CUDA, or actual H3 verification.
No raw photo/source paths are included in this branch or in the redacted plan.

The tool assumes Owner-controlled, non-shared parents. lstat/O_EXCL checks and
bounded reads are not a race-proof OS sandbox against the same user swapping
parent directories. R1 must retain the project's native bound-handle protections.

Primary code sources: exact ffc4130 schemas/data_gate_manifest_v1.schema.json,
approvals/data_gate_approval_G1.yaml, engineering/{source_identity,lease,controlled_entry}.py.
Python distribution metadata documentation:
https://docs.python.org/3.12/library/importlib.metadata.html
