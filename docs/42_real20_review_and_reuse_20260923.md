# Real20 review, repairs and reuse — 2026-09-23

## Scope and baseline

Repo: Jovifei/nightly-photo-intelligence-pipeline.
Branch: gpt/real20-transition-20260921.
Reviewed runtime: 0eb61780418474ca2acbe8f84961d55820dae484.
Parent: 6263ebd2c7c4854ca13026a678397f83ef8adcef.
Tree: 4174df5a328c20e92a27163f743a1aa102bed3a0.
Main observed: ffc4130823c1308f089b835c766e341ec2173e82.

Verdict on 0eb: CHANGES_REQUIRED. Its stated snapshot/limited-test scope is
truthful; an earlier 759-test result is NOT a full-quality result for this SHA.
Cloud review does not have the Owner's local H3/Real20 logs, original manifest,
source configuration or actual photographs. H3 success remains locally reported.
Real20 is NOT_RUN. No code update here is an execution lease or phase unlock.

## Progress versus drift

Real progress: there is now a real Real20 CLI, 19+1 planning, fixed Owner-control
admission, v1.2 facts, nested EXIF allowlist, model-by-model unload, Qwen reasoning
and handle-bound output/ledger work. That is materially more than the archived R0
metadata package. Never overwrite current R1 with R0 or rerun completed H3.

Process drift: candidate snapshots were repeatedly mistaken for completed default
execution chains. Repeatedly registering exact commit counts and writing new
handoffs consumed effort without demonstrating a complete Real20. The next unit
of acceptance must be the actual CLI -> admission -> probe -> bound reservation
-> model pipeline -> evidence/terminal, not isolated helpers or historical counts.

## Findings and actual changes in this commit

A1 (blocking): public run_real20 built factories and entered _run_real20 before
full fixed-location admit; runtime probe/readonly checks occurred before that
admission. The new public entry takes the full metadata admission snapshot FIRST,
then passes an immutable baseline to every later revalidation. A denial test
proves no factory/internal runner is reached.

A2 (blocking): admit converted a BoundDirectory to a path in one check, but still
put the handle object into path_plan JSON and checked_path. It also compared a
native final_path spelling to a configured Path. The new signature keeps the
configured ledger Path for policy/digest and receives bound_ledger separately;
it verifies object identity against a handle opened on that exact configured
path. It never serializes a handle as a policy path. Regression exercises actual
admit control flow with explicitly fake control/native dependencies.

A3 (blocking): cleanup revalidation caught only Real20Error. An OSError, TypeError,
interrupt or evidence-write failure could skip FAILED recording; a partial
reservation write could leak the created handle. The new lifecycle uses standard
ExitStack and exception groups. All independent integrity/unload checks are
attempted; evidence failure does not prevent a terminal attempt; partial claims
are never deleted/refunded. Original and cleanup/terminal errors remain visible.
An explicit unload precedes COMPLETE publication. The native bound transaction
writer is retained. Disk/process loss cannot be promised to persist a terminal.

Three regressions fail against byte-verified original runner/admission; fixed
lifecycle and Label Studio exchange tests run against the new source.

## Important remaining native finding — NOT CLOSED by this commit

admission.protect_consumption requires DENIED on 0x40 (DELETE_CHILD), 0x10000
(DELETE), 0x40000 (WRITE_DAC) and 0x80000 (WRITE_OWNER). Meanwhile the existing
windows_bound_promotion._directory_access(writable=True) asks for DELETE_CHILD
and DELETE, including when opening the ledger and creating child directories.
This is a static access-mask conflict requiring an actual Windows rights matrix
and minimal-rights design review. It is not just the symlink 1314 capability gap.
No ACL or low-level native access mask was changed blindly in the cloud.

Before Real20, local Codex must reproduce in an external synthetic directory with
existing permission policy. If denied rights prevent required opens/creation,
add a narrowly scoped append-only ledger profile and separate publication rights
without weakening protect_consumption or enabling path-based fallback. Preserve
all N2B1P bound-handle tests. If genuinely impossible without a changed Owner
filesystem decision, report that precise decision once, not a generic authorize loop.

## Open-source reuse delivered, not a new home-made annotation UI

Label Studio: ready native XML UI config + offline export/import module + tool.
No upstream server code is copied; this is integration with its documented API.
Model predictions and human annotations remain distinct. Canceled/missing or
conflicting annotations are not silently approved. All task, candidate, row,
image and fact identities are checked on import; ACCEPT is not Owner release.
Preview pixels and actual server roundtrip remain local acceptance items.

jsonschema/referencing: existing pinned engines used for a closed review binding
schema; remote reference retrieval denied. CPython ExitStack/exception groups:
reuse battle-tested lifetime/error mechanisms rather than another state machine.
Atomicwrites was evaluated, NOT substituted for stricter native NT publication.
See integrations/label_studio/OPEN_SOURCE_REUSE.json and README for sources,
license/mode and installation limits. No model or heavy service was installed.

## Test evidence and its limits

Development environment: Python 3.13.5 / Linux (NOT project-supported acceptance).
42 targeted tests passed. Three selected regressions fail on the original exact
base, as expected. The development harness replaces unavailable surrounding
project/native/model dependencies; it is NOT included as production/test conftest.
The two new repo tests are intended to run against the FULL actual package locally.
Actual CLI export/import is exercised with synthetic JSON and no image access.

Not performed: whole-repo pytest, Windows Python3.12, native ledger rights/race
matrix, Ruff/mypy, Label Studio server/UI roundtrip, H3 reexecution, Real20, App.
Do not turn the 42 tests into a full project PASS or claim the three native
contracts are closed from fake tests alone.

## Candidate publication and exact stop

Changes are in real src files, not payloads. No apply-old-patch step is needed.
Root MANIFEST is regenerated from verified base inventory plus computed new-file
bytes. Current historical fixed-ancestry checks have NOT been extended for this
review snapshot; local final qualification must register the actual normal
successor once and re-run the full gate. No old SHA is rewritten to fit a count.
Thus this snapshot is NOT a qualified Real20 execution candidate.

Preserve PROJECT_STATE, AGENTS, historical approvals/reports/evidence and main.
Do not issue/consume credentials for this snapshot. Finish remaining native and
whole-project acceptance first, then bind the final candidate under the Owner's
already-requested narrow Real20 scope. Missing exact manifest/source configuration
paths are genuine inputs; check known control records first, ask for the two
specific paths once only if still absent, never scan the library to find them.

## Next product milestone

Actual Real20 (19 unique images + 1 reference) -> human checks in Label Studio ->
recorded revisions -> Owner-approved items -> qualified Bundle v1 -> independent
App import/display/rejection/rollback -> 100-image pilot -> full nightly library.
No new model/vector database/OpenClaw detour. There is no defensible percentage
completion without this end-to-end outcome.
