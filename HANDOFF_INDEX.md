# 交付索引

## 1. 权威层级

从高到低：

1. Owner 在当前仓库中签署的、范围明确且仍有效的批准记录；
2. `PROJECT_STATE.json`；
3. `MASTER_EXECUTION_CONTRACT.md`；
4. 当前已授权的 `tasks/*.yaml`；
5. `PROJECT_CHARTER.md`、PRD、架构和安全文档；
6. 智能体适配器文件；
7. 研究候选、模板和示例。

任何低层文件都不能扩大高层授权。聊天中的模糊表述不能替代签署批准。

## 2. 必读路径

### 所有实现智能体

1. `README_FIRST.md`
2. `MASTER_EXECUTION_CONTRACT.md`
3. `PROJECT_STATE.json`
4. `PROJECT_CHARTER.md`
5. `OWNER_INPUTS_REQUIRED.md`
6. `docs/00_reading_order.md`
7. 当前授权任务
8. `docs/05_scope_and_non_goals.md`
9. `docs/13_read_only_source_protection.md`
10. `docs/20_testing_and_quality_strategy.md`
11. `docs/24_definition_of_done.md`

### Owner 审核 N0

1. `reports/N0_environment_report.md`
2. `reports/N0_test_evidence.md`
3. `reports/N0_unresolved_issues.md`
4. `reports/N1_detailed_plan.md`
5. Git diff 与 N0 commit
6. `PROJECT_STATE.json` 是否仍保持 N1 锁定

## 3. 内容地图

| 目录 | 作用 |
|---|---|
| `docs/` | 产品、架构、安全、数据合同、测试与路线图 |
| `tasks/` | 每阶段机器可读执行合同 |
| `schemas/` | Bundle、Item、Pose、Prompt、Review、Provenance 等 JSON Schema |
| `fixtures/` | N0 三张合成图片及固定清单 |
| `examples/` | 合法/非法结构化输出和 App Bundle fixture |
| `config/` | 默认执行、重试、资源和智能体角色策略 |
| `research/` | 官方来源、GitHub 参考工程、候选技术与许可登记 |
| `adr/` | 已接受的架构决策 |
| `approvals/` | Owner 批准模板；模板本身绝不构成批准 |
| `templates/` | 阶段报告、Benchmark、Review Card、日报模板 |
| `tools/` | 交付包本身的离线自检工具 |
| `reports/` | N0 实现后产生的证据；当前仅含说明 |
| `prompts/` | Prompt 版本和边界规范；N0 无生产 Prompt |
| `model_registry/` | 研究候选；全部默认禁止下载 |
| `openclaw/` | N8 之后才可能启用的窄调度接口设计 |

## 4. 交付包不是许可替代物

仓库、库或模型被列入研究目录，不表示：

- 已允许下载；
- 已允许处理真实收藏；
- 代码许可自动覆盖权重或数据；
- 通过技术测试就允许扩大运行规模；
- 智能体可以替 Owner 做法律或版权结论。
