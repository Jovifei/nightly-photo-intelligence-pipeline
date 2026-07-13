# N1 详细计划基线

本文件是 N0 前的规划基线。N0 实现智能体必须根据真实环境报告更新并复制为 `reports/N1_detailed_plan.md`，但不得执行 N1。

## 目标

把 N0 骨架扩展为可持久导入、去重、领取、失败隔离和恢复的单机任务引擎。

## 工作包

1. DB migration 机制；
2. assets/asset_sources/stage_runs/transitions/outputs；
3. 正式 ingest；
4. 批准 manifest 和 Gate 校验；
5. exact duplicate；
6. 感知近似重复候选，不自动删除；
7. lease/heartbeat；
8. retry/error taxonomy；
9. `npi resume`；
10. `npi report --latest`；
11. 数据库备份/integrity check；
12. N1 安全和故障注入测试。

## N1 仍禁止

- 模型下载；
- Pose/VLM 假实现；
- 100/全量；
- OpenClaw；
- 主 App；
- 云端。

## 进入输入

- N0 Owner 批准；
- 20 张清单可准备但未必立即处理；
- source/runtime 只读方案；
- 磁盘预算；
- 支持格式决定；
- N0 环境风险处置。

## 退出证据

- 任务不丢失；
- exact duplicate 幂等；
- 中断恢复；
- DB 备份恢复；
- source integrity；
- manifest 越权拒绝；
- 20 张 Gate 仍锁定，除非 Owner 单独批准。
