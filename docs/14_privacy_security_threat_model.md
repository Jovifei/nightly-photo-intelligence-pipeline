# 隐私与安全威胁模型

## 资产

- 原始收藏图片；
- EXIF 与本地路径；
- 缩略图、mask、cutout、背景图；
- Embedding；
- SQLite 运行库；
- 模型权重；
- Prompt 与配置；
- Token、SSH 密钥；
- Git 历史；
- 审核修改。

## 信任边界

```text
Owner
  ├─ Read-only photo source (highest sensitivity)
  ├─ Pipeline process/runtime
  ├─ Model containers (later, controlled)
  ├─ App bundle release
  └─ Scheduler/OpenClaw (future, least privilege)
```

## 主要威胁与控制

| 威胁 | 控制 |
|---|---|
| 原图被覆盖/删除 | OS/Docker 只读、无写 API、前后 Hash、负向测试 |
| 图片误上传 | 默认断网、无云 SDK、域名白名单审批、网络审计 |
| 绝对路径进 Git | 日志脱敏、Git 扫描、忽略规则、pre-commit |
| 权重/派生物进 Git | 扩展名/目录 ignore + 文件大小扫描 |
| Prompt 注入自图片文字 | 模型输出视为不可信数据；不能改变工具/权限 |
| VLM 幻觉 | facts/interpretation 分层、Schema、受限断言规则、人工审核 |
| 状态伪成功 | 产物原子写 + Hash + 事务性状态提交 |
| OpenClaw 权限过大 | 无 socket/原图/Token/Git 权限，只调固定 wrapper |
| 依赖供应链 | exact version/hash、官方来源、许可登记、Owner 下载批准 |
| 恶意/损坏图片 | 解码限制、像素预算、超时、隔离、无动态代码 |
| SQLite 损坏 | 事务、备份、integrity_check、恢复演练 |
| 敏感报告 | 路径/机器名/用户名脱敏，报告目录本地 |

## 默认网络策略

- N0：无网络；
- N1：无网络；
- 模型研究可由 PM 外部完成，但执行机下载必须单独批准；
- 运行图片分析时默认无网络；
- 不提供云 fallback；
- Telemetry 必须关闭或经审核确认不存在。

## 安全事件

若发现源被修改、图片上传、密钥暴露、未授权模型下载或 Git 跟踪敏感产物：

1. 立即停止新任务；
2. 不删除证据；
3. 记录时间、命令、进程、文件 Hash；
4. 撤销相关凭据/权限由 Owner 执行；
5. 生成安全事件报告；
6. 未完成根因分析前不得恢复全量。
