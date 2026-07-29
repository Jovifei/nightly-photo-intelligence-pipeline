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
11. `approvals/owner_local_research_execution_N2B1R_to_N5R.yaml`
12. `tasks/phase_n2b1r_local_research_model_acquisition.yaml`
13. `research/N2B1R_local_research_artifact_register.json`
14. 与 N2B1R 相关的来源、隔离下载、环境、测试和验收文档

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
