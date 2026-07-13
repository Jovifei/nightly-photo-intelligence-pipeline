# 总体实施计划（适用于任意实现智能体）

## N0

建立安全、typed、可测试底座。禁止真实数据和模型。

## N1

在 Owner 批准后：

- 正式 ingest 非 dry-run；
- 批准 manifest；
- asset/source/dedupe 数据模型；
- worker lease、重试、resume；
- report；
- 20 张前置 dry-run；
- 不下载模型，除非另有批准。

## N2

- 建立 Pose/segmentation adapter；
- 候选下载独立批准；
- 20 张 Benchmark；
- 左右/镜像、遮挡、全身/半身评测；
- 选择或拒绝候选；
- 不进入故事生成。

## N3

- 确定性构图/亮度/颜色；
- 严格 observed facts；
- 小型 VLM Benchmark（另行批准）；
- reconciliation；
- photographic interpretation；
- 20 张人工校准。

## N4

- safe/narrative/dynamic；
- standard/dramatic/Plan B/technical；
- 受限断言检测；
- 语言可说出口评测；
- 仍不自动进入 100 张。

## N5

- HTML Review Card；
- 审核修改历史；
- APPROVED-only exporter；
- Bundle fixture 与 release；
- 静态审查闭环。

## N6

在 G2 批准后运行 100 张 Pilot：

- 全链路稳定性；
- 性能/显存/磁盘；
- 恢复演练；
- 摄影质量抽检；
- Embedding/检索只在明确需求集上评估。

## N7

- App 仅基于 Bundle fixture 实现；
- 契约测试；
- major/minor 兼容；
- release 回滚；
- 不共享 DB。

## N8

- 固定 CLI/Windows Task Scheduler 先行；
- 全量 readiness；
- OpenClaw 仅设计并通过最小权限负向测试；
- 另行激活批准；
- G3 全量由 Owner 最后批准。

每阶段只完成自身 DoD 后停止。
