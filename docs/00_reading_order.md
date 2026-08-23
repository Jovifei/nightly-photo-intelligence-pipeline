# 智能体阅读顺序与执行协议

## 必读顺序

1. `README_FIRST.md`
2. `MASTER_EXECUTION_CONTRACT.md`
3. `PROJECT_STATE.json`
4. `PROJECT_CHARTER.md`
5. `docs/01_two_project_relationship.md`
6. `docs/02_timeline_and_gates.md`
7. `docs/03_architecture_and_pipeline.md`
8. `docs/04_export_contract.md`
9. `OWNER_INPUTS_REQUIRED.md`
10. `approvals/phase_completion_N2B0_7.yaml`
11. `approvals/owner_n2b1p_cache_promotion.yaml`
12. `tasks/phase_n2b1p_local_research_cache_promotion.yaml`
13. `research/N2B1R_acquisition_evidence.json`
14. `research/N2B1P_cache_promotion_evidence.json`
15. `research/N2B1R_local_research_artifact_register.json`
16. 与 N2B1P 相关的 cache、测试和验收文档

此顺序完成前不得编辑代码。

## 执行协议

```text
VERIFY_HANDOFF
→ READ_AUTHORIZATION
→ INSPECT_ENVIRONMENT_READ_ONLY
→ IMPLEMENT_ONLY_AUTHORIZED_TASK
→ RUN_POSITIVE_AND_NEGATIVE_TESTS
→ WRITE_EVIDENCE
→ REVIEW_DIFF_AND_GITIGNORE
→ CREATE_ONE_COMMIT
→ STOP
```

## 不允许的捷径

- 不能根据聊天摘要跳过仓库合同；
- 不能把后续任务当作待办自动实施；
- 不能用一个“万能分析函数”替代阶段边界；
- 不能创建假模型输出来声称 N2–N4 已完成；
- 不能因为当前机器已有某权重就自动使用；
- 不能把 fixture 结果外推成 500–600 张的性能结论。

## 失败时

遇到完整性失败、权限不明、原图可写、输出目录与源目录重叠、疑似密钥、Git 将跟踪敏感文件或任务合同冲突时：

1. 停止变更；
2. 不尝试“自动修复”系统；
3. 记录命令、事实与影响；
4. 输出 `BLOCKED_AWAITING_OWNER_DECISION`。
## Bounded N2B2 review-candidate addendum (2026-08-09)

Also read `tasks/phase_n2b2_runtime_gpu_validation_and_s20_preparation.yaml`
and `approvals/owner_n2b2_runtime_gpu_validation_receipt.yaml`. These permit
synthetic GPU validation and S20 planning only; they do not change
`PROJECT_STATE.json` or the production `N2B2=LOCKED` state.

## N2B2 S20 completion-artifact integrity addendum (2026-08-11)

Before any synthetic S20 remediation work, additionally read:

1. `tasks/phase_n2b2_s20_artifact_integrity_remediation.yaml`
2. `approvals/owner_n2b2_s20_artifact_integrity_remediation_receipt.yaml`
3. `schemas/n2b2_s20_checkpoint.schema.json`
4. `schemas/n2b2_s20_independent_review.schema.json`

This is a replacement-run contract for the frozen synthetic set only. It
requires one unambiguous terminal outcome and external review after a clean
candidate; it does not unlock N2B2 or authorize real data.

## Owner-authorized synthetic continuation (2026-08-23)

For this bounded continuation also read:

1. `approvals/phase_completion_N2B1P.yaml`
2. `approvals/owner_n2b2_synthetic_model_stack_validation.yaml`
3. `tasks/phase_n2b2_authorized_synthetic_validation_20260823.yaml`
4. `schemas/phase_completion_n2b1p_v1_0.schema.json`
5. `schemas/owner_n2b2_synthetic_model_stack_v1_0.schema.json`

These records authorize only synthetic/GPU/S3/S20 validation and preserve the
production `N2B2=LOCKED` boundary.

## N2B2 synthetic validation status (2026-08-23)

Before using the bounded candidate or preparing review, read
`docs/38_n2b2_synthetic_validation_status.md`. It is the current redacted
summary of S3/S20 runtime evidence, local quality gates, locked production
state, and the independent-review stop condition.
