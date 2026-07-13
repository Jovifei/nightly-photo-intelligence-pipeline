# 可观测性、断点续传与失败策略

## 日志

结构化字段：

```text
timestamp
level
run_id
asset_id
stage
event
attempt
duration_ms
error_code
model_id/revision
schema_version
```

路径只显示脱敏相对标识。Prompt 原文、Token、EXIF、绝对路径默认不进普通日志。

## 指标

- 各状态数量；
- stage 成功/失败/重试；
- p50/p95 耗时；
- GPU 峰值（可获得时）；
- Schema 通过率；
- review backlog；
- 输出磁盘；
- 许可/版本缺失数；
- source integrity 异常。

## 恢复

启动时：

1. SQLite integrity check；
2. 找出过期 lease；
3. 将未原子完成 stage run 标为 INTERRUPTED；
4. 校验已有输出 Hash；
5. 只排队缺失/无效阶段；
6. 不重新处理已验证相同幂等键产物。

## 失败策略

- 解码失败：UNSUPPORTED 或 NEEDS_REVIEW；
- 超时：按策略重试一次；
- OOM：降预算一次后重试；
- JSON 无效：允许一次受限修复，仍失败进复核；
- 模型冲突：NEEDS_REVIEW；
- 单图失败：继续其他图；
- DB/磁盘/source integrity 错误：停止批次；
- 网络意外访问：安全失败并停止；
- 温度异常：应用不猜测；由外部批准的监控触发停止。

## 报告

日报区分：

- 完成；
- 跳过；
- 人工复核；
- 失败；
- 被 Gate 阻止；
- 尚未尝试。

不能把 SKIPPED 当作 PASS。
