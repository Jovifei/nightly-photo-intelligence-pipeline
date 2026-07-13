# 测试与质量策略

## 质量层

1. 单元测试：Hash、路径、状态迁移、Schema helper；
2. 集成测试：SQLite、CLI、重启恢复；
3. 契约测试：Item/Bundle/CLI；
4. 安全负向测试：只读、symlink、路径脱敏、Git ignore；
5. Fixture golden tests：稳定输出；
6. 模型 Benchmark：后续 Gate；
7. 人工摄影质量评测；
8. 恢复与故障注入；
9. Release 完整性测试。

## N0 统一质量命令

实现应提供一个命令，例如：

```bash
make quality
```

它至少运行：

```text
ruff check
ruff format --check
mypy
pytest
handoff/schema checks
sensitive file scan
```

具体工具版本要在 N0 锁定。N0 无网络时，缺失工具可以报告，但在宣布 N0 完成前必须有 Owner 可接受的可运行方式；不得假造通过。

## N0 必测

- 三张 fixture SHA 与 manifest 一致；
- 一张 exact duplicate 被识别；
- dry-run 两次输出一致；
- dry-run 不写资产记录；
- 原图 pre/post SHA/size/mtime 相同；
- 无效状态迁移失败；
- SQLite 关闭/重开保留状态；
- 模拟中断可识别恢复；
- 合法 Schema 通过；
- 非法示例失败；
- 日志不含 fixture 根绝对路径；
- `.gitignore` 阻止 DB、图片派生物、权重和 Token；
- source/runtime 重叠被拒绝；
- symlink escape 被拒绝；
- CLI exit code 稳定。

## 证据

报告必须给命令、环境、开始/结束时间、退出码、摘要、失败详情和是否真实运行。截图不是唯一证据；首选文本输出和机器可读结果。
