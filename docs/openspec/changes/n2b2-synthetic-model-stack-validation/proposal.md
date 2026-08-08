## Why

Owner（Jovi）已授权 `N2B2_SYNTHETIC_MODEL_STACK_VALIDATION`（本轮 Owner Choice A）。但按 `CODEX_N2B2_Execution_Prompt.md` 第 2 节硬性门禁，模型执行仅当磁盘证据证明 N2B1P 已通过独立外部审查时才允许。当前磁盘证据 `research/N2B1P_cache_promotion_evidence.json` 的 `result` 仍为 `N2B1P_REMEDIATION_COMPLETE_AWAITING_EXTERNAL_REVIEW`，且无 `review_verdict` / `external_review` / `independent_reviewer` 字段——独立审查尚未落盘。

因此本变更仅完成「不越权的控制面检查」，并停止于契约规定的 `N2B2_EXECUTION_BLOCKED_N2B1P_NOT_APPROVED` 状态。不运行任何模型、不下载、不写入 SQLite、不触碰 App/Obsidian。

## What Changes

本变更创建以下控制面产物（均为非模型执行的契约落地文件）：

- `tasks/phase_n2b2_synthetic_model_stack_validation.yaml`：N2B2 任务契约（status: AUTHORIZED_CONTROL_PLANE_ONLY）。
- `schemas/n2b2_synthetic_model_stack.schema.json`：顶层校验摘要 schema。
- `schemas/n2b2_vision_fact_contract.schema.json`：确定性视觉事实契约。
- `schemas/n2b2_photography_reasoning.schema.json`：Qwen 推理输出契约（allowed/forbidden 字段）。
- `schemas/reference_bundle_v1_synthetic.schema.json`：合成参考包 v1 变体。
- `reports/N2B2_synthetic_validation_plan.md`：执行计划与第 3.3 节延迟状态变更清单。
- `reports/N2B2_owner_inputs_and_limits.md`：模型栈决策、运行时限制、数据门零计数、停止条件。
- `reports/N2B2_execution_blocked_n2b1p_not_approved.md`：第 18 节 blocked 停止态报告（全部鉴证字段）。
- `model_registry/candidates.yaml`：新增 `vlm-qwen3.5-9b-ollama-local` 条目；`vlm-qwen3-vl-2b-class` 标记 `SUPERSEDED_FOR_N2B2_SYNTHETIC_VALIDATION`，`not_downloaded:true`。

未变更任何锁定/停止边界状态（PROJECT_STATE.json、tasks/index.json、preflight.py、error_taxonomy、verify_handoff.py 的更新均延迟至 N2B1P 批准之后）。

## Capabilities

### New Capabilities

（无 spec 级能力变更，仅控制面文件落地。设置 `skip_specs: true`。）

### Modified Capabilities

（无。）

## Impact

- 不影响 `MASTER_EXECUTION_CONTRACT.md` 治理体系权威。
- 不影响 N2B1P 停止边界：`required_stop_after` 仍为 `N2B1P_REMEDIATION_COMPLETE_AWAITING_EXTERNAL_REVIEW`。
- 不推进 git 历史（单一 N2B2 commit 延迟至 N2B1P 批准，避免破坏 N2B1P-pinned 的 `verify_handoff.py` 与 `tests/test_git.py`）。
