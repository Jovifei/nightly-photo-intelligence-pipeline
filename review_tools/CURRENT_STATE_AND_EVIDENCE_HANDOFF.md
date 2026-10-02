# CURRENT_STATE_AND_EVIDENCE_HANDOFF

Status date: 2026-10-02  
Primary reviewed branch: \`chatgpt/npi-fetcher-lease-crash-state-20261001\`  
Reviewed HEAD: \`860e29a889b7c80c3281e5ce35e5bb803c0d3191\`  
Tree: \`045d455b674dc6f68cd8df9b48e0889554044f06\`  
Implementation commit: \`53edba38ee3915c68315e5d1d7c692409c9eae2c\`

This document distinguishes repository evidence, current-session statements and unavailable local verification. It does not create execution authority or a DONE receipt.

## 1. What was actually read

### GitHub exact-SHA evidence

Repository identity was verified through GitHub as \`Jovifei/nightly-photo-intelligence-pipeline\`. The underscore spelling supplied in one handoff message does not exist under the connected GitHub account. The current credentials can push to this repository, but this handoff uses only the authorized review branch.

Read at \`860e29a...\`:

- \`MASTER_EXECUTION_CONTRACT.md\`
- \`PROJECT_STATE.json\`
- \`docs/00_reading_order.md\`
- current N2B1P task and Owner approval
- \`review_tools/NEXT_LOCAL_CODEX_PROMPT.md\`
- \`tasks/todo.md\`
- N2B1R/N2B1P artifact/cache evidence and runtime configuration
- B-source network reacquisition task/Owner/runtime controls
- preflight/handoff/promotion implementation
- N2B2 synthetic status and model/runtime strategy
- Real20 acceptance, review/reuse, ledger inheritance design/plan
- N3–N7 task contracts
- root and review-tools manifests.

The divergent plan \`review_tools/NEXT_CACHE_GAP_RECONCILIATION_PLAN_20261002.md\` was read at \`codex/npi-fetcher-lease-crash-20261002@acc43cfe2b0f2dab8877490f06ffcbcfba284457\`.

### Current-session limitations

- Requested Codex connector \`workspace_info\` was invoked and failed internally. Therefore no local workspace name, local branch or local filesystem observation is claimed from this session.
- Both supplied old ChatGPT conversation URLs were attempted but could not be opened by the available web layer. The complete old chats were not read.
- The local-only branch \`codex/npi-branch-hygiene-20261002\` returned GitHub 404. Its \`docs/39...\` and branch-audit report were therefore not read remotely.
- A historical 2026-09-06 handoff ZIP was sampled for project-goal/model/roadmap context only. It is subordinate to current GitHub exact-SHA contracts.

## 2. Latest code-review state

At \`860e29a...\`, the durable one-shot recovery repair is incorporated. The key implementation is \`53edba38...\`.

Recorded local validation for that implementation/handoff:

- focused suite: 136 passed;
- fetcher-focused subset: 41 passed;
- contract subset: 28 passed;
- Ruff check and format: PASS;
- mypy: PASS on 103 files;
- 115 schemas plus current task/Owner records: PASS;
- review eligibility: PASS;
- sensitive scan: 0 findings;
- \`verify_handoff.py\`: 8 PASS / 1 FAIL;
- full quality: 992 passed, 2 failed, 1 skipped, 95 subtests;
- Python 3.12 compileall was reported PASS by local Codex.

The two remaining full-quality failures are:

1. canonical N2B1P cache absent;
2. \`current_authorization_contracts\` preflight fails.

No full-quality PASS is claimed.

The current Project handoff from Jovi states that the newest exact-SHA remote verdict is \`PASS_WITH_OPEN_GATES\`, with the durable one-shot findings closed and no DONE. That verdict is current-session input; the repository file at \`860e29a...\` still says a fresh exact-SHA review was pending when that file was written. Do not rewrite repository history to make the older handoff pretend it already contained the later verdict.

## 3. Durable one-shot repair that is closed

The implementation now binds the one-shot B-source executor to durable identities rather than descriptive retry flags:

- claim identity is tied to a handle-observed lease identity digest plus nonce;
- initial lease/reservation publication is handle-bound staging plus atomic directory rename;
- reservation and terminal evidence are strict-schema validated;
- restart states distinguish \`CLAIMED\`, \`INCOMPLETE_CLAIM\`, \`COMPLETED\`;
- pre-existing incomplete or completed state blocks transport construction and therefore causes zero new HTTP requests;
- terminal binding ties lease/reservation identity, nonce, reviewed HEAD/tree and content digests;
- live claim HEAD/tree mismatches are rejected;
- legacy control-only receipt remains rejected;
- no cross-version shared lock was added because admission is bound to exact current executor scope/head/tree and no DONE was issued for the unreviewed predecessor.

These findings are code/review closure only. They do not authorize a network request.

## 4. Current executable authority

The authoritative current execution boundary is still:

- phase: N2B1P;
- capability: \`N2B1P_LOCAL_RESEARCH_CACHE_PROMOTION\`;
- operation: exact N2B1R quarantine bytes -> exact content-addressed cache;
- network: denied by default;
- model execution: not authorized;
- CUDA: not authorized;
- source-photo content read: not authorized;
- source-photo EXIF read: not authorized;
- SQLite ingest write: not authorized;
- Real20: not authorized;
- main merge/release: not authorized in this handoff.

The current task/approval permits copy-only promotion of exactly three SHA-bound TorchVision artifacts and verification of an existing exact cache hit. It does not permit searching drives for missing bytes, downloading replacements, inventing a new cache root, or broadening into model execution.

## 5. Historical cache evidence versus current physical state

Historical evidence is strong:

- the three approved artifacts were acquired from the registered official source domain;
- their local SHA-256 and sizes were recorded;
- promotion evidence records three \`CACHE_HIT\` entries;
- later remediation baseline/revalidation recorded six cache files, zero reparse points and zero mutations;
- an independent historical reviewer recomputed the three payload hashes/sizes.

The approved artifact identities are:

- Keypoint R-CNN payload: 237,034,793 bytes, SHA-256 \`fc266e953d2b302cdcbb9ae66f71f6b0d4649928bf02dc573961e361e4918926\`.
- LRASPP payload: 13,097,061 bytes, SHA-256 \`d234d4eae9d55d5f76de18b77cf0dc62c66fe5c5482758209d00f950c92bb280\`.
- DeepLabV3 payload: 44,356,159 bytes, SHA-256 \`fc3c493d68e89cc31ef488c803d5d7dd2f3190fb570598faa49fef69be8e5e70\`.

All remain local-research-only evidence; no commercial-rights clearance is implied.

The current handoff from Jovi and the recorded local quality failures say the fixed quarantine/cache are now missing. Because the local connector failed, this session did not independently re-run filesystem checks. Treat the absence as current Owner/local-Codex evidence requiring revalidation, not as something freshly observed by the remote agent.

Historical \`CACHE_HIT\` therefore means “these bytes were present and verified at that historical point,” not “the bytes exist now.”

## 6. Why the two quality failures are coupled

\`tools/verify_handoff.py\` directly calls \`verify_promoted_artifact()\` for all three exact artifact IDs. If the approved cache root or entries are absent, it fails the canonical-cache check.

\`src/nightly_photo_intelligence_pipeline/preflight.py::_check_n2b1p_authorization()\` also calls \`verify_promoted_artifact()\` for all three IDs and requires the status set to equal exactly \`{"CACHE_HIT"}\`. Missing cache state therefore causes \`current_authorization_contracts\` to fail closed.

The immediate root problem is physical/current cache availability, not two unrelated test bugs. Do not weaken either verifier merely to make the suite green.

## 7. Newly surfaced recovery-control issues

### 7.1 Missing cache root is stronger than missing payloads

The approved N2B1P runtime configuration binds the cache root to a \`cache_root_identity\`. In \`windows_bound_promotion.py\`, that identity digest is derived from the live volume serial number plus file ID observed through a bound handle.

\`promote_artifact()\` opens the cache root with \`bind_existing_directory(..., writable=True)\` and then requires the observed identity digest to equal the approved identity.

Therefore, if the canonical cache root directory itself is absent, restoring only the quarantine payloads is not enough. A newly created directory cannot be assumed to have the historical file identity and must not be silently substituted.

There are only two safe classes of resolution:

1. restore/recover the original approved cache-root object so its live identity still matches; or
2. authorize a new versioned cache-root control plane bound to its new observed identity.

The existing Route-B-v2 re-provision task/Owner record is explicitly \`DRAFT_NOT_AUTHORIZED\` and cannot be used without a new Owner decision.

### 7.2 The public promotion CLI has a steady-state/recovery circularity

\`npi model promote\` calls global \`run_preflight()\` before invoking \`promote_artifact()\`.

Global current-stage preflight requires all three cache entries to already be \`CACHE_HIT\`.

The lower-level \`promote_artifact()\` itself is capable of verifying a valid quarantine payload and creating a missing cache entry under an already valid approved cache root, but the public CLI cannot reach that code while the cache is missing because global preflight fails first.

Do not bypass the CLI by directly calling the internal function from an ad-hoc Python snippet. If Owner chooses a recovery route, the next remote code work should create a bounded recovery admission path that separates:

- pre-mutation authorization/integrity conditions; from
- post-mutation steady-state requirement that all three cache entries be \`CACHE_HIT\`.

The ordinary steady-state handoff/preflight checks should remain strict after recovery.

### 7.3 Source recovery and cache-target recovery are separate decisions

The divergent cache-gap plan described two source choices: restore existing N2B1R payloads or separately reacquire exact payloads. Because current handoff evidence says both quarantine and canonical cache are absent, there is also an independent cache-target choice. Do not treat source recovery as automatically solving cache-target authorization.

## 8. B-source reacquisition packet status

The repository already contains a tightly scoped exact-three network reacquisition control packet. It is important not to misread its mixed states.

The Owner approval file says \`OWNER_AUTHORIZED_AWAITING_EXTERNAL_REVIEW\`, but the same packet also says:

- \`execution_authority: NOT_AUTHORIZED\`;
- \`network_access: DENY\`;
- pre-download exact external review required;
- post-review receipt type \`EXTERNAL_EXACT_SHA_REVIEW_RECEIPT_V1\`;
- required verdict \`DONE\`;
- missing-payload evidence required;
- exact HTTPS source/domain/file identities only;
- one-shot claim before request;
- cache promotion remains separately unauthorized;
- model/CUDA/photo/EXIF/SQLite/Real20 remain unauthorized.

The runtime-configuration record is still \`DRAFT_NOT_AUTHORIZED\`.

Jovi’s current handoff also explicitly says the Owner has not yet selected “restore existing payload” versus “separate exact reacquisition.” The recent review verdict is \`PASS_WITH_OPEN_GATES\`, not DONE.

Therefore no network request is currently authorized.

## 9. Divergent planning branch

\`codex/npi-fetcher-lease-crash-20261002@acc43cfe...\` contains the useful \`NEXT_CACHE_GAP_RECONCILIATION_PLAN_20261002.md\`, but it is not a linear successor of the final reviewed \`860e29a...\` lineage.

GitHub comparison showed the histories diverge, with merge base \`b96457115477128254e7f3aab33a2f19efe6784b\`.

Use that document only for planning semantics. Do not base new implementation on \`acc43cfe...\` and do not wholesale merge/cherry-pick its branch over the final durable-recovery lineage. Port needed plan text deliberately onto the \`860e29a...\` review line.

## 10. Synthetic/model evidence that is valid but not executable production state

Historical N2B2 synthetic evidence records successful local capability validation for:

- TorchVision Keypoint R-CNN on CUDA;
- LRASPP and DeepLabV3 person segmentation;
- deterministic fact contracts;
- local qwen3.5:9b reasoning;
- S3 and fixed S20 synthetic cases;
- explicit unload/residency behavior;
- no-op resume;
- zero real-photo/EXIF/G1/SQLite/App/model-download actions.

This remains valuable engineering evidence but does not unlock production N2B2 or Real20.

MMPose, SAM2 and Qwen3-VL remain future research candidates requiring separate artifact/license/runtime/data/phase gates.

## 11. Real20 state

The repository has substantial Real20 code, safety design and Label Studio integration, but actual Real20 remains NOT_RUN in the authoritative handoff.

The Real20 documentation requires candidate-bound controls, a frozen 20-entry manifest, source fingerprint/read-only proof, exact model/runtime identity, one-shot execution controls, append-only ledger protections and human calibration.

A later ledger-inheritance design selected an isolated synthetic ACL probe plus separate cleanup identity. That design itself says the required runtime probe/cleanup setup was not yet provided and does not authorize photos.

Prior local project context also reports the configured Real20 ledger directory was absent. This session could not re-check that local fact. The preferred future Owner action is still to pre-provision the exact ledger/probe/cleanup resources; code bootstrap is a separately reviewed alternative.

## 12. Documentation/status conflicts to preserve, not erase

1. Some older roadmap docs contain historical phase tables that no longer reflect the exact current \`PROJECT_STATE.json\`. Source-of-truth priority is current Master Contract -> Project State -> current task/Owner approval -> current execution receipt, not an old table.
2. \`phase_completion_N2B1P.yaml\` is historical completion/evidence for a prior validated state; current physical cache absence is a new operational blocker. Do not rewrite the completion record to pretend the historical run never happened.
3. Real20 and synthetic code maturity is not execution authority.
4. “Owner-authorized awaiting external review” is not the same as executable network authorization.
5. A \`PASS_WITH_OPEN_GATES\` review is not the required B-source \`DONE\` receipt.
6. Branch-hygiene docs reported as local-only are not GitHub source-of-truth until they are pushed/reviewed.

## 13. Current stop state

The truthful current stop state is:

\`N2B1P_CACHE_GAP_BLOCKED_AWAITING_OWNER_RECOVERY_PATH_AND_CACHE_TARGET_DECISION\`

Open gates:

- exact current canonical cache root/entries absent or not presently verified;
- exact approved historical quarantine absent or not presently verified;
- public promotion recovery path is circular under current steady-state preflight;
- no Owner-selected source recovery route;
- no authorized versioned cache-root replacement if the original object cannot be restored;
- no B-source DONE receipt;
- Python 3.12 quality environment currently reported absent;
- Real20/data/model/App gates remain closed.

No DONE, download, model/CUDA run, photo/EXIF read, SQLite write, main merge or release should be inferred.
