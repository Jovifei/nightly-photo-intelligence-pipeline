# E2 local Codex acceptance and integration — no inference authorization

## 0. Read the actual latest remote, preserve published history

Repository: Jovifei/nightly-photo-intelligence-pipeline.
Branch: codex/n2b2-ollama-runtime-identity-revalidation-20260906.
E1 is a normal direct child of frozen runtime 835007b3cf12cd19a23cbd476545a2d10cf49c50.
Fetch all refs/tags, inspect any later changes, and never reset, amend published
commits, force-push or update main. Primary AGENTS must remain 2638 bytes and
SHA-256 b07a0460c28c74388b4d83500b128aa59fc8af1af9a753e97e1a5f8bdea70048.
Do not stash/restore/stage that file. Work in a new non-elevated clean worktree.

## 1. Verify E1 as a delivery, not as a qualified runtime candidate

Use the existing isolated CPython 3.12.10 interpreter by its full path. Do not
install dependencies, update CUDA/drivers/Ollama, change permissions, or enable
Developer Mode. Run:

```text
python review_stages/E1/verify_delivery.py
python -m unittest discover -s review_stages/E1 -p test_stage.py -v
python review_stages/E1/apply_runtime_fixes.py --project-root <worktree>
```

The last command is check-only. Verify all source SHA anchors before --apply.
If the remote has later source changes, manually review/port the delta; do not
change EXPECTED hashes merely to force the recipe through. E1's original
runtime and root MANIFEST were intentionally frozen. The old pipeline handoff
at this delivery HEAD is not a success criterion; it rejects unregistered
runtime ancestry and extra tracked delivery files. Do not label it PASS.

## 2. Apply and finish the actual runtime integration in this same batch

Run --apply only after reviewing the six-file plan. The recipe writes:

- n2b2_synthetic/controlled_runtime.py
- n2b2_synthetic/controlled_runtime_worker.py
- n2b2_synthetic/worker_dispatch.py
- n2b2_synthetic/legacy_s20_binding.py
- n2b2_synthetic/orchestrator.py
- n2b2_synthetic/s20_orchestrator.py

Review the installed code, format/lint it, and add project-native regression
tests (not just delivery tests). Do not stop at "files copied".

E1-A: parent issues the exact configuration-bound fresh/resume dispatch only
after the real engineering reservation. Worker must claim once before entry.
Changing any path/digest/mode/nonce must fail. Terminal/failed/crashed/replayed
requests must not run the corresponding model stage. Resume requires successful
fresh for the same configuration. Keep the old RESERVED validator in defense.

E1-B: verify _review_gate and _artifact_integrity_gate against actual immutable
historical inputs before ledger/S3. Use the historical reviewed commit only in
legacy S20 gate parameters. Keep current candidate/tree/full-source in the new
lease, dispatch, outer evidence and S3 source field. Do not rewrite historical
receipts, use current INCONCLUSIVE as PASS, or rely on old receipts as a fresh
execution authorization. A new Owner lease is still required to run anything.

E1-C: verify runtime identity against the admitted digest before each stage,
not only when validating results after inference. One preflight observation
must be recorded in guarded_probe for both real and injected probes. Runner
stdout diagnostics must not corrupt its JSON process result.

E1-D: actual S3/S20 counter dictionaries must include the explicit producer
scope declaration production_bundle_count. Both writers are synthetic-only.
Retain all optional counters; do not add aggregator defaults or claim this is
independent OS measurement. Test actual producer -> actual aggregator and
actual summary schema validation, not only hand-crafted fake callback records.

## 3. Test the default path instead of replacing it entirely

The former fake CLI harness replaces _default_execute; that hid the historical
SHA mismatch. Add tests that exercise actual Typer -> adapter -> default
execution factory -> dispatch -> worker protocol -> callback evidence. Mock
only the real model backend/Ollama/fixture I/O when unavoidable, not the very
authorization or protocol checks being tested. Clearly label simulation.

Required cases:

- current execution SHA differs from valid historical review SHA; source and
  historical bindings stay distinct; original historical validators still run;
- bad old receipt/review/manifest rejected before reservation and first S3;
- exact config success; changed output/cache/review/source/digest denied;
- raw RESERVED-only envelope rejected and repeated claim rejected;
- concurrent identical dispatch permits one claimant; crashes do not refund;
- fresh failure or no fresh completion blocks resume;
- identity changes before S3 or before S20 block that stage;
- all runner counters, including both Obsidian keys, remain present and nonzero
  values cause FAILED, never COMPLETE;
