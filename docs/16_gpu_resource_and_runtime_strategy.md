# GPU 与运行资源策略

## 约束

目标 GPU 为 RTX 4070 SUPER 12GB。实际可用显存、驱动、CUDA、WSL 和 Docker GPU 情况必须由 `npi preflight` 只读检查；文档不能替代实测。

## 单重模型原则

```text
Pose stage
→ unload / process exit
Segmentation stage
→ unload / process exit
VLM stage
→ unload / process exit
Embedding stage
→ unload / process exit
```

第一版不让多个重模型同时常驻。优先以阶段容器或独立进程实现显存释放。

## Benchmark 必测

- 冷启动时间；
- 单图 p50/p95；
- 峰值 VRAM；
- 系统 RAM；
- 输入像素预算；
- 输出 Schema 合法率；
- OOM 次数；
- 重试后结果；
- 进程退出后显存释放；
- 20 张端到端时长；
- 热稳定性由 Owner 使用系统工具观察，不由应用猜测。

## OOM 策略

1. 记录阶段、输入尺寸、模型、配置和 VRAM；
2. 释放当前进程；
3. 按批准策略降低像素预算/批量；
4. 单次重试；
5. 再失败则 `NEEDS_REVIEW` 或 `FAILED`；
6. 不能自动下载更小模型；
7. 不能删除既有有效产物。

## 磁盘

Preflight 要估算：

```text
原始输入只读（不复制）
+ SQLite / WAL
+ 每阶段 JSON
+ 缩略图与 overlay
+ 可选 mask/cutout/background
+ 模型权重
+ 临时文件
+ 至少一个上一 release
```

磁盘阈值触发时停止新任务，不清理原图或未经 Owner 同意的有效产物。
