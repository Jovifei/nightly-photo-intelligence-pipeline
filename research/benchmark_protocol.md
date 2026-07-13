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
