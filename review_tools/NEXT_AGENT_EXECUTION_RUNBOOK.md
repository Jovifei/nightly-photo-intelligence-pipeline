# NEXT_AGENT_EXECUTION_RUNBOOK

Purpose: executable continuity instructions for the next remote ChatGPT agent and local Codex.  
Base reviewed code lineage: \`chatgpt/npi-fetcher-lease-crash-state-20261001@860e29a889b7c80c3281e5ce35e5bb803c0d3191\`.  
Latest durable one-shot implementation: \`53edba38ee3915c68315e5d1d7c692409c9eae2c\`.

This runbook is fail-closed. Planning sections do not grant execution authority.

## 0. Role split

### Remote agent

May:

- read/review exact GitHub commits;
- repair code/docs within a bounded authorized work package;
- run cloud-available code/static tests and truthfully mark platform-limited items NOT_RUN;
- commit and ordinary-push the existing review branch when authorized by Jovi’s project instructions;
- produce exact-SHA handoff documents.

Must not:

- claim local Windows/GPU/filesystem execution without tool evidence;
- download model payloads;
- read photos/EXIF;
- write SQLite runtime state;
- create Owner receipts or DONE without the required evidence/decision;
- merge main, release, delete branches, or activate OpenClaw.

### Local Codex

Owns machine-local facts/actions:

- exact Windows path/object checks;
- Python 3.12 environment verification;
- native filesystem/ACL tests;
- model/GPU/CUDA execution when separately authorized;
- photo/EXIF/SQLite actions only after their explicit gates;
- exact external evidence generation.

Local Codex must return exact branch/commit/tree, commands, exit codes and evidence hashes for remote review.

## 1. Branch and checkout discipline

Do not use the dirty primary main checkout for review work.

Remote/current review line is:

\`chatgpt/npi-fetcher-lease-crash-state-20261001\`

The cache-gap planning branch \`codex/npi-fetcher-lease-crash-20261002@acc43cfe...\` diverges from this line and is not the next implementation base.

Local reception sequence:

~~~bash
git fetch origin --tags
git fetch origin chatgpt/npi-fetcher-lease-crash-state-20261001
git worktree add <isolated-review-worktree> origin/chatgpt/npi-fetcher-lease-crash-state-20261001
cd <isolated-review-worktree>
git rev-parse HEAD
git rev-parse HEAD^{tree}
git status --short
~~~

Expected starting code/handoff ancestor before this continuity-doc commit:

- HEAD \`860e29a889b7c80c3281e5ce35e5bb803c0d3191\`
- tree \`045d455b674dc6f68cd8df9b48e0889554044f06\`

After this handoff is committed, fetch the new exact handoff SHA recorded by the remote agent and validate it is a single ordinary child of \`860e29a...\`.

Never reset/clean the Owner’s primary checkout and never force-push.

## 2. Required reading before any local mutation

Read, in this order:

1. \`MASTER_EXECUTION_CONTRACT.md\`
2. \`PROJECT_STATE.json\`
3. \`docs/00_reading_order.md\`
4. \`approvals/owner_n2b1p_cache_promotion.yaml\`
5. \`tasks/phase_n2b1p_local_research_cache_promotion.yaml\`
6. \`review_tools/NEXT_LOCAL_CODEX_PROMPT.md\`
7. \`review_tools/PROJECT_GOAL_AND_ROADMAP_HANDOFF.md\`
8. \`review_tools/CURRENT_STATE_AND_EVIDENCE_HANDOFF.md\`
9. this runbook
10. \`docs/31_agent_execution_playbook.md\`
11. \`tasks/todo.md\`
12. relevant N2B1R/N2B1P research evidence and runtime configuration.

If planning Real20 later, additionally read \`docs/41\`–\`45\`; that reading does not authorize Real20.

## 3. Initial read-only verification

Use only already available tooling. Do not install dependencies and do not let \`uv\`, pip or another tool implicitly solve missing Python packages.

First record:

~~~bash
git status --short
git rev-parse HEAD
git rev-parse HEAD^{tree}
git log -1 --oneline
python --version
~~~

If a pre-existing supported Python 3.12 interpreter is available, prefer its absolute path and record it. If not, record \`PY312_QUALITY_ENV_NOT_AVAILABLE\`; do not install.

Where dependencies are already present:

~~~bash
python tools/print_authorization.py
python tools/verify_handoff.py
python tools/verify_review_candidate.py
python tools/sensitive_file_scan.py
~~~

Expected current behavior before cache reconciliation: handoff/preflight may fail on canonical cache/current authorization. Preserve that as a truthful RED baseline.

Read-only check the configured canonical cache root without recursive drive search. On PowerShell:

~~~powershell
$cfg = Get-Content -Raw approvals/n2b1p_runtime_configuration.json | ConvertFrom-Json
Test-Path -LiteralPath $cfg.cache_root
~~~

For the historical quarantine, use only the fixed implementation/configured location or an Owner-provided known location. Do not search the drive for model filenames.

For B-source controls, the only currently allowed command is the control-plane/read-only check:

~~~bash
npi n2b1p network-check --project-root .
~~~

Do not run \`network-acquire\` without the required selected route, exact DONE receipt and missing-payload evidence.

## 4. Mandatory Owner Decision A — cache target

Current handoff evidence says the canonical cache root is absent. Because it is identity-bound, the next local action cannot simply create a directory with the same pathname.

Owner must choose one of these routes.

### A1 — Recover the original approved cache-root object

Use only a known recovery location or Owner-managed restore. No broad search.

Pass conditions:

- configured path exists;
- non-reparse and path-bound controls pass;
- live handle identity digest equals the exact approved \`cache_root_identity\`;
- if payload entries are already present, all three return \`CACHE_HIT\`;
- no file is overwritten merely to match history.

If the original object identity cannot be recovered, stop A1. Do not falsify the identity.

### A2 — Authorize a new versioned cache root

This is a new control-plane decision.

The existing \`tasks/phase_n2b1p_cache_reprovision_v2.yaml\`, \`approvals/owner_n2b1p_cache_reprovision_v2.yaml\` and its runtime configuration are currently \`DRAFT_NOT_AUTHORIZED\`.

Remote agent tasks after explicit Owner selection:

1. review the draft versus current \`860e29a...\` lineage;
2. bind the actual new cache-root handle identity and non-overlap attestation;
3. define exact allowed source bytes and copy-only semantics;
4. preserve the historical runtime configuration rather than rewriting it;
5. create a narrowly scoped Owner authority record;
6. add tests for identity drift, reparse/overlap, missing payload, hash mismatch, atomic publish and no-network/no-model boundaries;
7. exact-SHA review the resulting code/control packet before local mutation.

A2 must not be silently inferred from the old draft.

## 5. Mandatory Owner Decision B — source payload

This decision is independent of the cache-target choice.

### B1 — Restore the exact approved historical N2B1R quarantine

Preferred when the exact prior payload hierarchy still exists in a known Owner-managed backup/location.

If Owner performs the restore outside the agent, local Codex may verify it after the fact under the current N2B1P read/copy boundary.

If the agent itself is asked to copy from a backup into the approved quarantine, materialize a separate scoped Owner record first; the current N2B1P approval authorizes quarantine -> cache, not arbitrary backup -> quarantine restoration.

Required exact source content:

- the three approved payload files;
- their exact approved transfer-manifest bytes;
- the original approved run-directory identity/name from known evidence or Owner input.

Do not invent a run ID and do not reconstruct transfer manifests from current expectations.

Verification for each artifact:

- filename exact;
- byte count exact;
- SHA-256 exact;
- transfer manifest raw SHA-256 exact;
- request/final domain facts equal the historical approved evidence;
- non-reparse and bound-handle source rules pass.

### B2 — Select exact-three B-source reacquisition

This is not authorized merely because a control packet exists.

Before execution all must be true:

1. Owner explicitly selects B2 for the current cache-gap recovery.
2. Exact payload absence evidence is generated only within the allowed download-root scope.
3. A valid \`EXTERNAL_EXACT_SHA_REVIEW_RECEIPT_V1\` binds the exact current executor code HEAD/tree and has required verdict \`DONE\`.
4. The packet’s runtime/quarantine identity is still valid.
5. One-shot lease state is fresh and valid.
6. Network request/final host/path/file/size/hash constraints match the exact three registered artifacts.
7. No cache-promotion authority is inferred from the acquisition.

Admission command:

~~~bash
npi n2b1p network-admission \
  --project-root . \
  --review-receipt <exact-approved-receipt>
~~~

Only after it passes and the Owner-selected route is materialized:

~~~bash
npi n2b1p network-acquire \
  --project-root . \
  --review-receipt <exact-approved-receipt> \
  --missing-payload-evidence <exact-git-external-evidence>
~~~

One-shot means one actual claimed attempt. A crash/incomplete/completed existing state blocks a second HTTP attempt. Do not delete or reset lease evidence to retry.

Current \`PASS_WITH_OPEN_GATES\` is not the required DONE receipt.

## 6. Code-only recovery work package — public promotion reachability

If Owner selects a route that requires copying restored quarantine bytes into a cache target, review the public command path before mutation.

Current code has this structure:

~~~text
npi model promote
  -> run_preflight()
     -> current N2B1P authorization check
        -> requires all three CACHE_HIT
  -> promote_artifact()
     -> can create a missing entry if root/quarantine are valid
~~~

That is a steady-state/recovery circularity.

Do not work around it by importing \`promote_artifact()\` in an ad-hoc Python command.

Remote bounded fix should separate action admission from final steady-state verification. A safe design is:

- retain ordinary \`npi preflight\` and \`verify_handoff\` as strict postcondition/steady-state checks;
- add or refactor a promotion-action admission that validates state/task/Owner/runtime/artifact/quarantine/cache-root identity without requiring the target entry to pre-exist;
- call the same handle-bound \`promote_artifact()\`;
- after each promotion, verify the new cache entry;
- after all three, run ordinary preflight/handoff and require all \`CACHE_HIT\`.

Required tests:

1. valid control + valid root + valid quarantine + missing entry -> public action returns \`PROMOTED\`;
2. existing exact entry -> \`CACHE_HIT\` with no mutation;
3. wrong cache-root identity -> zero publish;
4. reparse/overlap -> zero publish;
5. wrong source size/hash -> zero publish;
6. wrong raw transfer-manifest hash -> zero publish;
7. unauthorized artifact/run -> zero publish;
8. no network/model/CUDA/photo/EXIF/SQLite side effects;
9. after exact three promotions, ordinary current-stage preflight and handoff become green;
10. old negative tests and handle-bound atomic publication remain green.

This code-only work needs an exact remote review before local mutation.

## 7. Local cache reconciliation execution

Only after:

- Owner cache-target decision is materialized;
- Owner payload-source decision is materialized;
- any required public recovery-admission code has exact review approval;
- the exact source and target identities are known and valid.

Then execute only the approved copy action. For the historical N2B1P command shape:

~~~bash
npi model promote --artifact <exact-artifact-id> --quarantine-run-id <exact-approved-run-id>
~~~

Run once per exact artifact under the reviewed recovery path. The command must either report \`PROMOTED\` or \`CACHE_HIT\`. Any hash/identity/reparse/manifest error stops the work package.

After all three:

~~~bash
python tools/verify_handoff.py
python tools/verify_review_candidate.py
npi preflight
~~~

Pass conditions:

- all three exact cache entries are \`CACHE_HIT\`;
- canonical cache verification PASS;
- \`current_authorization_contracts\` PASS;
- no unexpected tracked/runtime mutation;
- no network except a separately authorized B2 attempt;
- no model/CUDA/photo/EXIF/SQLite activity.

## 8. Python 3.12 quality gate

Current handoff says the prior qualified Python 3.12 quality environment is missing. Do not use \`uv\` or another package manager implicitly.

If a pre-existing qualified Python 3.12 environment is restored/available, record its absolute interpreter identity and run:

~~~bash
<py312> -m compileall -q src tests tools
<py312> -m pytest -q
<py312> -m ruff check .
<py312> -m ruff format --check .
<py312> -m mypy src/nightly_photo_intelligence_pipeline
<py312> tools/run_quality.py
<py312> tools/verify_handoff.py
<py312> tools/verify_review_candidate.py
<py312> tools/sensitive_file_scan.py
git diff --check
~~~

Record actual counts; do not paste historical 992/2 into a new candidate as if freshly run.

If dependencies/interpreter are unavailable, report NOT_AVAILABLE and stop before claiming full quality PASS. Restoring/installing that environment is a separate Owner-controlled tooling action.

## 9. Exact-SHA remote review checkpoint after cache closure

Local Codex pushes only the active review branch, ordinary fast-forward, after allowed changes are committed and evidence is recorded.

Return:

- branch;
- exact HEAD;
- tree;
- parent;
- changed paths;
- test commands/counts/exit codes;
- cache identity/hash results;
- authorization/preflight/handoff results;
- actions NOT_RUN;
- remaining Owner gates.

Remote agent independently reviews that exact SHA. No main merge/release follows automatically.

## 10. Future Work Package — Real20 transition

This section is planning-only until a new Owner gate.

Entry requires:

- cache closure;
- supported full quality;
- exact remote review;
- explicit Owner transition away from N2B1P;
- fresh Real20 data/phase authorization;
- exact frozen 20-entry manifest and source fingerprint;
- candidate-bound code review/quality/runtime/model controls;
- valid one-shot ledger/lease path.

Preferred infrastructure action: Owner pre-provisions the fixed Real20 execution ledger and the ledger-probe/cleanup resources described by \`docs/44...\`. If Owner wants the program to create/bootstrap them, use a separately reviewed bootstrap task.

No Real20 execution if ledger/probe identity or ACL proof is missing/unknown.

Real20 success stops at human/external review. It does not auto-enter N3.

## 11. Future Work Package — human calibration and model upgrades

After actual Real20:

1. Export model predictions to the existing Label Studio exchange.
2. Human review records person count, pose usefulness, segmentation usefulness, composition/fact correctness, unsupported claims, advice value and edit time.
3. Preserve predictions separately from annotations; no automatic APPROVED.
4. Decide model upgrades by observed failures:
   - MMPose/RTMW if body/hand/face/foot pose coverage is materially insufficient;
   - SAM2 if contour/mask quality is materially insufficient;
   - Qwen3-VL if fact-bound visible reasoning quality materially improves over the accepted baseline and it independently passes license/artifact/VRAM/schema/non-fabrication gates.
5. One heavy model at a time and explicit unload/repeatability evidence remain mandatory.

## 12. Future Work Package — N3/N4/N5

Planning sequence:

- N3: deterministic + approved VLM observed facts -> reconciliation -> photographic interpretation.
- N4: fact-bound stories and director prompts with uncertainty/Plan B.
- N5: human review history -> Owner APPROVED -> Bundle v1.

Each requires its own Owner phase record. Completion of one does not authorize the next.

N5 exit requires an APPROVED-only Bundle with schema/checksum/release integrity and rollback metadata.

## 13. Future Work Package — G2/N6 and N7

Only after N5 and a separate G2 approval:

- run exact 100-photo Pilot;
- validate resume/recovery/resource/human-quality distribution;
- benchmark search/embedding only if the reviewed corpus demonstrates a need.

Then, under a separately authorized App repository scope:

- validate Bundle;
- import into staging;
- atomically switch active release;
- reject malformed/incomplete input;
- rollback to previous release;
- confirm App does not depend on Pipeline SQLite/runtime/source paths.

That evidence establishes \`PILOT_APP_INTEGRATION_PASS\`.

N8/full library/OpenClaw remain locked.

## 14. Failure states and stop rules

Stop immediately and preserve evidence on any of:

- branch/HEAD/tree mismatch;
- dirty or Owner-modified primary checkout at risk;
- missing/ambiguous Owner route;
- attempt to search drives for missing payloads;
- missing cache root or wrong cache-root identity;
- missing/unknown quarantine run identity;
- hash/size/manifest mismatch;
- reparse or path overlap;
- missing B-source DONE receipt;
- pre-existing one-shot claim;
- network redirect/domain/path mismatch;
- Python quality environment unavailable when full PASS is required;
- any model/CUDA/photo/EXIF/SQLite action before its gate;
- Real20 ledger/probe/ACL unknown or missing;
- test/schema/handoff/preflight/sensitive-scan failure;
- attempted main merge/release/branch deletion without explicit gate.

Never convert a failure into DONE by editing evidence, weakening a verifier, deleting a one-shot lease, changing an identity, regenerating a historical manifest, or silently substituting a new path.

## 15. Handoff format after every work package

Every local-to-remote return must include:

~~~text
STATE:
TASK_ID:
BRANCH:
HEAD:
TREE:
PARENT:
CHANGED_PATHS:
AUTHORITY_USED:
COMMANDS_AND_EXIT_CODES:
TEST_COUNTS:
NATIVE_WINDOWS_EVIDENCE:
CACHE_SOURCE_TARGET_IDENTITIES:
NETWORK_REQUEST_COUNT:
MODEL_CUDA_COUNT:
PHOTO_EXIF_COUNT:
SQLITE_WRITE_COUNT:
FINDINGS:
COMPLETED_SCOPE:
NOT_RUN:
REMAINING_GATES:
STOP_STATE:
~~~

Use truthful zero/NOT_RUN/NOT_AVAILABLE values. Never invent a DONE receipt or an execution success that is only a plan.
