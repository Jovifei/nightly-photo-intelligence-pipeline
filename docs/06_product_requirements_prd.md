# 产品需求文档（PRD）

## 1. 问题

Owner 拥有约 500–600 张本地摄影收藏。它们承载构图、姿势、光线、影调和故事灵感，但目前不可结构化检索、不可稳定复用、不可审计地交给实时摄影导演产品。

直接让一个 VLM 自由描述会混淆事实与想象，Pose 不可靠，结果不可重跑，失败后无法恢复，也会带来隐私、许可和原图安全风险。

## 2. 目标用户

第一版只有一个主要用户：Owner/摄影创作者。次级使用者是实现与审核智能体，但它们没有产品范围所有权。

## 3. Jobs to Be Done

- 当我准备在某种场景拍摄时，我能按背景、光线、构图、姿势、情绪和难度检索灵感；
- 当我选择一张参考图时，我能获得有证据的姿势模板和可说出口的导演话术；
- 当动作不自然时，我能得到更简单的 Plan B；
- 当模型不确定或冲突时，我能看见原因并人工修正；
- 当 App 需要内容时，我能导出审核后的稳定知识包；
- 当夜间任务中断时，我能从已完成阶段继续，而不是重跑全部。

## 4. 产品目标

- P0：原图完整性 100%；
- P0：任务不丢失、可恢复；
- P0：事实/解释/故事/提示严格分层；
- P0：Schema、Hash、版本和许可可追溯；
- P0：只导出 APPROVED；
- P1：单人/多人和可处理性高可靠；
- P1：Pose 对主要单人图可用；
- P1：导演方案经人工判断有帮助且可执行；
- P2：检索与个性化审美统计。

## 5. 功能需求

### 导入与安全

- `FR-ING-001` 支持只读目录 dry-run；
- `FR-ING-002` 计算流式 source SHA-256；
- `FR-ING-003` 提供版本化感知 Hash 接口；
- `FR-ING-004` 识别完全重复并保留来源关系；
- `FR-ING-005` 不跟随逃逸源根目录的 symlink；
- `FR-ING-006` 源与输出目录重叠时 fail closed；
- `FR-ING-007` 重复执行不得重复创建资产；
- `FR-ING-008` 原文件前后 Hash/mtime/size 保护可验证。

### 状态与恢复

- `FR-STA-001` 支持规定的最小状态集合；
- `FR-STA-002` 每次迁移持久化历史；
- `FR-STA-003` 每阶段记录开始/结束/耗时/错误/重试；
- `FR-STA-004` 崩溃后可恢复未完成工作；
- `FR-STA-005` 无效迁移被拒绝；
- `FR-STA-006` 单张失败不阻断整个批次；
- `FR-STA-007` 数据库 schema 有版本与迁移策略。

### 分析

- `FR-ANA-001` 可处理性分类；
- `FR-ANA-002` Pose 关键点来自专业模型或确定性计算；
- `FR-ANA-003` 分割结果保留模型、Hash 和置信度；
- `FR-ANA-004` observed facts 带证据和置信度；
- `FR-ANA-005` photographic interpretation 引用 facts；
- `FR-ANA-006` 固定提供 safe/narrative/dynamic 三类故事；
- `FR-ANA-007` 提供 standard/dramatic/plan_b/technical 四通道提示；
- `FR-ANA-008` 不确定与模型冲突显式记录；
- `FR-ANA-009` 禁止 VLM 产生 Pose 坐标；
- `FR-ANA-010` 禁止伪造受限事实。

### 审核与导出

- `FR-REV-001` 静态 HTML Review Card；
- `FR-REV-002` 审核状态和修改历史；
- `FR-REV-003` 人工修改不覆盖原始模型输出；
- `FR-EXP-001` 只导出 APPROVED；
- `FR-EXP-002` Bundle 路径相对、Hash 完整；
- `FR-EXP-003` Bundle 通过 JSON Schema；
- `FR-EXP-004` App 可用 fixture 独立开发；
- `FR-EXP-005` release 不可变、可回滚。

### CLI

必须最终支持：

```text
npi preflight
npi ingest --input <READ_ONLY_PHOTO_DIR>
npi run --profile calibration --limit 20
npi run --profile pilot --limit 100
npi run --profile nightly
npi resume
npi status
npi report --latest
npi export --release-id <ID>
```

N0 只实现 `preflight`、`status`、`ingest --dry-run`。

## 6. 非功能需求

- `NFR-SEC-001` 默认无网络；
- `NFR-SEC-002` 敏感产物不进 Git；
- `NFR-SEC-003` 最小权限；
- `NFR-REL-001` 幂等；
- `NFR-REL-002` 单资产故障隔离；
- `NFR-REL-003` 可恢复；
- `NFR-AUD-001` 全链路 provenance；
- `NFR-AUD-002` 输出 Hash；
- `NFR-PER-001` 12GB VRAM 单重模型驻留；
- `NFR-MNT-001` typed、lint、typecheck、pytest；
- `NFR-INT-001` App/数据工厂通过 Bundle 解耦；
- `NFR-LOC-001` 本地优先；
- `NFR-REP-001` 相同输入+版本下结果可重现或差异可解释。

## 7. 质量指标

这些是后续 Gate 目标，不是 N0 结果：

| 指标 | 初始目标 |
|---|---:|
| 原图任务不丢失 | 100% |
| Schema 通过率 | ≥99% |
| 崩溃后恢复 | 100% |
| 单人/多人基础分类 | ≥95% |
| 单人主要身体 Pose 可用率 | ≥90% |
| 失败有明确原因 | 100% |
| 摄影师认为“有帮助” | ≥80% |
| 故事方案可现场执行 | ≥80% |
| Plan B 更简单 | ≥85% |

主观指标必须由 Owner/摄影师人工评测，不能由模型自评分。

## 8. 风险

- 收藏图版权与来源未知；
- 截图、拼图、多人物和镜面造成误判；
- 左右手/镜像错误；
- 12GB 显存 OOM；
- 模型输出不稳定；
- 本地路径或图像误提交；
- 自动化权限过大；
- 任务状态与实际产物不一致。

应对见安全、状态机、模型 Benchmark 与测试文档。
