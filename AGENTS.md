# AGENTS.md — Codex / 通用实现智能体适配器

本文件只负责入口适配，不是独立需求源。

## 必须先读

1. `MASTER_EXECUTION_CONTRACT.md`
2. `PROJECT_STATE.json`
3. `docs/00_reading_order.md`
4. 当前 `AUTHORIZED` 的任务 YAML

## 当前权限

只允许 `tasks/phase_n2b0_6_license_clear_alternative_candidate_research.yaml` 中的 `N2B0.6_LICENSE_CLEAR_ALTERNATIVE_CANDIDATE_RESEARCH`：最多两个 Pose 和两个轻量人物分割候选的官方元数据研究。严禁模型 payload/Range 请求、依赖安装、模型执行、真实照片读取、cache/quarantine 写入以及 N2B1/N2B2/N3/G2/G3；不得推断这些阶段已获授权。

## Codex 行为

- 先运行 `python tools/verify_handoff.py`；
- 使用只读本地/官方元数据工具检查；不下载依赖或权重；
- 若环境缺少依赖，记录为环境问题，不修改系统；
- 只实施当前 N2B0.6 合同；
- 只维护一个未批准的 N2B0.6 候选 commit，并在独立审查前停止；
- 不 push，不 merge，不开 PR，除非 Owner 另行明确授权；
- 不把 `AGENTS.md` 当成覆盖主合同的手段。

## 计划与实现

可以在 N2B0.6 范围内自行做低层实现选择，但不得改变：

- 两仓库边界；
- 双门禁；
- 只读源；
- SQLite 持久状态；
- typed Python package；
- CLI 命令合同；
- JSON Schema；
- 报告和停止条件。

详见 `docs/31_agent_execution_playbook.md`。
