# Stage E1 — audit and source-bound worker repair delivery

Date: 2026-09-15. Runtime reviewed: `835007b3cf12cd19a23cbd476545a2d10cf49c50`.
Parent: `ab69f2c46971e5fea0cd0bf6ca13367e964f0409`.
Runtime tree: `489a28e9d75bd3344784fe59574538d69f64cdea`.

## Honest status and stage boundary

E0 (remote source audit) is complete. E1 is a **delivery-only** code stage:
new repair modules, an exact-source application recipe, regression tests, and
this handoff. The original runtime, root MANIFEST, state and approvals remain
unchanged. E2 applies/integrates this delivery and runs complete supported-
environment acceptance on the local Windows machine. This commit is NOT a new
inference candidate and must not be submitted to the old runtime quality gate
as though it were one. Run `verify_delivery.py` for E1; qualify the frozen
runtime at 835007b separately. E2 must rebuild the root MANIFEST for ALL files
and register the exact new code-only ancestry before qualifying its new HEAD.

No Review PASS, model run, Ollama start, lease approval/consumption, Real20,
production Bundle, App modification, main update, or permission change occurred.
The user's current request authorizes code work and branch publication only.

## Audit of the four D findings

1. Counter aggregation now retains all keys. Keep zero validation in the
   controlled entry; never drop optional Obsidian counters or synthesize zeros.
2. The parent `_regular_file` validates the complete filename, including ADS,
   before reading. Keep native ADS/reparse regression tests.
3. The worker denies `-m` and checks RESERVED records, which is an improvement,
   but the record does not bind actual worker paths/arguments and is reusable
   while RESERVED. An exact original-function test demonstrates changed output
   parameters and repeated admission without running a model. Changing `-m`
   to `-c` is not itself an authorization boundary.
4. The parent now revalidates the task receipt and the exact old/new Ollama
   transition. This does not replace a new source-bound Owner execution lease.

## Remaining concrete findings and delivered repair

E1-A / worker launch binding: add a parent-issued dispatch record binding every
configuration field, current commit/tree/full-source digest, runtime identity,
reservation bytes, mode and a nonce. Atomically claim fresh/resume once each;
resume requires COMPLETE fresh with the same configuration. Crashes and failed
launches never refund the claim. A bare RESERVED record is not a dispatch.

E1-B / historical versus execution SHA: `_default_execute` passes the current
candidate as `reviewed_commit`; old `_common` forwarded it to S20 `_review_gate`,
which requires the historical review SHA and exact old receipt binding. Thus a
real current-candidate run would fail where fake tests (replacing the default
runner) did not. Prevalidate the actual historical gates before ledger/S3 and
use their validated historical SHA only for those legacy gate parameters.
Current source/lease/evidence retain the actual current candidate. No historical
review or receipt is rewritten and old approvals are not new authorization.

E1-C / identity check timing: original `_fresh` collected identity snapshots but
only the parent compared them after work. Check against the admitted identity
before S3, before S20, before resume, and after resume. Drift before a stage must
prevent that stage's runner. Route runner diagnostics to stderr, reserving
stdout for the one JSON subprocess result.

E1-D / producer-consumer counter contract: both real S3 and S20 producers omit
production_bundle_count, while the adapter requires it. Successful inference
would therefore still fail at counter aggregation. The recipe adds an explicit
zero declaration in both synthetic-only producers (they never invoke a
production Bundle writer), retaining every other counter. This is a scope
declaration, not independent OS telemetry. Do not add a missing-key default in
the aggregator. E2 must exercise the actual producer dictionaries against the
actual aggregator and validate their summary schemas.

## Test evidence and limits

Development environment: Linux, CPython 3.13.5 (NOT the project's supported
acceptance environment). 26 unittest tests passed, including a concurrent
one-winner claim test, real temporary ledger files, and AST-executed functions
from the original worker verified as Git blob
`cc1fc97224f95168c22012234ad12d53f648f0bd`.

Original worker SHA-256:
`1a93951841d2b2723b81abf49c06412bd6c612905441c06ab1175cab714159e2`.
The recipe enforces parent adapter SHA-256:
`0b4fe00f7b57e3e9e934bbc4d769ad7c74b04e8008cace41f4baf4ba0a22af7e`.

The worker transform was applied and Python-3.12 syntax checked against exact
original bytes. Parent transform anchors were inspected remotely; full parent
application and complete project tests must run in E2. Tests isolate ML runners,
fixture loaders and source probes where noted. No 714-test rerun, Windows native
acceptance, Ruff/mypy success or GPU result is claimed in E1.

The dispatch protocol is anti-confusion and anti-replay in an Owner-controlled
local account. It is NOT a sandbox against the same user modifying Python or
creating arbitrary ledger files. Actual Windows handle-bound path race testing
remains necessary; lstat snapshots alone do not make all I/O race-proof.

## Execute locally

1. Fetch current remote, protect the uncommitted primary AGENTS, use a clean
   worktree on the E1 delivery commit. Do not reset or rewrite published commits.
2. `python review_stages/E1/verify_delivery.py`
3. `python -m unittest discover -s review_stages/E1 -p test_stage.py -v`
4. Read NEXT_CODEX.md, run the application recipe check-only, then --apply.
5. Complete E2 integrations, supported Python 3.12 tests and normal branch push.

Use the explicit interpreter from the existing isolated environment. No new
package installation or system repair is required by this delivery. Tests read
the original worker from the immutable Git object by default; the optional
NPI_E1_BASE_SOURCE_DIR is only for a byte-verified offline development snapshot.

## Product route: stop replacing product acceptance with more audit summaries

E2 code integration/qualification -> independent whole-candidate review ->
new source-bound synthetic lease and one S3/S20/resume run -> Owner decision ->
separately authorized Real20 -> factual/photographic quality calibration ->
human Approve/Edit/Reject -> APPROVED-only Bundle -> actual App import/display/
reject/rollback acceptance -> 100-image pilot -> 500-600-image nightly operation.

Do not replace models or add a vector database/OpenClaw to solve these current
worker/receipt issues. The next product milestone is one trustworthy real-photo
knowledge item approved by a human and correctly consumed by the independent App.

## Primary sources used in the audit

Repository source at the exact runtime commit: controlled_runtime.py,
controlled_runtime_worker.py, s20_orchestrator.py, tests/test_controlled_runtime_cli.py.
Python path/status semantics: https://docs.python.org/3.12/library/pathlib.html
GitHub non-force ref update: https://docs.github.com/en/rest/git/refs#update-a-reference
