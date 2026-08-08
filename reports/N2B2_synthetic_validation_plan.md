# N2B2 Synthetic Model Stack Validation — Plan

**Phase:** N2B2_SYNTHETIC_MODEL_STACK_VALIDATION
**Owner:** Jovi
**Owner decision:** Choice A — use existing local `qwen3.5:9b` (Q4_K_M), supersede Qwen3-VL-2B
**Data gate:** SYNTHETIC_ONLY_DATA_GATE
**Date:** 2026-08-05

---

## 1. Purpose

This plan defines the N2B2 synthetic model stack validation: the first end-to-end
exercise of the photography intelligence pipeline's deterministic vision layer
(TorchVision Keypoint R-CNN / LRASPP / DeepLabV3) and photography reasoning layer
(local Ollama qwen3.5:9b) on synthetic-only data.

The goal is to prove the full stack can:

1. Produce deterministic, byte-identical vision facts from synthetic images.
2. Feed those immutable facts to Qwen, which produces schema-valid photography
   interpretation, story candidates, and director prompts without overwriting
   facts.
3. Respect all GPU, memory, unload, and hard-count boundaries.
4. Stop cleanly and not enter any locked phase.

---

## 2. Current state (disk-evidence reconciliation)

| Field | Value | Source |
|---|---|---|
| HEAD | `b819e2c48229cacbf62e399d2b4130cde55cf48a` | `git rev-parse HEAD` |
| Current stage | N2B1P (AWAITING_EXTERNAL_REVIEW) | `PROJECT_STATE.json` |
| N2B1P review verdict | NONE (pre-review was INCONCLUSIVE) | `research/N2B1P_cache_promotion_evidence.json` |
| N2B1P gate | AUTHORIZED (not APPROVED_COMPLETE) | `PROJECT_STATE.json` |
| `real_model_execution` | NOT_AUTHORIZED | `PROJECT_STATE.json` |
| Three TorchVision cache | all CACHE_HIT | `N2B1P_cache_promotion_evidence.json` |
| `N2B2_REAL_BENCHMARK` | LOCKED | `PROJECT_STATE.json` |

### 2.1 Blocking condition

N2B2 contract Section 2 requires N2B1P to have passed independent external review
(proven by disk evidence) before any model execution. The disk evidence shows
N2B1P is still `AWAITING_EXTERNAL_REVIEW`. No `phase_completion_N2B1P.yaml` exists.
The only pre-review (in `tasks/todo.md`) returned `INCONCLUSIVE` and explicitly
states it "does not satisfy the required external review."

**Therefore: model execution is blocked. Only non-overstepping control-plane
work is permitted. Stop condition: `N2B2_EXECUTION_BLOCKED_N2B1P_NOT_APPROVED`.**

---

## 3. Control-plane deliverables (this round)

### 3.1 Created files

| File | Purpose |
|---|---|
| `tasks/phase_n2b2_synthetic_model_stack_validation.yaml` | N2B2 task contract |
| `schemas/n2b2_synthetic_model_stack.schema.json` | Top-level validation summary schema |
| `schemas/n2b2_vision_fact_contract.schema.json` | Deterministic vision fact contract |
| `schemas/n2b2_photography_reasoning.schema.json` | Qwen reasoning output schema |
| `schemas/reference_bundle_v1_synthetic.schema.json` | Synthetic Bundle v1 variant |
| `reports/N2B2_synthetic_validation_plan.md` | This plan |
| `reports/N2B2_owner_inputs_and_limits.md` | Owner inputs and limits record |

### 3.2 Updated tracking files

| File | Change |
|---|---|
| `tasks/todo.md` | Added N2B2 control-plane section |
| `model_registry/candidates.yaml` | Added qwen3.5:9b entry; marked Qwen3-VL-2B superseded |

### 3.3 Deferred state changes (await N2B1P approval)

The following changes require N2B1P to pass independent review first. They are
documented here so they can be executed in a single batch when the gate opens:

| File | Required change |
|---|---|
| `PROJECT_STATE.json` | Bump schema to v1.8; add `N2B2_SYNTHETIC_MODEL_STACK_VALIDATION` gate = `AUTHORIZED`; keep N2B1P = `AWAITING_EXTERNAL_REVIEW` until review passes, then set to `APPROVED_COMPLETE` |
| `schemas/project_state_v1_8.schema.json` | New schema version allowing N2B2 gate field |
| `tasks/index.json` | Move N2B2 from `locked` to `authorized` |
| `src/nightly_photo_intelligence_pipeline/preflight.py` | Add `_check_n2b2_authorization` for schema v1.8 |
| `config/error_taxonomy_v1_3.yaml` | Add N2B2 error codes (N2B2_EXECUTION_BLOCKED_*, N2B2_LOCAL_QWEN_*, etc.) |
| `tools/verify_handoff.py` | Add N2B2 commit topology check |

