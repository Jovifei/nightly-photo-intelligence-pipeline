# AGENTS.md — Codex / 通用实现智能体适配器

本文件只负责入口适配，不是独立需求源。

## 必须先读

1. `MASTER_EXECUTION_CONTRACT.md`
2. `PROJECT_STATE.json`
3. `docs/00_reading_order.md`
4. 当前 `AUTHORIZED` 的任务 YAML

## 当前权限

当前只允许 `tasks/phase_n2b1r_local_research_model_acquisition.yaml` 中的
`N2B1R_LOCAL_RESEARCH_MODEL_ACQUISITION`。它仅允许通过审批 artifact register
下载模型 payload/依赖到 Git 外隔离区，并在 Git 外独立环境中安装 hash-locked wheels；
它不是商业权利结论。模型加载/推理、真实照片读取、EXIF、SQLite ingest 写入和 cache
promotion 仍被禁止。N2B2/N3/N4/N5、G2/G3、主 App、OpenClaw、push、merge 和 release
仍须等待各自硬门。

## Codex 行为

- 先运行 `python tools/verify_handoff.py`；
- 先严格验证当前 state、approval、task 和 artifact register；
- 仅向 register 内 official domain 下载到 Git 外 quarantine；保存本地 SHA-256，
  但不把它写成权重许可或商业授权；
- 只实施当前 N2B1R 合同；
- 完成 N2B1R 本地 commit 后，在 cache promotion 或模型执行前停止并验证下一门；
- 不 push，不 merge，不开 PR，除非 Owner 另行明确授权；
- 不把 `AGENTS.md` 当成覆盖主合同的手段。

## 计划与实现

可以在 N2B1R 范围内自行做低层实现选择，但不得改变：

- 两仓库边界；
- 双门禁；
- 只读源；
- SQLite 持久状态；
- typed Python package；
- CLI 命令合同；
- JSON Schema；
- 报告和停止条件。

详见 `docs/31_agent_execution_playbook.md`。
