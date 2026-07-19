# 模型 Benchmark 协议

## 先决条件

- 阶段授权；
- 数据 Gate；
- exact model approval；
- 下载 Hash/许可；
- 固定环境；
- 无云端；
- 只使用批准 manifest。

## 数据切片

20 张校准应刻意覆盖：

- 单人全身/半身；
- 坐姿；
- 手靠脸/拿道具；
- 逆光/窗边/走廊/草地/街道；
- 拼图/截图；
- 多人；
- 遮挡；
- 人物太小；
- 镜面；
- 横竖图。

不是随机前 20 张。

## Pose 指标

- 主体检出；
- 关键点可用率；
- 左右错误；
- 角度误差；
- 遮挡标记；
- 镜像策略；
- 运行时间/VRAM；
- 人工可用评分。

## 分割指标

- 主体选择正确；
- 边缘质量；
- 手/发丝/衣物错误；
- 遮挡；
- 漏分/背景污染；
- 轻量→精细升级比例；
- 时间/显存/磁盘。

## VLM 指标

- 事实 precision/recall（人工标注）；
- 禁止断言违规率；
- Schema 一次通过率；
- 修复后通过率；
- facts/interpretation 泄漏；
- 三类故事区分；
- 导演话术可执行；
- 稳定性；
- p50/p95/VRAM。

## 资源

每个候选单独进程，记录：

```text
model revision
weight hash
runtime versions
input dimensions/pixels
warmup
cold and warm latency
peak VRAM
host RAM
exit status
```

## 选择

P0 安全、许可或输出来源失败直接淘汰。不要用加权总分掩盖 P0。
## N2A benchmark-plan addendum (2026-07-20)

N2A defines a fixed, non-random 20-case synthetic metadata matrix: full body,
half body, seated pose, hand near face, held object, partial occlusion, two
people, small person, crop, collage, mirror view, left/right ambiguity, backlit
window, hair edge, clothing edge, translucent edge, out-of-frame, portrait,
landscape, and deterministic rerun. Each case has only a synthetic case ID,
fixture reference, dimensions, and expected-person count; no photo path exists.

Measured metrics are reserved for N2B. `processing_time_ms`, GPU peak memory,
CPU peak memory, and OOM are `NOT_MEASURED` in N2A, never estimates. N2B must
record exact model revision, artifact hash, runtime versions, input dimensions,
cold/warm latency, peak memory, failure reason, and deterministic rerun result.
