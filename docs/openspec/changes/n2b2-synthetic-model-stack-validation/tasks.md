## 1. 控制面产物（已完成，未越权）

- [x] 1.1 创建 `tasks/phase_n2b2_synthetic_model_stack_validation.yaml`（AUTHORIZED_CONTROL_PLANE_ONLY）
- [x] 1.2 创建 4 份 N2B2 JSON Schema（synthetic_model_stack / vision_fact_contract / photography_reasoning / reference_bundle_v1_synthetic）
- [x] 1.3 创建 3 份报告（validation_plan / owner_inputs_and_limits / execution_blocked_n2b1p_not_approved）
- [x] 1.4 更新 `model_registry/candidates.yaml`（qwen3.5:9b 本地条目 + Qwen3-VL-2B 标记 superseded/not_downloaded）
- [x] 1.5 运行 Section 16 质量门：ruff/format/mypy PASS；sensitive_scan 0 违规（gitignore 排除 scratch 目录后）；pytest 残留失败均为 N2B1P-pinned 治理校验器与脏树导致，非 N2B2 产物内容

## 2. 停止态与门禁（已完成）

- [x] 2.1 落盘 `N2B2_EXECUTION_BLOCKED_N2B1P_NOT_APPROVED` 报告（Section 18 全部鉴证字段）
- [x] 2.2 确认 N2B1P 独立审查未落盘 → 不运行模型、不下载、不写 SQLite/App/Obsidian
- [x] 2.3 comet-classic 配置完成：`.comet/config.yaml` + OpenSpec classic 布局（docs/openspec）

## 3. 延迟至 N2B1P 批准之后的工作（门控，非本变更范围）

- [ ] 3.1 N2B1P 独立审查 PASS 落盘后，更新 PROJECT_STATE.json（v1.8）→ tasks/index.json → preflight.py → error_taxonomy v1_3 → verify_handoff.py
- [ ] 3.2 运行合成数据门（S3=3 smoke → S20=20 fixed），执行 TorchVision 确定性视觉 + qwen3.5:9b 推理
- [ ] 3.3 创建单一 N2B2 commit `feat(n2b2): validate synthetic photography model stack`（no push/merge）
- [ ] 3.4 停止于 `N2B2_SYNTHETIC_MODEL_STACK_VALIDATION_COMPLETE_AWAITING_EXTERNAL_REVIEW`
