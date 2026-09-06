# Definition of Done

## N0 完成定义

全部满足才可写 `N0_COMPLETE_AWAITING_OWNER_APPROVAL`：

- [ ] 已只读检查真实环境；
- [ ] `reports/N0_environment_report.md` 完整；
- [ ] 独立 Git 仓库初始化；
- [ ] 最小 typed package 可导入；
- [ ] `npi preflight` 实现；
- [ ] `npi status` 实现；
- [ ] `npi ingest --dry-run` 实现；
- [ ] SQLite 状态库骨架；
- [ ] SHA-256 与版本化感知 Hash 接口；
- [ ] source guard；
- [ ] 三张 fixture 测试；
- [ ] 幂等、日志、Schema、恢复测试；
- [ ] pytest/lint/typecheck/统一质量命令；
- [ ] 安全负向测试；
- [ ] 测试证据；
- [ ] 环境问题；
- [ ] 未解决问题；
- [ ] 根据实测更新 N1 详细计划；
- [ ] Git status 无敏感/运行文件；
- [ ] 一个独立 commit；
- [ ] 未访问真实照片；
- [ ] 未下载模型；
- [ ] 未连接云端；
- [ ] 未接入 OpenClaw；
- [ ] 未修改主 App；
- [ ] 已停止。

## 不算完成

- 只有代码没有证据；
- 测试被跳过却标记通过；
- 使用真实照片代替 fixture；
- 自动安装/修改系统环境；
- commit 含数据库、日志、路径或派生图；
- 后续命令以“占位成功”返回；
- N1 已开始；
- Owner 尚未审核却更新为 N1 authorized。

## N2B2 synthetic review candidate 完成定义

以下全部满足时，可记录
`N2B2_SYNTHETIC_MODEL_STACK_VALIDATION_COMPLETE_AWAITING_EXTERNAL_REVIEW`：

- [x] N2B1P completion record 与 Owner synthetic-only receipt 绑定；
- [x] production `N2B2=LOCKED` 未改变；
- [x] S3 A/B/C Pose、Seg、facts 和 Qwen 合同通过；
- [x] S20 固定 20 case、20 bundles、checksums、checkpoint 和 no-op resume 通过；
- [x] GPU/Qwen residency 与显式 unload 有证据；
- [x] 真实照片、EXIF、G1、SQLite、App、模型下载计数为 0；
- [x] pytest、Ruff、mypy、统一质量、preflight、handoff 和敏感扫描通过；
- [ ] 精确 candidate 的独立外部 Review PASS；
- [ ] Owner 后续 phase decision。

上述状态不是 `N2B2_COMPLETE`。在最后两项完成前，不得进入 Real20、生产 Bundle、
App 或任何真实照片处理。

## N2B2 Ollama runtime-identity revalidation 完成定义

仅当 Owner receipt 精确绑定 `d83f9627`、已接受的 `INCONCLUSIVE` review、旧版本
`0.32.15` 与当前 `0.33.3`，并且模型 digest、大小、量化和 vision capability 完全不变时，
允许一轮新的 synthetic S3/S20。新 output 必须位于 Git 外，旧 evidence 不得修改。

成功还要求新 S20 COMPLETE checkpoint 的同 identity `--resume` 返回
`ALREADY_COMPLETE_VERIFIED`，且所有 release 文件字节不变。成功停止于
`N2B2_OLLAMA_0_33_3_SYNTHETIC_REVALIDATION_COMPLETE_AWAITING_EXTERNAL_REVIEW`；它不
解锁 production N2B2、Real20 或任何真实照片路径。
