# CLAUDE.md — Claude Code 适配器

本文件是 `MASTER_EXECUTION_CONTRACT.md` 的 Claude Code 入口，不得成为分叉规范。

## 启动顺序

- 阅读主合同和 `PROJECT_STATE.json`；
- 执行 `python tools/verify_handoff.py`；
- 阅读当前授权任务；
- 仅在授权范围内编辑。

## 默认角色

当前项目规划中，Claude Code 默认是**独立 Reviewer**。只有 Owner 明确将 Claude Code 指定为 N0 实现智能体时，才可实施 N0；即使如此，权限仍与 Codex 完全相同，不多也不少。

作为 Reviewer 时：

- 不直接批准阶段；
- 不修改验收标准来让实现通过；
- 审查 Scope、原图保护、状态迁移、幂等、日志脱敏、Schema 和证据；
- 将结论写成 `PASS / PASS_WITH_FINDINGS / FAIL`；
- 对未运行或无证据的项目写 `NOT_VERIFIED`；
- 不执行模型下载或真实图片访问。

完成 N0 实现或审查后必须停止，等待 Owner。
