# 路线图、阶段门禁与数据放量

## 双门禁模型

任何处理必须同时拥有：

1. **Phase Gate**：允许实现什么能力；
2. **Data Gate**：允许使用多少、哪些数据。

两者独立。完成代码阶段不自动放量；批准数据集也不授权新能力。

## 阶段

| 阶段 | 目标 | 当前状态 |
|---|---|---|
| N0 | 环境检查、安全脚手架、三张 fixture | `AUTHORIZED` |
| N1 | 正式导入、去重、任务引擎、恢复语义 | `LOCKED` |
| N2 | Pose 与分割候选 Benchmark、生产接口 | `LOCKED` |
| N3 | observed facts、构图/光线/影调、摄影解释 | `LOCKED` |
| N4 | 三类故事候选与导演提示 | `LOCKED` |
| N5 | HTML 审核、修改记录、Bundle 导出 | `LOCKED` |
| N6 | 100 张 Pilot、检索与 Embedding 评估 | `LOCKED` |
| N7 | App Bundle fixture/导入合同集成 | `LOCKED` |
| N8 | 夜间运行、Windows 调度、受限 OpenClaw | `LOCKED` |

## 数据门禁

| Gate | 数据 | 当前状态 | 进入条件 |
|---|---|---|---|
| G0 | 3 张仓库内合成 fixture | `AUTHORIZED` | 交付包校验通过 |
| G1 | 20 张 Owner 清单化校准集 | `LOCKED` | N1 底座通过 + Owner 批准 |
| G2 | 100 张 Pilot | `LOCKED` | 20 张质量/稳定性 Gate 通过 |
| G3 | 500–600 张全量 | `LOCKED` | 100 张 Pilot + 夜间恢复/停机演练通过 |

## 放量不是“limit 参数”而是数据许可

`--limit 20` 不能替代 manifest。运行时必须确认候选资产都在已批准 manifest 中。`--limit` 只限制上限，不能扩大许可。

## 每个 Gate 的退出证据

- 输入 manifest 与 Hash；
- 处理成功、失败、人工复核数量；
- Schema 通过率；
- 状态丢失率；
- 恢复演练；
- 原图完整性抽检；
- GPU 峰值与平均耗时；
- 人工摄影价值抽检；
- 未解决问题；
- Owner 决定。

## 停止点

每阶段完成后默认停止。只有 Owner 更新 `PROJECT_STATE.json` 并放入有效批准记录，智能体才可继续。

## 当前 N2B2 synthetic review candidate

N2B2 的 production phase 仍为 `LOCKED`。但在独立、受限的 review branch 上，Owner
已授权 synthetic/GPU/S3/S20 验证；该 candidate 已完成 S3、S20、CUDA、Qwen facts 和
20 个 synthetic validation bundles。本地质量门通过后仍默认停止于独立外部 Review。

这是一条 capability evidence 路径，不是数据放量：G1、G2、G3 的状态不变，Real20、
真实照片、SQLite ingest 和生产 Bundle 仍不可执行。

已验证的 N2B2 synthetic 源码和脱敏文档可在线性、无 merge commit 的治理链中整合到
`main`，用于建立可复现基线；这不等同于 `N2B2_COMPLETE`，也不改变任何数据门或生产
执行许可。下一硬门仍是独立外部 Review，其后仍需 Owner 的专门 Real20 决策。