- ADS, reparse, protected-root replacement and symlink 1314 classification;
- worker stdout has exactly one JSON object; no fabricated exit/status/count.

Retain C1-C5 and F0-F6 tests. Do not remove historical negative tests to pass.

## 4. Register the new code-only candidate and rebuild the manifest

E1 is a delivery-only commit. E2 becomes the actual new source candidate.
Register this exact code-only successor in the stage-aware Git checks,
preflight and handoff tests. Preserve immutable tags, no-merge history, all
old approvals/evidence and unchanged PROJECT_STATE. Do not remap HEAD to an old
SHA, monkeypatch production Git checks, skip integrity checks, or force-update
refs to fit a hardcoded commit count.

Generate root MANIFEST.sha256 automatically from final Git index bytes,
including delivery files and new integrated code, excluding only itself.
Keep review_tools/MANIFEST unchanged unless its own files actually changed.
Commit normally after source/test changes stabilize. Generate full source
identity OUTSIDE Git after the final commit; strict-parse the entire JSON file
and verify exactly one LF terminator, not the literal characters backslash+n.
Machine-generate reports from computed values; do not hand-copy guessed hashes.

## 5. Qualify the final E2 source on the supported local environment

Use PYTHONPATH=src for a src-layout checkout that is not installed editable;
record it explicitly. Do not treat missing package import as a runner bug or
silently claim the bare command worked. Use the same interpreter everywhere:

```text
python -m pytest -q -ra
python tools/run_quality.py
python tools/verify_handoff.py
python -m nightly_photo_intelligence_pipeline.cli preflight
python -m ruff check src tests tools
python -m ruff format --check src tests tools
python -m mypy src/nightly_photo_intelligence_pipeline
python tools/sensitive_file_scan.py
git diff --check
```

Run E1 delivery unit tests too; they still read frozen 835007b via git show.
Do not re-run verify_delivery.py on integrated E2 and expect its frozen-source
profile to pass: the E2 root MANIFEST and whole-project gate now apply.

Record actual collected/passed/failed/errors/skipped/subtests, each command's
start/end/timezone/exit/stdout+stderr SHA, environment/dependency lock, and
source/state/manifest bindings. Do not hard-lock a historical test count.

Run ordinary-user Windows native ADS/junction/reparse/handle tests in new
external synthetic temporary roots. Only genuine winerror=1314 is a symlink
capability gap. Other OSError values are failures, not skips. Report the exact
coverage of worker native races; this Python dispatch protocol is not an OS
sandbox against a same-user attacker who can modify all files.

## 6. Push and read back — code publication, not permission to run

The user's request permits code work and normal push to the specified branch.
After no actual quality failures and all manifests/protected files agree, push
normally, then fetch/read the remote commit. Do not update main or old archive
refs. A precisely disclosed native capability gap can remain a review gap,
but never FULL_PASS, permission to run, or a fabricated independent review.
If an actual safety assertion fails, fix it before publishing a qualified E2.

Do not start Ollama, load models, read photos/EXIF, use production SQLite,
change App, create production Bundle, approve/consume an Owner lease, or enter
Real20. Tests may use fake/model-free temporary data only. E1/E2 are not leases.

## 7. Deliver one evidence-backed completion record

Return E2 commit/parent/tree, remote/main, changed-file list, E1-A/B/C/D actual
call sites, original D regressions, default-path tests, complete quality matrix,
native gaps, strict JSON/source hashes, AGENTS and old evidence before/after,
actual push result, report path and full SHA-256.

Stop at CODE_IMPLEMENTED_AWAITING_INDEPENDENT_REVIEW_AND_NEW_OWNER_LEASE,
with SUPPORTED_ENV_VALIDATED_WITH_GAPS_NOT_FULL_PASS as applicable.
Do not stop at a generic "need authorization" for already authorized code work.

Next product route: independently reviewed code -> new source-bound synthetic
S3/S20/resume -> Owner decision -> separately authorized Real20 -> human-reviewed
real photography knowledge -> APPROVED-only Bundle -> actual independent App
import/display/rejection/rollback. No model upgrade or OpenClaw detour.
