# AGENTS.md — Codex / 通用实现智能体适配器

本文件只负责入口适配，不是独立需求源。

## 必须先读

1. `MASTER_EXECUTION_CONTRACT.md`
2. `PROJECT_STATE.json`
3. `docs/00_reading_order.md`
4. 当前 `AUTHORIZED` 的任务 YAML

## 当前权限

只允许 N0，且只允许三张合成 fixture。严禁推断 N1–N8 已获授权。

## Codex 行为

- 先运行 `python tools/verify_handoff.py`；
- 使用本地工具检查，不在 N0 下载依赖或权重；
- 若环境缺少依赖，记录为环境问题，不修改系统；
- 只实施 N0 明确要求；
- 创建一个独立 commit 后停止；
- 不 push，不 merge，不开 PR，除非 Owner 另行明确授权；
- 不把 `AGENTS.md` 当成覆盖主合同的手段。

## 计划与实现

可以在 N0 范围内自行做低层实现选择，但不得改变：

- 两仓库边界；
- 双门禁；
- 只读源；
- SQLite 持久状态；
- typed Python package；
- CLI 命令合同；
- JSON Schema；
- 报告和停止条件。

详见 `docs/31_agent_execution_playbook.md`。