**Rationale for deferral:** `project_state_v1_7.schema.json` has
`additionalProperties: false` at every level. Adding an N2B2 gate field requires a
new schema version. Modifying the preflight to handle a new version requires test
updates. Doing this now would risk breaking the N2B1P stop-boundary enforcement
that is currently the project's most critical safety mechanism.

---

## 4. Execution plan (when N2B1P is approved)

### 4.1 Prerequisites

1. N2B1P independent external review produces `PASS_FOR_EXTERNAL_REVIEW` on disk.
2. `approvals/phase_completion_N2B1P.yaml` is created with the reviewer verdict.
3. `PROJECT_STATE.json` is updated: N2B1P gate → `APPROVED_COMPLETE`,
   `real_model_execution` remains `NOT_AUTHORIZED` (N2B2 uses synthetic data,
   not real photos), N2B2 gate → `AUTHORIZED`.
4. Preflight and handoff verifier are updated and pass.

### 4.2 Step sequence (from N2B2 contract Section 11)

1. State reconciliation (read-only)
2. TorchVision cache read-only verification (no redownload)
3. Ollama model identity verification (read-only `/api/tags`, `/api/show`)
4. Synthetic fixture generation and freeze
5. S3 Pose stage (3 smoke images: single-person, multi-person/occlusion, no-person)
6. Unload Pose
7. S3 LRASPP stage
8. Unload LRASPP
9. S3 DeepLab comparator (fixed 5-case subset, predeclared)
10. Unload DeepLab
11. Build vision fact contracts (deterministic, canonical JSON)
12. S3 Qwen reasoning stage
13. Unload Qwen (`keep_alive=0`, verify `/api/ps` + GPU baseline)
14. S3 strict validation (schema, fact digest, forbidden fields)
15. Only if S3 passes → repeat for S20 (20 fixed synthetic images)

### 4.3 S20 case matrix

| Cases | Scene |
|---|---|
| 01–04 | Single person: full-body, half-body, seated, prop |
| 05–08 | Multi-person: separated, close, occluded, mirror |
| 09–11 | Night / low-light |
| 12–14 | Complex background |
| 15–16 | Strong backlight / silhouette |
| 17–18 | Minimal composition / large negative space |
| 19 | No-person negative control |
| 20 | Collage/screenshot unsupported control |

### 4.4 Stop conditions

- **Success:** `N2B2_SYNTHETIC_MODEL_STACK_VALIDATION_COMPLETE_AWAITING_EXTERNAL_REVIEW`
- **Blocked (current):** `N2B2_EXECUTION_BLOCKED_N2B1P_NOT_APPROVED`
- **Identity mismatch:** `N2B2_LOCAL_QWEN_IDENTITY_MISMATCH`
- **Vision missing:** `N2B2_LOCAL_QWEN_VISION_CAPABILITY_MISSING`
- **Fixture insufficient:** `N2B2_SYNTHETIC_FIXTURE_CAPABILITY_INSUFFICIENT`
- **GPU exceeded:** `N2B2_GPU_LIMIT_EXCEEDED`
- **Fact violation:** `N2B2_FACT_IMMUTABILITY_VIOLATION`
- **Schema/provenance:** `N2B2_QWEN_SCHEMA_OR_PROVENANCE_FAILED`
- **Unload failure:** `N2B2_MODEL_UNLOAD_FAILED`
- **Changes required:** `N2B2_CHANGES_REQUIRED`

---

## 5. Quality gates (when execution runs)

```powershell
.venv\Scripts\python.exe -m pytest -q
.venv\Scripts\python.exe -m ruff check .
.venv\Scripts\python.exe -m ruff format --check .
.venv\Scripts\python.exe -m mypy src/nightly_photo_intelligence_pipeline
.venv\Scripts\python.exe tools/run_quality.py
.venv\Scripts\python.exe tools/sensitive_file_scan.py
.venv\Scripts\npi.exe preflight
.venv\Scripts\python.exe tools/verify_handoff.py
git diff --check
```

Requirements: pytest 0 failed, Ruff/format/mypy exit 0, quality ≥7 PASS,
sensitive scan 0 violations, preflight 0 FAIL, handoff 0 FAIL, no NOT_AVAILABLE,
no false PASS for SKIPPED.

---

## 6. Git rules

- N2B1P approved baseline must not be rewritten.
- N2B2 completion creates exactly one commit: `feat(n2b2): validate synthetic photography model stack`
- No merge, no push.
- No mixing of docs/02, docs/24, docs/31, Obsidian, or print_authorization drift.

---

## 7. Next action

**Owner must arrange N2B1P independent external review.** When the review
produces a `PASS_FOR_EXTERNAL_REVIEW` verdict on disk, the deferred state changes
in Section 3.3 can be executed, and N2B2 model execution can proceed per
Section 4.
