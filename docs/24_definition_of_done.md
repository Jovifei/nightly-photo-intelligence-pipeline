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
