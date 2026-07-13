# ADR-0007：一个主合同，多智能体适配器

状态：Accepted

`MASTER_EXECUTION_CONTRACT.md` 与 `PROJECT_STATE.json` 是唯一规范源；`AGENTS.md`、`CLAUDE.md`、`OPENCLAW.md` 只做入口适配。

原因：执行工具可替换，但安全和范围不能随工具分叉。
