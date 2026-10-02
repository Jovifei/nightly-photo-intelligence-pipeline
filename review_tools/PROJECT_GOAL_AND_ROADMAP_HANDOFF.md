# PROJECT_GOAL_AND_ROADMAP_HANDOFF

Status: durable continuity handoff, planning/evidence only  
Prepared from GitHub exact reviewed lineage: \`chatgpt/npi-fetcher-lease-crash-state-20261001\` @ \`860e29a889b7c80c3281e5ce35e5bb803c0d3191\`, tree \`045d455b674dc6f68cd8df9b48e0889554044f06\`  
Implementation of the latest durable one-shot recovery repair: \`53edba38ee3915c68315e5d1d7c692409c9eae2c\`  
This document does not authorize execution, download, model/CUDA use, photo/EXIF reads, SQLite writes, main merge, release, branch deletion, or OpenClaw.

## 1. Evidence scope and reading limits

This handoff was reconstructed from the exact GitHub repository plus the Project conversation context and the historical 2026-09-06 handoff ZIP. The current session attempted the requested local connector \`workspace_info\`, but that connector failed internally, so no local workspace name, local branch, or current filesystem state is claimed from that connector. The two supplied ChatGPT conversation URLs were also attempted but could not be opened by the available web layer. Therefore any old-chat detail not present in Project context is not claimed as read.

Primary current sources, all read at exact \`860e29a...\` unless another SHA is stated:

- \`MASTER_EXECUTION_CONTRACT.md\`
- \`PROJECT_STATE.json\`
- \`docs/00_reading_order.md\`
- \`approvals/owner_n2b1p_cache_promotion.yaml\`
- \`tasks/phase_n2b1p_local_research_cache_promotion.yaml\`
- \`review_tools/NEXT_LOCAL_CODEX_PROMPT.md\`
- \`docs/02_timeline_and_gates.md\`, \`03_architecture_and_pipeline.md\`
- \`docs/16_gpu_resource_and_runtime_strategy.md\`, \`17_pose_segmentation_vlm_strategy.md\`
- \`docs/19_human_review_workflow.md\`, \`22_app_integration_boundary.md\`, \`24_definition_of_done.md\`
- \`docs/38_n2b2_synthetic_validation_status.md\`
- \`docs/41_real20_acceptance.md\` through \`docs/45_real20_ledger_inheritance_code_plan.md\`
- \`tasks/phase_n3_facts_and_interpretation.yaml\` through \`tasks/phase_n7_app_bundle_integration.yaml\`
- current cache/artifact evidence under \`research/\`
- the divergent planning document \`review_tools/NEXT_CACHE_GAP_RECONCILIATION_PLAN_20261002.md\` from \`codex/npi-fetcher-lease-crash-20261002@acc43cfe2b0f2dab8877490f06ffcbcfba284457\`, used only for plan semantics because that branch diverges from the final reviewed lineage.

The local-only branch-hygiene branch named by Jovi was not present on GitHub when checked, so \`docs/39_git_branch_lifecycle_and_remote_handoff.md\` and \`reports/git_branch_audit_20261002.md\` are not treated as remotely available evidence.

## 2. Final product target

The bounded product target for the current delivery line is:

\`PILOT_APP_INTEGRATION_PASS\`

It means a local-first pipeline can turn approved local photographs into auditable, human-reviewed photo intelligence and deliver an approved-only Bundle v1 that an independent App can atomically import, validate, switch, reject on error, and roll back. It does not include N8, full-library processing, unrestricted scheduling, or OpenClaw.

The product boundary is permanently repository-decoupled:

~~~text
READ-ONLY PHOTO SOURCE
  -> ingest / fingerprint / duplicate reference
  -> approved local pose + segmentation
  -> deterministic visual and photographic facts
  -> bounded local VLM visible-fact reasoning
  -> fact reconciliation
  -> photographic interpretation
  -> safe / narrative / dynamic story candidates
  -> standard / dramatic / Plan-B / technical director prompts
  -> human review
  -> APPROVED-only Photo Intelligence Bundle v1
  -> independent App verify / atomic import / rollback
~~~

The App consumes Bundle v1 only. It must not share the Pipeline SQLite database, read Pipeline runtime internals, depend on source absolute paths, access model caches, or ingest unreviewed drafts.

## 3. Non-negotiable architecture

1. Originals remain read-only and immutable.
2. Phase gate and data gate are independent.
3. Every runtime/artifact/data/model transition is fail-closed.
4. Geometry and other deterministic facts outrank VLM narration. A VLM never fabricates pose coordinates.
5. One heavy model is resident at a time; unload/process-exit behavior is part of qualification.
6. All model adoption is benchmark-first and artifact/license-bound.
7. Automatic output never self-approves; Owner/human review is required before export.
8. Release export is APPROVED-only and independently checks item, review record, and release integrity.
9. App integration is a Bundle contract, not a shared-database integration.
10. N8/full-library/OpenClaw remain separately gated even after \`PILOT_APP_INTEGRATION_PASS\`.

## 4. Roadmap from the current gate to PILOT_APP_INTEGRATION_PASS

### R0 — Close the N2B1P physical cache gap

Current active execution authority remains N2B1P copy-only cache promotion. Historical cache-hit evidence is valid historical evidence, but it is not current physical existence proof.

Exit conditions:

- the approved cache target exists under an Owner-authorized identity;
- exactly the three approved TorchVision payloads and adjacent manifests validate by exact byte count and SHA-256;
- current handoff verification no longer fails on canonical cache absence;
- \`current_authorization_contracts\` passes without weakening its phase/data boundaries;
- no network, model, CUDA, photo/EXIF, SQLite or Real20 action is smuggled into this closure;
- supported Python 3.12 quality evidence is either fresh PASS or truthfully recorded NOT_AVAILABLE until the separately authorized environment is restored.

This gate is the immediate work. Do not jump directly to Real20.

### R1 — Owner transition from N2B1P to a new Real20 execution scope

After R0 and an exact remote review, Owner must separately authorize the next execution scope. The existing Real20 implementation/design evidence does not itself unlock real photographs.

Real20 admission must bind the exact candidate commit/tree/full-source identity, data receipt, code review, quality evidence, frozen manifest, source fingerprint, runtime/model identities, output/ledger locations, one-shot lease, and explicit real-photo/EXIF scope.

The preferred infrastructure route remains Owner pre-provisioning of the required fixed Real20 ledger/probe/cleanup resources. A code-driven bootstrap is a separate reviewed task, not an implicit fallback.

### R2 — Real20: first real end-to-end value evidence

Scope: the frozen 20-entry set with 19 unique inferable assets and one duplicate/reference record.

Measure at minimum:

- person count correctness;
- pose usability;
- segmentation usability;
- composition/light/tone fact correctness;
- unsupported-claim rate;
- local VLM factual consistency;
- photography advice usefulness;
- edit/review time;
- GPU peak, latency, OOM/retry behavior;
- source integrity before/after;
- recovery/terminal semantics.

Real20 completion is not automatic N3 authorization. It stops for external review and Owner decision.

### R3 — Human value review and model absorption decision

Use the existing Label Studio exchange instead of creating another review UI. Preserve model predictions separately from human annotations. ACCEPT is not the same as Owner APPROVED.

The initial baseline should be reused before adding more models:

- Pose baseline: TorchVision Keypoint R-CNN, 17 COCO keypoints.
- Segmentation baseline: LRASPP; DeepLabV3 as comparator.
- Local reasoning evidence: existing qwen3.5:9b synthetic path.

Only measured Real20 shortcomings justify adding/replacing components.

Progressive candidates:

- MMPose / RTMPose or RTMW for higher-quality or whole-body pose when 17-point pose is materially insufficient.
- SAM2 for refinement where baseline person masks are materially insufficient, normally prompted by a detector/bbox rather than used as an unbounded automatic replacement.
- Qwen3-VL as a bounded research candidate for visible-fact/reasoning evaluation when it can be exact-artifact, license, VRAM, schema and non-fabrication qualified.

Each candidate is a separate artifact/license/runtime/data/phase decision. Do not install all candidates at once and do not use a model upgrade as a substitute for Real20 evidence.

### R4 — N3 approved facts and photographic interpretation

After Owner N3 authorization:

- deterministic composition/light/tone/value facts;
- bounded VLM visible facts;
- explicit evidence references;
- conflict reconciliation;
- uncertainty;
- photographic interpretation.

Hard rules: stories are not facts, VLM pose coordinates remain forbidden, and the 100-photo gate stays closed.

### R5 — N4 director layer

After Owner N4 authorization, generate fact-bound:

- safe / narrative / dynamic stories;
- standard / dramatic / Plan-B / technical prompts.

Every generated claim must preserve provenance and uncertainty. No psychology/intention invention and no auto-approval.

### R6 — N5 human review and first real Bundle v1

After Owner N5 authorization:

- render review cards / Label Studio exchange;
- retain before/after or JSON Patch history;
- human ACCEPT/EDIT/REJECT;
- Owner APPROVED state remains explicit;
- export only APPROVED items;
- validate Bundle v1 checksums/schema/release metadata;
- prove rollback to a previous release.

This is the first product-level knowledge artifact.

### R7 — G2 / N6 100-photo Pilot

Only after Real20/N5 quality evidence and explicit G2 authorization:

- execute an exact 100-item manifest;
- validate resume/recovery, failure distribution, review burden, schema pass rate, runtime stability and GPU/resource behavior;
- determine whether search/embedding adds real value.

Embedding/vector work remains deferred until an actual reviewed corpus exists. At this scale, exact cosine over normalized vectors may be sufficient before introducing Faiss or another index.

### R8 — N7 independent App integration

With an accepted Bundle contract and separately authorized App repository:

- verify schema major and checksums;
- import into staging;
- fail closed on malformed/incomplete bundle;
- atomically switch active release;
- rollback to previous known-good release;
- display/search without Pipeline SQLite/runtime access.

\`PILOT_APP_INTEGRATION_PASS\` requires the 100-photo Pilot evidence plus this independent import/rollback proof.

### R9 — Outside this delivery line

N8 scheduling, full 500–600 library, Windows night operation and restricted OpenClaw are separate future gates. None is implied by R8 success.

## 5. Technology-route conflicts and the resolved policy

### Existing qwen3.5:9b versus future Qwen3-VL

The September handoff argued against downloading Qwen3-VL because a local multimodal qwen3.5:9b path had already been qualified synthetically. Later cache-gap planning lists Qwen3-VL as a future bounded candidate. These are not mutually exclusive if the policy is evidence-first:

- keep qwen3.5:9b as historical baseline evidence;
- do not replace it before Real20 reveals a measurable gap;
- if a gap exists, qualify Qwen3-VL as a separate candidate rather than silently changing the production model.

### TorchVision baseline versus MMPose/SAM2

TorchVision has the strongest current local synthetic evidence and should remain the baseline for the first real benchmark. MMPose and SAM2 are quality-upgrade candidates, not prerequisites for starting Real20. This preserves the shortest value path while keeping the planned upgrade route.

### Synthetic validation versus production authorization

N2B2 synthetic results are capability evidence only. They never unlock production N2B2, Real20, G1 reads, SQLite, Bundle production or App writes by themselves.

### Mature Real20 code versus current active execution

The repository contains substantial Real20 code and safety design. That maturity does not override \`PROJECT_STATE.json\`: active execution remains N2B1P until Owner explicitly transitions the state and provides a scoped execution record.

## 6. Owner decision points

The next Owner decisions are concrete and should not be collapsed into a generic “continue?” question:

1. **Canonical cache target**: restore the original approved cache-root object/identity if it still exists in a known recoverable location, or authorize a new versioned cache root. The existing Route-B-v2 cache re-provision task is still DRAFT_NOT_AUTHORIZED.
2. **Payload source**: restore the exact previously approved N2B1R quarantine hierarchy from a known source, or explicitly select the separate exact-three B-source reacquisition route.
3. **Python 3.12 quality environment**: if the previously qualified environment is absent, restore it from an already-approved source or separately authorize exact tooling acquisition. No implicit \`uv\`/pip install.
4. **Real20 transition**: after cache closure and exact review, authorize a candidate-bound Real20 execution/data scope.
5. **Real20 ledger/probe setup**: preferred Owner pre-provision route versus separately reviewed bootstrap code.
6. **Model upgrades**: after Real20 human review, decide independently whether MMPose, SAM2 and/or Qwen3-VL is justified.
7. **N3, N4, N5, G2/N6, N7**: each remains its own gate; none is inferred from the prior one.

## 7. Definition of PILOT_APP_INTEGRATION_PASS

All of the following must be evidence-backed:

- read-only source integrity preserved;
- Real20 completed under a valid one-shot/candidate-bound authorization;
- human photography-value review completed and recorded;
- selected model stack exact identities and runtime evidence recorded;
- N3 facts/interpretations pass schema/evidence/non-fabrication checks;
- N4 prompts pass attribution/uncertainty/Plan-B checks;
- N5 human review produces APPROVED-only Bundle v1;
- G2 100-photo Pilot passes stability/recovery/resource/human-quality gates;
- independent App validates, atomically imports and can roll back the Pilot Bundle;
- no shared DB/source-path coupling;
- no N8/full-library/OpenClaw implication.

Until all of those are true, do not report the product milestone as complete.
